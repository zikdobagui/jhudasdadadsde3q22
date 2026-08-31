import json
import os
import threading
from datetime import datetime
from textwrap import dedent

import telebot
from telebot import types

from child_runtime import build_trial, parse_datetime, serialize_trial, start_trial_bot, stop_trial_bot
from storage import (
    create_child_bot,
    create_customer_request,
    find_bot,
    load_bots,
    load_requests,
    load_trials,
    update_child_bot,
    update_request_status,
    update_trial_status,
    update_status,
    upsert_trial,
)
from stock_api import run_stock_api
from stock_storage import stock_summary


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
pending_new_bots = {}
pending_trials = {}
pending_bot_edits = {}


def load_config():
    if not os.path.isfile(CONFIG_FILE):
        raise RuntimeError(
            "Crie bot_pai/config.json usando bot_pai/config.example.json como modelo."
        )
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as file:
        return json.load(file)


config = load_config()
bot = telebot.TeleBot(config["bot_token"], parse_mode="HTML")
admin_ids = {int(admin_id) for admin_id in config.get("admin_ids", [])}


def user_id_from(obj):
    user = getattr(obj, "from_user", None)
    return int(user.id) if user else 0


def is_admin_obj(obj):
    return user_id_from(obj) in admin_ids


def deny(obj):
    if hasattr(obj, "id") and hasattr(obj, "message"):
        bot.answer_callback_query(obj.id, "Acesso negado.", show_alert=True)
        return
    bot.reply_to(obj, "Acesso negado.")


def require_admin_message(func):
    def wrapper(message):
        if not is_admin_obj(message):
            deny(message)
            return
        return func(message)

    return wrapper


def main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Novo bot", callback_data="menu:new_bot"),
        types.InlineKeyboardButton("Bots filhos", callback_data="menu:bots"),
    )
    markup.add(
        types.InlineKeyboardButton("Estoque", callback_data="menu:stock"),
        types.InlineKeyboardButton("Pedidos", callback_data="menu:requests"),
    )
    markup.add(
        types.InlineKeyboardButton("Ver como cliente", callback_data="client:home"),
        types.InlineKeyboardButton("Atualizar", callback_data="menu:home"),
    )
    return markup


def customer_menu_markup(show_admin=False):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Testar bot", callback_data="client:test"),
        types.InlineKeyboardButton("Alugar bot", callback_data="client:rent"),
        types.InlineKeyboardButton("Falar com suporte", callback_data="client:support"),
    )
    if show_admin:
        markup.add(types.InlineKeyboardButton("Painel admin", callback_data="menu:home"))
    return markup


def back_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Voltar", callback_data="menu:home"))
    return markup


def bot_actions_markup(child):
    status_action = "Ativar" if child.get("status") == "suspended" else "Suspender"
    status_callback = f"bot:activate:{child['id']}" if child.get("status") == "suspended" else f"bot:suspend:{child['id']}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(status_action, callback_data=status_callback),
        types.InlineKeyboardButton("Editar", callback_data=f"bot:edit:{child['id']}"),
    )
    markup.add(types.InlineKeyboardButton("Bots", callback_data="menu:bots"))
    markup.add(types.InlineKeyboardButton("Menu", callback_data="menu:home"))
    return markup


def bot_edit_markup(child_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Nome", callback_data=f"botedit:name:{child_id}"),
        types.InlineKeyboardButton("Dono", callback_data=f"botedit:owner:{child_id}"),
    )
    markup.add(
        types.InlineKeyboardButton("Token", callback_data=f"botedit:token:{child_id}"),
        types.InlineKeyboardButton("Usuario", callback_data=f"botedit:username:{child_id}"),
    )
    markup.add(types.InlineKeyboardButton("Vencimento", callback_data=f"botedit:expires:{child_id}"))
    markup.add(types.InlineKeyboardButton("Voltar", callback_data=f"bot:view:{child_id}"))
    return markup


def trial_actions_markup(trial_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Desligar teste", callback_data=f"trial:stop:{trial_id}"),
        types.InlineKeyboardButton("Menu", callback_data="menu:home"),
    )
    return markup


def home_text():
    children = load_bots()
    requests = load_requests()
    active = sum(1 for child in children if child.get("status") == "active")
    suspended = sum(1 for child in children if child.get("status") == "suspended")
    pending = sum(1 for item in requests if item.get("status") == "pending")
    return dedent(
        f"""
        <b>Painel admin</b>

        Bots cadastrados: <code>{len(children)}</code>
        Ativos: <code>{active}</code>
        Suspensos: <code>{suspended}</code>
        Pedidos pendentes: <code>{pending}</code>
        """
    ).strip()


def customer_home_text():
    return dedent(
        """
        <b>Aluguel de bot</b>

        Escolha uma opção abaixo para testar ou solicitar seu bot.
        """
    ).strip()


def show_home(chat_id, message_id=None):
    if message_id:
        bot.edit_message_text(
            home_text(),
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=main_menu_markup(),
        )
        return
    bot.send_message(chat_id, home_text(), reply_markup=main_menu_markup())


@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.send_message(
        message.chat.id,
        customer_home_text(),
        reply_markup=customer_menu_markup(is_admin_obj(message)),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("menu:"))
def menu_callback(call):
    if not is_admin_obj(call):
        deny(call)
        return

    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)

    if action == "home":
        show_home(call.message.chat.id, call.message.message_id)
        return

    if action == "new_bot":
        pending_new_bots[call.from_user.id] = {}
        msg = bot.edit_message_text(
            "<b>Novo bot filho</b>\n\nEnvie o nome da loja.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_markup(),
        )
        bot.register_next_step_handler(msg, collect_child_name)
        return

    if action == "bots":
        show_bots(call.message.chat.id, call.message.message_id)
        return

    if action == "stock":
        show_stock(call.message.chat.id, call.message.message_id)
        return

    if action == "requests":
        show_requests(call.message.chat.id, call.message.message_id)
        return


@bot.callback_query_handler(func=lambda call: call.data.startswith("client:"))
def client_callback(call):
    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)

    if action == "home":
        bot.edit_message_text(
            customer_home_text(),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=customer_menu_markup(is_admin_obj(call)),
        )
        return

    if action in ("test", "rent"):
        if action == "test":
            pending_trials[call.from_user.id] = {}
            msg = bot.edit_message_text(
                "<b>Teste grátis</b>\n\nEnvie o nome da sua loja.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
            bot.register_next_step_handler(msg, collect_trial_store_name)
            return

        request = create_customer_request(call.from_user, action)
        bot.edit_message_text(
            (
                "Pedido de aluguel recebido.\n\n"
                f"Protocolo: <code>{request['id']}</code>\n"
                "Nossa equipe vai chamar você para continuar."
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=customer_menu_markup(is_admin_obj(call)),
        )
        notify_admins_about_request(request)
        return

    if action == "support":
        bot.edit_message_text(
            "Chame o suporte para tirar dúvidas ou concluir seu aluguel.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=customer_menu_markup(is_admin_obj(call)),
        )
        return


def notify_admins_about_request(request):
    label = "teste" if request.get("type") == "test" else "aluguel"
    username = f"@{request['username']}" if request.get("username") else "sem username"
    text = dedent(
        f"""
        <b>Novo pedido de {label}</b>

        Protocolo: <code>{request['id']}</code>
        Cliente: <code>{request['user_id']}</code>
        Nome: {request.get('first_name') or 'sem nome'}
        Usuario: {username}
        """
    ).strip()
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, text, reply_markup=request_admin_markup(request["id"]))
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("trial:"))
def trial_callback(call):
    if not is_admin_obj(call):
        deny(call)
        return

    _, action, trial_id = call.data.split(":", 2)
    bot.answer_callback_query(call.id)

    if action == "stop":
        stopped = stop_trial_bot(int(trial_id), "manual", on_expire=notify_trial_expired)
        text = "Teste desligado." if stopped else "Teste nao estava ativo."
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=main_menu_markup())


def collect_trial_store_name(message):
    if not message.text:
        msg = bot.send_message(message.chat.id, "Envie o nome da loja.")
        bot.register_next_step_handler(msg, collect_trial_store_name)
        return
    pending_trials[message.from_user.id] = {"store_name": message.text.strip()}
    msg = bot.send_message(message.chat.id, "Agora envie o token do bot que você criou no BotFather.")
    bot.register_next_step_handler(msg, collect_trial_token)


def collect_trial_token(message):
    data = pending_trials.get(message.from_user.id, {})
    token = (message.text or "").strip()
    if ":" not in token or len(token) < 30:
        msg = bot.send_message(message.chat.id, "Token inválido. Envie o token completo do BotFather.")
        bot.register_next_step_handler(msg, collect_trial_token)
        return
    data["token"] = token
    pending_trials[message.from_user.id] = data
    msg = bot.send_message(message.chat.id, "Por último, envie seu ID Telegram de admin.")
    bot.register_next_step_handler(msg, collect_trial_admin_id)


def collect_trial_admin_id(message):
    data = pending_trials.pop(message.from_user.id, {})
    try:
        data["admin_id"] = int((message.text or "").strip())
    except ValueError:
        pending_trials[message.from_user.id] = data
        msg = bot.send_message(message.chat.id, "ID inválido. Envie apenas números.")
        bot.register_next_step_handler(msg, collect_trial_admin_id)
        return

    request = create_customer_request(message.from_user, "test")
    trial = build_trial(data, config, request["id"])
    update_request_status(request["id"], "trial_running")

    try:
        upsert_trial(serialize_trial(trial))
        start_trial_bot(trial, on_expire=notify_trial_expired)
    except Exception as exc:
        update_request_status(request["id"], "failed")
        bot.send_message(
            message.chat.id,
            f"Não consegui ligar o teste automaticamente.\n\nErro: <code>{exc}</code>",
            reply_markup=customer_menu_markup(is_admin_obj(message)),
        )
        return

    minutes = trial["trial_minutes"]
    bot.send_message(
        message.chat.id,
        (
            "Seu bot de teste foi ligado.\n\n"
            f"Loja: <b>{trial['store_name']}</b>\n"
            f"Tempo: <code>{minutes} minutos</code>\n"
            f"Expira em: <code>{trial['expires_at'].strftime('%H:%M:%S')}</code>\n\n"
            "Quando o tempo acabar, ele será desligado automaticamente."
        ),
        reply_markup=customer_menu_markup(is_admin_obj(message)),
    )
    notify_admins_trial_started(trial, request)


def notify_admins_trial_started(trial, request):
    text = dedent(
        f"""
        <b>Teste automático iniciado</b>

        Protocolo: <code>{request['id']}</code>
        Loja: <b>{trial['store_name']}</b>
        Cliente: <code>{request['user_id']}</code>
        Admin informado: <code>{trial['admin_id']}</code>
        Duração: <code>{trial['trial_minutes']} minutos</code>
        Expira: <code>{trial['expires_at'].strftime('%d/%m/%Y %H:%M:%S')}</code>
        """
    ).strip()
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, text, reply_markup=trial_actions_markup(trial["id"]))
        except Exception:
            pass


def notify_trial_expired(trial_id, reason, runtime):
    status = "trial_expired" if reason == "expired" else "stopped"
    update_request_status(trial_id, status)
    update_trial_status(trial_id, status)
    text = f"Teste #{trial_id} expirou e foi desligado automaticamente." if reason == "expired" else f"Teste #{trial_id} foi desligado."
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, text)
        except Exception:
            pass


def request_admin_markup(request_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Atender", callback_data=f"request:progress:{request_id}"),
        types.InlineKeyboardButton("Concluir", callback_data=f"request:done:{request_id}"),
    )
    markup.add(types.InlineKeyboardButton("Cancelar", callback_data=f"request:cancel:{request_id}"))
    markup.add(types.InlineKeyboardButton("Menu", callback_data="menu:home"))
    return markup


def show_requests(chat_id, message_id=None):
    pending = [item for item in load_requests() if item.get("status") == "pending"]
    if not pending:
        text = "<b>Pedidos</b>\n\nNenhum pedido pendente."
        markup = back_markup()
    else:
        text = "<b>Pedidos pendentes</b>\n\nEscolha um pedido para gerenciar."
        markup = types.InlineKeyboardMarkup()
        for item in pending[:40]:
            label = "Teste" if item.get("type") == "test" else "Aluguel"
            user = item.get("username") or item.get("first_name") or item.get("user_id")
            markup.add(
                types.InlineKeyboardButton(
                    f"#{item['id']} {label} - {user}",
                    callback_data=f"request:view:{item['id']}",
                )
            )
        markup.add(types.InlineKeyboardButton("Voltar", callback_data="menu:home"))

    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("request:"))
def request_callback(call):
    if not is_admin_obj(call):
        deny(call)
        return

    _, action, request_id = call.data.split(":", 2)
    bot.answer_callback_query(call.id)

    if action == "view":
        request = next((item for item in load_requests() if int(item["id"]) == int(request_id)), None)
    elif action == "progress":
        request = update_request_status(request_id, "in_progress")
    elif action == "done":
        request = update_request_status(request_id, "done")
    elif action == "cancel":
        request = update_request_status(request_id, "cancelled")
    else:
        request = None

    if not request:
        bot.edit_message_text("Pedido nao encontrado.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=back_markup())
        return

    show_request_detail(call.message.chat.id, call.message.message_id, request)


def show_request_detail(chat_id, message_id, request):
    label = "Teste" if request.get("type") == "test" else "Aluguel"
    username = f"@{request['username']}" if request.get("username") else "sem username"
    text = dedent(
        f"""
        <b>Pedido #{request['id']}</b>

        Tipo: <code>{label}</code>
        Status: <code>{request['status']}</code>
        Cliente: <code>{request['user_id']}</code>
        Nome: {request.get('first_name') or 'sem nome'}
        Usuario: {username}
        Criado em: <code>{request['created_at']}</code>
        """
    ).strip()
    bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=request_admin_markup(request["id"]))


def show_bots(chat_id, message_id=None):
    children = load_bots()
    if not children:
        text = "<b>Bots filhos</b>\n\nNenhum bot cadastrado ainda."
        markup = back_markup()
    else:
        text = "<b>Bots filhos</b>\n\nEscolha um bot para ver detalhes."
        markup = types.InlineKeyboardMarkup()
        for child in children[:40]:
            status = "OK" if child.get("status") == "active" else "PAUSADO"
            markup.add(
                types.InlineKeyboardButton(
                    f"{status} #{child['id']} {child['name']}",
                    callback_data=f"bot:view:{child['id']}",
                )
            )
        markup.add(types.InlineKeyboardButton("Voltar", callback_data="menu:home"))

    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def show_stock(chat_id, message_id=None):
    items = stock_summary()
    if not items:
        text = "<b>Estoque central</b>\n\nEstoque vazio."
    else:
        lines = ["<b>Estoque central</b>"]
        for item in items[:60]:
            lines.append(f"{item['nome']}: <code>{item['quantidade']}</code> - R${float(item['valor']):.2f}")
        text = "\n".join(lines)

    if message_id:
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=back_markup())
    else:
        bot.send_message(chat_id, text, reply_markup=back_markup())


@bot.callback_query_handler(func=lambda call: call.data.startswith("bot:"))
def bot_callback(call):
    if not is_admin_obj(call):
        deny(call)
        return

    _, action, bot_id = call.data.split(":", 2)
    bot.answer_callback_query(call.id)

    if action == "view":
        child = find_bot(bot_id)
    elif action == "suspend":
        child = update_status(bot_id, "suspended")
    elif action == "activate":
        child = update_status(bot_id, "active")
    elif action == "edit":
        child = find_bot(bot_id)
        if child:
            bot.edit_message_text(
                f"<b>Editar {child['name']}</b>\n\nEscolha o campo que deseja alterar.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=bot_edit_markup(child["id"]),
            )
            return
    else:
        child = None

    if not child:
        bot.edit_message_text(
            "Bot filho nao encontrado.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_markup(),
        )
        return

    show_child_detail(call.message.chat.id, call.message.message_id, child)


def show_child_detail(chat_id, message_id, child):
    token_preview = child["token"][:8] + "..." if child.get("token") else "sem token"
    text = dedent(
        f"""
        <b>{child['name']}</b>

        ID: <code>{child['id']}</code>
        Dono: <code>{child['owner_id']}</code>
        Usuario: <code>{child.get('username') or 'sem usuario'}</code>
        Status: <code>{child['status']}</code>
        Vencimento: <code>{child.get('expires_at') or 'sem vencimento'}</code>
        Token: <code>{token_preview}</code>
        SquareCloud app: <code>{child.get('squarecloud_app_id') or 'nao criado'}</code>
        Criado em: <code>{child['created_at']}</code>
        """
    ).strip()
    bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=bot_actions_markup(child))


@bot.callback_query_handler(func=lambda call: call.data.startswith("botedit:"))
def bot_edit_callback(call):
    if not is_admin_obj(call):
        deny(call)
        return
    _, field, child_id = call.data.split(":", 2)
    child = find_bot(child_id)
    if not child:
        bot.answer_callback_query(call.id, "Bot nao encontrado.", show_alert=True)
        return
    labels = {
        "name": "novo nome",
        "owner": "novo ID do dono",
        "token": "novo token",
        "username": "novo usuario",
        "expires": "novo vencimento",
    }
    bot.answer_callback_query(call.id)
    pending_bot_edits[call.from_user.id] = {"bot_id": int(child_id), "field": field}
    msg = bot.send_message(call.message.chat.id, f"Envie o {labels.get(field, 'novo valor')}.")
    bot.register_next_step_handler(msg, collect_bot_edit)


def collect_bot_edit(message):
    state = pending_bot_edits.pop(message.from_user.id, None)
    if not state:
        return
    value = (message.text or "").strip()
    field_map = {
        "name": "name",
        "owner": "owner_id",
        "token": "token",
        "username": "username",
        "expires": "expires_at",
    }
    field = field_map.get(state["field"])
    if not field:
        bot.send_message(message.chat.id, "Campo invalido.", reply_markup=main_menu_markup())
        return
    if field == "owner_id":
        try:
            value = int(value)
        except ValueError:
            bot.send_message(message.chat.id, "ID invalido. Envie apenas numeros.")
            return
    child = update_child_bot(state["bot_id"], **{field: value})
    if not child:
        bot.send_message(message.chat.id, "Bot nao encontrado.", reply_markup=main_menu_markup())
        return
    bot.send_message(message.chat.id, "Bot atualizado.")
    show_home(message.chat.id)


def collect_child_name(message):
    if not is_admin_obj(message):
        deny(message)
        return
    if message.text and message.text.startswith("/"):
        return
    pending_new_bots[message.from_user.id] = {"name": message.text.strip()}
    msg = bot.send_message(message.chat.id, "Envie o ID Telegram do dono desse bot.")
    bot.register_next_step_handler(msg, collect_child_owner)


def collect_child_owner(message):
    if not is_admin_obj(message):
        deny(message)
        return
    data = pending_new_bots.get(message.from_user.id, {})
    try:
        data["owner_id"] = int(message.text.strip())
    except (ValueError, AttributeError):
        msg = bot.send_message(message.chat.id, "ID invalido. Envie apenas numeros.")
        bot.register_next_step_handler(msg, collect_child_owner)
        return
    pending_new_bots[message.from_user.id] = data
    msg = bot.send_message(message.chat.id, "Envie o token do bot filho.")
    bot.register_next_step_handler(msg, collect_child_token)


def collect_child_token(message):
    if not is_admin_obj(message):
        deny(message)
        return
    data = pending_new_bots.get(message.from_user.id, {})
    data["token"] = message.text.strip()
    pending_new_bots[message.from_user.id] = data
    msg = bot.send_message(message.chat.id, "Envie o usuario do bot filho, exemplo @minhaloja_bot. Se nao tiver, envie -")
    bot.register_next_step_handler(msg, collect_child_username)


def collect_child_username(message):
    if not is_admin_obj(message):
        deny(message)
        return
    data = pending_new_bots.get(message.from_user.id, {})
    username = message.text.strip()
    data["username"] = "" if username == "-" else username
    pending_new_bots[message.from_user.id] = data
    msg = bot.send_message(message.chat.id, "Envie o vencimento, exemplo 30/09/2026. Se nao quiser, envie -")
    bot.register_next_step_handler(msg, collect_child_expiration)


def collect_child_expiration(message):
    if not is_admin_obj(message):
        deny(message)
        return
    data = pending_new_bots.pop(message.from_user.id, {})
    expires_at = message.text.strip()
    data["expires_at"] = "" if expires_at == "-" else expires_at

    try:
        child = create_child_bot(
            data["name"],
            data["owner_id"],
            data["token"],
            data.get("username", ""),
            data.get("expires_at", ""),
        )
    except Exception as exc:
        bot.send_message(message.chat.id, f"Falha ao cadastrar bot: {exc}", reply_markup=main_menu_markup())
        return

    bot.send_message(
        message.chat.id,
        f"Bot filho cadastrado.\n\nID: <code>{child['id']}</code>\nNome: <b>{child['name']}</b>",
    )
    show_home(message.chat.id)


@bot.message_handler(commands=["bots"])
@require_admin_message
def listar_bots_command(message):
    show_bots(message.chat.id)


@bot.message_handler(commands=["estoque"])
@require_admin_message
def estoque_command(message):
    show_stock(message.chat.id)


if __name__ == "__main__":
    print("[BOT PAI] Iniciando...")
    api_port = int(config.get("stock_api_port", 8080))
    api_key = config.get("stock_api_key", "")
    threading.Thread(
        target=run_stock_api,
        args=("0.0.0.0", api_port, api_key),
        daemon=True,
    ).start()
    restored = 0
    now = datetime.now()
    for saved_trial in load_trials():
        if saved_trial.get("status") != "trial_running":
            continue
        try:
            if parse_datetime(saved_trial["expires_at"]) <= now:
                update_trial_status(saved_trial["id"], "trial_expired")
                update_request_status(saved_trial["id"], "trial_expired")
                continue
            start_trial_bot(saved_trial, on_expire=notify_trial_expired, rebuild_runtime=False)
            restored += 1
        except Exception as exc:
            update_trial_status(saved_trial.get("id", 0), "failed")
            print(f"[TRIAL] Falha ao restaurar teste {saved_trial.get('id')}: {exc}")
    print(f"[TRIAL] Testes restaurados: {restored}")
    bot.infinity_polling(skip_pending=True)
