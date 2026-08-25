import os
import re
import json
import io
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ========================
# CONFIGURAÇÕES E PATHS
# ========================
BOT_TOKEN = "token do bot"


ALLOWED_USERS = {
    int(user_id)
    for user_id in re.split(r"[\s,;]+", os.getenv("ADMIN_IDS", ""))
    if user_id.isdigit()
}

CREDENCIAIS_PATH = os.path.join("settings", "credenciais.json")
START_TXT_PATH   = os.path.join("textos", "start.txt")
USERS_FOLDER     = os.path.join("database", "users")


user_editing_state = {}

# ========================
# FUNÇÕES DE ARQUIVOS
# ========================
def carregar_credenciais():
    with open(CREDENCIAIS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_credenciais(cred):
    with open(CREDENCIAIS_PATH, "w", encoding="utf-8") as f:
        json.dump(cred, f, indent=4, ensure_ascii=False)

def carregar_start_txt():
    with open(START_TXT_PATH, "r", encoding="utf-8") as f:
        return f.read()

def salvar_start_txt(conteudo):
    with open(START_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(conteudo)

# ========================
# COMANDOS E HANDLERS
# ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        await context.bot.send_message(chat_id, "Você não tem permissão para usar este bot.")
        return

    menu = gerar_menu_principal()
   
    await context.bot.send_animation(
        chat_id,
        animation="imagem",
        caption="Bem-vindo! Escolha uma opção:",
        reply_markup=menu
    )

def gerar_menu_principal():
    """Gera o menu principal com as opções disponíveis."""
    keyboard = [
        [
            InlineKeyboardButton("🔑 Alterar ID dono", callback_data="edit_id_dono")
        ],
        [
            InlineKeyboardButton("🔑 Alterar token do bot", callback_data="edit_api_bot")

        ],
        [
            InlineKeyboardButton("🔗 Alterar link suporte", callback_data="edit_link_suporte"),
            InlineKeyboardButton("🔗 Trocar link do chat", callback_data="edit_chat_link")
        ],
        [
            InlineKeyboardButton("🖼 Trocar imagem do bot", callback_data="edit_image_link")
        ],
        [
            InlineKeyboardButton("💬 Suporte", callback_data="suporte")
        ],
        [
            InlineKeyboardButton("📊 Logins por data", callback_data="fetch_logins_data")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  
    data = query.data
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    if user_id not in ALLOWED_USERS:
        await context.bot.send_message(chat_id, "Você não tem permissão para usar este bot.")
        return

    credenciais = carregar_credenciais()

    async def perguntar_novo_valor(campo):
        user_editing_state[user_id] = campo
        await context.bot.send_message(chat_id, f"Qual é o novo valor para '{campo}'?")

    if data == "edit_id_dono":
        await perguntar_novo_valor("id_dono")

    elif data == "edit_user_bot":
        await perguntar_novo_valor("user_bot")

    elif data == "edit_api_bot":
        await perguntar_novo_valor("api-bot")

    elif data == "edit_link_suporte":
        await perguntar_novo_valor("link_suporte")

    elif data == "edit_chat_link":
        await perguntar_novo_valor("chat_link")

    elif data == "edit_image_link":
        user_editing_state[user_id] = "imagem_bot"
        await context.bot.send_message(chat_id, "Qual o novo link da imagem? (URL completa)")

    elif data == "reiniciar_bot":
        await context.bot.send_message(chat_id, "Reiniciando bot...")
        os._exit(0)

    elif data == "suporte":
        link_sup = credenciais.get("link_suporte", "Não definido.")
        await context.bot.send_message(chat_id, f"Entre em contato no suporte: {link_sup}")

    elif data == "add_mes":
        venc_atual = credenciais.get("vencimento_bot", "00/00/0000")
        await context.bot.send_message(chat_id, f"Vencimento atual: {venc_atual}")
        # Supondo formato DD/MM/YYYY
        dia, mes, ano = venc_atual.split("/")
        dia = int(dia)
        mes = int(mes)
        ano = int(ano)
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
        novo_venc = f"{dia:02d}/{mes:02d}/{ano}"
        credenciais["vencimento_bot"] = novo_venc
        salvar_credenciais(credenciais)
        await context.bot.send_message(chat_id, f"Novo vencimento: {novo_venc}")

    elif data == "fetch_logins_data":
        
        user_editing_state[user_id] = "fetch_logins_data"
        await context.bot.send_message(
            chat_id,
            "Informe o período desejado no seguinte formato:\n\nDD/MM/YYYY a DD/MM/YYYY\n\nExemplo: 10/01/2024 a 10/01/2025"
        )

    else:
        await context.bot.send_message(chat_id, "Opção inválida ou não implementada.")

async def mensagem_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text

    if user_id not in ALLOWED_USERS:
        return

    if user_id not in user_editing_state:
        return  

    campo = user_editing_state[user_id]

    if campo == "fetch_logins_data":
       
        pattern = r'(\d{2}/\d{2}/\d{4})\s*(?:a|às)\s*(\d{2}/\d{2}/\d{4})'
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            await update.message.reply_text("Formato inválido. Por favor, use: DD/MM/YYYY a DD/MM/YYYY")
            return

        start_date_str, end_date_str = match.groups()
        try:
            start_date = datetime.strptime(start_date_str, "%d/%m/%Y")
            end_date   = datetime.strptime(end_date_str, "%d/%m/%Y")
        except ValueError:
            await update.message.reply_text("Data inválida. Certifique-se de usar o formato DD/MM/YYYY.")
            return

        if start_date > end_date:
            await update.message.reply_text("A data inicial não pode ser maior que a data final.")
            return

        
        resultados = {}
        if not os.path.isdir(USERS_FOLDER):
            await context.bot.send_message(chat_id, "Pasta de usuários não encontrada.")
            del user_editing_state[user_id]
            return

        for filename in os.listdir(USERS_FOLDER):
            if filename.endswith(".json"):
                filepath = os.path.join(USERS_FOLDER, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                except Exception:
                    continue

                username = user_data.get("username", f"ID {user_data.get('id', 'desconhecido')}")
                for compra in user_data.get("compras", []):
                    data_compra_str = compra.get("data", "")
                    if "as" in data_compra_str:
                        date_part = data_compra_str.split("as")[0].strip()
                    else:
                        date_part = data_compra_str.strip()
                    try:
                        compra_date = datetime.strptime(date_part, "%d/%m/%Y")
                    except ValueError:
                        continue

                    if start_date <= compra_date <= end_date:
                        if username not in resultados:
                            resultados[username] = []
                        resultados[username].append(compra)

        if not resultados:
            await update.message.reply_text("Nenhum login vendido no período especificado.")
        else:
            texto_relatorio = "Logins vendidos no período:\n\n"
            for usuario, compras in resultados.items():
                texto_relatorio += f"Usuário: {usuario}\n"
                texto_relatorio += "-" * 40 + "\n"
                for compra in compras:
                    servico        = compra.get("servico", "N/A")
                    email          = compra.get("email", "N/A")
                    senha          = compra.get("senha", "N/A")
                    data_compra    = compra.get("data", "N/A")
                    data_expiracao = compra.get("data_expiracao", "N/A")
                    texto_relatorio += (
                        f"Serviço: {servico}\n"
                        f"Login: {email}\n"
                        f"Senha: {senha}\n"
                        f"Data: {data_compra}\n"
                        f"Expiração: {data_expiracao}\n"
                        + "-" * 40 + "\n"
                    )
                texto_relatorio += "\n"

            
            arquivo_relatorio = io.BytesIO(texto_relatorio.encode("utf-8"))
            arquivo_relatorio.name = "logins_report.txt"
            await context.bot.send_document(
                chat_id,
                document=arquivo_relatorio,
                caption="Relatório de logins vendidos no período"
            )

        await context.bot.send_message(chat_id, "Menu principal:", reply_markup=gerar_menu_principal())
        del user_editing_state[user_id]

    elif campo != "imagem_bot":
        # Edição de outros campos do JSON
        credenciais = carregar_credenciais()
        credenciais[campo] = text
        salvar_credenciais(credenciais)
        await context.bot.send_message(chat_id, f"Campo '{campo}' atualizado com sucesso para: {text}")
        await context.bot.send_message(chat_id, "Menu principal:", reply_markup=gerar_menu_principal())
        del user_editing_state[user_id]

    else:
        # Atualiza o link da imagem no start.txt
        start_txt = carregar_start_txt()
        regex = r'(<a href=")[^"]+(">)'
        novo_start = re.sub(regex, fr'\1{text}\2', start_txt)
        salvar_start_txt(novo_start)
        await context.bot.send_message(chat_id, f"Link da imagem atualizado para: {text}")
        await context.bot.send_message(chat_id, "Menu principal:", reply_markup=gerar_menu_principal())
        del user_editing_state[user_id]

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem_handler))
    print("Bot iniciado. Pressione Ctrl+C para encerrar.")
    application.run_polling()

if __name__ == "__main__":
    main()
