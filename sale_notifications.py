"""Notificações de vendas compartilhadas pelo bot e pela API."""
import html
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def _normalize_key(s: str) -> str:
    """Normaliza uma string para facilitar a correspondência."""
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _get_emoji_for_product(nome: str, emoji_map: dict = None) -> str:
    """Obtém o emoji premium para um produto baseado no nome."""
    if not emoji_map or not isinstance(emoji_map, dict):
        return ""
    
    normalized_name = _normalize_key(nome)
    
    # Procura correspondência no mapa de emojis por serviço
    for key, emoji_id in sorted(emoji_map.items(), key=lambda item: len(item[0]), reverse=True):
        if key in normalized_name or normalized_name in key:
            if emoji_id and re.fullmatch(r'\d+', str(emoji_id).strip()):
                return f'<tg-emoji emoji-id="{html.escape(str(emoji_id))}">{html.escape("🛍️")}</tg-emoji>'
    
    return ""


def enviar_venda_canal(bot, chat_id, username, user_id, nome, valor, horario):
    nome_limpo = html.escape(str(nome))
    try:
        valor_texto = f'{float(valor):.2f}'.replace('.', ',')
    except (TypeError, ValueError):
        valor_texto = html.escape(str(valor))
    
    # Carrega o mapa de emojis por serviço
    try:
        import json
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        emoji_map = data.get("service_emoji_map", {})
    except Exception:
        emoji_map = {}
    
    # Obtém o emoji premium para o produto
    emoji_premium = _get_emoji_for_product(nome, emoji_map)
    emoji_exibicao = emoji_premium if emoji_premium else "🛍️"
    
    texto = (
        f'{emoji_exibicao} <b>NOVA COMPRA REALIZADA</b>\n\n'
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

