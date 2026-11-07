"""Notificações de vendas compartilhadas pelo bot e pela API.

Todos os emojis das mensagens saem como emoji premium animado
(`<tg-emoji emoji-id="...">`). Se o pacote configurado não tiver o ícone do
serviço, entra o ícone do pacote, nunca um emoji padrão.
"""
import html
import json
import re
import unicodedata

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

CREDENTIALS_FILE = 'settings/credenciais.json'

# Índices dentro de service_emoji_ids (settings/credenciais.json) usados nos avisos.
PACK_EMOJI_INDEX = {
    'carrinho': 42,
    'status': 0,
    'musica': 30,
    'video': 31,
    'jogos': 20,
}

# Reserva fixa, para o caso de o pacote configurado ser trocado.
PACK_EMOJI_FALLBACK = {
    'carrinho': '5069283688252965958',
    'status': '5069081919279334693',
    'musica': '5069196298553394676',
    'video': '5071309770355377294',
    'jogos': '5071338791449396331',
}


def _normalize_key(s: str) -> str:
    """Normaliza uma string (sem acento, sem espaços, sem símbolos)."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _load_credentials() -> dict:
    try:
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pack_emoji_id(key: str, data: dict = None) -> str:
    """ID premium de um ícone genérico do pacote (carrinho, status, vídeo...)."""
    data = data if data is not None else _load_credentials()
    ids = data.get('service_emoji_ids') or []
    index = PACK_EMOJI_INDEX.get(key)
    if isinstance(ids, list) and index is not None and index < len(ids):
        candidate = str(ids[index]).strip()
        if candidate.isdigit():
            return candidate
    return PACK_EMOJI_FALLBACK.get(key, PACK_EMOJI_FALLBACK['status'])


def premium(emoji_id: str, fallback: str) -> str:
    """Monta a tag de emoji premium; devolve o fallback só se o ID for inválido."""
    emoji_id = str(emoji_id or '').strip()
    if not emoji_id.isdigit():
        return str(fallback)
    return f'<tg-emoji emoji-id="{emoji_id}">{html.escape(str(fallback))}</tg-emoji>'


def _get_emoji_for_product(nome: str, emoji_map: dict = None, data: dict = None) -> str:
    """ID premium do serviço do produto ('' quando não há)."""
    if not emoji_map or not isinstance(emoji_map, dict):
        return ""

    normalized_name = _normalize_key(nome)
    if not normalized_name:
        return ""

    # _normalize_key remove espaços, então a comparação é por trecho do nome
    # compactado. Uma tecla curta (ex.: 'SKY') casaria dentro de outra palavra,
    # então ela só entra quando o nome começa ou termina com ela.
    best_id, best_len = '', 0
    for key, emoji_id in emoji_map.items():
        normalized_key = _normalize_key(key)
        emoji_id = str(emoji_id).strip()
        if not normalized_key or not emoji_id.isdigit():
            continue
        if len(normalized_key) >= 4:
            matches = normalized_key in normalized_name
        else:
            matches = (normalized_name.startswith(normalized_key)
                       or normalized_name.endswith(normalized_key))
        if matches and len(normalized_key) > best_len:
            best_id, best_len = emoji_id, len(normalized_key)

    if best_id:
        return best_id
    return _pack_emoji_id('carrinho', data)


def enviar_venda_canal(bot, chat_id, username, user_id, nome, valor, horario):
    nome_limpo = html.escape(str(nome))
    try:
        valor_texto = f'{float(valor):.2f}'.replace('.', ',')
    except (TypeError, ValueError):
        valor_texto = html.escape(str(valor))

    data = _load_credentials()
    emoji_map = data.get("service_emoji_map", {}) if isinstance(data.get("service_emoji_map"), dict) else {}

    # Todos os ícones da mensagem saem do pacote premium animado.
    emoji_premium = premium(
        _get_emoji_for_product(nome, emoji_map, data),
        '🛍️',
    )
    pacote = premium(_pack_emoji_id('status', data), '📦')
    dinheiro = premium(_pack_emoji_id('video', data), '💰')
    cliente = premium(_pack_emoji_id('jogos', data), '🆔')
    relogio = premium(_pack_emoji_id('musica', data), '🕒')
    raio = premium(_pack_emoji_id('carrinho', data), '⚡')
    carrinho = premium(_pack_emoji_id('carrinho', data), '🛒')

    texto = (
        f'{emoji_premium} <b>NOVA COMPRA REALIZADA</b>\n\n'
        f'{pacote} <b>Produto:</b> {nome_limpo}\n'
        f'{dinheiro} <b>Valor:</b> R$ {valor_texto}\n'
        f'{cliente} <b>Cliente:</b> <code>{html.escape(str(user_id))}</code>\n'
        f'{relogio} <b>Horário:</b> {html.escape(str(horario))}\n\n'
        f'{raio} <i>Entrega automática, rápida e segura.</i>'
    )
    markup = InlineKeyboardMarkup()
    # Texto do botão sem emoji: o ícone entra por icon_custom_emoji_id.
    botao = InlineKeyboardButton('[cor:azul] COMPRAR NO BOT', url=f'https://t.me/{username}')
    botao.icon_custom_emoji_id = _pack_emoji_id('carrinho', data)
    markup.row(botao)
    return bot.send_message(
        chat_id,
        texto,
        parse_mode='HTML',
        reply_markup=markup
    )
