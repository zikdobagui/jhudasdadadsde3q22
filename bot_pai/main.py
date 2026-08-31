import json
import os
import threading
from textwrap import dedent

import telebot

from storage import create_child_bot, find_bot, load_bots, update_status
from stock_api import run_stock_api
from stock_storage import stock_summary


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def load_config():
    if not os.path.isfile(CONFIG_FILE):
        raise RuntimeError(
            "Crie bot_pai/config.json usando bot_pai/config.example.json como modelo."
        )
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


config = load_config()
bot = telebot.TeleBot(config["bot_token"], parse_mode="HTML")
admin_ids = {int(admin_id) for admin_id in config.get("admin_ids", [])}


def is_admin(message):
    return message.from_user and int(message.from_user.id) in admin_ids


def admin_only(func):
    def wrapper(message):
        if not is_admin(message):
            bot.reply_to(message, "Acesso negado.")
            return
        return func(message)

    return wrapper


def help_text():
    return dedent(
        """
        <b>Bot Pai</b>

        /start - mostrar painel
        /novo_bot - cadastrar bot filho
        /bots - listar bots filhos
        /bot ID - ver detalhes
        /suspender ID - suspender bot filho
        /ativar ID - ativar bot filho

        Cadastro rapido:
        <code>/novo_bot Nome da Loja | ID_DONO | TOKEN | @usuario | 30/09/2026</code>
        """
    ).strip()


@bot.message_handler(commands=["start", "help"])
@admin_only
def start(message):
    bot.reply_to(message, help_text())


@bot.message_handler(commands=["novo_bot"])
@admin_only
def novo_bot(message):
    raw = message.text.partition(" ")[2].strip()
    if not raw:
        bot.reply_to(
            message,
            "Use:\n<code>/novo_bot Nome da Loja | ID_DONO | TOKEN | @usuario | 30/09/2026</code>",
        )
        return

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 3:
        bot.reply_to(message, "Faltam dados. Informe pelo menos nome, ID do dono e token.")
        return

    name = parts[0]
    owner_id = parts[1]
    token = parts[2]
    username = parts[3] if len(parts) >= 4 else ""
    expires_at = parts[4] if len(parts) >= 5 else ""

    try:
        child = create_child_bot(name, owner_id, token, username, expires_at)
    except ValueError:
        bot.reply_to(message, "O ID do dono precisa ser numerico.")
        return

    bot.reply_to(
        message,
        (
            f"Bot filho cadastrado.\n"
            f"ID: <code>{child['id']}</code>\n"
            f"Nome: <b>{child['name']}</b>\n"
            f"Status: <code>{child['status']}</code>"
        ),
    )


@bot.message_handler(commands=["bots"])
@admin_only
def listar_bots(message):
    children = load_bots()
    if not children:
        bot.reply_to(message, "Nenhum bot filho cadastrado ainda.")
        return

    lines = ["<b>Bots filhos</b>"]
    for child in children:
        username = child.get("username") or "sem usuario"
        expires_at = child.get("expires_at") or "sem vencimento"
        lines.append(
            f"#{child['id']} - {child['name']} - {username} - {child['status']} - {expires_at}"
        )
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["estoque"])
@admin_only
def estoque(message):
    items = stock_summary()
    if not items:
        bot.reply_to(message, "Estoque central vazio.")
        return

    lines = ["<b>Estoque central</b>"]
    for item in items:
        lines.append(f"{item['nome']}: {item['quantidade']} - R${float(item['valor']):.2f}")
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["bot"])
@admin_only
def detalhe_bot(message):
    bot_id = message.text.partition(" ")[2].strip()
    if not bot_id:
        bot.reply_to(message, "Use: <code>/bot ID</code>")
        return

    child = find_bot(bot_id)
    if not child:
        bot.reply_to(message, "Bot filho nao encontrado.")
        return

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
    bot.reply_to(message, text)


@bot.message_handler(commands=["suspender"])
@admin_only
def suspender(message):
    change_status(message, "suspended")


@bot.message_handler(commands=["ativar"])
@admin_only
def ativar(message):
    change_status(message, "active")


def change_status(message, status):
    bot_id = message.text.partition(" ")[2].strip()
    if not bot_id:
        bot.reply_to(message, "Informe o ID.")
        return
    child = update_status(bot_id, status)
    if not child:
        bot.reply_to(message, "Bot filho nao encontrado.")
        return
    bot.reply_to(message, f"Bot #{child['id']} atualizado para <code>{status}</code>.")


if __name__ == "__main__":
    print("[BOT PAI] Iniciando...")
    api_port = int(config.get("stock_api_port", 8080))
    api_key = config.get("stock_api_key", "")
    threading.Thread(
        target=run_stock_api,
        args=("0.0.0.0", api_port, api_key),
        daemon=True,
    ).start()
    bot.infinity_polling(skip_pending=True)
