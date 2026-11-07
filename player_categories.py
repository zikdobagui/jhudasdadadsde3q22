# -*- coding: utf-8 -*-
"""
Agrupamento do catálogo Player (Contas Globais) por categoria.

A API do Player não devolve o campo `category` em /products, então a
categoria é deduzida do nome do produto. O mapa salvo em
settings/player_categories.json permite ajustar o resultado manualmente:

{
    "overrides": { "netflix": "Streaming", "gpt": "IA" },
    "order": ["Streaming", "IA", "..."],
    "hidden_categories": []
}

`overrides` casa por trecho do nome (casefold); o valor define a categoria
daquele produto. `order` define a ordem dos botões de categoria no menu.
"""

import json
import os
import re
import unicodedata
from typing import Dict, List, Any

CATEGORIES_FILE = os.path.join('settings', 'player_categories.json')
OTHER_CATEGORY = 'Outros'

STANDARD_EMOJI_PATTERN = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+')

# (categoria, emoji, regex de palavras-chave)
# A ordem importa: a primeira regra que casar define a categoria.
CATEGORY_RULES = [
    ('Streaming', '🎬', r'netflix|disney|\bhbo\b|paramount|globoplay|star\+|telecine|'
                       r'claro tv|uni tv|crunchyroll|cruncyroll|hotstar|shahid|'
                       r'star plus|looke|pluto|sling|amazon prime|prime video|apple tv|'
                       r'conta max|tela max|max plano|hbo max'),
    ('Música', '🎵', r'spotify|apple music|tidal|deezer|youtube premium|ytb premium|'
                      r'yt music|soundcloud'),
    ('IA / Criação', '🤖', r'chatgpt|\bgpt\b|gemini|claude|copilot|perplexity|grok|kling|'
                            r'midjourney|magic patterns|wispr|wisper|elevenlabs|muse ai|'
                            r'\bia\b|\bai\b|fin ia|google ai|meitu|locket|brain ?fm|'
                            r'quillbot|notion ai|leonardo|cursor|\bv0\b|minimax|gamma|supabase|'
                            r'manus|runway|dreamina|veo ?[0-9]|veo|suno|heygen|openart|'
                            r'kimi|genspark|lovable|bolt\.?new|replit|framer|n8n|warp|'
                            r'railway|resend|arize|posthog|pangram|mobbin|readwise|bolt |'
                            r'granola|supercut|wordwall|vidiq|pitpit|filmora|clipchamp|'
                            r'capcut|coreldraw|canva|miro'),
    ('Microsoft / Office', '🪟', r'outlook|hotmail|office|microsoft|365|gmail|e-mail|mail|'
                                r'windows|onedrive|excel|powerpoint|icloud|office 20'),
    ('Design / Produtividade', '🎨', r'adobe|express|figma|ilovepdf|scribd|notion|airtable|'
                                   r'miro|linear|trello|slack|zoom|solidworks|autodesk|'
                                   r'jetbrains|linkedin|linkdin|udemy|coursera|edx|duolingo|'
                                   r'quizlet|vitalsource|grammarly|intercom|mercury|stripe|'
                                   r'github|proton|jam |corel'),
    ('VPN / Proxy', '🛡️', r'vpn|proxy|hma|expressvpn|avira|surfshark|v2ray|nordvpn|'
                           r'ipvanish|cyberghost|mcafee|eset|antivirus|norton'),
    ('Jogos', '🎮', r'game|steam|xbox|playstation|psn|nintendo|nitro|discord|fortnite|'
                    r'valorant|gift card|decor discord'),
    ('IPTV / Servidores', '📺', r'player|\bserver\b|play tv|space tv|club tv|\bstream|iptv|smart|'
                                r'xtream|tivimate|4k|\btv\b|\bplay\b|\bplay\d|\bking\b|stb|ai player|miroplayer|'
                                r'box |sports|futebol|p2p|tivi|bay|dtv|dontv|hush|messitv|'
                                r'qplay|ktn|vip|you tivi|assist plus|simple pro|duplex|'
                                r'foco x|tvoyatv|playsim|bob '),
    ('Contas Globais', '🌍', r'conta |tela |codigo|acesso |chave|assinatura|tiktok|'
                           r'waking up|king stand|tv ?360'),
]

# Emoji exibido no botão de cada categoria.
CATEGORY_EMOJIS = {name: emoji for name, emoji, _ in CATEGORY_RULES}
CATEGORY_EMOJIS[OTHER_CATEGORY] = '📦'

# Ícone premium (icon_custom_emoji_id) de cada categoria. Os IDs do pacote são
# lidos de settings/credenciais.json (service_emoji_ids); o JSON mantém uma
# cópia padrão em CATEGORY_PREMIUM_EMOJI_FALLBACK caso o pacote seja trocado.
CATEGORY_PREMIUM_EMOJI_INDEX = {
    'Streaming': 31,            # 🎥
    'Música': 30,               # 🎵
    'Jogos': 20,                # 🏀
    'Microsoft / Office': 0,    # 🔴 (sem ícone próprio no pacote)
    'Design / Produtividade': 42,
    'VPN / Proxy': 0,
    'IPTV / Servidores': 31,
    'Contas Globais': 6,
    OTHER_CATEGORY: 0,
}

CATEGORY_PREMIUM_EMOJI_FALLBACK = {
    'Streaming': '5071309770355377294',
    'Música': '5069196298553394676',
    'Jogos': '5071338791449396331',
    'Design / Produtividade': '5071344551000540341',
    'IPTV / Servidores': '5071309770355377294',
    'Contas Globais': '5069305356362974762',
    OTHER_CATEGORY: '5069081919279334693',
}

_COMPILED_RULES = [(name, re.compile(pattern)) for name, _, pattern in CATEGORY_RULES]


def _normalize(text: str) -> str:
    """Remove emojis, acentos e caixa para comparar nomes de produto."""
    text = STANDARD_EMOJI_PATTERN.sub(' ', str(text or ''))
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text).casefold().strip()


def load_category_config() -> Dict[str, Any]:
    try:
        if os.path.exists(CATEGORIES_FILE):
            with open(CATEGORIES_FILE, 'r', encoding='utf-8-sig') as file:
                data = json.load(file)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass
    return {}


def save_category_config(config: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CATEGORIES_FILE), exist_ok=True)
    with open(CATEGORIES_FILE, 'w', encoding='utf-8') as file:
        json.dump(config, file, indent=4, ensure_ascii=False)


def detect_category(product_name: str, config: Dict[str, Any] = None) -> str:
    """Deduz a categoria de um produto a partir do nome."""
    config = config if config is not None else load_category_config()
    normalized = _normalize(product_name)

    overrides = config.get('overrides') or {}
    for term, category in overrides.items():
        if term and _normalize(term) in normalized:
            return str(category)

    for name, pattern in _COMPILED_RULES:
        if pattern.search(normalized):
            return name
    return OTHER_CATEGORY


SERVICE_NAME_RULES = [
    ('YouTube Premium', r'youtube|ytb premium|yt music'),
    ('Spotify', r'spotify'), ('ChatGPT', r'chatgpt|\bgpt\b'),
    ('Prime Video', r'prime video|amazon prime'), ('Gemini', r'gemini|google ai'),
    ('Crunchyroll', r'crunchyroll|cruncyroll'), ('CapCut', r'capcut'),
    ('Claude', r'claude'), ('Office 365', r'(?:office|microsoft)\s*365|\b365\b'),
    ('Canva', r'canva'), ('Apple TV', r'apple tv'), ('ElevenLabs', r'elevenlabs'),
    ('Netflix', r'netflix'), ('Disney+', r'disney'), ('Max', r'\bhbo\b|\bmax\b'),
    ('Microsoft / Office', r'microsoft|microsfot|office|windows|outlook|hotmail|onedrive|excel|powerpoint'),
    ('Discord', r'discord|nitro'), ('TikTok', r'tiktok'), ('Waking Up', r'waking up'),
    ('TV360', r'tv ?360'), ('Adobe', r'adobe'), ('Figma', r'figma'),
    ('Notion', r'notion'), ('Perplexity', r'perplexity'), ('Grok', r'grok'),
    ('Midjourney', r'midjourney'), ('Steam', r'steam'), ('Xbox', r'xbox'),
    ('PlayStation', r'playstation|\bpsn\b'), ('Nintendo', r'nintendo'),
    ('NordVPN', r'nordvpn'), ('Surfshark', r'surfshark'), ('ExpressVPN', r'expressvpn'),
    ('Paramount+', r'paramount'), ('Globoplay', r'globoplay'),
    ('Apple Music', r'apple music'), ('Deezer', r'deezer'), ('Tidal', r'tidal'),
    ('LinkedIn', r'linkedin|linkdin'), ('Duolingo', r'duolingo'),
    ('Cursor', r'cursor'), ('Lovable', r'lovable'), ('Kling', r'kling'),
    ('Suno', r'suno'), ('Runway', r'runway'), ('HeyGen', r'heygen'),
]


def product_group(product, config=None):
    """Agrupa pelo serviço no nome, ignorando a categoria recebida da API."""
    config = config if config is not None else load_category_config()
    if config.get('group_by') != 'name':
        return str(config.get('single_category') or product.get('category') or
                   detect_category(product.get('name', ''), config)).strip()
    name = str(product.get('name') or '').strip()
    normalized = _normalize(name)
    for term, label in (config.get('service_overrides') or {}).items():
        if _normalize(term) and _normalize(term) in normalized:
            return str(label)
    for label, pattern in SERVICE_NAME_RULES:
        if re.search(pattern, normalized):
            return label
    # Serviços desconhecidos continuam visíveis com seu nome original.
    return STANDARD_EMOJI_PATTERN.sub('', name).strip() or 'Produto sem nome'


def category_emoji(category: str) -> str:
    return CATEGORY_EMOJIS.get(category, CATEGORY_EMOJIS[OTHER_CATEGORY])


def category_premium_emoji_id(category: str, emoji_ids: List[str] = None) -> str:
    """ID do emoji premium do pacote configurado para a categoria.

    Tenta o índice em service_emoji_ids; se o pacote configurado não tiver esse
    índice (ou não existir), usa o ID padrão conhecido. Sempre devolve um ID
    premium válido, para o botão nunca cair no emoji padrão.
    """
    if category not in CATEGORY_PREMIUM_EMOJI_INDEX:
        return '5447410659077661506'
    if emoji_ids is None:
        emoji_ids = load_service_emoji_ids()
    index = CATEGORY_PREMIUM_EMOJI_INDEX.get(category)
    if emoji_ids and index is not None and index < len(emoji_ids):
        candidate = str(emoji_ids[index]).strip()
        if candidate.isdigit():
            return candidate
    return CATEGORY_PREMIUM_EMOJI_FALLBACK.get(category, CATEGORY_PREMIUM_EMOJI_FALLBACK[OTHER_CATEGORY])


def load_service_emoji_ids() -> List[str]:
    """Lê service_emoji_ids de settings/credenciais.json (pacote de emojis premium)."""
    try:
        with open(os.path.join('settings', 'credenciais.json'), 'r', encoding='utf-8-sig') as file:
            ids = json.load(file).get('service_emoji_ids', [])
        if isinstance(ids, list):
            return [str(item).strip() for item in ids if str(item).strip().isdigit()]
    except (OSError, ValueError):
        pass
    return []


def slug(category: str) -> str:
    """Chave curta e estável para callback_data (sem acentos/espaços)."""
    normalized = unicodedata.normalize('NFKD', str(category))
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    value = re.sub(r'[^a-z0-9]+', '_', normalized.casefold()).strip('_') or 'outros'
    if len(value) > 24:
        import hashlib
        return value[:15] + '_' + hashlib.sha256(str(category).encode('utf-8')).hexdigest()[:8]
    return value


def _sort_key(category: str, order: List[str]):
    try:
        return (order.index(category), '')
    except ValueError:
        return (len(order) + (1 if category == OTHER_CATEGORY else 0), category)


def group_products(products: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Agrupa a lista de produtos por categoria, na ordem configurada.

    O menu Contas Globais vende só contas/serviços globais: produtos com
    `source` diferente de 'global' (acessos de login prontos, MACs de
    aplicativos e itens manuais) ficam fora do menu. Ajuste em
    `settings/player_categories.json` com `sources` / `exclude_sources`.
    """
    config = load_category_config()
    hidden = {str(item).casefold() for item in (config.get('hidden_categories') or [])}
    order = [str(item) for item in (config.get('order') or [])]
    order = order + [name for name, _, _ in CATEGORY_RULES if name not in order]

    sources = config.get('sources')
    allowed_sources = ({str(item).casefold() for item in sources} if sources else None)
    blocked_sources = {str(item).casefold() for item in (config.get('exclude_sources') or [])}

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for product in products or []:
        source = str(product.get('source') or '').strip().casefold()
        if allowed_sources is not None and source not in allowed_sources:
            continue
        if source and source in blocked_sources:
            continue

        category = product_group(product, config)
        if category.casefold() in hidden:
            continue
        grouped.setdefault(category, []).append(product)

    for items in grouped.values():
        items.sort(key=lambda item: (-int(item.get('stock') or 0), _normalize(item.get('name', ''))))

    return {category: grouped[category]
            for category in sorted(grouped, key=lambda item: _sort_key(item, order))}


def resolve_category(slug_value: str, products: List[Dict[str, Any]]) -> str:
    """Converte o slug do callback de volta no nome da categoria."""
    for category in group_products(products):
        if slug(category) == slug_value:
            return category
    return ''


def category_summary(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resumo por categoria: nome, slug, quantidade, itens em estoque."""
    summary = []
    emoji_ids = load_service_emoji_ids()
    for category, items in group_products(products).items():
        summary.append({
            'category': category,
            'slug': slug(category),
            'emoji': category_emoji(category),
            'premium_emoji_id': category_premium_emoji_id(category, emoji_ids),
            'count': len(items),
            'in_stock': sum(1 for item in items if int(item.get('stock') or 0) > 0),
        })
    return summary
