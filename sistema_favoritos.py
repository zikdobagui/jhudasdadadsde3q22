import os
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

PASTA_FAVORITOS = os.path.join('database', 'favoritos')

def _garantir_pasta():
    """Garante que a pasta de favoritos exista."""
    if not os.path.exists(PASTA_FAVORITOS):
        os.makedirs(PASTA_FAVORITOS)

def carregar_favoritos(user_id):
    """Carrega a lista de favoritos do usuário."""
    _garantir_pasta()
    caminho = os.path.join(PASTA_FAVORITOS, f"{user_id}.json")
    if os.path.exists(caminho):
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_favoritos(user_id, favoritos):
    """Salva a lista de favoritos do usuário."""
    _garantir_pasta()
    caminho = os.path.join(PASTA_FAVORITOS, f"{user_id}.json")
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(favoritos, f, ensure_ascii=False, indent=4)

def registrar_handlers(bot, api):
    @bot.callback_query_handler(func=lambda call: call.data.startswith('fav_toggle|'))
    def handle_fav_toggle(call):
        user_id = call.from_user.id
        servico = call.data.split('|')[1]
        favoritos = carregar_favoritos(user_id)
        
        if servico in favoritos:
            favoritos.remove(servico)
            mensagem = f"💔 {servico} foi removido!"
            novo_texto = "❤️ FAVORITAR"
        else:
            favoritos.append(servico)
            mensagem = f"❤️ {servico} salvo com sucesso!"
            novo_texto = "💔 DESFAVORITAR"
            
        salvar_favoritos(user_id, favoritos)
        
        # Envia o balãozinho pop-up
        bot.answer_callback_query(call.id, mensagem, show_alert=True)
        
        # Atualiza o texto do botão na mesma hora sem recarregar a mensagem inteira
        if call.message and call.message.reply_markup:
            markup = call.message.reply_markup
            for row in markup.keyboard:
                for btn in row:
                    if btn.callback_data == call.data:
                        btn.text = novo_texto
            try:
                bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    reply_markup=markup
                )
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data == 'mostrar_favoritos')
    def handle_mostrar_favoritos(call):
        user_id = call.from_user.id
        favoritos = carregar_favoritos(user_id)
        
        if not favoritos:
            bot.answer_callback_query(call.id, "💔 Seu painel de favoritos está vazio.", show_alert=True)
            # Atualiza a tela informando que esvaziou a lista
            markup_vazio = InlineKeyboardMarkup()
            markup_vazio.add(InlineKeyboardButton("🔙 Voltar", callback_data="perfil"))
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="💔 <b>Seu painel de favoritos está vazio.</b>\n\nAdicione novos produtos navegando pela nossa loja!",
                    parse_mode='HTML',
                    reply_markup=markup_vazio
                )
            except:
                pass
            return
            
        texto = "❤️ <b>Seus Produtos Favoritos:</b>\n\n👇 Clique em um produto abaixo para visualizar:"
        markup = InlineKeyboardMarkup(row_width=1)
        
        for servico in favoritos:
            try:
                estoque = int(api.ControleLogins.pegar_estoque(servico))
            except Exception:
                estoque = 0
            
            if estoque > 0:
                texto_botao = f"⭐ {servico}"
                cb_data = f"exibir_servico {servico}" # Abre o produto
            else:
                texto_botao = f"❌ {servico} [ESGOTADO]"
                cb_data = f"fav_esgotado|{servico}" # Abre menu de remoção rápida
            
            markup.add(InlineKeyboardButton(texto_botao, callback_data=cb_data))
            
        markup.add(InlineKeyboardButton("🔙 Voltar", callback_data="perfil"))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

    # NOVO: Handler que barra a abertura do produto esgotado
    @bot.callback_query_handler(func=lambda call: call.data.startswith('fav_esgotado|'))
    def handle_fav_esgotado(call):
        servico = call.data.split('|')[1]
        texto = (
            f"⚠️ <b>O produto {servico} está atualmente ESGOTADO!</b>\n\n"
            f"Você deseja removê-lo da sua lista de favoritos ou mantê-lo para quando o estoque for reposto?"
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🗑️ Remover dos Favoritos", callback_data=f"fav_del_return|{servico}"))
        markup.row(InlineKeyboardButton("🔙 Manter e Voltar", callback_data="mostrar_favoritos"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

    # NOVO: Handler que deleta o produto e retorna pra lista
    @bot.callback_query_handler(func=lambda call: call.data.startswith('fav_del_return|'))
    def handle_fav_del_return(call):
        user_id = call.from_user.id
        servico = call.data.split('|')[1]
        favoritos = carregar_favoritos(user_id)
        
        if servico in favoritos:
            favoritos.remove(servico)
            salvar_favoritos(user_id, favoritos)
            bot.answer_callback_query(call.id, f"🗑️ {servico} foi removido!", show_alert=True)
        else:
            bot.answer_callback_query(call.id)
            
        # Chama a função principal de favoritos de novo para atualizar a tela automaticamente
        handle_mostrar_favoritos(call)
