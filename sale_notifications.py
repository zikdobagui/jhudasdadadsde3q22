"""Notificações de vendas compartilhadas pelo bot e pela API."""
import html
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def enviar_venda_canal(bot, chat_id, username, user_id, nome, valor, horario):
    nome_limpo = html.escape(str(nome))
    try:
        valor_texto = f'{float(valor):.2f}'.replace('.', ',')
    except (TypeError, ValueError):
        valor_texto = html.escape(str(valor))
    texto = (
        '🛍️ <b>NOVA COMPRA REALIZADA</b>\n\n'
        f'📦 <b>Produto:</b> {nome_limpo}\n'
        f'💰 <b>Valor:</b> R$ {valor_texto}\n'
        f'🆔 <b>Cliente:</b> <code>{html.escape(str(user_id))}</code>\n'
        f'🕒 <b>Horário:</b> {html.escape(str(horario))}\n\n'
        '⚡ <i>Entrega automática, rápida e segura.</i>'
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('[cor:azul] 🛒 COMPRAR NO BOT', url=f'https://t.me/{username}'))
    return bot.send_message(
        chat_id,
        texto,
        parse_mode='HTML',
        reply_markup=markup
    )

