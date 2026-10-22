import json
import os
from telebot import types
import central as api
import premium_emojis

ARQUIVO_FOTOS = 'database/fotos_menus.json'

# Menus que já têm um ponto de exibição integrado (aparecem no /setfotomenu
# com o aviso de que já funcionam). Para adicionar um novo menu à lista,
# basta chamar exibir_com_foto_opcional(...) no ponto onde ele é mostrado
# (veja o exemplo em modulo_relatorios_configuracoes.py -> addsaldo()
# e em modulo_pix_transmissao_carrinho.py -> cart_show_products()).
MENUS_DISPONIVEIS = [
    ('🛍️ Ver Produtos', 'servicos'),
    ('🛒 Carrinho', 'carrinho'),
    ('🛒📲 Categorias (Contas/Telas)', 'servicos_categoria'),
    ('💰 Adicionar Saldo / Recarga', 'addsaldo'),
    ('👤 Perfil', 'perfil'),
    ('🎁 Central de Prêmios', 'menu_premios'),
    ('🎮 Entretenimento', 'entretenimento'),
    ('📊 Ranking', 'ranking'),
    ('🏠 Menu Inicial (/start)', 'start'),
    ('🛍️ Menu Comprar', 'menu_comprar'),
    ('💠 PIX Manual', 'pix_manual'),
    ('🎁 Gift Card', 'giftcard'),
]


def is_admin_user(user_id):
    try:
        return api.Admin.verificar_admin(user_id) or str(user_id) == str(api.CredentialsChange.id_dono())
    except Exception:
        return False


def carregar_fotos_menus():
    if not os.path.exists('database'):
        os.makedirs('database')
    if os.path.exists(ARQUIVO_FOTOS):
        try:
            with open(ARQUIVO_FOTOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def salvar_foto_menu(chave, file_id):
    fotos = carregar_fotos_menus()
    fotos[chave] = file_id
    if not os.path.exists('database'):
        os.makedirs('database')
    with open(ARQUIVO_FOTOS, 'w', encoding='utf-8') as f:
        json.dump(fotos, f, indent=4, ensure_ascii=False)


def remover_foto_menu(chave):
    fotos = carregar_fotos_menus()
    if chave in fotos:
        del fotos[chave]
        with open(ARQUIVO_FOTOS, 'w', encoding='utf-8') as f:
            json.dump(fotos, f, indent=4, ensure_ascii=False)
        return True
    return False


def obter_foto_menu(chave):
    return carregar_fotos_menus().get(chave)


def exibir_com_foto(bot, chat_id, message_id, foto, texto, reply_markup=None, parse_mode='HTML'):
    """
    Exibe 'foto' (file_id de upload OU uma URL) com 'texto' como legenda,
    no lugar da mensagem 'message_id'. SEMPRE força a foto certa, mesmo que
    a mensagem atual já seja uma foto de OUTRO menu (evita herdar a imagem
    errada ao trocar de tela).
    Retorna:
      - True        -> editou a mensagem existente com sucesso (mesmo message_id)
      - Message     -> precisou apagar e mandar mensagem nova (pegue .message_id)
      - None        -> falhou completamente
    """
    # bot.edit_message_media() não passa pelos patches de premium_emojis.py
    # (que só cobrem send_message/send_photo/edit_message_text/edit_message_caption),
    # então sem isso os emojis premium viravam o emoji padrão toda vez que o
    # menu era trocado usando essa função (ex: botão "Voltar").
    if isinstance(parse_mode, str) and parse_mode.lower() == 'html':
        texto = premium_emojis.replace_emojis(texto, context="message")
    legenda = texto if len(texto) <= 1024 else texto[:1021] + '...'

    # 1ª tentativa: TROCAR a mídia da mensagem atual (funciona mesmo se a
    # mensagem já for uma foto de outro menu — troca pela foto certa).
    try:
        media = types.InputMediaPhoto(foto, caption=legenda, parse_mode=parse_mode)
        bot.edit_message_media(media, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
        return True
    except Exception:
        pass

    # 2ª tentativa: apaga a mensagem atual (texto) e envia a foto no lugar
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    try:
        return bot.send_photo(chat_id, foto, caption=legenda, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        print(f"[fotos_menus] Erro ao exibir foto: {e}")
        return None


def exibir_com_foto_opcional(bot, chat_id, message_id, chave, texto, reply_markup=None, parse_mode='HTML'):
    """
    Se houver uma foto customizada salva para 'chave' (via /setfotomenu),
    tenta exibir essa foto no lugar da mensagem 'message_id', usando 'texto'
    como legenda. Retorna True se conseguiu (o chamador não precisa fazer
    mais nada). Retorna False se não há foto customizada para essa chave
    (o chamador deve seguir com o fluxo normal em texto).
    """
    file_id = obter_foto_menu(chave)
    if not file_id:
        return False
    resultado = exibir_com_foto(bot, chat_id, message_id, file_id, texto, reply_markup=reply_markup, parse_mode=parse_mode)
    return resultado is not None


def _montar_menu_selecao():
    markup = types.InlineKeyboardMarkup(row_width=1)
    fotos_atuais = carregar_fotos_menus()
    for nome, chave in MENUS_DISPONIVEIS:
        marcador = ' ✅' if chave in fotos_atuais else ''
        markup.add(types.InlineKeyboardButton(f"{nome}{marcador}", callback_data=f'setfotomenu_escolher_{chave}'))
    return markup


def registrar_handlers(bot):
    @bot.message_handler(commands=['setfotomenu'])
    def cmd_setfotomenu(message):
        if not is_admin_user(message.from_user.id):
            return bot.reply_to(message, "🚫 Acesso Negado!")
        bot.send_message(
            message.chat.id,
            "📸 <b>FOTO DOS MENUS</b>\n\n"
            "Escolha para qual menu você quer definir (ou trocar) a foto.\n"
            "Os menus com ✅ já têm uma foto customizada salva.",
            parse_mode='HTML',
            reply_markup=_montar_menu_selecao()
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('setfotomenu_escolher_'))
    def cb_escolher_menu(call):
        if not is_admin_user(call.from_user.id):
            return bot.answer_callback_query(call.id, "🚫 Acesso Negado!", show_alert=True)
        bot.answer_callback_query(call.id)
        chave = call.data.replace('setfotomenu_escolher_', '')
        nome_exibicao = dict((c, n) for n, c in MENUS_DISPONIVEIS).get(chave, chave)

        markup = types.InlineKeyboardMarkup()
        if obter_foto_menu(chave):
            markup.add(types.InlineKeyboardButton('🗑️ Remover foto atual', callback_data=f'setfotomenu_remover_{chave}'))
        markup.add(types.InlineKeyboardButton('❌ Cancelar', callback_data='setfotomenu_cancelar'))

        msg = bot.send_message(
            call.message.chat.id,
            f"✅ Menu selecionado: <b>{nome_exibicao}</b>\n\n"
            f"Agora, envie a <b>foto</b> (imagem) que deve aparecer nesse menu.\n"
            f"Basta enviar a foto pelo chat, sem precisar de link.",
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, _processar_imagem_menu, bot, chave, nome_exibicao)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('setfotomenu_remover_'))
    def cb_remover_menu(call):
        if not is_admin_user(call.from_user.id):
            return bot.answer_callback_query(call.id, "🚫 Acesso Negado!", show_alert=True)
        chave = call.data.replace('setfotomenu_remover_', '')
        removeu = remover_foto_menu(chave)
        bot.answer_callback_query(call.id, "✅ Foto removida!" if removeu else "Nenhuma foto encontrada.", show_alert=True)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda call: call.data == 'setfotomenu_cancelar')
    def cb_cancelar_menu(call):
        bot.answer_callback_query(call.id)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    def _processar_imagem_menu(message, bot, chave, nome_exibicao):
        if message.text and message.text.lower() in ['/cancel', 'cancelar']:
            return bot.reply_to(message, "Operação cancelada.")
        if not message.photo:
            bot.send_message(message.chat.id, "❌ Você não enviou uma foto válida. Use o comando /setfotomenu novamente.")
            return

        file_id = message.photo[-1].file_id
        salvar_foto_menu(chave, file_id)

        bot.send_message(
            message.chat.id,
            f"✅ <b>Sucesso!</b> A foto do menu <b>{nome_exibicao}</b> foi salva e já aparecerá "
            f"da próxima vez que esse menu for aberto.",
            parse_mode='HTML'
        )
