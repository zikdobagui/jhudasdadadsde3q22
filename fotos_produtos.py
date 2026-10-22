import json
import os
from telebot import types
import central as api

ARQUIVO_FOTOS = 'database/fotos_produtos.json'

def is_admin_user(user_id):
    try:
        return api.Admin.verificar_admin(user_id) or str(user_id) == str(api.CredentialsChange.id_dono())
    except:
        return False

def carregar_fotos_produtos():
    if not os.path.exists('database'):
        os.makedirs('database')
    if os.path.exists(ARQUIVO_FOTOS):
        try:
            with open(ARQUIVO_FOTOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_foto_produto(nome_produto, file_id):
    fotos = carregar_fotos_produtos()
    fotos[nome_produto.lower().strip()] = file_id
    with open(ARQUIVO_FOTOS, 'w', encoding='utf-8') as f:
        json.dump(fotos, f, indent=4, ensure_ascii=False)

def obter_foto_customizada(nome_produto):
    fotos = carregar_fotos_produtos()
    return fotos.get(nome_produto.lower().strip())

def registrar_handlers(bot):
    @bot.message_handler(commands=['setfoto'])
    def cmd_setfoto(message):
        if not is_admin_user(message.from_user.id):
            return bot.reply_to(message, "🚫 Acesso Negado!")
        
        msg = bot.send_message(
            message.chat.id, 
            "📸 <b>DEFINIR FOTO DO PRODUTO</b>\n\nDigite o <b>NOME EXATO</b> do produto que deseja adicionar/alterar a foto:", 
            parse_mode='HTML', 
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(msg, processar_nome_foto, bot)

    def processar_nome_foto(message, bot):
        if message.text.lower() in ['/cancel', 'cancelar']:
            return bot.reply_to(message, "Operação cancelada.")
            
        nome_produto = message.text.strip()
        msg = bot.send_message(
            message.chat.id, 
            f"✅ Produto selecionado: <b>{nome_produto}</b>\n\nAgora, envie a <b>IMAGEM (FOTO)</b> que aparecerá para os clientes.", 
            parse_mode='HTML', 
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(msg, processar_imagem_foto, bot, nome_produto)

    def processar_imagem_foto(message, bot, nome_produto):
        if not message.photo:
            bot.send_message(message.chat.id, "❌ Você não enviou uma foto válida. Use o comando /setfoto novamente.")
            return
            
        file_id = message.photo[-1].file_id
        salvar_foto_produto(nome_produto, file_id)
        
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Sucesso!</b> A foto do produto <b>{nome_produto}</b> foi salva e já aparecerá no menu e na entrega.", 
            parse_mode='HTML'
        )
