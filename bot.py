import mercadopago
import json
import string
import telebot
import time
import casino 
import rankings
import telebot.apihelper
import html
import sys
import jogos_filmes_final as jf_final
import requests
import uuid
import httpx
import inspect
from threading import Timer
import base64
import time
from telebot.apihelper import ApiTelegramException
import database
import threading
import re
import os
import datetime
import subprocess
import threading
import random
import html
import zipfile
import shutil
import urllib.parse
import hashlib
import central as api
import pytz
from io import BytesIO
from os import system
from pathlib import PurePosixPath
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import timezone
from pytz import timezone
from database import get_user_balance, add_saldo, add_pagamento, get_top_users

def service_callback_token(servico):
    return hashlib.sha1(str(servico).strip().casefold().encode('utf-8')).hexdigest()[:16]

def resolve_service_callback_token(token):
    token = str(token or '').strip()
    vistos = set()
    try:
        for acesso in api.ControleLogins.pegar_servicos():
            nome = str(acesso.get('nome', '')).strip()
            if not nome or nome in vistos:
                continue
            vistos.add(nome)
            if service_callback_token(nome) == token:
                return nome
    except Exception as error:
        print(f"[SERVICO] Erro ao resolver token {token}: {error}")
    return None

def service_callback_data(prefixo, servico):
    return f"{prefixo}|{service_callback_token(servico)}"

# Compatibilidade com versoes do pyTelegramBotAPI que ainda nao serializam
# style/icon_custom_emoji_id, embora esses campos ja existam na Bot API.
_original_button_to_dict = InlineKeyboardButton.to_dict

def _patched_button_to_dict(self):
    result = _original_button_to_dict(self)
    text = result.get('text')
    button_style = getattr(self, 'style', None)
    if isinstance(text, str):
        if 'fix_mojibake_text' in globals():
            text = fix_mojibake_text(text)
        color_match = re.search(
            r'(?:\[|\{)\s*(?:cor|color|style)\s*:\s*([a-zA-Z_ -]+)\s*(?:\]|\})|<\s*(?:cor|color|style)\s*=\s*["\']?([a-zA-Z_ -]+)["\']?\s*>',
            text,
            flags=re.IGNORECASE
        )
        if color_match:
            color_name = (color_match.group(1) or color_match.group(2) or '').strip().lower().replace(' ', '_')
            text = re.sub(
                r'(?:\[|\{)\s*(?:cor|color|style)\s*:\s*[a-zA-Z_ -]+\s*(?:\]|\})|<\s*(?:cor|color|style)\s*=\s*["\']?[a-zA-Z_ -]+["\']?\s*>',
                '',
                text,
                count=1,
                flags=re.IGNORECASE
            ).strip()
            button_style = {
                'verde': 'success',
                'green': 'success',
                'success': 'success',
                'azul': 'primary',
                'blue': 'primary',
                'primary': 'primary',
                'vermelho': 'danger',
                'red': 'danger',
                'danger': 'danger',
            }
            button_style = button_style.get(color_name)

        emoji_match = re.search(
            r'<tg-emoji\s+emoji-id=["\']([^"\']+)["\']>(.*?)</tg-emoji>',
            text,
            flags=re.IGNORECASE | re.DOTALL
        )
        if emoji_match and not getattr(self, 'icon_custom_emoji_id', None):
            self.icon_custom_emoji_id = emoji_match.group(1)
        result['text'] = re.sub(
            r'<tg-emoji\s+emoji-id=["\'][^"\']+["\']>(.*?)</tg-emoji>',
            lambda m: m.group(1),
            text,
            flags=re.IGNORECASE | re.DOTALL
        )
    if button_style in ('primary', 'success', 'danger'):
        result['style'] = button_style
    else:
        result.pop('style', None)
    icon_custom_emoji_id = getattr(self, 'icon_custom_emoji_id', None)
    if icon_custom_emoji_id:
        result['icon_custom_emoji_id'] = str(icon_custom_emoji_id)
    return result

InlineKeyboardButton.to_dict = _patched_button_to_dict

# Compatibilidade para versoes do pyTelegramBotAPI que ainda exigem
# is_animated/is_video no StickerSet, mesmo quando a API nao envia.
def _patched_sticker_set_de_json(cls, json_string):
    if json_string is None:
        return None

    obj = cls.check_json(json_string)
    obj.setdefault('is_animated', False)
    obj.setdefault('is_video', False)
    obj.setdefault('contains_masks', obj.get('sticker_type') == 'mask')

    stickers = []
    for sticker in obj.get('stickers', []) or []:
        stickers.append(types.Sticker.de_json(sticker))
    obj['stickers'] = stickers

    thumbnail = obj.get('thumbnail') or obj.get('thumb')
    if isinstance(thumbnail, dict) and 'file_id' in thumbnail:
        thumbnail = types.PhotoSize.de_json(thumbnail)
    else:
        thumbnail = None
    obj['thumbnail'] = thumbnail
    obj['thumb'] = thumbnail

    try:
        return cls(**obj)
    except TypeError as error:
        signature = inspect.signature(cls.__init__)
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )
        if accepts_kwargs:
            raise error

        allowed = {
            name for name in signature.parameters
            if name != 'self'
        }
        filtered = {key: value for key, value in obj.items() if key in allowed}
        return cls(**filtered)

types.StickerSet.de_json = classmethod(_patched_sticker_set_de_json)
from database import update_usernames
from utils import hc, virtualPayToken
from backup_manager import backup_manager
update_usernames()
# ==========================================================================
# ==========================================================================

termos_texto = """LEIA COM ATENÃ‡ÃƒO ANTES DE FINALIZAR SUA COMPRA

âš ï¸ Ao clicar no botÃ£o de confirmaÃ§Ã£o, vocÃª declara estar de pleno acordo com tudo que estÃ¡ descrito aqui. âš ï¸

ðŸ• HORÃRIO DE ATENDIMENTOS E SUPORTES
ðŸ“…DE SEGUNDA A SEXTA FEIRA DAS 11 HORAS DO DIA AS 11 HORAS DA NOITE 
ðŸ“… SÃBADO DE MEIO DIA AS 8 HORAS DA NOITE ,   
âš ï¸ DOMINGO E FERIADOS NÃƒO TEM ATENDIMENTO  âš ï¸

â° suporte de uma hora a 24 horas podendo prolongar se tiver queda em massa 

1ï¸âƒ£ Clique em SUPORTE no bot.
2ï¸âƒ£ Descreva detalhadamente seu problema.
3ï¸âƒ£ Aguarde a resposta de um administrador.

Para que possamos ajudÃ¡-lo(a) corretamente, Ã© *obrigatÃ³rio* apresentar:
ðŸ“¸ Print (captura de tela) do erro.
ðŸ”‘ Login exatamente como foi recebido.
ðŸ“… Data da compra.

Sem essas informaÃ§Ãµes, o suporte nÃ£o poderÃ¡ ser prestado.

âš ï¸ REGRAS IMPORTANTES
âŒ NÃ£o altere o e-mail de nenhuma conta adquirida; caso contrÃ¡rio, o suporte daquele acesso serÃ¡ anulado.
âŒ Reembolsos nÃ£o sÃ£o feitos via PIX: devolvemos apenas em forma de saldo no prÃ³prio bot.
âŒ Respeito Ã© essencial: ofensas ou postura inadequada no atendimento podem levar ao banimento e perda do saldo disponÃ­vel.

â° PRAZOS E RESPONSABILIDADES
A CONTA DEU PROBLEMA? NÃƒO ESTOU NO HORÃRIO DE ATENDIMENTO OS DIAS VÃƒO SER ADICIONADOSâ°

âœ… Ao prosseguir, vocÃª confirma que leu e aceita todas as regras acima. âœ…
"""


# OBRIGATORIEDADE DE CANAL/GRUPO
REQUIRED_GROUP_ID = -1002573223312
JOIN_GROUP_LINK = "https://t.me/ramonstorebottt"
MINIAPP_URL = "https://vendasdoramon.squareweb.app/"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')
MINIAPP_CATALOG_FILE = os.path.join(BASE_DIR, 'miniapp', 'catalog.json')
MINIAPP_SERVICE_IMAGES_DIR = os.path.join(BASE_DIR, 'miniapp', 'assets', 'service-images')
MINIAPP_AUTO_ICONS_DIR = os.path.join(MINIAPP_SERVICE_IMAGES_DIR, 'auto-icons')

SALES_GROUP_ID = -1002573223312
RESERVE_VERIFICATION_FILE = 'database/reserve_verified.json'
STREAMING_CUSTOM_EMOJI_IDS = [
    "4958633635512058775", "4986012398461649574", "4961180134506758889", "4985813751929242386",
    "4985515049838707600", "4958467583486460654", "4960802091485364850", "4958664490557112996",
    "4985753360394093436", "4958980582970229374", "4958554243041592144", "4988265954916958701",
    "4958804296037565428", "4986022148037411275", "4960853356215009939", "4985837348479566586",
    "4985962778704478831", "4985975637836563078", "4987988495734670151", "4985728793181160241",
    "4959010488827511510", "4958806499355787828", "4985515767098245768", "4958651631425028870",
    "4961018652326363924", "4961092130626863749", "4985855211248550547", "4959024657924620833",
    "4958942551034823207", "4985789541198594578", "4958621463574741708", "4958988936681620024",
    "4986044688025781087", "4961276870055166788", "4985527500948898533", "4958625341930209797",
    "4985895532401525692", "4960853077042135785", "4958754525956539026", "4985938215786513021",
    "4958609227212915351", "4985540952786469504", "4958941520242672323", "4958554874401784589",
    "4985722320665444957", "4985767645455319960", "4985848077307872263", "4960881741653869353",
    "4958606585808028640", "4958555540121715996", "4985619816975958694", "4985856667242464043",
    "4961198572801360596", "4961167524482777676", "4958554264516428555", "4985863131168245587",
    "4985766679087677981", "4958909307987952352", "4960774754018526158", "4958602853481447952",
    "4958518148136436370", "4985489542027936396", "4985725262718042690", "4985497290148938384",
    "4958518693597283075", "4986029393647239705", "4958915247927722993", "4986012952512430877",
    "4958783181978338042", "4958963029438890549", "4961021070392951429", "4961161137866408822",
    "4985700038375113098", "4985982767482274583", "4986030703612264985", "4985701202311250420",
    "4985673177649644111", "4985892989780886133", "4985925506978284297", "4988101934410892061",
    "4986034139586102139", "4985999144192574149", "4985615324440167276", "4985553451141300945",
    "4985826413492830719", "4987889548278104793", "4985857393091937162", "4985749430499017290",
    "4985789536903627323", "4985808293025809054", "4985699170791720094", "4985626074743308991",
    "4985867619409068909", "4986034740881523519", "4985862229225112539", "4958646649262965468",
]
DEFAULT_STREAMING_CUSTOM_EMOJI_IDS = STREAMING_CUSTOM_EMOJI_IDS[:]

def load_service_emoji_ids_from_settings():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        ids = data.get("service_emoji_ids", [])
        if isinstance(ids, list):
            ids = [
                str(emoji_id).strip()
                for emoji_id in ids
                if re.fullmatch(r'\d+', str(emoji_id).strip())
            ]
        return ids or DEFAULT_STREAMING_CUSTOM_EMOJI_IDS[:]
    except Exception:
        return DEFAULT_STREAMING_CUSTOM_EMOJI_IDS[:]

STREAMING_CUSTOM_EMOJI_IDS = load_service_emoji_ids_from_settings()

USER_DATA_DIR = 'database/users'

def load_user_data(user_id):
    user_file = os.path.join(USER_DATA_DIR, f'{user_id}.json')
    if os.path.exists(user_file):
        with open(user_file, 'r') as f:
            return json.load(f)
    return None

def save_user_data(user_id, user_data):
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
    
    user_file = os.path.join(USER_DATA_DIR, f'{user_id}.json')
    with open(user_file, 'w') as f:
        json.dump(user_data, f)

def get_sales_notification_chat_id():
    try:
        return api.Notificacoes.id_grupo()
    except Exception:
        return SALES_GROUP_ID

def set_sales_notification_chat_id(chat_id):
    api.Notificacoes.trocar_id_grupo(int(chat_id))

# Estado para upload de Ã­cones de serviÃ§os
pending_icon_upload = {}
pending_miniapp_image = {}

def _pending_keys(message_or_call):
    chat_id = None
    user_id = None
    if hasattr(message_or_call, 'message'):
        chat_id = getattr(message_or_call.message.chat, 'id', None)
        user_id = getattr(message_or_call.from_user, 'id', None)
    else:
        chat_id = getattr(getattr(message_or_call, 'chat', None), 'id', None)
        user_id = getattr(getattr(message_or_call, 'from_user', None), 'id', None)
    return [str(value) for value in (user_id, chat_id) if value is not None]

def _set_pending_miniapp_image(message_or_call, state):
    for key in _pending_keys(message_or_call):
        pending_miniapp_image[key] = dict(state)

def _get_pending_miniapp_image(message_or_call, pop=False):
    keys = _pending_keys(message_or_call)
    state = None
    for key in keys:
        if key in pending_miniapp_image:
            state = pending_miniapp_image[key]
            break
    if pop and state is not None:
        for key in keys:
            pending_miniapp_image.pop(key, None)
    return state
# Estado para ediÃ§Ã£o de textos (arquivo -> aguardando novo conteÃ©do)
pending_text_edit = {}
pending_button_edit = {}
pending_icon_remove = {}
pending_icon_rename = {}
# Estado para configurar emoji premium por nome de serviÃ§o
pending_service_emoji_name = {}
pending_service_emoji_remove = {}
# Estado para ediÃ§Ã£o de descriÃ§Ãµes personalizadas
pending_description_edit = {}
# Estado para adicionar quantidade ao carrinho
pending_carrinho_qtd = {}
pending_duplicate_logins = {}
pending_vip_level_edit = {}
# Estado para adicionar notificaÃ§Ã£o de reabastecimento
pending_notif_reabast = {}
# Compras aguardando aceite dos termos antes de descontar saldo/entregar
pending_terms_purchase = {}

# ═══════════════════════════════════════════════════════════════════════════
# Sistema de Follow-up: Envia mensagem após X minutos se usuário não comprou
# ═══════════════════════════════════════════════════════════════════════════
followup_timers = {}  # {user_id: Timer}
followup_delay = 300  # 5 minutos (300 segundos)

def agendar_followup(user_id):
    """Agenda mensagem de follow-up para ser enviada após X minutos"""
    cancelar_followup(user_id)  # Cancela timer anterior se existir
    
    timer = Timer(followup_delay, enviar_mensagem_followup, args=[user_id])
    timer.daemon = True
    timer.start()
    followup_timers[user_id] = timer

def cancelar_followup(user_id):
    """Cancela o timer de follow-up se existir"""
    if user_id in followup_timers:
        followup_timers[user_id].cancel()
        del followup_timers[user_id]

def enviar_mensagem_followup(user_id):
    """Envia mensagem de follow-up se usuário ainda não fez compra"""
    try:
        # Verifica se o usuário fez alguma compra
        user_data = database.load_user_data(user_id)
        if not user_data:
            return
        
        total_compras = user_data.get('total_compras', 0)
        if total_compras > 0:
            # Usuário já comprou, não envia mensagem
            return
        
        # Monta a mensagem
        texto = (
            "👋 Olá! Vi que você ainda não realizou nenhuma compra.\n\n"
            "Posso te ajudar? Escolha uma das opções abaixo 👇\n\n"
            "🔔 Para receber novidades e lançamentos, use: /alertas"
        )
        
        # Monta o teclado inline
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton('🎧 Suporte ↗', url='https://t.me/RamonSuporteV'),
            InlineKeyboardButton('🛒 Comprar Agora', callback_data='servicos')
        )
        markup.row(
            InlineKeyboardButton('🛒 Carrinho', callback_data='ver_carrinho'),
            InlineKeyboardButton('👀 Termos', callback_data='termos_uso')
        )
        
        bot.send_message(user_id, texto, parse_mode='HTML', reply_markup=markup)
        
        # Remove do dicionário após enviar
        if user_id in followup_timers:
            del followup_timers[user_id]
            
    except Exception as e:
        print(f"[FOLLOWUP] Erro ao enviar para {user_id}: {e}")
        if user_id in followup_timers:
            del followup_timers[user_id]

# DiretÃ©rio onde os Ã­cones serÃ©o salvos
ICONS_DIR = 'icons'
if not os.path.exists(ICONS_DIR):
    os.makedirs(ICONS_DIR, exist_ok=True)

def _normalize_key(s: str) -> str:
    """
    Normaliza uma string para facilitar a correspondÃ©ncia:
    - minÃ©sculas
    - remove espaÃ©os
    - remove caracteres nÃ£o alfanumÃ©ricos
    """
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

def _find_icon_for_service(servico: str):
    """Procura um arquivo de Ã­cone dentro de icons/ que combine com o nome do serviÃ§o.
    CritÃ©rio: nome base do arquivo contido no nome do serviÃ§o (normalizados) ou vice-versa.
    Retorna caminho absoluto/relativo do arquivo se achar, senÃ£o None.
    """
    if not os.path.isdir(ICONS_DIR):
        return None
    key = _normalize_key(servico)
    exts = ['.jpg', '.jpeg', '.png', '.webp']
    try:
        for fname in os.listdir(ICONS_DIR):
            base, ext = os.path.splitext(fname)
            if ext.lower() not in exts:
                continue
            bkey = _normalize_key(base)
            if not bkey:
                continue
            if bkey in key or key in bkey:
                return os.path.join(ICONS_DIR, fname)
    except Exception:
        pass
    return None

# Handlers de /icone_upload movidos para depois da inicializaÃ§Ã£o do bot

def _build_personal_mention(user_id: int) -> str:
    # Busca o nome direto no Telegram, SEM usar o JSON
    try:
        chat = bot.get_chat(user_id)
        parts = [p for p in [getattr(chat, "first_name", None), getattr(chat, "last_name", None)] if p]
        display = " ".join(parts) if parts else (getattr(chat, "username", None) or "amigo")
    except Exception:
        display = "amigo"

    display = html.escape(str(display))
    return f'<a href="tg://user?id={user_id}">{display}</a>'

def streaming_emoji(index: int, fallback: str = None) -> str:
    if fallback is None:
        fallback = chr(0x1F4FA)
    emoji_id = service_emoji_id_at(index)
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{html.escape(str(emoji_id))}">{html.escape(str(fallback))}</tg-emoji>'

def custom_emoji(emoji_id: str, fallback: str) -> str:
    emoji_id = str(emoji_id).strip()
    if not re.fullmatch(r'\d+', emoji_id):
        return fallback
    return f'<tg-emoji emoji-id="{html.escape(emoji_id)}">{html.escape(str(fallback))}</tg-emoji>'

def strip_tg_emoji_tags(text: str) -> str:
    return re.sub(
        r'<tg-emoji\s+emoji-id=["\'][^"\']+["\']\s*>(.*?)</tg-emoji>',
        lambda m: m.group(1),
        text or '',
        flags=re.IGNORECASE | re.DOTALL
    )

def html_to_plain_text(text: str) -> str:
    clean = strip_tg_emoji_tags(text)
    clean = re.sub(r'<br\s*/?>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'</(?:p|blockquote)\s*>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    return html.unescape(clean)

def service_emoji_id_at(index: int):
    emoji_ids = STREAMING_CUSTOM_EMOJI_IDS or DEFAULT_STREAMING_CUSTOM_EMOJI_IDS
    if not emoji_ids:
        return None
    try:
        return emoji_ids[int(index) % len(emoji_ids)]
    except (TypeError, ValueError, IndexError):
        return None

def reserve_bot_url():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("bot_reserva_url", "https://t.me/SEU_BOT_RESERVA")
    except Exception:
        return "https://t.me/SEU_BOT_RESERVA"

def reserve_group_url():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("grupo_reserva_url", JOIN_GROUP_LINK)
    except Exception:
        return JOIN_GROUP_LINK

def reserve_group_id():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return int(data.get("grupo_reserva_id", REQUIRED_GROUP_ID))
    except Exception:
        return REQUIRED_GROUP_ID

def reserve_verification_enabled():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("bot_reserva_verificacao", "on") == "on"
    except Exception:
        return True

def set_reserve_bot_url(url: str):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["bot_reserva_url"] = str(url).strip()
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def set_reserve_group_url(url: str):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["grupo_reserva_url"] = str(url).strip()
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def set_reserve_group_id(group_id: int):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["grupo_reserva_id"] = int(group_id)
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def reserve_group_username():
    url = reserve_group_url().strip()
    if url.startswith('@'):
        return url
    match = re.search(r'(?:t\.me|telegram\.me)/([^/?\s]+)', url, re.IGNORECASE)
    if not match:
        return None
    username = match.group(1).strip()
    if not username or username in ('+', 'joinchat') or username.startswith('+'):
        return None
    return f'@{username}'

def service_emoji_pack_link():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("service_emoji_pack_link", "")
    except Exception:
        return ""

def service_emoji_count():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        ids = data.get("service_emoji_ids", [])
        return len(ids) if isinstance(ids, list) and ids else len(STREAMING_CUSTOM_EMOJI_IDS)
    except Exception:
        return len(STREAMING_CUSTOM_EMOJI_IDS)

def parse_emoji_pack_name(text: str):
    value = str(text).strip()
    value = value.split('?', 1)[0].rstrip('/')
    match = re.search(r'(?:t\.me|telegram\.me)/(?:addemoji|addstickers)/([^/\s]+)', value, re.IGNORECASE)
    if match:
        return match.group(1)
    if re.fullmatch(r'[A-Za-z0-9_]+', value):
        return value
    return None

def save_service_emoji_pack(link: str, pack_name: str, emoji_ids):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["service_emoji_pack_link"] = str(link).strip()
    data["service_emoji_pack_name"] = str(pack_name).strip()
    data["service_emoji_ids"] = [str(emoji_id) for emoji_id in emoji_ids]
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_service_emoji_pack(link: str):
    pack_name = parse_emoji_pack_name(link)
    if not pack_name:
        raise ValueError("Envie um link vÃ¡lido do pacote. Exemplo: https://t.me/addemoji/seu_pacote")

    sticker_set = bot.get_sticker_set(pack_name)
    emoji_ids = []
    for sticker in getattr(sticker_set, 'stickers', []) or []:
        custom_emoji_id = getattr(sticker, 'custom_emoji_id', None)
        if custom_emoji_id and re.fullmatch(r'\d+', str(custom_emoji_id).strip()):
            emoji_ids.append(str(custom_emoji_id).strip())

    if not emoji_ids:
        raise ValueError("NÃ£o encontrei emojis premium nesse pacote.")

    save_service_emoji_pack(link, pack_name, emoji_ids)
    global STREAMING_CUSTOM_EMOJI_IDS
    STREAMING_CUSTOM_EMOJI_IDS = emoji_ids
    return pack_name, len(emoji_ids)

def toggle_reserve_verification():
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["bot_reserva_verificacao"] = "off" if data.get("bot_reserva_verificacao", "on") == "on" else "on"
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return data["bot_reserva_verificacao"]

def clear_reserve_verified_users():
    os.makedirs(os.path.dirname(RESERVE_VERIFICATION_FILE), exist_ok=True)
    with open(RESERVE_VERIFICATION_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": []}, f, indent=4)

def _load_reserve_verified():
    try:
        if not os.path.exists(RESERVE_VERIFICATION_FILE):
            return {"users": []}
        with open(RESERVE_VERIFICATION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"users": []}

def is_reserve_verified(user_id: int) -> bool:
    data = _load_reserve_verified()
    return str(user_id) in {str(uid) for uid in data.get("users", [])}

def mark_reserve_verified(user_id: int):
    data = _load_reserve_verified()
    users = {str(uid) for uid in data.get("users", [])}
    users.add(str(user_id))
    os.makedirs(os.path.dirname(RESERVE_VERIFICATION_FILE), exist_ok=True)
    with open(RESERVE_VERIFICATION_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": sorted(users)}, f, indent=4)

def is_user_in_reserve_group(user_id: int) -> bool:
    chat_refs = [reserve_group_id()]
    username = reserve_group_username()
    if username:
        chat_refs.append(username)

    last_error = None
    for chat_ref in chat_refs:
        try:
            member_info = bot.get_chat_member(chat_ref, user_id)
            return getattr(member_info, 'status', 'left') not in ['left', 'kicked']
        except ApiTelegramException as error:
            last_error = error

    if last_error:
        raise last_error
    return False

def reserve_access_ok(user_id: int) -> bool:
    if not reserve_verification_enabled():
        return True
    try:
        in_reserve_group = is_user_in_reserve_group(user_id)
    except Exception as error:
        print(f"[RESERVA] Falha ao conferir usuÃ¡rio {user_id} no grupo {reserve_group_id()}: {error}")
        return False
    return is_reserve_verified(user_id) and in_reserve_group

def ensure_reserve_access(user_id: int, chat_id: int) -> bool:
    if reserve_access_ok(user_id):
        return True
    send_reserve_verification(chat_id)
    return False

def is_owner_or_admin(user_id: int) -> bool:
    try:
        return api.Admin.verificar_admin(user_id) or int(user_id) == int(api.CredentialsChange.id_dono())
    except Exception:
        return False

def reserve_verification_text():
    shield = custom_emoji("5447644880824181073", "âš ï¸")
    check = custom_emoji("5350486389806868244", "âœ…")
    globe = custom_emoji("5447410659077661506", "ðŸŒ")
    return (
        f"{shield} <b>VerificaÃ§Ã£o de identidade</b>\n\n"
        "Para liberar seu acesso, entre no grupo reserva e dÃª /start no nosso bot reserva.\n"
        "Isso ajuda a proteger sua conta caso este bot principal saia do ar.\n\n"
        "Depois de concluir os dois passos, volte aqui e clique em "
        f"<b>JÃ¡ verifiquei, continuar</b>.\n\n"
        f"{globe} <i>Sua loja fica mais protegida e seus dados continuam salvos.</i> {check}"
    )

def send_reserve_verification(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('👥 Entrar no Grupo Reserva', url=reserve_group_url()))
    markup.row(InlineKeyboardButton('🛡️ Iniciar Bot Reserva', url=reserve_bot_url()))
    markup.row(InlineKeyboardButton('✅ Já verifiquei, continuar', callback_data='reserve_verified_continue'))
    try:
        bot.send_message(chat_id, reserve_verification_text(), parse_mode='HTML', reply_markup=markup)
    except ApiTelegramException as error:
        error_text = str(error).lower()
        if 'bot was blocked by the user' in error_text or 'user is deactivated' in error_text or 'chat not found' in error_text:
            print(f'[RESERVA] Usuário {chat_id} não pode receber mensagens ({error}).', flush=True)
            return False
        raise
    return True

def set_streaming_button_icon(button, index: int):
    emoji_id = service_emoji_id_at(index)
    if emoji_id:
        button.icon_custom_emoji_id = emoji_id
    return button

MENU_PREMIUM_EMOJI_IDS = {
    "catalogo": "5229064374403998351",
    "pix": "5456140674028019486",
    "perfil": "5352825278672412291",
    "suporte": "5443038326535759644",
    "termos": "5440660757194744323",
    "ranking": "5370784581341422520",
    "jogos": "5350710934992069206",
    "filmes": "5350693961281314631",
    "estoque": "5231200819986047254",
    "telegram": "5447410659077661506",
    "whatsapp": "5467538555158943525",
    "alugar": "5350396951407895212",
    "carrinho": "5350486389806868244",
    "notificar": "5447644880824181073",
    "pesquisar": "5210956306952758910",
}

def set_menu_premium_icon(button, key: str):
    emoji_id = MENU_PREMIUM_EMOJI_IDS.get(key)
    if emoji_id:
        button.icon_custom_emoji_id = emoji_id
    return button

SERVICE_EMOJI_INDEX_BY_KEYWORD = [
    ("hbo max", 0),
    ("hbomax", 0),
    ("prime video", 2),
    ("prime", 2),
    ("netflix", 5),
    ("telecine play", 9),
    ("telecine", 10),
    ("globo play", 12),
    ("globoplay", 12),
    ("globo", 12),
    ("premiere", 15),
    ("vivo play", 16),
    ("oi play", 17),
    ("claro video", 18),
    ("claro tv", 19),
    ("claro", 19),
    ("disney", 21),
    ("dazn", 24),
    ("star plus", 25),
    ("star+", 25),
    ("starz", 29),
    ("crunchyroll", 30),
    ("crunchyrool", 30),
    ("looke", 33),
    ("paramount", 35),
    ("hulu", 38),
    ("spotify", 42),
    ("plex", 46),
    ("discovery", 49),
    ("oldflix", 52),
    ("youtube", 60),
    ("you tube", 60),
    ("twitch", 64),
    ("justwatch", 66),
    ("just watch", 66),
    ("watch", 70),
    ("tunein", 73),
    ("apple tv", 76),
    ("airplay", 74),
    ("deezer", 81),
    ("dgo", 82),
    ("directv go", 82),
    ("directv", 82),
    ("espn", 83),
    ("filmbox", 84),
    ("kodi", 85),
    ("mflix", 89),
    ("red bull", 91),
    ("tidal", 92),
    ("vix", 94),
]

def load_service_emoji_map_from_settings():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        emoji_map = data.get("service_emoji_map", {})
        if not isinstance(emoji_map, dict):
            return {}
        return {
            _normalize_key(key): str(value).strip()
            for key, value in emoji_map.items()
            if _normalize_key(str(key)) and re.fullmatch(r'\d+', str(value).strip())
        }
    except Exception:
        return {}

def load_raw_service_emoji_map_from_settings():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        emoji_map = data.get("service_emoji_map", {})
        if not isinstance(emoji_map, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in emoji_map.items()
            if str(key).strip() and re.fullmatch(r'\d+', str(value).strip())
        }
    except Exception:
        return {}

def save_service_emoji_map(emoji_map):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["service_emoji_map"] = {
        str(key).strip(): str(value).strip()
        for key, value in emoji_map.items()
        if str(key).strip() and re.fullmatch(r'\d+', str(value).strip())
    }
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def service_emoji_map_count():
    return len(load_raw_service_emoji_map_from_settings())

def extract_custom_emoji_id_from_message(message):
    entities = []
    entities.extend(getattr(message, 'entities', None) or [])
    entities.extend(getattr(message, 'caption_entities', None) or [])
    for entity in entities:
        if getattr(entity, 'type', None) != 'custom_emoji':
            continue
        custom_emoji_id = getattr(entity, 'custom_emoji_id', None)
        if custom_emoji_id and re.fullmatch(r'\d+', str(custom_emoji_id).strip()):
            return str(custom_emoji_id).strip()
    text = (getattr(message, 'text', None) or getattr(message, 'caption', None) or '').strip()
    match = re.search(r'emoji-id=["\'](\d+)["\']', text)
    if match:
        return match.group(1)
    if re.fullmatch(r'\d{8,}', text):
        return text
    return None

def streaming_emoji_id_for_service(service_name: str):
    normalized = _normalize_key(service_name)
    emoji_map = load_service_emoji_map_from_settings()
    for key, emoji_id in sorted(emoji_map.items(), key=lambda item: len(item[0]), reverse=True):
        if key in normalized or normalized in key:
            return emoji_id
    for keyword, index in SERVICE_EMOJI_INDEX_BY_KEYWORD:
        if _normalize_key(keyword) in normalized:
            return service_emoji_id_at(index)
    return None

def set_service_button_icon(button, service_name: str):
    emoji_id = streaming_emoji_id_for_service(service_name)
    if emoji_id:
        button.icon_custom_emoji_id = emoji_id
    return button

def load_service_button_settings():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        settings = data.get('service_button_settings', {})
        return settings if isinstance(settings, dict) else {}
    except Exception:
        return {}

def save_service_button_settings(settings):
    with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['service_button_settings'] = settings
    with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def service_button_setting(service_name: str):
    normalized = _normalize_key(service_name)
    for name, setting in load_service_button_settings().items():
        if _normalize_key(name) == normalized and isinstance(setting, dict):
            return setting
    return {}

def configure_service_button(button, service_name: str):
    set_service_button_icon(button, service_name)
    color = service_button_setting(service_name).get('color')
    style = {
        'verde': 'success',
        'azul': 'primary',
        'vermelho': 'danger',
    }.get(color)
    if style:
        button.style = style
    return button

def set_category_button_icon(button, category: str):
    category_indexes = {
        'conta': 5,
        'tela': 12,
        'outros': 2,
    }
    emoji_id = service_emoji_id_at(category_indexes.get(category, 0))
    if emoji_id:
        button.icon_custom_emoji_id = emoji_id
    return button

def clean_service_button_name(service_name: str) -> str:
    cleaned = re.sub(r'^[^\wÀ-ÿ]+', '', str(service_name)).strip()
    return cleaned or str(service_name).strip()

def service_button_text(service_name: str, value) -> str:
    setting = service_button_setting(service_name)
    template = str(setting.get('text') or '{nome} R${valor}')
    try:
        return template.format(
            nome=clean_service_button_name(service_name),
            valor=f'{float(value):.2f}'
        )
    except (KeyError, ValueError):
        return f'{clean_service_button_name(service_name)} R${float(value):.2f}'

def parse_valor_monetario(value) -> float:
    texto = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', texto):
        raise ValueError('valor monetario invalido')
    valor = float(texto)
    if valor <= 0:
        raise ValueError('o valor deve ser maior que zero')
    return round(valor, 2)

BUTTON_OVERRIDES_PATH = os.path.join('settings', 'button_overrides.json')

def load_button_overrides():
    try:
        with open(BUTTON_OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_button_overrides(data):
    os.makedirs(os.path.dirname(BUTTON_OVERRIDES_PATH), exist_ok=True)
    with open(BUTTON_OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def button_override_key(filename_or_name: str) -> str:
    base = os.path.basename(str(filename_or_name))
    return base[:-4] if base.lower().endswith('.txt') else base

def get_button_override(filename_or_name: str):
    return load_button_overrides().get(button_override_key(filename_or_name))

def set_button_override(filename_or_name: str, content: str):
    data = load_button_overrides()
    data[button_override_key(filename_or_name)] = content
    save_button_overrides(data)

def migrate_colored_button_files_to_overrides():
    if os.path.exists(BUTTON_OVERRIDES_PATH):
        return
    if not os.path.isdir('botoes'):
        return
    overrides = {}
    for filename in os.listdir('botoes'):
        if not filename.lower().endswith('.txt'):
            continue
        path = os.path.join('botoes', filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
        except Exception:
            continue
        if _extract_button_color(content):
            overrides[button_override_key(filename)] = content
    if overrides:
        save_button_overrides(overrides)

def botao_personalizado(nome_arquivo: str, padrao: str) -> str:
    os.makedirs('botoes', exist_ok=True)
    path = os.path.join('botoes', f'{nome_arquivo}.txt')
    try:
        override = get_button_override(nome_arquivo)
        if isinstance(override, str) and override.strip():
            return override.strip()
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(padrao)
            return padrao
        with open(path, 'r', encoding='utf-8') as f:
            texto = f.read().strip()
        return texto or padrao
    except Exception:
        return padrao

def decorate_start_text(message):
    eye = custom_emoji("5210956306952758910", chr(0x1F440))
    bag = custom_emoji("5229064374403998351", chr(0x1F6CD))
    warning = custom_emoji("5447644880824181073", chr(0x26A0) + chr(0xFE0F))
    check = custom_emoji("5350486389806868244", chr(0x2705))
    star = custom_emoji("5370784581341422520", chr(0x2B50))
    globe = custom_emoji("5447410659077661506", chr(0x1F310))
    base_text = api.Textos.start(message)
    return (
        f"{star} <b>RAMON STORE</b> {star}\n"
        f"{bag} <b>Acessos premium disponÃ­veis</b> {eye}\n\n"
        f"{base_text}\n\n"
        f"{warning} <i>Confira o catÃ¡logo e escolha seu produto abaixo.</i>\n"
        f"{globe} <b>Loja protegida com bot reserva</b> {check}"
    )



MOJIBAKE_REPLACEMENTS = {
    'â€¢': '•',
    'âœ…': '✅',
    'âŒ': '❌',
    'âš™ï¸': '⚙️',
    'âš™': '⚙',
    'âš ï¸': '⚠️',
    'âšª': '⚪',
    'âš½': '⚽',
    'âœï¸': '✏️',
    'âž•': '➕',
    'â­': '⭐',
    'â°': '⏰',
    'ðŸ¤–': '🤖',
    'ðŸ“…': '📅',
    'ðŸ“‹': '📋',
    'ðŸ“Š': '📊',
    'ðŸ“¦': '📦',
    'ðŸ“¢': '📢',
    'ðŸ“': '📝',
    'ðŸ“¸': '📸',
    'ðŸ‘¥': '👥',
    'ðŸ‘¨â€ðŸ’¼': '👨‍💼',
    'ðŸ’°': '💰',
    'ðŸ’¡': '💡',
    'ðŸ’³': '💳',
    'ðŸ’¾': '💾',
    'ðŸ”': '🔐',
    'ðŸ”‘': '🔑',
    'ðŸ”˜': '🔘',
    'ðŸ”™': '🔙',
    'ðŸ”µ': '🔵',
    'ðŸ”´': '🔴',
    'ðŸ•': '🕐',
    'ðŸ–¼ï¸': '🖼️',
    'ðŸ—‘': '🗑',
    'ðŸ˜€': '😀',
    'ðŸŸ¢': '🟢',
    'ðŸ¤': '🤝',
    'ðŸŒ': '🌐',
    'ðŸŽ¬': '🎬',
    'ðŸ›': '🛍',
    'ðŸ›¡ï¸': '🛡️',
    'ðŸš«': '🚫',
}

def _mojibake_score(text: str) -> int:
    return sum(text.count(marker) for marker in ('Ã', 'Â', 'â', 'ðŸ', '�'))

def _decode_mojibake_once(text: str) -> str:
    best = text
    best_score = _mojibake_score(text)
    for encoding in ('cp1252', 'latin1'):
        try:
            candidate = text.encode(encoding).decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if '�' in candidate:
            continue
        score = _mojibake_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return best

def fix_mojibake_text(text):
    if not isinstance(text, str):
        return text

    fixed = text
    for _ in range(2):
        decoded = _decode_mojibake_once(fixed)
        if decoded == fixed:
            break
        fixed = decoded

    # Emojis e acentos corretos podem impedir a conversao da frase inteira.
    # Nesse caso, recupera apenas as palavras que ainda estao corrompidas.
    fixed = re.sub(
        r'\S+',
        lambda match: _decode_mojibake_once(match.group(0)),
        fixed
    )

    for broken, replacement in MOJIBAKE_REPLACEMENTS.items():
        fixed = fixed.replace(broken, replacement)
    return fixed

print("Codigo iniciado...")

sdk = mercadopago.SDK(api.CredentialsChange.InfoPix.token_mp())
bot = telebot.TeleBot(api.CredentialsChange.token_bot())

_original_bot_send_message = bot.send_message
_original_bot_send_photo = bot.send_photo
_original_bot_send_video = bot.send_video
_original_bot_send_animation = bot.send_animation
_original_bot_send_document = bot.send_document
_original_bot_edit_message_text = bot.edit_message_text
_original_bot_edit_message_caption = bot.edit_message_caption
_original_bot_answer_callback_query = bot.answer_callback_query

def _sanitize_text_kwargs(kwargs, *names):
    sanitized = dict(kwargs)
    for name in names:
        if name in sanitized:
            sanitized[name] = fix_mojibake_text(sanitized[name])
    return sanitized

def _ignore_message_not_modified(error):
    return "message is not modified" in str(error).lower()

def _ignore_expired_callback_query(error):
    error_text = str(error).lower()
    return (
        "query is too old" in error_text
        or "response timeout expired" in error_text
        or "query id is invalid" in error_text
    )

def _safe_bot_edit_message_text(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'text')
    if args:
        args = (fix_mojibake_text(args[0]), *args[1:])
    try:
        return _original_bot_edit_message_text(*args, **kwargs)
    except ApiTelegramException as error:
        if _ignore_message_not_modified(error):
            return None
        raise

def _safe_bot_edit_message_caption(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'caption')
    if args:
        args = (fix_mojibake_text(args[0]), *args[1:])
    try:
        return _original_bot_edit_message_caption(*args, **kwargs)
    except ApiTelegramException as error:
        if _ignore_message_not_modified(error):
            return None
        raise

def _safe_bot_send_message(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'text')
    if len(args) >= 2:
        args = (args[0], fix_mojibake_text(args[1]), *args[2:])
    return _original_bot_send_message(*args, **kwargs)

def _safe_bot_send_photo(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'caption')
    return _original_bot_send_photo(*args, **kwargs)

def _safe_bot_send_video(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'caption')
    return _original_bot_send_video(*args, **kwargs)

def _safe_bot_send_animation(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'caption')
    return _original_bot_send_animation(*args, **kwargs)

def _safe_bot_send_document(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'caption')
    return _original_bot_send_document(*args, **kwargs)

def _safe_bot_answer_callback_query(*args, **kwargs):
    kwargs = _sanitize_text_kwargs(kwargs, 'text')
    if len(args) >= 2:
        args = (args[0], fix_mojibake_text(args[1]), *args[2:])
    try:
        return _original_bot_answer_callback_query(*args, **kwargs)
    except ApiTelegramException as error:
        if _ignore_expired_callback_query(error):
            return None
        raise

def _is_entity_text_invalid(error):
    error_text = str(error).lower()
    return (
        'entity_text_invalid' in error_text
        or "can't parse entities" in error_text
        or 'entity text invalid' in error_text
    )

def send_html_or_plain(chat_id, text, reply_markup=None, **kwargs):
    try:
        return bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            **kwargs
        )
    except ApiTelegramException as error:
        if _is_entity_text_invalid(error):
            return bot.send_message(
                chat_id=chat_id,
                text=html_to_plain_text(text),
                reply_markup=reply_markup,
                **kwargs
            )
        raise

def edit_html_or_plain(chat_id, message_id, text, reply_markup=None, **kwargs):
    try:
        return bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            **kwargs
        )
    except ApiTelegramException as error:
        if _is_entity_text_invalid(error):
            return bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=html_to_plain_text(text),
                reply_markup=reply_markup,
                **kwargs
            )
        raise

bot.send_message = _safe_bot_send_message
bot.send_photo = _safe_bot_send_photo
bot.send_video = _safe_bot_send_video
bot.send_animation = _safe_bot_send_animation
bot.send_document = _safe_bot_send_document
bot.edit_message_text = _safe_bot_edit_message_text
bot.edit_message_caption = _safe_bot_edit_message_caption
bot.answer_callback_query = _safe_bot_answer_callback_query

def notificar_versao_atual_aos_admins():
    try:
        commit_result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10
        )
        if commit_result.returncode != 0:
            return

        commit = commit_result.stdout.strip()
        marcador = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.last_admin_update_commit')
        if os.path.exists(marcador):
            with open(marcador, 'r', encoding='utf-8') as arquivo:
                if arquivo.read().strip() == commit:
                    return

        subject_result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%s'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10
        )
        assunto = subject_result.stdout.strip() if subject_result.returncode == 0 else 'Sem detalhes'
        admin_ids = {int(api.CredentialsChange.id_dono())}
        admins_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'admins.json')
        if os.path.exists(admins_path):
            with open(admins_path, 'r', encoding='utf-8') as arquivo:
                admins = json.load(arquivo).get('admins', [])
            admin_ids.update(int(admin['id']) for admin in admins if admin.get('id'))
        texto = (
            '<b>Bot atualizado e iniciado com sucesso!</b>\n\n'
            f'<b>Versão:</b> <code>{commit[:7]}</code>\n'
            f'<b>Novidades:</b> {html.escape(assunto)}\n'
            f'<b>Horário:</b> {datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
        )

        enviado = False
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, texto, parse_mode='HTML')
                enviado = True
            except Exception as error:
                print(f'Falha ao avisar atualização ao admin {admin_id}: {error}', flush=True)

        if enviado:
            with open(marcador, 'w', encoding='utf-8') as arquivo:
                arquivo.write(commit)
    except Exception as error:
        print(f'Falha ao verificar aviso da versão atual: {error}', flush=True)

notificar_versao_atual_aos_admins()

def enviar_backup_automatico_aos_admins(backup_path):
    enviado = False
    try:
        admin_ids = {int(api.CredentialsChange.id_dono())}
        admins_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'admins.json')
        if os.path.exists(admins_path):
            with open(admins_path, 'r', encoding='utf-8') as arquivo:
                admins = json.load(arquivo).get('admins', [])
            admin_ids.update(int(admin['id']) for admin in admins if admin.get('id'))

        horario = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        for admin_id in admin_ids:
            try:
                with open(backup_path, 'rb') as arquivo:
                    bot.send_document(
                        admin_id,
                        arquivo,
                        caption=(
                            '<b>Backup automático dos dados importantes</b>\n\n'
                            f'<b>Data:</b> {horario}\n'
                            '<i>Guarde este arquivo em local seguro.</i>'
                        ),
                        parse_mode='HTML'
                    )
                    enviado = True
            except ApiTelegramException as error:
                error_text = str(error).lower()
                if 'bot was blocked by the user' in error_text or 'user is deactivated' in error_text or 'chat not found' in error_text:
                    print(f'[BACKUP] Admin {admin_id} não pode receber o backup; ignorando.', flush=True)
                else:
                    print(f'[BACKUP] Falha ao enviar para o admin {admin_id}: {error}', flush=True)
    finally:
        try:
            if backup_path and os.path.exists(backup_path):
                os.remove(backup_path)
                print(f'[BACKUP] Arquivo temporário removido: {backup_path}', flush=True)
        except OSError as error:
            print(f'[BACKUP] Falha ao remover arquivo temporário: {error}', flush=True)
    return enviado

backup_manager.auto_backup_callback = enviar_backup_automatico_aos_admins
try:
    total_contas_registradas = api.ControleLogins.inicializar_registro()
    print(f'[LOGIN] Histórico de duplicatas carregado: {total_contas_registradas} conta(s).', flush=True)
except Exception as error:
    print(f'[LOGIN] Falha ao inicializar histórico de duplicatas: {error}', flush=True)
if backup_manager.config.get('auto_backup_enabled', False):
    backup_manager.start_auto_backup()

try:
    bot.send_message(
        chat_id=api.CredentialsChange.id_dono(),
        text='ðŸ¤– <b>BOT INICIADO COM SUCESSO!</b> âœ…',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('âš™ï¸ PAINEL ADMIN', callback_data='voltar_paineladm')]]
        )
    )
except Exception as e:
    print(f"âš ï¸ NÃ£o foi possÃ­vel enviar mensagem de inicializaÃ§Ã£o: {e}")

def salvar_chat_notificacoes(message):
    chat = message.chat
    chat_id = chat.id
    chat_type = getattr(chat, 'type', 'desconhecido')
    chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id)

    if chat_type not in ('group', 'supergroup', 'channel'):
        bot.reply_to(message, "Use este comando dentro do grupo ou canal que receberÃ¡ as notificaÃ§Ãµes de compra.")
        return

    if chat_type != 'channel':
        is_admin = api.Admin.verificar_admin(message.from_user.id) or int(message.from_user.id) == int(api.CredentialsChange.id_dono())
        if not is_admin:
            bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
            return

    set_sales_notification_chat_id(chat_id)

    texto = (
        "âœ… <b>Destino das notificaÃ§Ãµes atualizado!</b>\n\n"
        f"â€¢ <b>Chat:</b> {html.escape(str(chat_title))}\n"
        f"â€¢ <b>ID:</b> <code>{chat_id}</code>\n\n"
        "As prÃ³ximas compras serÃ£o postadas aqui."
    )
    bot.send_message(chat_id, texto, parse_mode='HTML')

@bot.message_handler(commands=['noti'])
def cmd_noti(message):
    salvar_chat_notificacoes(message)

@bot.channel_post_handler(commands=['noti'])
def cmd_noti_channel(message):
    salvar_chat_notificacoes(message)

def salvar_grupo_reserva_atual(message):
    chat = message.chat
    chat_id = chat.id
    chat_type = getattr(chat, 'type', 'desconhecido')
    chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id)

    if chat_type not in ('group', 'supergroup'):
        bot.reply_to(message, "Use este comando dentro do grupo reserva.")
        return

    is_admin = api.Admin.verificar_admin(message.from_user.id) or int(message.from_user.id) == int(api.CredentialsChange.id_dono())
    if not is_admin:
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    set_reserve_group_id(chat_id)
    username = getattr(chat, 'username', None)
    if username:
        set_reserve_group_url(f"https://t.me/{username}")

    texto = (
        "âœ… <b>Grupo reserva atualizado!</b>\n\n"
        f"â€¢ <b>Grupo:</b> {html.escape(str(chat_title))}\n"
        f"â€¢ <b>ID correto:</b> <code>{chat_id}</code>\n\n"
        "Agora a verificaÃ§Ã£o de entrada vai usar este grupo."
    )
    bot.send_message(chat_id, texto, parse_mode='HTML')

@bot.message_handler(commands=['grupo_reserva', 'setgrupo_reserva'])
def cmd_grupo_reserva(message):
    salvar_grupo_reserva_atual(message)

# Comando admin para iniciar upload de Ã­cone: /icone_upload NOME
@bot.message_handler(commands=['icone_upload'])
def cmd_icone_upload(message):
    # Verifica se Ã© admin
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Use: /icone_upload NOME\nEnvie em seguida a FOTO ou DOCUMENTO da logo.")
        return
    nome = parts[1].strip()
    if not nome:
        bot.reply_to(message, "Use: /icone_upload NOME\nEnvie em seguida a FOTO ou DOCUMENTO da logo.")
        return

    pending_icon_upload[message.from_user.id] = nome
    bot.reply_to(message, f"OK! Envie a FOTO ou DOCUMENTO da logo para: {nome}")

@bot.message_handler(content_types=['photo', 'document'])
def receber_icone_upload(message):
    user_id = message.from_user.id
    if _get_pending_miniapp_image(message):
        salvar_upload_imagem_miniapp(message)
        return

    if user_id not in pending_icon_upload:
        return  # nÃ£o Ã© upload de Ã­cone esperado

    target_name = pending_icon_upload.pop(user_id)
    # Define nome do arquivo
    base_name = _normalize_key(target_name) or 'icon'

    file_info = None
    file_bytes = None
    file_ext = '.jpg'  # padrÃ©o para fotos

    try:
        if message.content_type == 'photo':
            photo = message.photo[-1]  # maior resoluÃ§Ã£o
            file_info = bot.get_file(photo.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            file_ext = '.jpg'
        elif message.content_type == 'document':
            doc = message.document
            file_info = bot.get_file(doc.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            # tenta manter a extensÃ£o original, se houver
            if doc.file_name and '.' in doc.file_name:
                _, ext = os.path.splitext(doc.file_name)
                if ext:
                    file_ext = ext.lower()
    except Exception as e:
        bot.reply_to(message, f"âœ… Falha ao baixar o arquivo: {e}")
        return

    try:
        # Salva arquivo
        path = os.path.join(ICONS_DIR, f"{base_name}{file_ext}")
        with open(path, 'wb') as f:
            f.write(file_bytes)
        bot.reply_to(message, f"âœ… Ã­cone salvo para '{target_name}'. Agora, quando exibir o serviÃ§o, a logo serÃ© mostrada.")
    except Exception as e:
        bot.reply_to(message, f"âœ… Erro ao salvar: {e}")

@bot.message_handler(commands=['icone_list'])
def cmd_icone_list(message):
    # Apenas admins/dono
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    if not os.path.isdir(ICONS_DIR):
        bot.reply_to(message, "â€¢ A pasta de Ã­cones ainda nÃ£o existe.")
        return

    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in os.listdir(ICONS_DIR) if os.path.splitext(f)[1].lower() in exts]
    if not files:
        bot.reply_to(message, "ðŸ“‹ Nenhum Ã­cone cadastrado em icons/.")
        return

    files.sort()
    lista = "\n".join(f"âœ… {f}" for f in files)
    bot.reply_to(message, f"â€¢ Ã­cones cadastrados ({len(files)}):\n\n{lista}")

@bot.message_handler(commands=['icone_remover'])
def cmd_icone_remover(message):
    # Apenas admins/dono
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Use: /icone_remover NOME\nEx: /icone_remover netflix")
        return

    target = parts[1].strip()
    key = _normalize_key(target)
    if not key:
        bot.reply_to(message, "âœ… Nome invÃ©lido para remoÃ§Ã£o.")
        return

    if not os.path.isdir(ICONS_DIR):
        bot.reply_to(message, "â€¢ A pasta de Ã­cones ainda nÃ£o existe.")
        return

    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    removidos = []
    for fname in list(os.listdir(ICONS_DIR)):
        base, ext = os.path.splitext(fname)
        if ext.lower() not in exts:
            continue
        bkey = _normalize_key(base)
        if not bkey:
            continue
        if bkey in key or key in bkey:
            try:
                os.remove(os.path.join(ICONS_DIR, fname))
                removidos.append(fname)
            except Exception:
                pass

    if removidos:
        lista = "\n".join(f"âœ… {f}" for f in removidos)
        bot.reply_to(message, f"âœ… Removidos {len(removidos)} Ã­cone(s):\n{lista}")
    else:
        bot.reply_to(message, "âš™ï¸ Nenhum Ã­cone correspondente encontrado para remover.")

@bot.message_handler(commands=['icone_renomear'])
def cmd_icone_renomear(message):
    # Apenas admins/dono
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Use: /icone_renomear ANTIGO NOVO\nEx: /icone_renomear hbomax max")
        return

    antigo_raw = parts[1].strip()
    novo_raw = parts[2].strip()
    old_key = _normalize_key(antigo_raw)
    new_base = _normalize_key(novo_raw)
    if not old_key or not new_base:
        bot.reply_to(message, "âœ… ParÃ©metros invÃ©lidos para renomear.")
        return

    if not os.path.isdir(ICONS_DIR):
        bot.reply_to(message, "â€¢ A pasta de Ã­cones ainda nÃ£o existe.")
        return

    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    renomes = []
    for fname in list(os.listdir(ICONS_DIR)):
        base, ext = os.path.splitext(fname)
        if ext.lower() not in exts:
            continue
        bkey = _normalize_key(base)
        if not bkey:
            continue
        if old_key in bkey or bkey in old_key:
            # Construir novo nome cuidando de conflitos
            candidate = f"{new_base}{ext.lower()}"
            target_path = os.path.join(ICONS_DIR, candidate)
            idx = 1
            while os.path.exists(target_path):
                candidate = f"{new_base}_{idx}{ext.lower()}"
                target_path = os.path.join(ICONS_DIR, candidate)
                idx += 1
            try:
                os.rename(os.path.join(ICONS_DIR, fname), target_path)
                renomes.append((fname, os.path.basename(target_path)))
            except Exception:
                pass

    if renomes:
        linhas = "\n".join(f"âœ… {a}  âœ…  {b}" for a, b in renomes)
        bot.reply_to(message, f"âš™ï¸ Renomeados {len(renomes)} arquivo(s):\n{linhas}")
    else:
        bot.reply_to(message, "âš™ï¸ Nenhum Ã­cone correspondente encontrado para renomear.")

@bot.message_handler(commands=['ajudaicon'])
def cmd_ajudaicon(message):
    # Apenas admins/dono
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "âš™ï¸ Os comandos de Ã­cones sÃ£o apenas para administradores.")
        return

    texto = (
        "<b>ðŸ“‹ Comandos de Ã­cones</b>\n\n"
        "âœ… <b>/icone_upload NOME</b> âœ… Inicia o fluxo para enviar uma logo para o serviÃ§o NOME.\n"
        "   Envie a imagem como FOTO ou DOCUMENTO em seguida.\n\n"
        "âœ… <b>/icone_list</b> âœ… Lista todos os Ã­cones cadastrados em <code>icons/</code>.\n\n"
        "âœ… <b>/icone_remover NOME</b> âœ… Remove Ã­cones cujo nome combine com NOME (normalizado).\n"
        "   Ex: <code>/icone_remover netflix</code>\n\n"
        "âœ… <b>/icone_renomear ANTIGO NOVO</b> âœ… Renomeia Ã­cones que combinem com ANTIGO\n"
        "   para o nome NOVO, preservando a extensÃ£o. Resolve conflitos com sufixos.\n"
        "   Ex: <code>/icone_renomear hbomax max</code>\n\n"
        "Obs.: O match usa normalizaÃ§Ã£o (minÃ©sculas, sem espaÃ©os e sem caracteres especiais)."
    )
    bot.reply_to(message, texto, parse_mode='HTML')

def ver_se_expirou():
 
    if api.Admin.verificar_vencimento() == True:
        bot.send_message(
            api.CredentialsChange.id_dono(),
            "OPSS, O PLANO DO SEU BOT VENCEU ELE ESTA INATIVO. RENOVE-O AGORA!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('âœ… RENOVAR AGORA', callback_data='renovar_bot')]]
            )
        )
        bot.send_message(
            chat_id=7240103075,
            text=f'OlÃ© chefe, o bot @{api.CredentialsChange.user_bot()} estÃ© vencido!'
        )

@bot.message_handler(commands=['cancelar'])
def handle_cancelar(message):
    if api.Admin.verificar_vencimento() == True:
        ver_se_expirou()
        return
    bot.clear_step_handler_by_chat_id(message.chat.id)
    # Limpar estados pendentes
    pending_text_edit.pop(message.chat.id, None)
    pending_button_edit.pop(message.chat.id, None)
    pending_description_edit.pop(message.chat.id, None)
    bot.reply_to(message, "ordem cancelada!")

@bot.message_handler(commands=['admin'])
def painel_admin(message):
    blocked = chr(0x1F6AB)

    if api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono()):
        gear = chr(0x2699) + chr(0xFE0F)
        warning = chr(0x26A0) + chr(0xFE0F)
        calendar = chr(0x1F4C5)
        chart = chr(0x1F4CA)
        users = chr(0x1F465)
        money = chr(0x1F4B0)
        box = chr(0x1F4E6)
        bulb = chr(0x1F4A1)
        lock = chr(0x1F510)
        admin_icon = chr(0x1F468) + chr(0x200D) + chr(0x1F4BC)
        handshake = chr(0x1F91D)
        card = chr(0x1F4B3)
        megaphone = chr(0x1F4E2)
        memo = chr(0x1F4DD)
        image_icon = chr(0x1F5BC) + chr(0xFE0F)
        button_icon = chr(0x1F518)
        clipboard = chr(0x1F4CB)
        soccer = chr(0x26BD)
        movie = chr(0x1F3AC)
        floppy = chr(0x1F4BE)
        back = chr(0x1F519)
        check = chr(0x2705)

        if api.Admin.tempo_ate_o_vencimento() <= 0:
            vencimento = f"{warning} <b>SEU BOT ESTA VENCIDO!</b> {warning}"
        else:
            vencimento = f"{calendar} <b>SEU BOT VENCE EM {api.Admin.tempo_ate_o_vencimento()} DIAS!</b>"

        texto = (
            f'{gear} <b>PAINEL DE GERENCIAMENTO @{api.CredentialsChange.user_bot()}</b>\n'
            f'{vencimento}\n'
            f'{chart} <i>V{api.CredentialsChange.versao_bot()}</i>\n\n'
            f'{chart} <b>Estatisticas:</b>\n'
            f'{users} Usuarios: {api.Admin.total_users()}\n'
            f'{money} Receita total: R${api.Admin.receita_total():.2f}\n'
            f'{money} Receita de hoje: R${api.Admin.receita_hoje():.2f}\n'
            f'{box} Acessos vendidos: {api.Admin.acessos_vendidos()}\n'
            f'{box} Acessos vendidos hoje: {api.Admin.acessos_vendidos_hoje()}\n\n'
            f'{bulb} <i>Use os botoes abaixo para me configurar</i>'
        )

        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(f'{gear} Configuracoes Gerais', callback_data='configuracoes_geral'))
        markup.row(InlineKeyboardButton(f'{lock} Configurar Logins', callback_data='configurar_logins'),
                   InlineKeyboardButton(f'{admin_icon} Configurar Admins', callback_data='configurar_admins'))
        markup.row(InlineKeyboardButton(f'{handshake} Configurar Afiliados', callback_data='configurar_afiliados'),
                   InlineKeyboardButton('👑 Clube VIP', callback_data='admin_vip'))
        markup.row(InlineKeyboardButton(f'{card} Configurar PIX', callback_data='configurar_pix'))
        markup.row(InlineKeyboardButton(f'{megaphone} Notificacoes Fake', callback_data='configurar_notificacoes_fake'))
        markup.row(InlineKeyboardButton(f'{memo} Editar Textos', callback_data='editar_textos'),
                   InlineKeyboardButton(f'{image_icon} Gerenciar Imagens', callback_data='gerenciar_imagens'))
        markup.row(InlineKeyboardButton(f'{card} Configurar Pagamentos', callback_data='configurar_pagamentos'))
        markup.row(InlineKeyboardButton('📣 Destinos Reais', callback_data='config_destinos_reais'),
                   InlineKeyboardButton(f'{button_icon} Editar Botoes', callback_data='editar_botoes'))
        markup.row(InlineKeyboardButton(f'{clipboard} Gerenciar Descricoes', callback_data='gerenciar_descricoes'))
        markup.row(InlineKeyboardButton(f'{soccer}{movie} Jogos e Filmes', callback_data='gerenciar_jogos_filmes'))
        markup.row(InlineKeyboardButton('🎰 Configurar Roleta', callback_data='admin_roleta'),
                   InlineKeyboardButton(f'{check} Gift Card', callback_data='gift_card'))
        markup.row(InlineKeyboardButton(f'{chart} Consultar Vendas', callback_data='menu_vendas'),
                   InlineKeyboardButton(f'{floppy} Gerenciar Backups', callback_data='menu_backups'))
        markup.row(InlineKeyboardButton(f'{megaphone} Transmitir a Todos', callback_data='configurar_usuarios'))
        markup.row(InlineKeyboardButton(f'{back} Voltar', callback_data='voltar_menu'))

        if message.text != '/admin':
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    else:
        bot.reply_to(message, f"{blocked} Voce nao tem permissao para acessar o painel de administracao!")


@bot.message_handler(commands=['renda'])
def comando_renda(message):

    admin_id = 7240103075 #ID DO ADMINISTRADOR

    if int(message.chat.id) == admin_id:
        texto = (
            f'â€¢ <b>EstatÃ©sticas Financeiras:</b>\n'
            f'â€¢ UsuÃ©rios: {api.Admin.total_users()}\n'
            f'â€¢ Receita Total: R${api.Admin.receita_total():.2f}\n'
            f'â€¢ Receita de Hoje: R${api.Admin.receita_hoje():.2f}\n'
            f'â€¢ Acessos Vendidos: {api.Admin.acessos_vendidos()}\n'
            f'â€¢ Acessos Vendidos Hoje: {api.Admin.acessos_vendidos_hoje()}\n\n'
        )
        bot.send_message(message.chat.id, texto, parse_mode='HTML')
    else:
        bot.reply_to(message, "VocÃª nÃ£o tem permissÃ£o para usar este comando.")

@bot.message_handler(commands=['vendas_dia'])
def comando_vendas_dia(message):
    """Comando para consultar vendas de um dia especÃ©fico"""
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return
    
    # Verificar se foi passada uma data
    parts = message.text.split()
    if len(parts) < 2:
        # Se nÃ£o passou data, pedir para o usuÃ¡rio
        msg = bot.reply_to(message, "â€¢ Digite a data que deseja consultar no formato DD/MM/YYYY\n\nExemplo: 24/02/2026")
        bot.register_next_step_handler(msg, processar_consulta_vendas_dia)
    else:
        # Se passou a data no comando
        data = parts[1]
        exibir_vendas_do_dia(message, data)

def processar_consulta_vendas_dia(message):
    """Processa a data informada pelo usuÃ¡rio"""
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o!")
        return
    
    data = message.text.strip()
    exibir_vendas_do_dia(message, data)

def exibir_vendas_do_dia(message, data):
    """Exibe todas as vendas de um dia especÃ©fico com navegaÃ§Ã£o"""
    try:
        # Validar formato da data
        datetime.datetime.strptime(data, "%d/%m/%Y")
    except ValueError:
        bot.reply_to(message, "âœ… Data invÃ©lida! Use o formato DD/MM/YYYY\n\nExemplo: 24/02/2026")
        return
    
    # Buscar vendas do dia
    vendas = database.get_sales_by_date(data)
    
    if not vendas:
        bot.reply_to(message, f"â€¢ Nenhuma venda encontrada para o dia {data}")
        return
    
    # Calcular totais
    total_valor = sum(float(v['valor']) for v in vendas)
    
    # Enviar resumo com navegaÃ§Ã£o
    resumo = f"â€¢ <b>VENDAS DO DIA {data}</b>\n\n"
    resumo += f"â€¢ <b>Total de vendas:</b> {len(vendas)}\n"
    resumo += f"â€¢ <b>Valor total:</b> R$ {total_valor:.2f}\n"
    resumo += f"{'='*30}\n\n"
    resumo += "Use os botÃµes abaixo para navegar pelas vendas:"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âš™ï¸ Ver Vendas', callback_data=f'nav_venda|{data}|0'))
    
    bot.send_message(message.chat.id, resumo, parse_mode='HTML', reply_markup=markup)

def mostrar_venda_navegavel(call, data, indice):
    """Mostra uma venda especÃ©fica com botÃµes de navegaÃ§Ã£o"""
    vendas = database.get_sales_by_date(data)
    
    if not vendas or indice < 0 or indice >= len(vendas):
        bot.answer_callback_query(call.id, "âœ… Venda nÃ£o encontrada!", show_alert=True)
        return
    
    venda = vendas[indice]
    
    # Escapar caracteres especiais do HTML
    username = html.escape(str(venda['username']))
    servico = html.escape(str(venda['servico']))
    email = html.escape(str(venda['email']))
    senha = html.escape(str(venda['senha']))
    
    texto = f"â€¢ <b>VENDA {indice + 1} de {len(vendas)}</b>\n"
    texto += f"â€¢ <b>Data:</b> {data}\n\n"
    texto += f"{'='*30}\n\n"
    texto += f"â€¢ <b>UsuÃ©rio:</b> {username}\n"
    texto += f"â€¢ <b>ID:</b> <code>{venda['user_id']}</code>\n\n"
    texto += f"â€¢ <b>ServiÃ©o:</b> {servico}\n"
    texto += f"â€¢ <b>Valor:</b> R$ {venda['valor']}\n"
    texto += f"â€¢ <b>HorÃ©rio:</b> {venda['data_completa']}\n\n"
    texto += f"â€¢ <b>Email:</b>\n<code>{email}</code>\n\n"
    texto += f"â€¢ <b>Senha:</b>\n<code>{senha}</code>"
    
    # Criar botÃµes de navegaÃ§Ã£o
    markup = InlineKeyboardMarkup()
    botoes = []
    
    # BotÃ©o anterior
    if indice > 0:
        botoes.append(InlineKeyboardButton('âš™ï¸ Anterior', callback_data=f'nav_venda|{data}|{indice-1}'))
    
    # Contador
    botoes.append(InlineKeyboardButton(f'{indice+1}/{len(vendas)}', callback_data='nada'))
    
    # BotÃ©o prÃ³ximo
    if indice < len(vendas) - 1:
        botoes.append(InlineKeyboardButton('PrÃ³ximo âš™ï¸', callback_data=f'nav_venda|{data}|{indice+1}'))
    
    markup.row(*botoes)
    
    # BotÃ©o para voltar ao resumo
    markup.row(InlineKeyboardButton('â€¢ Ver Resumo', callback_data=f'resumo_vendas|{data}'))
    markup.row(InlineKeyboardButton('â€¢ Voltar ao Menu', callback_data='menu_vendas'))
    
    kb = InlineKeyboardMarkup()

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, "âœ… Erro ao exibir venda", show_alert=True)

# =====================
# Sistema de Carrinho de Compras
# =====================

def exibir_carrinho(call_or_message):
    """Exibe o carrinho de compras do usuÃ¡rio"""
    if hasattr(call_or_message, 'message'):
        # Ã© um callback
        user_id = call_or_message.from_user.id
        chat_id = call_or_message.message.chat.id
        message_id = call_or_message.message.message_id
        is_callback = True
    else:
        # Ã© uma mensagem
        user_id = call_or_message.from_user.id
        chat_id = call_or_message.chat.id
        message_id = None
        is_callback = False
    
    carrinho = database.get_carrinho(user_id)
    
    if not carrinho:
        texto = "â€¢ <b>SEU CARRINHO ESTÃ© VAZIO</b>\n\n"
        texto += "Adicione produtos ao carrinho para finalizar a compra!"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Ver Produtos', callback_data='servicos'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
    else:
        total = database.get_carrinho_total(user_id)
        qtd_total = database.get_carrinho_quantidade_total(user_id)
        
        texto = "â€¢ <b>SEU CARRINHO DE COMPRAS</b>\n\n"
        
        for i, item in enumerate(carrinho, 1):
            servico_escaped = html.escape(item['servico'])
            texto += f"{i}. <b>{servico_escaped}</b>\n"
            texto += f"   â€¢ R$ {item['valor']:.2f} x {item['quantidade']} = R$ {(item['valor'] * item['quantidade']):.2f}\n\n"
        
        texto += f"{'='*30}\n"
        texto += f"â€¢ <b>Total de itens:</b> {qtd_total}\n"
        texto += f"â€¢ <b>Valor total:</b> R$ {total:.2f}\n"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âœ… FINALIZAR COMPRA', callback_data='finalizar_carrinho'))
        markup.row(InlineKeyboardButton('âœ… Adicionar Mais', callback_data='servicos'),
                   InlineKeyboardButton('â€¢ Limpar Carrinho', callback_data='limpar_carrinho'))
        markup.row(InlineKeyboardButton('âš™ï¸ Editar Quantidades', callback_data='editar_carrinho'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
    
    if is_callback:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(chat_id, texto, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(chat_id, texto, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(content_types=['web_app_data'])
def receber_carrinho_miniapp(message):
    try:
        payload = json.loads(message.web_app_data.data)
        if payload.get('action') != 'miniapp_cart' or not isinstance(payload.get('items'), list):
            raise ValueError('Formato de carrinho inválido')

        solicitados = {}
        for item in payload['items'][:20]:
            servico = str(item.get('servico') or '').strip()
            quantidade = int(item.get('quantidade') or 0)
            if not servico or quantidade < 1 or quantidade > 10:
                raise ValueError('Item ou quantidade inválida')
            solicitados[servico] = solicitados.get(servico, 0) + quantidade

        acessos = api.ControleLogins.pegar_servicos()
        disponiveis = {}
        for acesso in acessos:
            nome = acesso['nome']
            if nome not in disponiveis:
                disponiveis[nome] = {'valor': float(acesso['valor']), 'estoque': 0}
            disponiveis[nome]['estoque'] += 1

        if not solicitados:
            raise ValueError('O carrinho está vazio')
        for servico, quantidade in solicitados.items():
            produto = disponiveis.get(servico)
            if not produto or quantidade > produto['estoque']:
                raise ValueError(f'Estoque indisponível para {servico}')

        database.clear_carrinho(message.from_user.id)
        for servico, quantidade in solicitados.items():
            database.add_to_carrinho(message.from_user.id, servico, disponiveis[servico]['valor'])
            database.update_quantidade_carrinho(message.from_user.id, servico, quantidade)

        bot.send_message(
            message.chat.id,
            '✅ Carrinho recebido da loja. Confira os itens antes de finalizar.',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🛒 CONFERIR CARRINHO', callback_data='ver_carrinho')]])
        )
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        bot.send_message(
            message.chat.id,
            f'⚠️ Não foi possível importar o carrinho: {html.escape(str(error))}. Abra a loja e tente novamente.',
            parse_mode='HTML'
        )

def carregar_catalogo_miniapp():
    try:
        with open(MINIAPP_CATALOG_FILE, 'r', encoding='utf-8') as f:
            produtos = json.load(f)
        if isinstance(produtos, list):
            return produtos
    except Exception:
        pass
    return []

def _load_miniapp_images():
    try:
        if not os.path.exists(MINIAPP_IMAGES_FILE):
            _save_miniapp_images({})
            return {}
        with open(MINIAPP_IMAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def _save_miniapp_images(data):
    os.makedirs(os.path.dirname(MINIAPP_IMAGES_FILE), exist_ok=True)
    with open(MINIAPP_IMAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _miniapp_image_for_service(nome, image_map=None):
    image_map = image_map if image_map is not None else _load_miniapp_images()
    exact = image_map.get(nome)
    if exact:
        return exact
    nome_key = _normalize_key(nome)
    for key, value in image_map.items():
        key_norm = _normalize_key(key)
        if key_norm and (key_norm in nome_key or nome_key in key_norm):
            return value
    return ''

def _miniapp_auto_icon_for_service(nome):
    if not os.path.isdir(ICONS_DIR):
        return ''
    nome_key = _normalize_key(nome)
    if not nome_key:
        return ''
    stopwords = {
        'conta', 'tela', 'premium', 'padrao', 'standard', 'anuncio', 'anuncios',
        'acesso', 'acessos', 'convite', 'seu', 'email', 'gmail', 'link', 'meses',
        'mes', 'com', 'sem', 'familia', 'family', 'adicional', 'adicionais'
    }
    nome_tokens = {
        token for token in re.findall(r'[a-z0-9]{3,}', re.sub(r'[^a-zA-Z0-9]+', ' ', nome.lower()))
        if token not in stopwords
    }
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    best = None
    best_score = 0
    for fname in os.listdir(ICONS_DIR):
        base, ext = os.path.splitext(fname)
        if ext.lower() not in exts:
            continue
        icon_key = _normalize_key(base)
        if not icon_key:
            continue
        score = 0
        if icon_key == nome_key:
            score = 10000
        elif icon_key in nome_key:
            score = 6000 + len(icon_key)
        elif nome_key in icon_key:
            score = 5000 + len(nome_key)
        else:
            icon_tokens = {
                token for token in re.findall(r'[a-z0-9]{3,}', re.sub(r'[^a-zA-Z0-9]+', ' ', base.lower()))
                if token not in stopwords
            }
            shared = nome_tokens & icon_tokens
            partial = [token for token in nome_tokens if token in icon_key]
            score = sum(len(token) * 10 for token in shared) + sum(len(token) for token in partial)
        if score > best_score:
            best_score = score
            best = fname
    if not best or best_score < 6:
        return ''

    os.makedirs(MINIAPP_AUTO_ICONS_DIR, exist_ok=True)
    source = os.path.join(ICONS_DIR, best)
    target = os.path.join(MINIAPP_AUTO_ICONS_DIR, best)
    try:
        if not os.path.exists(target) or os.path.getmtime(source) > os.path.getmtime(target):
            shutil.copy2(source, target)
        return f'assets/service-images/auto-icons/{best}'
    except Exception:
        return ''

def atualizar_catalogo_miniapp():
    image_map = _load_miniapp_images()
    agrupados = {}
    for acesso in api.ControleLogins.pegar_servicos():
        nome = acesso['nome']
        if nome not in agrupados:
            agrupados[nome] = {
                'id': service_callback_token(nome),
                'name': nome,
                'price': float(acesso['valor']),
                'stock': 0
            }
        agrupados[nome]['stock'] += 1

    catalogo = []
    for produto in sorted(agrupados.values(), key=lambda item: _normalize_key(item['name'])):
        image = _miniapp_image_for_service(produto['name'], image_map) or _miniapp_auto_icon_for_service(produto['name'])
        if image:
            produto['image'] = image
            produto['updated_at'] = int(time.time())
        catalogo.append(produto)

    os.makedirs(os.path.dirname(MINIAPP_CATALOG_FILE), exist_ok=True)
    with open(MINIAPP_CATALOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, indent=2, ensure_ascii=False)
    return catalogo

def publicar_miniapp_no_git(motivo):
    try:
        paths = ['miniapp/catalog.json']
        if os.path.exists(MINIAPP_SERVICE_IMAGES_DIR):
            paths.append('miniapp/assets/service-images')
        if paths:
            add = subprocess.run(['git', 'add', *paths], cwd=BASE_DIR, capture_output=True, text=True, check=False)
            if add.returncode != 0:
                return False, (add.stderr or add.stdout or 'Falha ao preparar arquivos no Git.').strip()
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=BASE_DIR, capture_output=True, text=True, check=False)
        if status.returncode != 0:
            return False, (status.stderr or status.stdout or 'Git não disponível nessa pasta.').strip()
        if not status.stdout.strip():
            ahead = subprocess.run(
                ['git', 'rev-list', '--count', '@{u}..HEAD'],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                check=False
            )
            ahead_count = int((ahead.stdout or '0').strip() or 0) if ahead.returncode == 0 else 0
            if ahead_count > 0:
                push = subprocess.run(['git', 'push', 'origin', 'main'], cwd=BASE_DIR, capture_output=True, text=True, check=False)
                if push.returncode != 0:
                    return False, (push.stderr or push.stdout or 'Falha ao enviar commits pendentes para o Git.').strip()
                return True, f'Publicado no GitHub ({ahead_count} commit pendente enviado).'
            return True, 'Imagem já estava salva localmente. Se ainda não apareceu no site, aguarde o cache do Telegram/GitHub ou envie a imagem novamente.'
        commit_msg = f'Update Mini App service images: {motivo}'[:120]
        commit = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=BASE_DIR, capture_output=True, text=True, check=False)
        if commit.returncode != 0:
            return False, (commit.stderr or commit.stdout or 'Falha ao criar commit.').strip()
        push = subprocess.run(['git', 'push', 'origin', 'main'], cwd=BASE_DIR, capture_output=True, text=True, check=False)
        if push.returncode != 0:
            return False, (push.stderr or push.stdout or 'Falha ao enviar para o Git.').strip()
        return True, 'Publicado no GitHub. O GitHub Pages vai atualizar em instantes.'
    except Exception as e:
        return False, str(e)

def _miniapp_product_by_index(index):
    produtos = _get_unique_products()
    if 0 <= index < len(produtos):
        return produtos[index]
    return ''

def _miniapp_product_by_id(product_id, catalogo=None):
    product_id = str(product_id or '').strip()
    if not product_id:
        return ''

    catalogo = catalogo if catalogo is not None else carregar_catalogo_miniapp()
    for produto in catalogo:
        nome = str(produto.get('name') or '').strip()
        if produto.get('id') == product_id or service_callback_token(nome) == product_id:
            return nome

    return resolve_service_callback_token(product_id) or ''

def importar_carrinho_miniapp_start(message, payload):
    if len(payload or '') > 64:
        return False
    if not re.fullmatch(r'mc_(?:(?:\d+|[a-f0-9]{16})x\d+)(?:_(?:\d+|[a-f0-9]{16})x\d+)*', payload or ''):
        return False

    catalogo = carregar_catalogo_miniapp()
    if not catalogo:
        bot.send_message(message.chat.id, 'Não consegui carregar o catálogo da loja. Tente pelo catálogo do bot.')
        return True

    solicitados = {}
    for item in payload[3:].split('_'):
        produto_ref, qtd_text = item.split('x', 1)
        quantidade = int(qtd_text)
        if quantidade < 1 or quantidade > 10:
            bot.send_message(message.chat.id, 'Carrinho inválido. Abra a loja e tente novamente.')
            return True
        if produto_ref.isdigit():
            idx = int(produto_ref)
            if idx < 0 or idx >= len(catalogo):
                bot.send_message(message.chat.id, 'Carrinho inválido. Abra a loja e tente novamente.')
                return True
            servico = str(catalogo[idx].get('name') or '').strip()
        else:
            servico = _miniapp_product_by_id(produto_ref, catalogo)
        if not servico:
            bot.send_message(message.chat.id, 'Um produto do carrinho não foi encontrado.')
            return True
        solicitados[servico] = solicitados.get(servico, 0) + quantidade

    acessos = api.ControleLogins.pegar_servicos()
    disponiveis = {}
    for acesso in acessos:
        nome = acesso['nome']
        if nome not in disponiveis:
            disponiveis[nome] = {'valor': float(acesso['valor']), 'estoque': 0}
        disponiveis[nome]['estoque'] += 1

    for servico, quantidade in solicitados.items():
        produto = disponiveis.get(servico)
        if not produto or quantidade > produto['estoque']:
            bot.send_message(
                message.chat.id,
                f'O produto <b>{html.escape(servico)}</b> não tem estoque suficiente agora.',
                parse_mode='HTML'
            )
            return True

    user_id = message.from_user.id
    database.clear_carrinho(user_id)
    for servico, quantidade in solicitados.items():
        database.add_to_carrinho(user_id, servico, disponiveis[servico]['valor'])
        database.update_quantidade_carrinho(user_id, servico, quantidade)

    total = database.get_carrinho_total(user_id)
    saldo = database.get_user_balance(user_id)
    if saldo < total:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('💰 ADICIONAR SALDO', callback_data='addsaldo'))
        markup.row(InlineKeyboardButton('🛒 VER CARRINHO', callback_data='ver_carrinho'))
        bot.send_message(
            message.chat.id,
            f'🛒 Carrinho recebido da loja.\n\nTotal: R$ {total:.2f}\nSeu saldo: R$ {saldo:.2f}\n\nAdicione saldo para finalizar.',
            reply_markup=markup
        )
        return True

    solicitar_aceite_termos(message, 'carrinho', {})
    return True

def notificar_reabastecimento(produto):
    """Notifica usuÃ¡rios que estÃ©o aguardando um produto"""
    usuarios = database.get_usuarios_aguardando_produto(produto)
    
    if not usuarios:
        return 0
    
    notificados = 0
    for user_id in usuarios:
        try:
            texto = f"â€¢ <b>PRODUTO REABASTECIDO!</b>\n\n"
            texto += f"â€¢ O produto <b>{html.escape(produto)}</b> voltou ao estoque!\n\n"
            texto += "Corra para garantir o seu!"
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton('â€¢ Ver Produto', callback_data='servicos'))
            markup.row(InlineKeyboardButton('â€¢ Minhas NotificaÃ§Ãµes', callback_data='voltar_notif'))
            
            bot.send_message(user_id, texto, parse_mode='HTML', reply_markup=markup)
            notificados += 1
            
            # Remover a notificaÃ§Ã£o apÃ©s enviar
            database.remover_notificacao_reabastecimento(user_id, produto)
        except Exception as e:
            print(f"[NOTIF] Erro ao notificar usuÃ¡rio {user_id}: {e}")
            continue
    
    return notificados

def notificar_abastecimento_estoque(abastecidos):
    """Publica um aviso único no canal após abastecer um ou mais serviços."""
    if not abastecidos:
        return False

    try:
        linhas = []
        for produto, quantidade in abastecidos.items():
            estoque_atual = api.ControleLogins.pegar_estoque(produto)
            linhas.append(
                f'🟢 <b>{html.escape(str(produto))}</b> — '
                f'+{int(quantidade)} unidade(s) | '
                f'<b>total: {int(estoque_atual)}</b>'
            )

        texto = (
            '📦 <b>ESTOQUE REABASTECIDO!</b>\n\n'
            '✅ Novos produtos já estão disponíveis na loja:\n\n'
            + '\n'.join(linhas)
            + '\n\n🛒 <i>Acesse a loja e garanta o seu!</i>'
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(botao_personalizado('abrir_loja', '🛒 ABRIR LOJA'), url=MINIAPP_URL))
        bot.send_message(
            get_sales_notification_chat_id(),
            texto,
            parse_mode='HTML',
            reply_markup=markup,
            disable_web_page_preview=True
        )
        return True
    except Exception as error:
        print(f'[ESTOQUE] Erro ao avisar reabastecimento no canal: {error}', flush=True)
        return False


def exibir_editar_carrinho(call):
    """Exibe o carrinho com opÃ§Ãµes de ediÃ§Ã£o"""
    user_id = call.from_user.id
    carrinho = database.get_carrinho(user_id)
    
    if not carrinho:
        bot.answer_callback_query(call.id, "Carrinho vazio!", show_alert=True)
        return
    
    texto = "âš™ï¸ <b>EDITAR CARRINHO</b>\n\n"
    texto += "Selecione um item para editar ou remover:"
    
    markup = InlineKeyboardMarkup()
    for item in carrinho:
        servico_escaped = html.escape(item['servico'])
        btn_text = f"{servico_escaped} (x{item['quantidade']})"
        markup.row(InlineKeyboardButton(btn_text, callback_data=f'edit_item_carrinho|{item["servico"]}'))
    
    markup.row(InlineKeyboardButton('â€¢ Voltar ao Carrinho', callback_data='ver_carrinho'))
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def exibir_opcoes_item_carrinho(call, servico):
    """Exibe opÃ§Ãµes para editar um item especÃ©fico do carrinho"""
    user_id = call.from_user.id
    carrinho = database.get_carrinho(user_id)
    
    item = next((i for i in carrinho if i['servico'] == servico), None)
    if not item:
        bot.answer_callback_query(call.id, "Item nÃ£o encontrado!", show_alert=True)
        return
    
    servico_escaped = html.escape(servico)
    texto = f"âš™ï¸ <b>EDITAR ITEM</b>\n\n"
    texto += f"<b>Produto:</b> {servico_escaped}\n"
    texto += f"<b>Quantidade atual:</b> {item['quantidade']}\n"
    texto += f"<b>Valor unitÃ©rio:</b> R$ {item['valor']:.2f}\n"
    texto += f"<b>Subtotal:</b> R$ {(item['valor'] * item['quantidade']):.2f}\n"
    
    markup = InlineKeyboardMarkup()
    
    # BotÃ©es de quantidade
    if item['quantidade'] > 1:
        markup.row(InlineKeyboardButton('âœ… Diminuir', callback_data=f'qtd_carrinho|{servico}|-1'))
    markup.row(InlineKeyboardButton(f"Quantidade: {item['quantidade']}", callback_data='nada'))
    markup.row(InlineKeyboardButton('âœ… Aumentar', callback_data=f'qtd_carrinho|{servico}|+1'))
    
    markup.row(InlineKeyboardButton('â€¢ Remover do Carrinho', callback_data=f'remove_carrinho|{servico}'))
    markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='editar_carrinho'))
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def processar_quantidade_carrinho(message, servico):
    """Processa a quantidade informada para adicionar ao carrinho"""
    print(f"[DEBUG] processar_quantidade_carrinho chamado")
    print(f"[DEBUG] message.text = '{message.text}'")
    print(f"[DEBUG] servico = '{servico}'")
    
    try:
        # Limpar o texto (remover espaÃ©os e quebras de linha)
        texto_limpo = message.text.strip()
        print(f"[DEBUG] texto_limpo = '{texto_limpo}'")
        
        # Tentar converter para inteiro
        quantidade = int(texto_limpo)
        print(f"[DEBUG] quantidade convertida = {quantidade}")
        
        if quantidade <= 0:
            print(f"[DEBUG] Quantidade <= 0")
            bot.reply_to(message, "âœ… A quantidade deve ser maior que zero!")
            return
        
        if quantidade > 50:
            print(f"[DEBUG] Quantidade > 50")
            bot.reply_to(message, "âœ… Quantidade mÃ©xima Ã© 50 unidades por vez!")
            return
        
        user_id = message.from_user.id
        print(f"[DEBUG] user_id = {user_id}")
        
        # Pegar valor do serviÃ§o
        print(f"[DEBUG] Tentando pegar info do serviÃ§o...")
        nome_servico, valor, descricao, duracao, email = api.ControleLogins.pegar_info(servico)
        print(f"[DEBUG] Valor do serviÃ§o = {valor} (tipo: {type(valor)})")
        
        # Converter valor para float
        valor = float(valor)
        print(f"[DEBUG] Valor convertido para float = {valor}")
        
        # Adicionar mÃ©ltiplas vezes ao carrinho
        print(f"[DEBUG] Adicionando {quantidade} itens ao carrinho...")
        for _ in range(quantidade):
            database.add_to_carrinho(user_id, servico, valor)
        
        qtd_carrinho = database.get_carrinho_quantidade_total(user_id)
        total_carrinho = database.get_carrinho_total(user_id)
        carrinho_completo = database.get_carrinho(user_id)
        print(f"[DEBUG] Carrinho atualizado: {qtd_carrinho} itens, total R$ {total_carrinho}")
        
        # Mostrar mensagem de sucesso
        texto = f"âœ… <b>{quantidade}x PRODUTOS ADICIONADOS AO CARRINHO!</b>\n\n"
        texto += f"â€¢ <b>Produto:</b> {html.escape(servico)}\n"
        texto += f"â€¢ <b>Valor unitÃ©rio:</b> R$ {valor:.2f}\n"
        texto += f"â€¢ <b>Quantidade:</b> {quantidade}\n"
        texto += f"â€¢ <b>Subtotal:</b> R$ {(valor * quantidade):.2f}\n\n"
        texto += f"{'='*30}\n\n"
        texto += f"â€¢ <b>RESUMO DO CARRINHO:</b>\n\n"
        
        # Listar todos os itens do carrinho
        for i, item in enumerate(carrinho_completo, 1):
            texto += f"{i}. {html.escape(item['servico'])}\n"
            texto += f"   â€¢ R$ {item['valor']:.2f} x {item['quantidade']} = R$ {(item['valor'] * item['quantidade']):.2f}\n\n"
        
        texto += f"{'='*30}\n"
        texto += f"â€¢ <b>Total de itens:</b> {qtd_carrinho}\n"
        texto += f"â€¢ <b>Valor total:</b> R$ {total_carrinho:.2f}\n\n"
        texto += "O que deseja fazer?"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Ver Carrinho', callback_data='ver_carrinho'))
        markup.row(InlineKeyboardButton('âœ… Adicionar Mais Produtos', callback_data='servicos'))
        markup.row(InlineKeyboardButton('âœ… Finalizar Compra', callback_data='finalizar_carrinho'))
        
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        print(f"[DEBUG] Mensagem de sucesso enviada!")
        
    except ValueError as e:
        print(f"[DEBUG] ValueError capturado: {e}")
        bot.reply_to(message, f"âœ… Por favor, envie um nÃ©mero vÃ©lido!\nTexto recebido: '{message.text}'")
    except Exception as e:
        print(f"[DEBUG] Exception capturada: {type(e).__name__}: {e}")
        bot.reply_to(message, f"âœ… Erro ao adicionar ao carrinho: {str(e)}")

@bot.message_handler(func=lambda message: message.from_user.id in pending_carrinho_qtd and not message.text.startswith('/'))
def handler_quantidade_carrinho(message):
    """Handler para processar quantidade do carrinho"""
    user_id = message.from_user.id
    servico = pending_carrinho_qtd.pop(user_id)
    processar_quantidade_carrinho(message, servico)

@bot.message_handler(func=lambda message: message.from_user.id in pending_notif_reabast and not message.text.startswith('/'))
def handler_notificacao_reabastecimento(message):
    """Handler para processar adiÃ§Ã£o de notificaÃ§Ã£o de reabastecimento"""
    user_id = message.from_user.id
    pending_notif_reabast.pop(user_id)
    
    produto = message.text.strip()
    
    if len(produto) < 3:
        bot.reply_to(message, "âœ… O nome do produto deve ter pelo menos 3 caracteres!")
        return
    
    if len(produto) > 100:
        bot.reply_to(message, "âœ… O nome do produto Ã© muito longo!")
        return
    
    # Adicionar notificaÃ§Ã£o
    sucesso = database.adicionar_notificacao_reabastecimento(user_id, produto)
    
    if sucesso:
        texto = f"âœ… <b>NOTIFICAÃ‡ÃƒO ADICIONADA!</b>\n\n"
        texto += f"â€¢ <b>Produto:</b> {html.escape(produto)}\n\n"
        texto += "VocÃª serÃ© notificado quando este produto voltar ao estoque!"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Ver Minhas NotificaÃ§Ãµes', callback_data='voltar_notif'))
        markup.row(InlineKeyboardButton('âœ… Adicionar Outro', callback_data='add_notif_reabast'))
        markup.row(InlineKeyboardButton('â€¢ Menu Principal', callback_data='voltar_menu'))
        
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    else:
        bot.reply_to(message, f"âš™ï¸ VocÃª jÃ¡ tem uma notificaÃ§Ã£o ativa para: {html.escape(produto)}", parse_mode='HTML')

@bot.message_handler(commands=['carrinho'])
def comando_carrinho(message):
    """Comando para ver o carrinho"""
    exibir_carrinho(message)

@bot.message_handler(commands=['notificar'])
def comando_notificar(message):
    """Comando para gerenciar notificaÃ§Ãµes de reabastecimento"""
    user_id = message.from_user.id
    notificacoes = database.get_notificacoes_reabastecimento(user_id)
    
    texto = "â€¢ <b>NOTIFICAÃ‡Ã•ES DE REABASTECIMENTO</b>\n\n"
    
    if notificacoes:
        texto += f"VocÃª serÃ© notificado quando estes produtos voltarem ao estoque:\n\n"
        for i, item in enumerate(notificacoes, 1):
            texto += f"{i}. {html.escape(item['produto'])}\n"
        texto += f"\nâ€¢ Total: {len(notificacoes)} produto(s)"
    else:
        texto += "VocÃª nÃ£o tem notificaÃ§Ãµes ativas.\n\n"
        texto += "Use o botÃ©o abaixo para adicionar produtos que deseja ser notificado quando voltarem ao estoque!"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœ… Adicionar Produto', callback_data='add_notif_reabast'))
    if notificacoes:
        markup.row(InlineKeyboardButton('â€¢ Remover Produto', callback_data='remove_notif_reabast'))
        markup.row(InlineKeyboardButton('â€¢ Limpar Todas', callback_data='limpar_notif_reabast'))
    markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
    
    bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(commands=['vendas_hoje'])
def comando_vendas_hoje(message):
    """Comando rÃ©pido para ver vendas de hoje"""
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return
    
    # Pegar data de hoje
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    exibir_vendas_do_dia(message, hoje)

@bot.message_handler(commands=['vendas_mes'])
def comando_vendas_mes(message):
    """Comando para ver estatÃ©sticas do mÃ©s atual"""
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return
    
    # Calcular inÃ©cio e fim do mÃ©s
    agora = datetime.datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calcular Ã©ltimo dia do mÃ©s
    if agora.month == 12:
        fim_mes = agora.replace(year=agora.year + 1, month=1, day=1, hour=23, minute=59, second=59)
    else:
        fim_mes = agora.replace(month=agora.month + 1, day=1, hour=23, minute=59, second=59)
    fim_mes = fim_mes - datetime.timedelta(seconds=1)
    
    # Buscar estatÃ©sticas
    stats = database.get_sales_stats(inicio_mes, fim_mes)
    
    texto = f"â€¢ <b>ESTATÃ©STICAS DO MÃ©S ({agora.strftime('%m/%Y')})</b>\n\n"
    texto += f"â€¢ <b>Total de vendas:</b> {stats['total_vendas']}\n"
    texto += f"â€¢ <b>Valor total:</b> R$ {stats['total_valor']:.2f}\n"
    texto += f"â€¢ <b>Ticket mÃ©dio:</b> R$ {(stats['total_valor'] / stats['total_vendas']):.2f}\n" if stats['total_vendas'] > 0 else ""
    texto += f"\n{'='*30}\n\n"
    texto += f"<b>â€¢ PRODUTOS MAIS VENDIDOS:</b>\n\n"
    
    # Ordenar produtos por quantidade
    produtos_ordenados = sorted(
        stats['produtos_vendidos'].items(),
        key=lambda x: x[1]['quantidade'],
        reverse=True
    )
    
    for i, (produto, info) in enumerate(produtos_ordenados[:10], 1):
        texto += f"{i}. <b>{produto}</b>\n"
        texto += f"   â€¢ Quantidade: {info['quantidade']}\n"
        texto += f"   â€¢ Total: R$ {info['valor_total']:.2f}\n\n"
    
    bot.send_message(message.chat.id, texto, parse_mode='HTML')

def configuracoes_geral(message):
    """
    Exibe o menu de configuraÃ§Ãµes gerais do bot com um design mais organizado.
    """
    status_manutencao = "â€¢ Ativado" if api.CredentialsChange.status_manutencao() else "â€¢ Desativado"
    status_reserva = "â€¢ Ativada" if reserve_verification_enabled() else "â€¢ Desativada"
    modo_exibicao = api.CredentialsChange.modo_exibicao()
    modo_texto = "â€¢ Categorizado" if modo_exibicao == "categorizado" else "â€¢ Lista Direta"
    emoji_pack = service_emoji_pack_link()
    emoji_pack_text = f'<a href="{emoji_pack}">Clique Aqui</a>' if emoji_pack else 'PadrÃ£o'
    
    texto = (
        f'âš™ï¸ <b>CONFIGURAÃ‡Ã•ES GERAIS</b> âš™ï¸\n\n'
        f'â€¢ <b>Destino das Logs:</b> {api.CredentialsChange.id_dono()}\n'
        f'â€¢ <b>Suporte:</b> <a href="{api.CredentialsChange.SuporteInfo.link_suporte()}">Clique Aqui</a>\n'
        f'â€¢ <b>Bot Reserva:</b> <a href="{reserve_bot_url()}">Clique Aqui</a>\n'
        f'â€¢ <b>Grupo Reserva:</b> <a href="{reserve_group_url()}">Clique Aqui</a>\n'
        f'â€¢ <b>ID Grupo Reserva:</b> <code>{reserve_group_id()}</code>\n'
        f'â€¢ <b>VerificaÃ§Ã£o Reserva:</b> {status_reserva}\n'
        f'â€¢ <b>Emojis ServiÃ§os:</b> {emoji_pack_text} (<code>{service_emoji_count()}</code>)\n'
        f'â€¢ <b>Emojis por ServiÃ§o:</b> <code>{service_emoji_map_count()}</code>\n'
        f'âš™ï¸ <b>Separador Atual:</b> {api.CredentialsChange.separador()}\n'
        f'â€¢ <b>Modo de ExibiÃ§Ã£o:</b> {modo_texto}\n\n'
        f'<i>O separador Ã© um caractere usado para estruturar as informaÃ§Ãµes no bot. Escolha um caractere que nÃ£o seja comum no seu uso para evitar confusÃµes.</i>\n\n'
        f'<b>Exemplo de Separador em AÃ§Ã£o:</b> <code>NOME{api.CredentialsChange.separador()}VALOR</code>'
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f'{status_manutencao} - Alternar', callback_data='manutencao'))
    markup.row(InlineKeyboardButton(f'{status_reserva} - Obrigar Reserva', callback_data='toggle_bot_reserva'))
    markup.row(InlineKeyboardButton('ðŸ›¡ï¸ Alterar Bot Reserva', callback_data='alterar_bot_reserva'),
               InlineKeyboardButton('ðŸ‘¥ Alterar Grupo Reserva', callback_data='alterar_grupo_reserva'))
    markup.row(InlineKeyboardButton('ðŸ†” ID Grupo Reserva', callback_data='alterar_id_grupo_reserva'),
               InlineKeyboardButton('ðŸ§¹ Limpar VerificaÃ§Ãµes', callback_data='limpar_verificacoes_reserva'))
    markup.row(InlineKeyboardButton('ðŸ˜€ Emojis por ServiÃ§o', callback_data='emojis_servicos_menu'))
    markup.row(InlineKeyboardButton('ðŸ“¦ Pacote Emojis ServiÃ§os', callback_data='alterar_emojis_servicos'))
    markup.row(InlineKeyboardButton('â€¢ Alterar Suporte', callback_data='suporte'),
               InlineKeyboardButton('âš™ï¸ Alterar Separador', callback_data='mudar_separador'))
    markup.row(InlineKeyboardButton('â€¢ Modo de ExibiÃ§Ã£o', callback_data='configurar_modo_exibicao'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        text=texto,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

# =====================
# Editor de Textos
# =====================
def _admin_only(message_or_call) -> bool:
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    from_user = getattr(message_or_call, 'from_user', None)
    user_id = getattr(from_user, 'id', chat_id)
    return (
        api.Admin.verificar_admin(chat_id)
        or api.Admin.verificar_admin(user_id)
        or int(chat_id) == int(api.CredentialsChange.id_dono())
        or int(user_id) == int(api.CredentialsChange.id_dono())
    )

ROLETA_CONFIG_PATH = 'settings/roleta.json'
ROLETA_GIROS_PATH = 'database/roleta_giros.json'

def _read_json_file(path, default):
    try:
        if not os.path.exists(path):
            _write_json_file(path, default)
            return default.copy() if isinstance(default, dict) else default
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default.copy() if isinstance(default, dict) else default

def _write_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def roleta_default_config():
    return {
        "status": "off",
        "valor_min": 0.1,
        "valor_max": 2.0,
        "chance_ganhar": 30,
        "limite_tempo": "on",
        "tempo_horas": 24
    }

def carregar_config_roleta():
    config = roleta_default_config()
    saved = _read_json_file(ROLETA_CONFIG_PATH, config)
    config.update(saved)
    try:
        config["valor_min"] = max(0.01, float(config.get("valor_min", 0.1)))
        config["valor_max"] = max(config["valor_min"], float(config.get("valor_max", 2.0)))
        config["chance_ganhar"] = min(100, max(0, float(config.get("chance_ganhar", 30))))
        config["limite_tempo"] = "on" if config.get("limite_tempo", "on") == "on" else "off"
        config["tempo_horas"] = max(1, float(config.get("tempo_horas", 24)))
    except Exception:
        config = roleta_default_config()
    return config

def salvar_config_roleta(config):
    _write_json_file(ROLETA_CONFIG_PATH, config)

def roleta_ativa():
    return carregar_config_roleta().get("status") == "on"

def roleta_agora():
    return datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))

def carregar_giros_roleta():
    return _read_json_file(ROLETA_GIROS_PATH, {})

def salvar_giros_roleta(giros):
    _write_json_file(ROLETA_GIROS_PATH, giros)

def roleta_tempo_restante(giro, tempo_horas):
    try:
        ultimo_giro = datetime.datetime.fromisoformat(giro.get("quando"))
        if ultimo_giro.tzinfo is None:
            ultimo_giro = pytz.timezone('America/Sao_Paulo').localize(ultimo_giro)
    except Exception:
        return None

    proximo_giro = ultimo_giro + datetime.timedelta(hours=float(tempo_horas))
    restante = proximo_giro - roleta_agora()
    if restante.total_seconds() <= 0:
        return None
    return restante

def formatar_tempo_restante(delta):
    total_seconds = int(delta.total_seconds())
    horas, resto = divmod(total_seconds, 3600)
    minutos = max(1, resto // 60)
    if horas > 0:
        return f"{horas}h {minutos}min"
    return f"{minutos}min"

def mostrar_roleta(call):
    config = carregar_config_roleta()
    markup = InlineKeyboardMarkup()
    if config.get("status") == "on":
        markup.row(InlineKeyboardButton('🎰 GIRAR ROLETA', callback_data='roleta_girar'))
    markup.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='menu_start'))

    if config.get("status") != "on":
        texto = (
            "🎰 <b>ROLETA DA SORTE</b>\n\n"
            "A roleta está desativada no momento.\n"
            "Volte mais tarde para testar sua sorte."
        )
    else:
        texto = (
            "🎰 <b>ROLETA DA SORTE</b>\n\n"
            "Teste sua sorte e concorra a saldo grátis!\n\n"
            f"Prêmios de <b>R${config['valor_min']:.2f}</b> até "
            f"<b>R${config['valor_max']:.2f}</b>.\n"
            "Toque em girar e boa sorte! 🍀"
        )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )

def girar_roleta(call):
    config = carregar_config_roleta()
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if config.get("status") != "on":
        bot.answer_callback_query(call.id, "A roleta está desativada.", show_alert=True)
        mostrar_roleta(call)
        return

    giros = carregar_giros_roleta()
    user_key = str(user_id)
    if config.get("limite_tempo") == "on":
        restante = roleta_tempo_restante(giros.get(user_key, {}), config["tempo_horas"])
        if restante:
            bot.answer_callback_query(
                call.id,
                f"Você já girou. Tente novamente em {formatar_tempo_restante(restante)}.",
                show_alert=True
            )
            return

    if database.load_user_data(user_id) is None:
        username = getattr(call.from_user, 'username', None)
        database.initialize_user(user_id, username)

    ganhou = random.uniform(0, 100) <= float(config["chance_ganhar"])
    premio = 0.0
    if ganhou:
        premio = round(random.uniform(float(config["valor_min"]), float(config["valor_max"])), 2)
        database.update_user_balance(user_id, premio)

    giros[user_key] = {
        "data": roleta_agora().strftime('%Y-%m-%d'),
        "quando": roleta_agora().isoformat(),
        "ganhou": ganhou,
        "valor": premio,
        "hora": roleta_agora().strftime('%d/%m/%Y %H:%M:%S')
    }
    salvar_giros_roleta(giros)

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='menu_start'))

    if ganhou:
        texto = (
            "🎰 <b>ROLETA DA SORTE!</b>\n\n"
            f"🎉 Você ganhou <b>R${premio:.2f}</b> de saldo grátis!\n"
            "💵 Já caiu na sua conta. Boa sorte no próximo giro! 🍀"
        )
    else:
        texto = (
            "🎰 <b>ROLETA DA SORTE!</b>\n\n"
            "Não foi dessa vez.\n"
            "Tente novamente quando a roleta liberar seu próximo giro! 🍀"
        )

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def mostrar_admin_roleta(message):
    if not _admin_only(message):
        bot.reply_to(message, 'Sem permissão.')
        return

    config = carregar_config_roleta()
    status_txt = "Ativada" if config.get("status") == "on" else "Desativada"
    limite_txt = "Ativado" if config.get("limite_tempo") == "on" else "Desativado"
    texto = (
        "🎰 <b>CONFIGURAR ROLETA DA SORTE</b>\n\n"
        f"<b>Status:</b> {status_txt}\n"
        f"<b>Valor mínimo:</b> R${config['valor_min']:.2f}\n"
        f"<b>Valor máximo:</b> R${config['valor_max']:.2f}\n"
        f"<b>Chance de ganhar:</b> {config['chance_ganhar']:.0f}%\n"
        f"<b>Limite de tempo:</b> {limite_txt}\n"
        f"<b>Tempo entre giros:</b> {config['tempo_horas']:.0f}h"
    )
    markup = InlineKeyboardMarkup()
    if config.get("status") == "on":
        markup.row(InlineKeyboardButton('Desativar Roleta', callback_data='roleta_admin_toggle'))
    else:
        markup.row(InlineKeyboardButton('Ativar Roleta', callback_data='roleta_admin_toggle'))
    markup.row(InlineKeyboardButton('Valor Mínimo', callback_data='roleta_admin_min'),
               InlineKeyboardButton('Valor Máximo', callback_data='roleta_admin_max'))
    markup.row(InlineKeyboardButton('Chance %', callback_data='roleta_admin_chance'))
    markup.row(InlineKeyboardButton('Tempo On/Off', callback_data='roleta_admin_tempo_toggle'),
               InlineKeyboardButton('Horas Espera', callback_data='roleta_admin_tempo_horas'))
    markup.row(InlineKeyboardButton('Voltar', callback_data='voltar_paineladm'))

    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def pedir_config_roleta(message, campo, titulo):
    msg = bot.send_message(
        message.chat.id,
        f"Envie o novo valor para <b>{titulo}</b>.\nUse apenas número. Exemplo: <code>2.50</code>",
        parse_mode='HTML',
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(msg, salvar_config_roleta_admin, campo)

def salvar_config_roleta_admin(message, campo):
    if not _admin_only(message):
        bot.reply_to(message, 'Sem permissão.')
        return
    try:
        valor = float((message.text or '').replace(',', '.').strip())
    except Exception:
        bot.reply_to(message, "Valor inválido. Envie apenas número.")
        return

    config = carregar_config_roleta()
    if campo == 'chance_ganhar':
        if valor < 0 or valor > 100:
            bot.reply_to(message, "A chance precisa ser entre 0 e 100.")
            return
        config[campo] = valor
    elif campo == 'valor_min':
        if valor <= 0 or valor > config["valor_max"]:
            bot.reply_to(message, "O valor mínimo precisa ser maior que 0 e menor ou igual ao máximo.")
            return
        config[campo] = round(valor, 2)
    elif campo == 'valor_max':
        if valor < config["valor_min"]:
            bot.reply_to(message, "O valor máximo precisa ser maior ou igual ao mínimo.")
            return
        config[campo] = round(valor, 2)
    elif campo == 'tempo_horas':
        if valor < 1:
            bot.reply_to(message, "O tempo precisa ser de pelo menos 1 hora.")
            return
        config[campo] = round(valor, 2)

    salvar_config_roleta(config)
    bot.reply_to(message, "Configuração da roleta atualizada com sucesso.")

@bot.message_handler(commands=['roleta_admin'])
def comando_roleta_admin(message):
    mostrar_admin_roleta(message)

def total_comissao_indicacao(user_id):
    user_data = database.load_user_data(user_id)
    if not user_data:
        return 0.0
    return float(user_data.get("pontos_indicado", 0) or 0)

def pagar_comissao_afiliado(indicado_id, valor_recarga):
    if not api.AfiliadosInfo.status_afiliado():
        return 0.0

    indicado = database.load_user_data(indicado_id)
    if not indicado:
        return 0.0

    indicador_id = int(indicado.get("afiliado_por") or 0)
    if not indicador_id or indicador_id == int(indicado_id):
        return 0.0

    indicador = database.load_user_data(indicador_id)
    if not indicador:
        return 0.0

    percentual = float(api.AfiliadosInfo.pontos_por_recarga())
    if percentual <= 0:
        return 0.0

    comissao = round(float(valor_recarga) * percentual / 100, 2)
    if comissao <= 0:
        return 0.0

    indicador["saldo"] = float(indicador.get("saldo", 0) or 0) + comissao
    indicador["pontos_indicado"] = float(indicador.get("pontos_indicado", 0) or 0) + comissao
    database.save_user_data(indicador_id, indicador)

    try:
        bot.send_message(
            indicador_id,
            (
                "👥 <b>Você ganhou comissão!</b>\n\n"
                f"Um indicado fez uma recarga de <b>R${float(valor_recarga):.2f}</b>.\n"
                f"Sua comissão: <b>R${comissao:.2f}</b>\n"
                "O valor já caiu no seu saldo."
            ),
            parse_mode='HTML'
        )
    except Exception:
        pass

    return comissao

def exibir_texto_no_callback(call, texto, markup, **kwargs):
    if call.message.content_type == 'text':
        return bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            reply_markup=markup,
            **kwargs
        )

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except ApiTelegramException:
        pass
    return bot.send_message(
        chat_id=call.message.chat.id,
        text=texto,
        reply_markup=markup,
        **kwargs
    )

def mostrar_indique_ganhe(call):
    if not api.AfiliadosInfo.status_afiliado():
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='menu_start'))
        exibir_texto_no_callback(
            call,
            (
                "👥 <b>INDIQUE E GANHE</b>\n\n"
                "O sistema de indicações está desativado no momento.\n"
                "Um administrador pode ativar em /admin."
            ),
            parse_mode='HTML',
            markup=markup
        )
        return

    user_id = call.from_user.id
    link = f"https://t.me/{api.CredentialsChange.user_bot()}?start={user_id}"
    percentual = api.AfiliadosInfo.pontos_por_recarga()
    quantidade = api.InfoUser.quantidade_afiliados(user_id)
    total_ganho = total_comissao_indicacao(user_id)

    texto = (
        "👥 <b>INDIQUE E GANHE</b>\n\n"
        f"Compartilhe seu link e ganhe <b>{percentual}%</b> de tudo que seus indicados recarregarem — "
        "direto no seu saldo, automático! 💰\n\n"
        "🔗 <b>Seu link de indicação:</b>\n"
        f"<code>{html.escape(link)}</code>\n\n"
        f"👤 <b>Seus indicados:</b> {quantidade}\n"
        f"💵 <b>Total já ganho:</b> R${total_ganho:.2f}\n\n"
        "<i>Toque no link acima para copiar e mande para os amigos!</i>"
    )
    share_url = (
        "https://t.me/share/url?"
        f"url={urllib.parse.quote(link, safe='')}"
        "&text=Entre%20nesse%20bot%20e%20confira%20as%20ofertas!"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('📤 Compartilhar meu link', url=share_url))
    markup.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='menu_start'))

    exibir_texto_no_callback(
        call,
        texto,
        markup,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

def _database_import_destination(zip_name: str):
    clean_name = zip_name.replace('\\', '/').strip('/')
    parts = PurePosixPath(clean_name).parts

    if not parts or any(part in ('', '.', '..') for part in parts):
        return None
    if any(part.lower() == '.git' for part in parts):
        return None

    if 'database' in parts:
        start = parts.index('database')
        allowed_parts = parts[start:]
    elif 'historicos' in parts:
        start = parts.index('historicos')
        allowed_parts = parts[start:]
    elif parts[0] == 'users':
        allowed_parts = ('database', *parts)
    elif len(parts) == 1 and parts[0].lower().endswith(('.json', '.txt', '.sync_hash')):
        allowed_parts = ('database', *parts)
    else:
        return None

    if allowed_parts[0] not in ('database', 'historicos'):
        return None

    return os.path.join(*allowed_parts)

def _safe_import_database_zip(zip_bytes: bytes):
    imported = 0
    skipped = 0
    total_size = 0
    max_files = 20000
    max_total_size = 250 * 1024 * 1024

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        files = [info for info in archive.infolist() if not info.is_dir()]
        if len(files) > max_files:
            raise ValueError(f"Zip tem arquivos demais ({len(files)}). Limite: {max_files}.")

        planned = []
        for info in files:
            total_size += info.file_size
            if total_size > max_total_size:
                raise ValueError("Zip muito grande para importar com seguranca.")

            destination = _database_import_destination(info.filename)
            if not destination:
                skipped += 1
                continue
            planned.append((info, destination))

        if not planned:
            raise ValueError("Nao encontrei arquivos de database/historicos dentro do zip.")

        backup_path = backup_manager.create_backup()

        for info, destination in planned:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(info) as source, open(destination, 'wb') as target:
                target.write(source.read())
            imported += 1

    return imported, skipped, backup_path

def pedir_importar_database(message):
    if not _admin_only(message):
        bot.reply_to(message, 'Sem permissao.')
        return

    msg = bot.send_message(
        message.chat.id,
        (
            "<b>Importar database</b>\n\n"
            "Envie agora um arquivo <code>.zip</code> contendo a pasta "
            "<code>database</code> e, se tiver, <code>historicos</code>.\n\n"
            "Eu vou criar um backup antes de importar."
        ),
        parse_mode='HTML',
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(msg, receber_database_zip)

def receber_database_zip(message):
    if not _admin_only(message):
        bot.reply_to(message, 'Sem permissao.')
        return

    document = getattr(message, 'document', None)
    if not document:
        bot.reply_to(message, "Envie o database como arquivo .zip.")
        return

    filename = document.file_name or ''
    if not filename.lower().endswith('.zip'):
        bot.reply_to(message, "Arquivo invalido. Envie um .zip.")
        return

    status_msg = bot.reply_to(message, "Recebi o zip. Baixando e importando com seguranca...")

    try:
        file_info = bot.get_file(document.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        imported, skipped, backup_path = _safe_import_database_zip(file_bytes)

        backup_text = backup_path if backup_path else "backup nao criado"
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=(
                "<b>Database importado com sucesso!</b>\n\n"
                f"<b>Arquivos importados:</b> {imported}\n"
                f"<b>Arquivos ignorados:</b> {skipped}\n"
                f"<b>Backup anterior:</b> <code>{html.escape(str(backup_text))}</code>"
            ),
            parse_mode='HTML'
        )
    except zipfile.BadZipFile:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text="Nao consegui abrir esse arquivo. Confirme se ele e um .zip valido."
        )
    except Exception as e:
        bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"Erro ao importar database: {html.escape(str(e))}",
            parse_mode='HTML'
        )

@bot.message_handler(commands=['importar_database'])
def comando_importar_database(message):
    pedir_importar_database(message)

def _utf16_index_to_py_index(text: str, utf16_index: int) -> int:
    total = 0
    for index, char in enumerate(text):
        if total >= utf16_index:
            return index
        total += len(char.encode('utf-16-le')) // 2
    return len(text)

def _message_text_with_custom_emoji_html(message) -> str:
    text = getattr(message, 'text', None) or getattr(message, 'caption', None) or ''
    entities = []
    entities.extend(getattr(message, 'entities', None) or [])
    entities.extend(getattr(message, 'caption_entities', None) or [])

    replacements = []
    for entity in entities:
        if getattr(entity, 'type', None) != 'custom_emoji':
            continue
        custom_emoji_id = getattr(entity, 'custom_emoji_id', None)
        if not custom_emoji_id:
            continue
        start = _utf16_index_to_py_index(text, int(entity.offset))
        end = _utf16_index_to_py_index(text, int(entity.offset) + int(entity.length))
        fallback = text[start:end] or chr(0x2B50)
        replacements.append((
            start,
            end,
            f'<tg-emoji emoji-id="{html.escape(str(custom_emoji_id))}">{html.escape(fallback)}</tg-emoji>'
        ))

    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text

def _list_text_files():
    try:
        files = [f for f in os.listdir('textos') if f.lower().endswith('.txt')]
        files.sort()
        return files
    except Exception:
        return []

def mostrar_menu_textos(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    files = _list_text_files()
    if not files:
        bot.reply_to(message, 'â€¢ Nenhum arquivo em textos/.')
        return
    markup = InlineKeyboardMarkup()
    rows = []
    for f in files:
        rows.append(InlineKeyboardButton(f"â€¢ {f}", callback_data=f"edit_text_file {f}"))
        if len(rows) == 2:
            markup.row(*rows)
            rows = []
    if rows:
        markup.row(*rows)
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text='â€¢ <b>EDIÃ‡ÃƒO DE TEXTOS</b>\nSelecione um arquivo para editar:',
        parse_mode='HTML',
        reply_markup=markup
    )

def _send_file_preview_and_wait(message, filename):
    path = os.path.join('textos', filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        bot.reply_to(message, f"âœ… Erro ao abrir {filename}: {e}")
        return
    pending_text_edit[message.chat.id] = path
    texto = (
        f"<b>âš™ï¸ Editando:</b> <code>{filename}</code>\n\n"
        f"<b>PrÃ©via atual:</b>\n<code>{html.escape(content)[:3500]}</code>\n\n"
        f"Envie a nova versÃ£o completa deste arquivo em uma Ãºnica mensagem.\n"
        f"Pode enviar emoji premium: eu salvo usando o <code>emoji_id</code> automaticamente.\n"
        f"Use /cancelar para abortar."
    )
    bot.send_message(message.chat.id, texto, parse_mode='HTML')
    bot.register_next_step_handler(message, salvar_texto_editado)

def salvar_texto_editado(message):
    if message.chat.id not in pending_text_edit:
        return
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        pending_text_edit.pop(message.chat.id, None)
        return
    path = pending_text_edit.pop(message.chat.id)
    if (message.text or '').strip() == '/cancelar':
        bot.reply_to(message, "EdiÃ§Ã£o cancelada.")
        return
    content = _message_text_with_custom_emoji_html(message)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        bot.reply_to(message, f"âœ… Arquivo atualizado: <code>{os.path.basename(path)}</code>", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"âœ… Falha ao salvar: {e}")

def _strip_button_color_tag(text: str) -> str:
    return re.sub(
        r'^\s*(?:\[|\{)\s*(?:cor|color|style)\s*:\s*[a-zA-Z_ -]+\s*(?:\]|\})\s*|^\s*<\s*(?:cor|color|style)\s*=\s*["\']?[a-zA-Z_ -]+["\']?\s*>\s*',
        '',
        text or '',
        count=1,
        flags=re.IGNORECASE
    ).strip()

def _extract_button_color(text: str):
    match = re.search(
        r'^\s*(?:\[|\{)\s*(?:cor|color|style)\s*:\s*([a-zA-Z_ -]+)\s*(?:\]|\})|^\s*<\s*(?:cor|color|style)\s*=\s*["\']?([a-zA-Z_ -]+)["\']?\s*>',
        text or '',
        flags=re.IGNORECASE
    )
    if not match:
        return None
    return (match.group(1) or match.group(2) or '').strip().lower()

def _button_color_prefix(color):
    color = (color or '').strip().lower().replace(' ', '_')
    return {
        'verde': chr(0x1F7E9),
        'green': chr(0x1F7E9),
        'azul': chr(0x1F7E6),
        'blue': chr(0x1F7E6),
        'vermelho': chr(0x1F7E5),
        'red': chr(0x1F7E5),
        'cinza': chr(0x2B1C),
        'gray': chr(0x2B1C),
        'grey': chr(0x2B1C),
        'branco': chr(0x2B1C),
        'white': chr(0x2B1C),
    }.get(color)

def _strip_button_color_prefix(text: str) -> str:
    color_markers = ''.join({
        chr(0x1F7E9), chr(0x1F7E6), chr(0x1F7E5), chr(0x2B1C),
        chr(0x1F7E2), chr(0x1F535), chr(0x1F534), chr(0x26AA),
    })
    return re.sub(rf'^[{re.escape(color_markers)}]\s*', '', text or '').strip()

def _compose_button_content(text: str, color=None) -> str:
    clean_text = _strip_button_color_prefix(_strip_button_color_tag(text)).strip()
    if color:
        return f"[cor:{color}] {clean_text}"
    return clean_text

migrate_colored_button_files_to_overrides()

def salvar_botao_editado(message):
    state = pending_button_edit.get(message.chat.id)
    if not state:
        return
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        pending_button_edit.pop(message.chat.id, None)
        return
    if (message.text or '').strip() == '/cancelar':
        pending_button_edit.pop(message.chat.id, None)
        bot.reply_to(message, "EdiÃ§Ã£o cancelada.")
        return

    content = _message_text_with_custom_emoji_html(message).strip()

    try:
        if state.get('kind') == 'service':
            settings = load_service_button_settings()
            setting = settings.setdefault(state['service'], {})
            setting['text'] = content
            if state.get('color'):
                setting['color'] = state['color']
            save_service_button_settings(settings)
            label = state['service']
        else:
            content = _compose_button_content(content, state.get('color'))
            set_button_override(state['filename'], content)
            label = state['filename']
        pending_button_edit.pop(message.chat.id, None)
        bot.reply_to(
            message,
            (
                f"âœ… BotÃ£o atualizado: <code>{html.escape(label)}</code>\n\n"
                "Se vocÃª enviou emoji premium, ele jÃ¡ foi salvo como <code>&lt;tg-emoji&gt;</code> automaticamente."
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        bot.reply_to(message, f"âœ… Falha ao salvar: {e}")

def salvar_cor_botao(message, color):
    state = pending_button_edit.get(message.chat.id)
    if not state:
        bot.send_message(message.chat.id, "Escolha primeiro um botÃ£o para editar.")
        return
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        pending_button_edit.pop(message.chat.id, None)
        return

    new_color = None if color == 'sem_cor' else color
    try:
        if state.get('kind') == 'service_all':
            settings = load_service_button_settings()
            produtos = _get_unique_products()
            for produto in produtos:
                setting = settings.setdefault(produto, {})
                if new_color:
                    setting['color'] = new_color
                else:
                    setting.pop('color', None)
            save_service_button_settings(settings)
            label = f'todos os {len(produtos)} produtos'
        elif state.get('kind') == 'service':
            settings = load_service_button_settings()
            setting = settings.setdefault(state['service'], {})
            if new_color:
                setting['color'] = new_color
            else:
                setting.pop('color', None)
            save_service_button_settings(settings)
            label = state['service']
        else:
            content = _compose_button_content(state.get('text', ''), new_color)
            set_button_override(state['filename'], content)
            label = state['filename']
        pending_button_edit.pop(message.chat.id, None)
        color_label = 'sem cor' if new_color is None else new_color
        bot.send_message(
            message.chat.id,
            f"âœ… Cor atualizada para <b>{html.escape(color_label)}</b> em <code>{html.escape(label)}</code>.",
            parse_mode='HTML'
        )
    except Exception as e:
        bot.reply_to(message, f"âœ… Falha ao salvar: {e}")

# =====================
# Editor de BotÃ©es (botoes/)
# =====================
def _list_botoes_files():
    try:
        files = [f for f in os.listdir('botoes') if f.lower().endswith('.txt')]
        files.sort()
        return files
    except Exception:
        return []

def _button_editor_label(filename: str) -> str:
    path = os.path.join('botoes', filename)
    try:
        override = get_button_override(filename)
        if isinstance(override, str) and override.strip():
            content = override.strip()
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
        label = _strip_button_color_tag(content)
        label = strip_tg_emoji_tags(label)
        label = fix_mojibake_text(label)
        label = re.sub(r'\s+', ' ', label).strip()
        prefix = _button_color_prefix(_extract_button_color(content))
        if prefix:
            label = f"{prefix} {_strip_button_color_prefix(label)}".strip()
        return label or filename
    except Exception:
        return filename

def mostrar_menu_botoes(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    files = _list_botoes_files()
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('ðŸ“¦ BotÃµes dos Produtos', callback_data='edit_service_buttons'))
    rows = []
    for f in files:
        rows.append(InlineKeyboardButton(f"â€¢ {_button_editor_label(f)}", callback_data=f"edit_boto_file {f}"))
        if len(rows) == 2:
            markup.row(*rows)
            rows = []
    if rows:
        markup.row(*rows)
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text='â€¢ <b>EDIÃ‡ÃƒO DE BOTÃ•ES</b>\nSelecione um botÃ£o para editar:',
        parse_mode='HTML',
        reply_markup=markup
    )

def mostrar_menu_botoes_servicos(message):
    produtos = _get_unique_products()
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(
        'ðŸŽ¨ Aplicar Cor em Todos',
        callback_data='service_buttons_color_all'
    ))
    for index, produto in enumerate(produtos):
        setting = service_button_setting(produto)
        prefix = _button_color_prefix(setting.get('color')) or chr(0x25AA)
        markup.row(InlineKeyboardButton(
            f"{prefix} {produto}",
            callback_data=f'edit_service_button {index}'
        ))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='editar_botoes'))
    texto = 'ðŸ“¦ <b>BOTÃ•ES DOS PRODUTOS</b>\n\nSelecione um produto para editar seu texto e sua cor.'
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )

def abrir_editor_botao_servico(message, index):
    produtos = _get_unique_products()
    if index < 0 or index >= len(produtos):
        bot.send_message(message.chat.id, 'Produto nÃ£o encontrado.')
        return
    produto = produtos[index]
    setting = service_button_setting(produto)
    texto_atual = setting.get('text') or '{nome} R${valor}'
    cor_atual = setting.get('color')
    pending_button_edit[message.chat.id] = {
        'kind': 'service',
        'service': produto,
        'filename': produto,
        'color': cor_atual,
        'text': texto_atual,
    }
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœï¸ Alterar Texto', callback_data='boto_action texto'))
    markup.row(InlineKeyboardButton('ðŸŽ¨ Trocar Cor', callback_data='boto_action cor'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='edit_service_buttons'))
    bot.send_message(
        message.chat.id,
        (
            f'<b>Editando produto:</b> <code>{html.escape(produto)}</code>\n\n'
            f'<b>Texto:</b> <code>{html.escape(texto_atual)}</code>\n'
            f'<b>Cor:</b> <code>{html.escape(cor_atual or "padrÃ£o")}</code>\n\n'
            'No texto, use <code>{nome}</code> e <code>{valor}</code> para dados dinÃ¢micos.'
        ),
        parse_mode='HTML',
        reply_markup=markup
    )

def _send_botoes_file_preview_and_wait(message, filename):
    path = os.path.join('botoes', filename)
    try:
        override = get_button_override(filename)
        if isinstance(override, str) and override.strip():
            content = override
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
    except Exception as e:
        bot.reply_to(message, f"âœ… Erro ao abrir {filename}: {e}")
        return
    current_color = _extract_button_color(content)
    preview = _strip_button_color_tag(content)
    pending_button_edit[message.chat.id] = {
        'path': path,
        'filename': filename,
        'color': current_color,
        'text': preview
    }
    color_preview = current_color or 'sem cor'
    texto = (
        f"<b>âš™ï¸ Editando:</b> <code>{filename}</code>\n\n"
        f"<b>PrÃ©via atual:</b>\n<code>{html.escape(preview)[:3500]}</code>\n\n"
        f"<b>Cor atual:</b> <code>{html.escape(color_preview)}</code>\n\n"
        f"Escolha abaixo o que deseja alterar."
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœï¸ Alterar Texto', callback_data='boto_action texto'))
    markup.row(InlineKeyboardButton('ðŸŽ¨ Trocar Cor', callback_data='boto_action cor'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='editar_botoes'))
    bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def mostrar_cores_botao(message):
    state = pending_button_edit.get(message.chat.id)
    if not state:
        bot.send_message(message.chat.id, "Escolha primeiro um botÃ£o para editar.")
        return
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('ðŸŸ¢ Verde', callback_data='boto_color verde'),
        InlineKeyboardButton('ðŸ”µ Azul', callback_data='boto_color azul')
    )
    markup.row(
        InlineKeyboardButton('ðŸ”´ Vermelho', callback_data='boto_color vermelho'),
        InlineKeyboardButton('âšª Cinza', callback_data='boto_color cinza')
    )
    markup.row(InlineKeyboardButton('Sem cor', callback_data='boto_color sem_cor'))
    voltar_callback = (
        'edit_service_buttons'
        if state.get('kind') in ('service', 'service_all')
        else f"edit_boto_file {state['filename']}"
    )
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data=voltar_callback))
    bot.send_message(
        message.chat.id,
        (
            f"<b>Trocar cor:</b> <code>{html.escape(state['filename'])}</code>\n\n"
            "Escolha a cor real de fundo do botÃ£o. Cinza usa o estilo padrÃ£o do Telegram."
        ),
        parse_mode='HTML',
        reply_markup=markup
    )

def pedir_texto_botao(message):
    state = pending_button_edit.get(message.chat.id)
    if not state:
        bot.send_message(message.chat.id, "Escolha primeiro um botÃ£o para editar.")
        return
    color_label = state.get('color') or 'sem cor'
    dica_produto = (
        "Use {nome} e {valor} para manter os dados do produto dinÃ¢micos.\n"
        if state.get('kind') == 'service'
        else ''
    )
    bot.send_message(
        message.chat.id,
        (
            f"<b>Alterar texto:</b> <code>{html.escape(state['filename'])}</code>\n"
            f"Cor serÃ¡ mantida: <code>{html.escape(color_label)}</code>\n\n"
            "Agora envie o novo texto do botÃ£o.\n"
            f"{dica_produto}"
            "Se quiser emoji premium, envie o emoji premium junto no texto que eu puxo o ID automaticamente.\n\n"
            "Use /cancelar para abortar."
        ),
        parse_mode='HTML',
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(message, salvar_botao_editado)

# =====================
# Gerenciar Imagens (icons/)
# =====================
def mostrar_menu_imagens(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('🖼️ Imagens da Mini App', callback_data='miniapp_images_menu'))
    markup.row(InlineKeyboardButton('â€¢ Listar Ã­cones', callback_data='icons_list'))
    markup.row(InlineKeyboardButton('â€¢ Adicionar/Atualizar Ã­cone', callback_data='icons_add'))
    markup.row(InlineKeyboardButton('â€¢ Remover Ã­cone', callback_data='icons_remove'))
    markup.row(InlineKeyboardButton('âš™ï¸ Renomear Ã­cone', callback_data='icons_rename'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text='â€¢ <b>GERENCIAR IMAGENS</b>\nEscolha uma opÃ§Ã£o:',
        parse_mode='HTML',
        reply_markup=markup
    )

def _listar_icones_texto():
    if not os.path.isdir(ICONS_DIR):
        return 'â€¢ A pasta de Ã­cones ainda nÃ£o existe.'
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in os.listdir(ICONS_DIR) if os.path.splitext(f)[1].lower() in exts]
    if not files:
        return 'ðŸ“‹ Nenhum Ã­cone cadastrado em icons/.'
    files.sort()
    lista = "\n".join(f"âœ… {f}" for f in files)
    return f"â€¢ Ã­cones cadastrados ({len(files)}):\n\n{lista}"

def _perguntar_nome_icone_para_upload(message):
    bot.send_message(message.chat.id, 'Envie o NOME do serviÃ§o para associar ao Ã­cone. Depois, envie a FOTO/DOCUMENTO.')
    bot.register_next_step_handler(message, _receber_nome_icone_upload)

def _receber_nome_icone_upload(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    nome = (message.text or '').strip()
    if not nome:
        bot.reply_to(message, 'âœ… Nome invÃ©lido.')
        return
    pending_icon_upload[message.from_user.id] = nome
    bot.reply_to(message, f"OK! Agora envie a FOTO ou DOCUMENTO da logo para: {nome}")

def _perguntar_nome_icone_para_remover(message):
    bot.send_message(message.chat.id, 'Digite o NOME do Ã­cone/serviÃ§o para remover (match por nome normalizado).')
    bot.register_next_step_handler(message, _remover_icone_por_nome)

def _remover_icone_por_nome(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    target = (message.text or '').strip()
    key = _normalize_key(target)
    if not key:
        bot.reply_to(message, 'âœ… Nome invÃ©lido.')
        return
    if not os.path.isdir(ICONS_DIR):
        bot.reply_to(message, 'â€¢ A pasta de Ã­cones ainda nÃ£o existe.')
        return
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    removidos = []
    for fname in list(os.listdir(ICONS_DIR)):
        base, ext = os.path.splitext(fname)
        if ext.lower() not in exts:
            continue
        bkey = _normalize_key(base)
        if not bkey:
            continue
        if bkey in key or key in bkey:
            try:
                os.remove(os.path.join(ICONS_DIR, fname))
                removidos.append(fname)
            except Exception:
                pass
    if removidos:
        lista = "\n".join(f"âœ… {f}" for f in removidos)
        bot.reply_to(message, f"âœ… Removidos {len(removidos)} Ã­cone(s):\n{lista}")
    else:
        bot.reply_to(message, 'âš™ï¸ Nenhum Ã­cone correspondente encontrado para remover.')

def _perguntar_renomear_icone(message):
    bot.send_message(message.chat.id, 'Envie: ANTIGO NOVO (separados por espaÃ©o)')
    bot.register_next_step_handler(message, _renomear_icone_por_nomes)

def _renomear_icone_por_nomes(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, 'âœ… Formato invÃ©lido. Use: ANTIGO NOVO')
        return
    antigo_raw, novo_raw = parts[0].strip(), parts[1].strip()
    old_key = _normalize_key(antigo_raw)
    new_base = _normalize_key(novo_raw)
    if not old_key or not new_base:
        bot.reply_to(message, 'âœ… ParÃ©metros invÃ©lidos para renomear.')
        return
    if not os.path.isdir(ICONS_DIR):
        bot.reply_to(message, 'â€¢ A pasta de Ã­cones ainda nÃ£o existe.')
        return
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    renomes = []
    for fname in list(os.listdir(ICONS_DIR)):
        base, ext = os.path.splitext(fname)
        if ext.lower() not in exts:
            continue
        bkey = _normalize_key(base)
        if not bkey:
            continue
        if old_key in bkey or bkey in old_key:
            candidate = f"{new_base}{ext.lower()}"
            target_path = os.path.join(ICONS_DIR, candidate)
            idx = 1
            while os.path.exists(target_path):
                candidate = f"{new_base}_{idx}{ext.lower()}"
                target_path = os.path.join(ICONS_DIR, candidate)
                idx += 1
            try:
                os.rename(os.path.join(ICONS_DIR, fname), target_path)
                renomes.append((fname, os.path.basename(target_path)))
            except Exception:
                pass
    if renomes:
        linhas = "\n".join(f"âœ… {a}  âœ…  {b}" for a, b in renomes)
        bot.reply_to(message, f"âš™ï¸ Renomeados {len(renomes)} arquivo(s):\n{linhas}")
    else:
        bot.reply_to(message, 'âš™ï¸ Nenhum Ã­cone correspondente encontrado para renomear.')

# =====================
# Gerenciar Emojis Premium por ServiÃ§o
# =====================
def mostrar_menu_emojis_servicos(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    emoji_map = load_raw_service_emoji_map_from_settings()
    if emoji_map:
        linhas = []
        for nome, emoji_id in sorted(emoji_map.items(), key=lambda item: item[0].lower()):
            linhas.append(
                f"â€¢ <b>{html.escape(nome)}</b>: "
                f'<tg-emoji emoji-id="{html.escape(emoji_id)}">â­</tg-emoji> '
                f"<code>{html.escape(emoji_id)}</code>"
            )
        lista = "\n".join(linhas[:30])
        if len(linhas) > 30:
            lista += f"\n\n... e mais {len(linhas) - 30} item(ns)."
    else:
        lista = "Nenhum emoji por serviÃ§o cadastrado ainda."

    texto = (
        "ðŸ˜€ <b>EMOJIS PREMIUM POR SERVIÃ‡O</b>\n\n"
        "Cadastre uma palavra ou nome do serviÃ§o e o emoji premium que ele deve usar nos botÃµes.\n\n"
        "<b>Exemplos:</b>\n"
        "â€¢ <code>netflix</code> aplica em qualquer produto com Netflix no nome.\n"
        "â€¢ <code>globo play</code> aplica em Conta Globo Play, Tela Globo Play, etc.\n\n"
        f"<b>Cadastrados:</b> <code>{len(emoji_map)}</code>\n\n"
        f"{lista}"
    )

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âž• Adicionar/Atualizar', callback_data='service_emoji_add'))
    markup.row(InlineKeyboardButton('ðŸ—‘ Remover', callback_data='service_emoji_remove'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='configuracoes_geral'))
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def perguntar_nome_service_emoji(message):
    bot.send_message(
        message.chat.id,
        (
            "Envie o nome ou palavra do serviÃ§o que vai receber o emoji premium.\n\n"
            "Exemplos: netflix, globo play, disney, prime video\n\n"
            "Use /cancelar para abortar."
        ),
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(message, receber_nome_service_emoji)

def receber_nome_service_emoji(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    nome = (message.text or '').strip()
    if nome == '/cancelar':
        bot.reply_to(message, 'ConfiguraÃ§Ã£o cancelada.')
        return
    if not _normalize_key(nome):
        bot.reply_to(message, 'Nome invÃ¡lido. Envie algo como: netflix')
        return
    pending_service_emoji_name[message.chat.id] = nome
    bot.reply_to(
        message,
        (
            f"Beleza. Agora envie o emoji premium que serÃ¡ usado em <b>{html.escape(nome)}</b>.\n\n"
            "VocÃª tambÃ©m pode enviar direto o ID numÃ©rico do emoji.\n"
            "Use /cancelar para abortar."
        ),
        parse_mode='HTML'
    )
    bot.register_next_step_handler(message, salvar_service_emoji)

def salvar_service_emoji(message):
    if message.chat.id not in pending_service_emoji_name:
        return
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        pending_service_emoji_name.pop(message.chat.id, None)
        return
    if (message.text or '').strip() == '/cancelar':
        pending_service_emoji_name.pop(message.chat.id, None)
        bot.reply_to(message, 'ConfiguraÃ§Ã£o cancelada.')
        return

    nome = pending_service_emoji_name.pop(message.chat.id)
    emoji_id = extract_custom_emoji_id_from_message(message)
    if not emoji_id:
        bot.reply_to(
            message,
            (
                "NÃ£o consegui identificar um emoji premium nessa mensagem.\n\n"
                "Envie o emoji premium sozinho, ou envie o ID numÃ©rico dele."
            )
        )
        return

    emoji_map = load_raw_service_emoji_map_from_settings()
    normalized_name = _normalize_key(nome)
    emoji_map = {
        key: value
        for key, value in emoji_map.items()
        if _normalize_key(key) != normalized_name
    }
    emoji_map[nome] = emoji_id
    save_service_emoji_map(emoji_map)

    bot.reply_to(
        message,
        (
            "âœ… Emoji premium salvo por serviÃ§o!\n\n"
            f"â€¢ ServiÃ§o/palavra: <b>{html.escape(nome)}</b>\n"
            f"â€¢ Emoji: <tg-emoji emoji-id=\"{html.escape(emoji_id)}\">â­</tg-emoji>\n"
            f"â€¢ ID: <code>{html.escape(emoji_id)}</code>"
        ),
        parse_mode='HTML'
    )

def perguntar_remover_service_emoji(message):
    bot.send_message(
        message.chat.id,
        "Envie o nome/palavra do serviÃ§o que deseja remover dos emojis premium.\n\nExemplo: netflix",
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(message, remover_service_emoji)

def remover_service_emoji(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    nome = (message.text or '').strip()
    normalized_name = _normalize_key(nome)
    if not normalized_name:
        bot.reply_to(message, 'Nome invÃ¡lido.')
        return

    emoji_map = load_raw_service_emoji_map_from_settings()
    removidos = [
        key for key in emoji_map
        if _normalize_key(key) == normalized_name
        or _normalize_key(key) in normalized_name
        or normalized_name in _normalize_key(key)
    ]
    for key in removidos:
        emoji_map.pop(key, None)
    save_service_emoji_map(emoji_map)

    if removidos:
        bot.reply_to(message, f"âœ… Removido(s): {', '.join(html.escape(item) for item in removidos)}", parse_mode='HTML')
    else:
        bot.reply_to(message, 'Nenhum emoji por serviÃ§o encontrado com esse nome.')

# =====================
# Gerenciar DescriÃ§Ãµes Personalizadas
# =====================
CUSTOM_DESC_FILE = 'database/custom_descriptions.json'

def _load_custom_descriptions():
    """Carrega as descriÃ§Ãµes personalizadas do arquivo JSON"""
    try:
        if not os.path.exists(CUSTOM_DESC_FILE):
            _save_custom_descriptions({"descriptions": {}})
            return {"descriptions": {}}
        with open(CUSTOM_DESC_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"descriptions": {}}

def _save_custom_descriptions(data):
    """Salva as descriÃ§Ãµes personalizadas no arquivo JSON"""
    try:
        with open(CUSTOM_DESC_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def _get_unique_products():
    """Retorna lista de produtos Ã©nicos do estoque (pelo nome exato)."""
    try:
        produtos_unicos = set()
        servicos = api.ControleLogins.pegar_servicos()
        for servico in servicos:
            produtos_unicos.add(servico['nome'])
        return sorted(list(produtos_unicos))
    except Exception:
        return []

def mostrar_menu_descricoes(message):
    """Exibe o menu de gerenciamento de descriÃ§Ãµes por produto (cada item do estoque)."""
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    produtos = _get_unique_products()
    if not produtos:
        bot.reply_to(message, 'â€¢ Nenhum produto encontrado no estoque.')
        return
    markup = InlineKeyboardMarkup()
    rows = []
    for produto in produtos:
        rows.append(InlineKeyboardButton(f"â€¢ {produto}", callback_data=f"edit_desc_product {produto}"))
        if len(rows) == 2:
            markup.row(*rows)
            rows = []
    if rows:
        markup.row(*rows)
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text='â€¢ <b>GERENCIAR DESCRIÃ‡Ã•ES</b>\nSelecione um produto para definir sua descriÃ§Ã£o personalizada:',
        parse_mode='HTML',
        reply_markup=markup
    )

def _send_description_preview_and_wait(message, produto):
    """Envia a prÃ©via da descriÃ§Ã£o atual do produto e aguarda nova descriÃ§Ã£o."""
    custom_data = _load_custom_descriptions()
    current_desc = custom_data.get("descriptions", {}).get(produto, "Nenhuma descriÃ§Ã£o personalizada definida.")
    pending_description_edit[message.chat.id] = produto
    texto = (
        f"<b>âš™ï¸ Editando descriÃ§Ã£o do produto:</b> <code>{produto}</code>\n\n"
        f"<b>DescriÃ§Ã£o atual:</b>\n<code>{html.escape(current_desc)}</code>\n\n"
        f"Envie a nova descriÃ§Ã£o personalizada para este produto.\n"
        f"Use /cancelar para abortar."
    )
    bot.send_message(message.chat.id, texto, parse_mode='HTML')
    bot.register_next_step_handler(message, salvar_descricao_editada)

def salvar_descricao_editada(message):
    """Salva a nova descriÃ§Ã£o personalizada (por produto exato)."""
    if message.chat.id not in pending_description_edit:
        return
    
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        pending_description_edit.pop(message.chat.id, None)
        return
    
    produto = pending_description_edit.pop(message.chat.id)
    nova_descricao = message.text.strip()
    
    if not nova_descricao:
        bot.reply_to(message, 'âœ… DescriÃ§Ã£o nÃ£o pode estar vazia.')
        return

    # Carrega, atualiza e salva (por nome exato)
    custom_data = _load_custom_descriptions()
    custom_data.setdefault("descriptions", {})
    custom_data["descriptions"][produto] = nova_descricao
    
    if _save_custom_descriptions(custom_data):
        bot.reply_to(message, f"âœ… DescriÃ§Ã£o personalizada salva para: <code>{produto}</code>", parse_mode='HTML')
    else:
        bot.reply_to(message, "âœ… Erro ao salvar a descriÃ§Ã£o.")

def get_custom_description(produto):
    """Retorna a descriÃ§Ã£o personalizada de um produto (nome exato)."""
    custom_data = _load_custom_descriptions()
    return custom_data.get("descriptions", {}).get(produto, None)


def configurar_modo_exibicao(message):
    """Exibe o menu de configuraÃ§Ã£o do modo de exibiÃ§Ã£o."""
    modo_atual = api.CredentialsChange.modo_exibicao()
    
    texto = (
        f'â€¢ <b>CONFIGURAÃ‡ÃƒO DO MODO DE EXIBIÃ‡ÃƒO</b>\n\n'
        f'Modo Atual: <b>{"â€¢ Categorizado" if modo_atual == "categorizado" else "â€¢ Lista Direta"}</b>\n\n'
        f'â€¢ <b>Modo Categorizado:</b>\n'
        f'âœ… Organiza serviÃ§os por categorias (CONTAS COMPLETAS, TELAS DE STREAMINGS, OUTROS ACESSOS)\n'
        f'âœ… Visual mais organizado e profissional\n'
        f'âœ… Facilita navegaÃ§Ã£o para usuÃ¡rios\n\n'
        f'â€¢ <b>Modo Lista Direta:</b>\n'
        f'âœ… Exibe todos os serviÃ§os em uma lista simples\n'
        f'âœ… Acesso mais rÃ©pido aos produtos\n'
        f'âœ… Ideal para catÃ©logos menores\n\n'
        f'Escolha o modo que melhor se adapta ao seu negÃ©cio:'
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(
            'âœ… Modo Categorizado' if modo_atual == 'categorizado' else 'â€¢ Modo Categorizado',
            callback_data='set_modo_categorizado'
        )
    )
    markup.row(
        InlineKeyboardButton(
            'âœ… Modo Lista Direta' if modo_atual == 'lista_direta' else 'â€¢ Modo Lista Direta',
            callback_data='set_modo_lista_direta'
        )
    )
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='configuracoes_geral'))
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        text=texto,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def trocar_suporte(message, idcall):
    suporte = message.text
    api.CredentialsChange.SuporteInfo.mudar_link_suporte(str(suporte))
    bot.answer_callback_query(idcall, text="Suporte alterado com sucesso!", show_alert=True)

def mudar_separador(message, callid):
    sep = message.text
    api.CredentialsChange.mudar_separador(sep)
    bot.answer_callback_query(callid, "Separador alterado com sucesso!", show_alert=True)

def mudar_bot_reserva(message, callid):
    url = message.text.strip()
    if not (url.startswith("https://t.me/") or url.startswith("http://t.me/") or url.startswith("@")):
        bot.reply_to(message, "Envie um link vÃ¡lido, exemplo: https://t.me/seu_bot_reserva ou @seu_bot_reserva")
        return
    if url.startswith("@"):
        url = f"https://t.me/{url[1:]}"
    set_reserve_bot_url(url)
    bot.answer_callback_query(callid, "Bot reserva atualizado com sucesso!", show_alert=True)
    bot.reply_to(message, f"âœ… Bot reserva atualizado:\n{html.escape(url)}", parse_mode='HTML')

def mudar_grupo_reserva(message, callid):
    url = message.text.strip()
    if not (url.startswith("https://t.me/") or url.startswith("http://t.me/") or url.startswith("@")):
        bot.reply_to(message, "Envie um link vÃ¡lido, exemplo: https://t.me/seu_grupo_reserva ou @seu_grupo_reserva")
        return
    if url.startswith("@"):
        url = f"https://t.me/{url[1:]}"
    set_reserve_group_url(url)
    bot.answer_callback_query(callid, "Grupo reserva atualizado com sucesso!", show_alert=True)
    bot.reply_to(message, f"âœ… Grupo reserva atualizado:\n{html.escape(url)}", parse_mode='HTML')

def mudar_id_grupo_reserva(message, callid):
    try:
        group_id = int(message.text.strip())
    except Exception:
        bot.reply_to(message, "Envie apenas o ID numÃ©rico do grupo. Exemplo: -1001234567890")
        return
    set_reserve_group_id(group_id)
    bot.answer_callback_query(callid, "ID do grupo reserva atualizado com sucesso!", show_alert=True)
    bot.reply_to(message, f"âœ… ID do grupo reserva atualizado:\n<code>{group_id}</code>", parse_mode='HTML')

def mudar_emojis_servicos(message, callid):
    link = message.text.strip()
    try:
        pack_name, total = import_service_emoji_pack(link)
    except Exception as e:
        bot.reply_to(
            message,
            f"NÃ£o consegui importar esse pacote.\n\nErro: {html.escape(str(e))}\n\n"
            "Envie um link no formato:\nhttps://t.me/addemoji/seu_pacote",
            parse_mode='HTML'
        )
        return

    bot.answer_callback_query(callid, "Pacote de emojis dos serviÃ§os atualizado!", show_alert=True)
    bot.reply_to(
        message,
        (
            "âœ… Pacote de emojis dos serviÃ§os atualizado!\n\n"
            f"â€¢ Pacote: <code>{html.escape(pack_name)}</code>\n"
            f"â€¢ Emojis encontrados: <code>{total}</code>"
        ),
        parse_mode='HTML'
    )

def perguntar_adicionar_logins_duplicados(chat_id, user_id, duplicados):
    if not duplicados:
        return

    pending_duplicate_logins[user_id] = duplicados
    preview = []
    for item in duplicados[:10]:
        preview.append(
            f"• <b>{html.escape(str(item['nome']))}</b> - <code>{html.escape(str(item['email']))}</code>"
        )
    if len(duplicados) > 10:
        preview.append(f"• ... e mais {len(duplicados) - 10} login(s)")

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('✅ Adicionar mesmo assim', callback_data='dup_login_add'),
        InlineKeyboardButton('❌ Ignorar', callback_data='dup_login_skip')
    )
    bot.send_message(
        chat_id,
        (
            f"⚠️ Encontrei <b>{len(duplicados)}</b> login(s) duplicado(s):\n\n"
            + "\n".join(preview)
            + "\n\nDeseja adicionar mesmo assim?"
        ),
        parse_mode='HTML',
        reply_markup=markup
    )

def adicionar_logins_duplicados_confirmados(user_id):
    duplicados = pending_duplicate_logins.pop(user_id, [])
    adicionados = 0
    notificacoes = {}

    for item in duplicados:
        try:
            if api.ControleLogins.add_login(
                nome=item['nome'],
                valor=item['valor'],
                descricao=item['descricao'],
                email=item['email'],
                senha=item['senha'],
                duracao=item['duracao'],
                force=True
            ):
                adicionados += 1
                notificacoes[item['nome']] = notificacoes.get(item['nome'], 0) + 1
        except Exception as e:
            print(f"[LOGIN] Erro ao forcar login duplicado: {e}")

    if adicionados > 0:
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('adicionar logins duplicados')
        except Exception as e:
            print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
        notificar_abastecimento_estoque(notificacoes)

    return adicionados

@bot.message_handler(func=lambda message: '/addlogin' in message.text.split('===')[0])
def adicionar_login(message):
    
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "â€¢ VocÃª nÃ£o tem permissÃ£o para usar este comando!")
        return

    sep = message.text.strip().split('\n')
    separador = api.CredentialsChange.separador()
    quantity = 0
    notificacoes = {} 
    duplicados_pendentes = []

    for ordem in sep:
        if len(ordem) > 0:
            if message.text.split('===')[0] == '/addlogin':
                try:
                    sp = ordem
                    if len(ordem.split('===')) == 6:
                        s = sp.split('===')
                        servico = s[1].strip()
                        email = s[2].strip()
                        senha = s[3].strip()
                        preco = parse_valor_monetario(s[4])
                        descricao = s[5].strip()
                        adicionado = api.ControleLogins.add_login(
                            nome=servico,
                            valor=preco,
                            descricao=descricao,
                            email=email,
                            senha=senha,
                            duracao='30'
                        )
                        if not adicionado:
                            duplicados_pendentes.append({
                                'nome': servico,
                                'valor': preco,
                                'descricao': descricao,
                                'email': email,
                                'senha': senha,
                                'duracao': '30'
                            })
                            continue
                        quantity += 1
                        notificacoes[servico] = notificacoes.get(servico, 0) + 1
                        
                        # Notificar usuÃ¡rios aguardando este produto
                        try:
                            notificados = notificar_reabastecimento(servico)
                            if notificados > 0:
                                print(f"[NOTIF] {notificados} usuÃ¡rio(s) notificado(s) sobre {servico}")
                        except Exception as e:
                            print(f"[NOTIF] Erro ao notificar: {e}")
                    else:
                        bot.reply_to(message, "Erro ao adicionar, vocÃ© enviou em um formato nÃ£o permitido!")
                except Exception as e:
                    print(e)
                    bot.reply_to(message, "Erro ao adicionar, vocÃ© enviou em um formato nÃ£o permitido!")
            else:
                try:
                    sp = ordem.split(f'{separador}')
                    servico = sp[0].strip()
                    valor_texto = sp[1].strip()
                    descricao = sp[2].strip()
                    email = sp[3].strip()
                    senha = sp[4].strip()
                    duracao = sp[5].strip()
                    if len(sp) == 6:
                        try:
                            valor = parse_valor_monetario(valor_texto)
                        except ValueError:
                            bot.reply_to(
                                message,
                                f'O valor do serviÃ§o {servico} Ã© invÃ¡lido. Use, por exemplo: 12.99 ou 12,99.'
                            )
                            continue
                        adicionado = api.ControleLogins.add_login(
                            nome=servico,
                            valor=valor,
                            descricao=descricao,
                            email=email,
                            senha=senha,
                            duracao=duracao
                        )
                        if not adicionado:
                            duplicados_pendentes.append({
                                'nome': servico,
                                'valor': valor,
                                'descricao': descricao,
                                'email': email,
                                'senha': senha,
                                'duracao': duracao
                            })
                            continue
                        quantity += 1
                        notificacoes[servico] = notificacoes.get(servico, 0) + 1
                    else:
                        bot.reply_to(message, f"Formato invÃ©lido! O login {servico} nÃ£o foi adicionado!")
                except:
                    bot.reply_to(message, "Erro ao adicionar, vocÃ© enviou em um formato nÃ£o permitido!")
    bot.reply_to(message, f"Feito! VocÃª abasteceu <b>{quantity}</b> login(s).", parse_mode='HTML')
    perguntar_adicionar_logins_duplicados(message.chat.id, message.from_user.id, duplicados_pendentes)

    # Atualizar catálogo do miniapp após adicionar logins
    if quantity > 0:
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('atualizar estoque')
        except Exception as e:
            print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")

    notificar_abastecimento_estoque(notificacoes)

@bot.message_handler(func=lambda message: adding_logins.get(message.from_user.id, False) and not message.text.startswith('/'))
def receber_logins(message):
    user_id = message.from_user.id
    if not adding_logins.get(user_id, False):
        return

    login_text = message.text.strip()
    separador = '/'  # Separador conforme mencionado

    # Dividir a mensagem em linhas
    linhas = login_text.split('\n')
    logins_adicionados = 0
    logins_invalidos = 0
    logins_processados = []

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue  # Ignorar linhas vazias

        partes = linha.split(separador)
        if len(partes) != 6:
            logins_invalidos += 1
            bot.reply_to(message, f"âœ… Formato invÃ©lido na linha: `{linha}`\nEnvie no formato: `NOME/VALOR/DESCRIÃ‡ÃƒO/EMAIL/SENHA/DURAÃ‡ÃƒO`", parse_mode='Markdown')
            continue

        # Opcional: Adicionar validaÃ§Ãµes adicionais aqui (e.g., verificar se VALOR Ã© numÃ©rico)

        # Adicionar o login temporariamente
        temp_logins[user_id].append(linha)
        logins_adicionados += 1
        logins_processados.append(linha)

    quantidade_total = len(temp_logins[user_id])

    # Feedback ao administrador
    feedback = f"âœ… Adicionados {logins_adicionados} login(s) com sucesso!"
    if logins_invalidos > 0:
        feedback += f"\nâœ… {logins_invalidos} login(s) com formato invÃ©lido foram ignorados."
    feedback += "\nEnvie mais logins ou envie `/done` para finalizar."

    bot.reply_to(message, feedback, parse_mode='Markdown')

    # Resetar o timer sempre que logins sÃ£o recebidos
    if user_id in add_login_timers:
        add_login_timers[user_id].cancel()

    timer = Timer(300, finalizar_adicao_logins, args=[user_id])
    timer.start()
    add_login_timers[user_id] = timer

def remover_login(message):
    separador = api.CredentialsChange.separador()
    try:
        stri = message.text.strip().split(f'{separador}')
        api.ControleLogins.remover_login(nome=stri[0], email=stri[1])
        bot.reply_to(message, "Removido com sucesso do estoque!")
        
        # Atualizar catálogo do miniapp após remover login
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('remover login do estoque')
        except Exception as e:
            print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
    except:
        bot.reply_to(message, "Erro ao remover o login.")

def remover_por_plataforma(message):
    plat = message.text
    try:
        api.ControleLogins.remover_por_nome(plat)
        bot.reply_to(message, f"Todos os logins de {plat} foram removidos com sucesso!")
        
        # Atualizar catálogo do miniapp após remover logins
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('remover plataforma do estoque')
        except Exception as e:
            print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
    except:
        bot.reply_to(message, 'Erro ao remover os logins...')

def mudar_valor_servico(message):
    try:
        sep = api.CredentialsChange.separador()
        txt = message.text.strip().split(f'{sep}')
        if len(txt) != 2:
            raise ValueError('formato invalido')
        servico = txt[0].strip()
        valor = parse_valor_monetario(txt[1])
        api.ControleLogins.mudar_valor_por_nome(servico, valor)
        bot.reply_to(message, f"O servico {servico} teve seu valor mudado para R${valor:.2f}")
    except (ValueError, IndexError):
        bot.reply_to(message, 'Falha ao mudar o valor. Use, por exemplo: NETFLIX/12.99')

def mudar_valor_todos(message):
    try:
        valor = parse_valor_monetario(message.text)
        api.ControleLogins.mudar_valor_de_todos(valor)
        bot.reply_to(message, f"Valores alterados com sucesso para R${valor:.2f}")
    except ValueError:
        bot.reply_to(message, "Valor invÃ¡lido. Use, por exemplo: 12.99 ou 12,99.")

def _mascarar_senha_estoque(senha):
    senha = str(senha or '')
    if len(senha) <= 2:
        return '*' * len(senha)
    return senha[:1] + ('*' * max(len(senha) - 2, 1)) + senha[-1:]

def pesquisar_estoque_admin(message):
    termo = message.text.strip()
    if not termo:
        bot.reply_to(message, "Envie um nome, email ou palavra da descriÃ§Ã£o para pesquisar.")
        return

    resultados = api.ControleLogins.pesquisar_estoque(termo, limite=30)
    if not resultados:
        bot.reply_to(
            message,
            f"Nenhum login abastecido encontrado para: <code>{html.escape(termo)}</code>",
            parse_mode='HTML'
        )
        return

    linhas = [
        f"🔎 <b>Resultado da pesquisa:</b> <code>{html.escape(termo)}</code>",
        f"<b>{len(resultados)}</b> login(s) encontrado(s).",
        ""
    ]
    for index, acesso in enumerate(resultados, start=1):
        valor = acesso.get('valor', 0)
        try:
            valor_fmt = f"{float(valor):.2f}"
        except (TypeError, ValueError):
            valor_fmt = html.escape(str(valor))
        linhas.append(
            "\n".join([
                f"<b>{index}. {html.escape(str(acesso.get('nome', '')))}</b>",
                f"• Valor: R${valor_fmt}",
                f"• Email: <code>{html.escape(str(acesso.get('email', '')))}</code>",
                f"• Senha: <code>{html.escape(_mascarar_senha_estoque(acesso.get('senha', '')))}</code>",
                f"• DuraÃ§Ã£o: {html.escape(str(acesso.get('duracao', '')))}",
            ])
        )

    texto = "\n\n".join(linhas)
    if len(resultados) >= 30:
        texto += "\n\nMostrei os 30 primeiros resultados. Pesquise algo mais especÃ­fico se precisar."
    bot.reply_to(message, texto, parse_mode='HTML')

def aplicar_cashback_vip(user_id, valor):
    try:
        resultado = api.ClubeVIP.registrar_compra(user_id, valor)
        cashback = float(resultado.get('cashback', 0) or 0)
        if resultado.get('ativo') and cashback > 0:
            bot.send_message(
                user_id,
                (
                    f"👑 <b>Cashback VIP recebido!</b>\n\n"
                    f"• Nível: <b>{html.escape(str(resultado.get('nivel', 'VIP')))}</b>\n"
                    f"• Cashback: <b>R$ {cashback:.2f}</b>\n"
                    f"• Já caiu no seu saldo."
                ),
                parse_mode='HTML'
            )
    except Exception as error:
        print(f"[VIP] Erro ao aplicar cashback: {error}")

def mostrar_clube_vip(call):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(api.Botoes.voltar(), callback_data='perfil'))
    bot.send_message(
        call.message.chat.id,
        api.ClubeVIP.texto_status(call.from_user.id),
        parse_mode='HTML',
        reply_markup=markup
    )

def mostrar_admin_vip(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return

    config = api.ClubeVIP.config()
    status = 'Ativado' if config.get('ativo', True) else 'Desativado'
    texto = (
        "👑 <b>CLUBE VIP - ADMIN</b>\n\n"
        f"Status: <b>{status}</b>\n"
        f"Ciclo: <b>{html.escape(str(config.get('ciclo', 'mensal')))}</b>\n\n"
        "<b>Níveis configurados:</b>\n"
    )
    for index, nivel in enumerate(config.get('niveis', []), start=1):
        texto += (
            f"{index}. {html.escape(str(nivel.get('nome', 'VIP')))} - "
            f"R$ {float(nivel.get('minimo', 0)):.2f} / "
            f"{float(nivel.get('cashback', 0)):.2f}%\n"
        )
    texto += "\nPara editar um nível, toque nele e envie: <code>valor_minimo/cashback</code>"

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('✅ Ativar/Desativar', callback_data='vip_toggle'))
    rows = []
    for index, nivel in enumerate(config.get('niveis', [])):
        rows.append(InlineKeyboardButton(
            str(nivel.get('nome', f'Nível {index + 1}')),
            callback_data=f'vip_edit|{index}'
        ))
        if len(rows) == 2:
            markup.row(*rows)
            rows = []
    if rows:
        markup.row(*rows)
    markup.row(InlineKeyboardButton('✅ Voltar', callback_data='voltar_paineladm'))

    bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def receber_edicao_nivel_vip(message):
    state = pending_vip_level_edit.pop(message.chat.id, None)
    if not state:
        bot.reply_to(message, "Nenhum nível VIP aguardando edição.")
        return
    try:
        partes = re.split(r'[/|;]', message.text.strip())
        if len(partes) != 2:
            raise ValueError
        minimo = parse_valor_monetario(partes[0])
        cashback = parse_valor_monetario(partes[1])
        if cashback < 0 or cashback > 100:
            raise ValueError
        if not api.ClubeVIP.atualizar_nivel(state['index'], minimo, cashback):
            bot.reply_to(message, "Nível VIP não encontrado.")
            return
        bot.reply_to(message, f"✅ Nível atualizado: mínimo R$ {minimo:.2f} e cashback {cashback:.2f}%.")
        mostrar_admin_vip(message)
    except ValueError:
        bot.reply_to(message, "Formato inválido. Envie assim: <code>50/2</code> ou <code>50,00/2,5</code>", parse_mode='HTML')

def configurar_logins(message):
    """
    Exibe o menu de configuraÃ§Ã£o de logins com uma interface melhorada.
    """
    separador = api.CredentialsChange.separador()
    texto = (
        f'â€¢ <b>Logins em Estoque:</b> {api.ControleLogins.estoque_total()}\n\n'
        f'â€¢ <b>Adicionar Login</b>\n'
        f'Envie os logins no seguinte formato:\n'
        f'<code>NOME{separador}VALOR{separador}DESCRICAO{separador}EMAIL{separador}SENHA{separador}DURACAO</code>\n'
        f'Pode adicionar mÃ©ltiplos logins separando por linha.\n\n'
        f'â€¢ <b>Remover Login</b>\n'
        f'Envie o serviÃ§o e o e-mail no formato:\n'
        f'<code>SERVICO{separador}EMAIL</code>\n\n'
        f'â€¢ <b>Remover Todos de uma Plataforma</b>\n'
        f'Envie apenas o nome da plataforma, e todos os logins serÃ©o removidos.\n\n'
        f'â€¢ <b>Zerar Estoque</b>\n'
        f'Remove todos os logins disponÃ©veis.\n\n'
        f'â€¢ <b>Alterar Valor de um ServiÃ©o</b>\n'
        f'Envie o serviÃ§o e o novo valor no formato:\n'
        f'<code>SERVICO{separador}VALOR</code>\n\n'
        f'â€¢ <b>Alterar Valor de Todos</b>\n'
        f'Envie o valor e todos os serviÃ§os serÃ©o ajustados para esse preÃ©o.\n\n'
        f'â€¢ <b>Pesquisar Estoque</b>\n'
        f'Busque por serviÃ§o, email ou descriÃ§Ã£o para ver o que foi abastecido.'
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('ðŸ“‹ Adicionar Login', callback_data='adicionar_login'))
    markup.row(InlineKeyboardButton('🔎 Pesquisar Estoque', callback_data='pesquisar_estoque_admin'))
    markup.row(InlineKeyboardButton('âš™ï¸ Remover Login', callback_data='remover_login'),
               InlineKeyboardButton('âœ… Remover por Plataforma', callback_data='remover_por_plataforma'))
    markup.row(InlineKeyboardButton('â€¢ Zerar Estoque', callback_data='confirmar_zerar_estoque'))
    markup.row(InlineKeyboardButton('â€¢ Alterar Valor do ServiÃ©o', callback_data='mudar_valor_servico'),
               InlineKeyboardButton('â€¢ Alterar Valor de Todos', callback_data='mudar_valor_todos'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        text=texto,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'confirmar_zerar_estoque')
def confirmar_zerar_estoque(call):
    """
    ConfirmaÃ§Ã£o antes de zerar o estoque.
    """
    texto = 'âœ… Tem certeza que deseja zerar todo o estoque? Essa aÃ§Ã£o nÃ£o pode ser desfeita.'
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœ… Sim, Zerar Estoque', callback_data='zerar_estoque'))
    markup.row(InlineKeyboardButton('âœ… Cancelar', callback_data='configurar_logins'))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=texto,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'zerar_estoque')
def zerar_estoque(call):
    """
    Zera completamente o estoque de logins.
    """
    api.ControleLogins.zerar_estoque()  # Chamando a função para zerar o estoque
    
    # Atualizar catálogo do miniapp após zerar estoque
    try:
        atualizar_catalogo_miniapp()
        publicar_miniapp_no_git('zerar estoque')
    except Exception as e:
        print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text='✅ O estoque foi zerado com sucesso!',
        parse_mode='HTML'
    )



def configurar_admins(message):
    texto = (
        f'ðŸ“‹ <b>PAINEL CONFIGURAR ADMIN</b>\n\n'
        f'â€¢ Administradores: {api.Admin.quantidade_admin()}\n'
        f'<i>Use os botÃµes abaixo para fazer as alteraÃ§Ãµes necessÃ¡rias</i>'
    )
    bt = InlineKeyboardButton('âœ… ADICIONAR ADM', callback_data='adicionar_adm')
    bt2 = InlineKeyboardButton('â€¢ REMOVER ADM', callback_data='remover_adm')
    bt3 = InlineKeyboardButton('â€¢ LISTA DE ADM', callback_data='lista_adm')
    bt4 = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_paineladm')
    markup = InlineKeyboardMarkup([[bt], [bt2], [bt3], [bt4]])
    bot.edit_message_text(
        chat_id=message.chat.id,
        text=texto,
        message_id=message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

def adicionar_adm(message):
    try:
        id_admin = message.text
        api.Admin.add_admin(id_admin)
        bot.reply_to(message, f"O usuario: {id_admin} foi feito admin!")
    except:
        bot.reply_to(message, "Erro ao promover para adm.")

def remover_adm(message):
    try:
        id = message.text
        api.Admin.remover_admin(id)
        bot.reply_to(message, f"Adm {id} foi feito um usuario comum novamente.")
    except:
        bot.reply_to(message, "Falha ao remover o adm.")

def exibir_rank_balance(call):
    top_users = rankings.get_top_users_by_balance()
    if top_users:
        medals = ['â€¢', 'â€¢', 'â€¢']
        output = "<b>â€¢ Top 20 UsuÃ©rios por Saldo â€¢</b>\n\n"
        for idx, user in enumerate(top_users):
            medal = medals[idx] if idx < 3 else f"{idx+1}Ã©"
            username = user.get('username') or f"User{user.get('id')}"
            saldo = float(user.get('saldo', 0.0))
            output += f"{medal} <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Saldo:</b> R${saldo:.2f}\n"
        bot.send_message(chat_id=call.message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=call.message.chat.id, text='NÃ©o hÃ© usuÃ¡rios para exibir no ranking.')

def exibir_rank_depositors(call):
    top_depositors = rankings.get_top_depositors()
    if top_depositors:
        output = "<b>â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos â€¢</b>\n\n"
        for idx, user in enumerate(top_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_pagos = float(user.get('total_pagos', 0.0))
            output += f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Total DepÃ©sitos:</b> R${total_pagos:.2f}\n"
        bot.send_message(chat_id=call.message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=call.message.chat.id, text='NÃ©o hÃ© depositadores para exibir no ranking.')

def exibir_rank_products(call):
    top_products = rankings.get_top_products_last_30_days()
    if top_products:
        output = "<b>â€¢ Top 10 Produtos Mais Vendidos (Ã©ltimos 30 dias) â€¢</b>\n\n"
        for idx, (produto, vendas) in enumerate(top_products, start=1):
            output += f"{idx}. <b>{produto}</b> - <b>Vendas:</b> {vendas}\n"
        bot.send_message(chat_id=call.message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=call.message.chat.id, text='Nenhum produto vendido nos Ã©ltimos 30 dias.')

def exibir_rank_recent_depositors(call):
    top_recent_depositors = rankings.get_top_recent_depositors()
    if top_recent_depositors:
        output = "<b>â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos Recentes (Ã©ltimos 30 dias) â€¢</b>\n\n"
        for idx, user in enumerate(top_recent_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_recent_pagos = float(user.get('total_recent_pagos', 0.0))
            output += f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>DepÃ©sitos Recentes:</b> R${total_recent_pagos:.2f}\n"
        bot.send_message(chat_id=call.message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=call.message.chat.id, text='Nenhum depÃ©sito recente registrado nos Ã©ltimos 30 dias.')

def mostrar_menu_rank(call):
    texto = "<b>â€¢ Selecione o tipo de ranking que deseja visualizar:</b>"
    markup = gerar_menu_rankings()   

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )
       
def gerar_menu_rankings(ranking_selecionado=None):
 
    
    tipos_rankings = [
        ('rank_balance', 'â€¢ Top 20 UsuÃ©rios por Saldo'),
        ('rank_depositors', 'â€¢ Top 10 Depositadores'),
        ('rank_products', 'â€¢ Top 10 Produtos Mais Vendidos (30 dias)'),
        ('rank_recent_depositors', 'â€¢ Top 10 Depositadores Recentes (30 dias)')
    ]

    
    icone_selecionado = 'âœ…'
    icone_nao_selecionado = 'â€¢'

     
    botoes = []

    for codigo, descricao in tipos_rankings:
        if codigo == ranking_selecionado:
            icone = icone_selecionado
        else:
            icone = icone_nao_selecionado
        botao = types.InlineKeyboardButton(f"{icone} {descricao}", callback_data=codigo)
        botoes.append([botao])

    
    bt_back = types.InlineKeyboardButton('â€¢ Voltar', callback_data='menu_start')
    botoes.append([bt_back])

    markup = types.InlineKeyboardMarkup(botoes)
    return markup

def atualizar_mensagem_rank(call, ranking_selecionado):
 
     
    if ranking_selecionado == 'rank_balance':
        top_users = rankings.get_top_users_by_balance()
        titulo = "â€¢ Top 20 UsuÃ©rios por Saldo â€¢"
        linhas = []
        for idx, user in enumerate(top_users):
            medal = ['â€¢', 'â€¢', 'â€¢'][idx] if idx < 3 else f"{idx+1}Ã©"
            username = user.get('username') or f"User{user.get('id')}"
            saldo = float(user.get('saldo', 0.0))
            linhas.append(f"{medal} <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Saldo:</b> R${saldo:.2f}")
        conteudo = f"<b>{titulo}</b>\n\n" + "\n".join(linhas)

    elif ranking_selecionado == 'rank_depositors':
        top_depositors = rankings.get_top_depositors()
        titulo = "â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos â€¢"
        linhas = []
        for idx, user in enumerate(top_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_pagos = float(user.get('total_pagos', 0.0))
            linhas.append(f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Total DepÃ©sitos:</b> R${total_pagos:.2f}")
        conteudo = f"<b>{titulo}</b>\n\n" + "\n".join(linhas)

    elif ranking_selecionado == 'rank_products':
        top_products = rankings.get_top_products_last_30_days()
        titulo = "â€¢ Top 10 Produtos Mais Vendidos (Ã©ltimos 30 dias) â€¢"
        linhas = []
        for idx, (produto, vendas) in enumerate(top_products, start=1):
            linhas.append(f"{idx}. <b>{produto}</b> - <b>Vendas:</b> {vendas}")
        conteudo = f"<b>{titulo}</b>\n\n" + "\n".join(linhas)

    elif ranking_selecionado == 'rank_recent_depositors':
        top_recent_depositors = rankings.get_top_recent_depositors()
        titulo = "â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos Recentes (Ã©ltimos 30 dias) â€¢"
        linhas = []
        for idx, user in enumerate(top_recent_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_recent_pagos = float(user.get('total_recent_pagos', 0.0))
            linhas.append(f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>DepÃ©sitos Recentes:</b> R${total_recent_pagos:.2f}")
        conteudo = f"<b>{titulo}</b>\n\n" + "\n".join(linhas)

    else:
        conteudo = "Selecione um tipo de ranking para visualizar."

     
    markup = gerar_menu_rankings(ranking_selecionado)

    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=conteudo,
        parse_mode='HTML',
        reply_markup=markup
    )


def configurar_afiliados(message):
    status = "ON" if api.AfiliadosInfo.status_afiliado() else "OFF"
    percentual = api.AfiliadosInfo.pontos_por_recarga()
    texto = (
        f'👥 <b>CONFIGURAR INDICAÇÕES</b>\n\n'
        f'<b>Status:</b> {status}\n'
        f'<b>Comissão por recarga:</b> {percentual}%\n\n'
        f'Quando um cliente entra pelo link de indicação e faz uma recarga, '
        f'quem indicou recebe essa porcentagem direto no saldo automaticamente.'
    )
    botao_status = InlineKeyboardButton(
        f'Sistema de Indicação: {status}',
        callback_data='mudar_status_afiliados'
    )
    markup = InlineKeyboardMarkup([
        [botao_status],
        [InlineKeyboardButton('Alterar Comissão %', callback_data='pontos_por_recarga')],
        [InlineKeyboardButton('VOLTAR', callback_data='voltar_paineladm')]
    ])
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except ApiTelegramException as error:
        if 'message is not modified' not in str(error).lower():
            bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def mostrar_menu_miniapp_imagens(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    produtos = _get_unique_products()
    image_map = _load_miniapp_images()
    markup = InlineKeyboardMarkup()
    rows = []
    for idx, produto in enumerate(produtos):
        status = '✅' if _miniapp_image_for_service(produto, image_map) else '▫️'
        rows.append(InlineKeyboardButton(f'{status} {produto[:28]}', callback_data=f'miniimg_edit|{idx}'))
        if len(rows) == 2:
            markup.row(*rows)
            rows = []
    if rows:
        markup.row(*rows)
    markup.row(InlineKeyboardButton('🔄 Atualizar catálogo', callback_data='miniimg_refresh_catalog'))
    markup.row(InlineKeyboardButton('✅ Voltar', callback_data='gerenciar_imagens'))
    texto = (
        '🖼️ <b>IMAGENS DA MINI APP</b>\n\n'
        'Escolha o serviço e cadastre uma imagem por link ou enviando a foto/documento.\n'
        'Essas imagens aparecem nos cards do site.'
    )
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def mostrar_acoes_imagem_miniapp(message, produto):
    image_url = _miniapp_image_for_service(produto)
    preview = image_url or 'sem imagem'
    markup = InlineKeyboardMarkup()
    idx = _get_unique_products().index(produto) if produto in _get_unique_products() else -1
    markup.row(InlineKeyboardButton('🔗 Usar link', callback_data=f'miniimg_link|{idx}'))
    markup.row(InlineKeyboardButton('📤 Enviar imagem', callback_data=f'miniimg_upload|{idx}'))
    if image_url:
        markup.row(InlineKeyboardButton('🗑 Remover imagem', callback_data=f'miniimg_remove|{idx}'))
    markup.row(InlineKeyboardButton('✅ Voltar', callback_data='miniapp_images_menu'))
    texto = (
        f'🖼️ <b>Imagem do serviço</b>\n\n'
        f'<b>Serviço:</b> <code>{html.escape(produto)}</code>\n'
        f'<b>Atual:</b> <code>{html.escape(preview)}</code>'
    )
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def perguntar_link_imagem_miniapp(message, produto):
    _set_pending_miniapp_image(message, {'mode': 'link', 'produto': produto})
    bot.send_message(
        message.chat.id,
        f'Envie o link da imagem para:\n<code>{html.escape(produto)}</code>\n\nUse /cancelar para abortar.',
        parse_mode='HTML',
        reply_markup=types.ForceReply()
    )
    bot.register_next_step_handler(message, salvar_link_imagem_miniapp)

def salvar_link_imagem_miniapp(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    if getattr(message, 'content_type', '') in ('photo', 'document'):
        salvar_upload_imagem_miniapp(message)
        return
    state = _get_pending_miniapp_image(message, pop=True)
    if not state or state.get('mode') != 'link':
        return
    link = (message.text or '').strip()
    if not re.match(r'^https?://', link):
        bot.reply_to(message, 'Link inválido. Envie uma URL começando com http:// ou https://.')
        return
    image_map = _load_miniapp_images()
    image_map[state['produto']] = link
    _save_miniapp_images(image_map)
    atualizar_catalogo_miniapp()
    ok, detalhe = publicar_miniapp_no_git(f'imagem {state["produto"]}')
    resposta = (
        f'✅ Imagem salva por link para <b>{html.escape(state["produto"])}</b>.\n'
        f'Link: <code>{html.escape(link)}</code>\n\n'
        f'{html.escape(detalhe)}'
    )
    bot.reply_to(message, resposta, parse_mode='HTML')

def pedir_upload_imagem_miniapp(message, produto):
    _set_pending_miniapp_image(message, {'mode': 'upload', 'produto': produto})
    msg = bot.send_message(
        message.chat.id,
        f'Agora envie a foto ou documento de imagem para:\n<code>{html.escape(produto)}</code>',
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, salvar_upload_imagem_miniapp)

def salvar_upload_imagem_miniapp(message):
    if not _admin_only(message):
        bot.reply_to(message, 'â€¢ Sem permissÃ£o.')
        return
    state = _get_pending_miniapp_image(message, pop=True)
    if not state:
        bot.reply_to(message, 'Nenhuma imagem da Mini App estava aguardando upload. Abra o painel e tente novamente.')
        return
    if message.content_type not in ('photo', 'document'):
        _set_pending_miniapp_image(message, state)
        bot.reply_to(message, 'Envie uma foto ou um documento de imagem.')
        return

    produto = state['produto']
    base_name = _normalize_key(produto) or 'produto'
    file_ext = '.jpg'
    try:
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            file_bytes = bot.download_file(file_info.file_path)
            file_ext = '.jpg'
        else:
            doc = message.document
            if doc.mime_type and not str(doc.mime_type).startswith('image/'):
                _set_pending_miniapp_image(message, state)
                bot.reply_to(message, 'Esse documento não parece ser uma imagem. Envie JPG, PNG ou WEBP.')
                return
            if doc.file_name and '.' in doc.file_name:
                _, ext = os.path.splitext(doc.file_name)
                if ext.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                    file_ext = ext.lower()
            file_info = bot.get_file(doc.file_id)
            file_bytes = bot.download_file(file_info.file_path)

        os.makedirs(MINIAPP_SERVICE_IMAGES_DIR, exist_ok=True)
        filename = f'{base_name}{file_ext}'
        path = os.path.join(MINIAPP_SERVICE_IMAGES_DIR, filename)
        with open(path, 'wb') as f:
            f.write(file_bytes)
        image_map = _load_miniapp_images()
        image_map[produto] = f'assets/service-images/{filename}'
        _save_miniapp_images(image_map)
        atualizar_catalogo_miniapp()
        ok, detalhe = publicar_miniapp_no_git(f'imagem {produto}')
        resposta = (
            f'✅ Imagem salva para <b>{html.escape(produto)}</b>.\n'
            f'Caminho: <code>assets/service-images/{html.escape(filename)}</code>\n\n'
            f'{html.escape(detalhe)}'
        )
        bot.reply_to(message, resposta, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f'Erro ao salvar imagem da Mini App: {e}')

def pontos_por_recarga(message):
    try:
        pontos = float((message.text or '').replace(',', '.'))
        if pontos < 0 or pontos > 100:
            bot.reply_to(message, "Envie uma porcentagem entre 0 e 100.")
            return
        api.AfiliadosInfo.mudar_pontos_por_recarga(pontos)
        bot.reply_to(message, f"Alterado com sucesso! Agora quem indicar ganha {pontos:.2f}% de cada recarga do indicado direto no saldo.")
    except:
        bot.reply_to(message, "Falha ao alterar a comissão, verifique se enviou um número aceitável.")

def pontos_minimo_converter(message):
    try:
        min = message.text
        api.AfiliadosInfo.trocar_minimo_pontos_pra_saldo(min)
        bot.reply_to(message, f"Feito! Agora os usuarios precisam ter {min} pontos para poder converter em saldo.")
    except:
        bot.reply_to(message, f"Erro ao alterar a quantidade de pontos, verifique se enviou um nÃ©mero aceitavel.")

def multiplicador_para_converter(message):
    try:
        mult = message.text
        api.AfiliadosInfo.trocar_multiplicador_pontos(mult)
        bot.reply_to(message, "Multiplicador alterado com sucesso!")
    except:
        bot.reply_to(message, "Falha ao alterar o multiplicador, verifique se enviou um nÃ©mero aceitavel.")

def configurar_usuarios(message):
    texto = (
        f'âœ… â€¢â€¢âš™ï¸ âœ… â€¢â€¢âš™ï¸ âœ…\n'
        f'â€¢ <b>TRANSMITIR A TODOS</b>\n'
        f'âœ… â€¢â€¢âš™ï¸ âœ… â€¢â€¢âš™ï¸ âœ…\n'
        f'Envia uma mensagem para todos os usuÃ¡rios registrados no bot. âš™ï¸\n'
        f'ApÃ©s clicar, envie o texto que quer transmitir ou a foto. Para enviar uma foto com texto, basta colocar '
        f'o texto na legenda da imagem. ðŸ“‹\n'
        f'â€¢â€¢â€¢â€¢â€¢â€¢â€¢ðŸ“‹\n\n'
        f'âœ… â€¢â€¢âš™ï¸ âœ… â€¢â€¢âš™ï¸ âœ…\n'
        f'â€¢ <b>PESQUISAR USUÃ©RIO</b>\n'
        f'âœ… â€¢â€¢âš™ï¸ âœ… â€¢â€¢âš™ï¸ âœ…\n'
        f'Se este usuÃ¡rio estiver registrado no bot, vai abrir as configuraÃ§Ãµes de ediÃ§Ã£o desse usuÃ¡rio. â€¢â€¢\n'
        f'VocÃª poderÃ© editar o saldo, ver o histÃ©rico de compras, e todas as informaÃ§Ãµes dele. â€¢â€¢\n'
        f'â€¢â€¢â€¢â€¢â€¢â€¢â€¢ðŸ“‹'
    )
    bt = InlineKeyboardButton('â€¢ TRANSMITIR A TODOS', callback_data='transmitir_todos')
    bt2 = InlineKeyboardButton('â€¢ PESQUISAR USUARIO', callback_data='pesquisar_usuario')
    bt3 = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_paineladm')
    markup = InlineKeyboardMarkup([[bt], [bt2], [bt3]])
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=texto,
        reply_markup=markup,
        parse_mode='HTML'
    )

import math

enviando_transmissao = False

def atualizar_status_envio(bot, status_message_info, stats):
    """
    Atualiza (edita) a mensagem de status no chat do ADM,
    mostrando quantos foram enviados, bloqueados, etc.
    """
    status_message_id = status_message_info['message_id']
    chat_id = status_message_info['chat_id']

    # Monta texto de status
    status_texto = (
        f"â€¢ Enviando mensagens...\n"
        f"Total de usuÃ¡rios processados: {stats['total_users']}\n"
        f"Mensagens enviadas com sucesso: {stats['mensagens_enviadas']}\n"
        f"UsuÃ©rios que bloquearam o bot: {stats['bloqueados']}\n"
        f"UsuÃ©rios que receberam: {stats['usuarios_recebidos']}\n"
        f"UsuÃ©rios que nÃ£o receberam: {stats['usuarios_nao_recebidos']}"
    )
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=status_texto,
            parse_mode='HTML'
        )
    except:
        pass


def processar_lote_usuarios(
    bot,
    lista_usuarios,
    texto: str or None,
    video_file_path: str or None,
    photo_file_path: str or None,
    markup,
    stats: dict,
    status_message_info: dict
):
    """
    FunÃ§Ã£o que processa (envia) um âœ…chunkâœ… (lote) de usuÃ¡rios.
    Ela atualiza um dicionÃ©rio stats compartilhado, incrementando
    a contagem de envios e bloqueios. Cada envio respeita 1s de delay.
    """
    for filename in lista_usuarios:
        user_id = filename.split('.')[0]

        user_data = load_user_data(user_id)
        if not user_data:
            with stats['lock']:
                stats['total_users'] += 1
                stats['usuarios_nao_recebidos'] += 1
            continue

        with stats['lock']:
            stats['total_users'] += 1

        try:
            if video_file_path:
                with open(video_file_path, 'rb') as video_file:
                    bot.send_video(
                        user_data["id"],
                        video=video_file,
                        caption=texto,
                        parse_mode='HTML',
                        reply_markup=markup,
                        timeout=120
                    )
            elif photo_file_path:
                with open(photo_file_path, 'rb') as photo_file:
                    bot.send_photo(
                        user_data["id"],
                        photo=photo_file,
                        caption=texto,
                        parse_mode='HTML',
                        reply_markup=markup,
                        timeout=120
                    )
            else:
                bot.send_message(
                    user_data["id"],
                    texto,
                    parse_mode='HTML',
                    reply_markup=markup
                )

            with stats['lock']:
                stats['mensagens_enviadas'] += 1
                stats['usuarios_recebidos'] += 1

        except ApiTelegramException as e:
            if "bot was blocked by the user" in str(e) or "user is deactivated" in str(e):

                try:
                    os.remove(os.path.join(USER_DATA_DIR, f"{user_id}.json"))
                except:
                    pass
                with stats['lock']:
                    stats['bloqueados'] += 1
            elif "Too Many Requests" in str(e):
                time.sleep(5)
                pass
            else:
                with stats['lock']:
                    stats['usuarios_nao_recebidos'] += 1
        except:
            with stats['lock']:
                stats['usuarios_nao_recebidos'] += 1

        time.sleep(1)

        with stats['lock']:
            total_enviados = (
                stats['mensagens_enviadas'] +
                stats['usuarios_nao_recebidos'] +
                stats['bloqueados']
            )
            if total_enviados % 50 == 0:
                atualizar_status_envio(bot, status_message_info, stats)

def gerar_menu_principal():
    bt_miniapp = InlineKeyboardButton(
        botao_personalizado('abrir_loja', '🛍️ ABRIR LOJA'),
        web_app=types.WebAppInfo(url=MINIAPP_URL)
    )
    bt_comprar = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('catalogo', 'VER CATÃLOGO'), callback_data='servicos'), 'catalogo')
    bt_addsaldo = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('recarga_pix', 'RECARGA / PIX'), callback_data='addsaldo'), 'pix')
    bt_jogos = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('jogos_hoje', 'JOGOS DE HOJE'), callback_data='jogos_hoje'), 'jogos')
    bt_filmes = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('filmes_alta', 'FILMES EM ALTA'), callback_data='filmes_alta'), 'filmes')

    bt_perfil = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('menu_perfil', 'MEU PERFIL'), callback_data='perfil'), 'perfil')
    bt_suporte = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('menu_suporte', 'SUPORTE'), url=api.CredentialsChange.SuporteInfo.link_suporte()), 'suporte')
    bt_estoque = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('estoque_disponivel', 'ESTOQUE DISPONÃVEL'), callback_data='ver_estoque'), 'estoque')
    bt_grupo_telegram = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('grupo_telegram', 'GRUPO TELEGRAM'), url=JOIN_GROUP_LINK), 'telegram')
    bt_grupo_whatsapp = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('grupo_whatsapp', 'GRUPO WHATSAPP'), url=api.CredentialsChange.SuporteInfo.link_suporte()), 'whatsapp')
    bt_alugar = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('menu_alugar_servidor', 'ALUGAR SERVIDOR'), callback_data='alugar_bot'), 'alugar')
    bt_carrinho = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('carrinho', 'CARRINHO'), callback_data='ver_carrinho'), 'carrinho')
    bt_notificar = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('notificar_reabastecimento', 'NOTIFICAR REABASTECIMENTO'), callback_data='notificar_reabastecimento'), 'notificar')
    bt_pesquisar = set_menu_premium_icon(InlineKeyboardButton(botao_personalizado('pesquisar_logins', 'PESQUISAR LOGINS'), switch_inline_query_current_chat=''), 'pesquisar')
    bt_roleta = InlineKeyboardButton('🎰 ROLETA DA SORTE', callback_data='roleta_sorte')
    bt_indique = InlineKeyboardButton(botao_personalizado('indique_ganhe', '👥 INDIQUE E GANHE'), callback_data='indique_ganhe')

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(bt_miniapp)
    markup.add(bt_comprar)
    markup.add(bt_addsaldo)
    markup.row(bt_perfil, bt_suporte)
    markup.add(bt_jogos)
    markup.add(bt_filmes)
    markup.row(bt_estoque, bt_grupo_telegram)
    markup.row(bt_alugar, bt_grupo_whatsapp)
    markup.row(bt_carrinho, bt_notificar)
    markup.add(bt_indique)
    if roleta_ativa():
        markup.add(bt_roleta)
    markup.add(bt_pesquisar)

    return markup

def markup_inatividade_cliente():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('👨‍💼 Suporte', url=api.CredentialsChange.SuporteInfo.link_suporte()),
        InlineKeyboardButton('🛒 Comprar Agora', callback_data='servicos')
    )
    markup.row(
        InlineKeyboardButton('🛒 Carrinho', callback_data='ver_carrinho'),
        InlineKeyboardButton('👀 Termos', callback_data='termos_inatividade')
    )
    return markup

def texto_inatividade_cliente():
    return (
        "👋 <b>Olá! Vi que você ainda não realizou nenhuma compra.</b>\n\n"
        "Posso te ajudar? Escolha uma das opções abaixo 👇\n\n"
        "🔔 Para receber novidades e lançamentos, use: /alertas"
    )

def enviar_aviso_inatividade_cliente(chat_id):
    return bot.send_message(
        chat_id,
        texto_inatividade_cliente(),
        parse_mode='HTML',
        reply_markup=markup_inatividade_cliente()
    )

@bot.message_handler(commands=['avisar_inativo'])
def comando_avisar_inativo(message):
    if not _admin_only(message):
        bot.reply_to(message, 'Sem permissão.')
        return

    partes = message.text.split(maxsplit=1)
    if len(partes) != 2 or not partes[1].strip().lstrip('-').isdigit():
        bot.reply_to(message, "Use assim: /avisar_inativo ID_DO_CLIENTE")
        return

    try:
        enviar_aviso_inatividade_cliente(int(partes[1].strip()))
        bot.reply_to(message, "Aviso de inatividade enviado.")
    except Exception as e:
        bot.reply_to(message, f"Erro ao enviar aviso: {e}")

def addsaldo(message):
    markup = InlineKeyboardMarkup()
    # Descobre o gateway selecionado
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
        gateway = cred.get('gateway_pagamento', {}).get('selecionada', 'mercado_pago')
    except Exception:
        gateway = 'mercado_pago'
    
    # Verifica se os gateways estÃ©o ativos
    if gateway == 'mercado_pago' or gateway == 'pushinpay' or gateway == 'misticpay':
        if api.CredentialsChange.StatusPix.pix_auto() == True and api.CredentialsChange.StatusPix.pix_manual() == True:
            bt = InlineKeyboardButton(f'{api.Botoes.pix_automatico()}', callback_data='pix_auto')
            bt2 = InlineKeyboardButton(f'{api.Botoes.pix_manual()}', callback_data='pix_manu')
            markup.add(bt2, bt)
        elif api.CredentialsChange.StatusPix.pix_auto() == True and api.CredentialsChange.StatusPix.pix_manual() == False:
            bt = InlineKeyboardButton(f'{api.Botoes.pix_automatico()}', callback_data='pix_auto')
            markup.add(bt)
        elif api.CredentialsChange.StatusPix.pix_auto() == False and api.CredentialsChange.StatusPix.pix_manual() == True:
            bt = InlineKeyboardButton(f'{api.Botoes.pix_manual()}', callback_data='pix_manu')
            markup.add(bt)
        else:
            bt = InlineKeyboardButton('âœ… â€¢â€¢â€¢ â€¢â€¢â€¢ âœ…', callback_data='aoooop')
            markup.add(bt)
    else:
        bt = InlineKeyboardButton('âœ… â€¢â€¢â€¢ â€¢â€¢â€¢ âœ…', callback_data='aoooop')
        markup.add(bt)
    
    bt3 = InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='menu_start')
    markup.add(bt3)
    texto = api.Textos.adicionar_saldo(message)
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except ApiTelegramException as e:
        if "message is not modified" not in str(e).lower():
            raise



def enviar_para_todos_thread(message, texto: str or None, video_file_path: str or None, photo_file_path: str or None, markup):
    status_inicial = (
        f"â€¢ Iniciando envio...\n"
        f"HÃ© {api.Admin.total_users()} usuÃ¡rios registrados.\n"
        f"Isto pode demorar alguns minutos... Por favor, aguarde."
    )
    sent_status_message = bot.send_message(
        chat_id=message.chat.id,
        text=status_inicial,
        parse_mode='HTML'
    )
    status_message_info = {
        'message_id': sent_status_message.message_id,
        'chat_id': message.chat.id
    }

    
    user_files = [f for f in os.listdir(USER_DATA_DIR) if f.endswith('.json')]
    total_users = len(user_files)

   
    stats = {
        'total_users': 0,
        'mensagens_enviadas': 0,
        'bloqueados': 0,
        'usuarios_recebidos': 0,
        'usuarios_nao_recebidos': 0
    }

    batch_size = 500  

    for batch_start in range(0, total_users, batch_size):
        batch = user_files[batch_start:batch_start + batch_size]

        for filename in batch:
            user_id = filename.split('.')[0]
            user_data = load_user_data(user_id)

            if not user_data:
                stats['total_users'] += 1
                stats['usuarios_nao_recebidos'] += 1
                continue

            stats['total_users'] += 1

 
            if texto is not None:
                try:
                    mention = _build_personal_mention(int(user_id))  
                    texto_final = texto.replace('{mention}', mention)
                except Exception:
                    texto_final = texto
            else:
                texto_final = None
           

            try:
                if video_file_path:
                    with open(video_file_path, 'rb') as video_file:
                        bot.send_video(
                            user_data["id"],
                            video=video_file,
                            caption=texto_final,
                            parse_mode='HTML',
                            reply_markup=markup,
                            timeout=120
                        )
                elif photo_file_path:
                    with open(photo_file_path, 'rb') as photo_file:
                        bot.send_photo(
                            user_data["id"],
                            photo=photo_file,
                            caption=texto_final,
                            parse_mode='HTML',
                            reply_markup=markup,
                            timeout=120
                        )
                else:
                    
                    if texto_final is None:
                        
                        stats['usuarios_nao_recebidos'] += 1
                    else:
                        bot.send_message(
                            user_data["id"],
                            texto_final,
                            parse_mode='HTML',
                            reply_markup=markup
                        )

                stats['mensagens_enviadas'] += 1
                stats['usuarios_recebidos'] += 1

            except ApiTelegramException as e:
                if "bot was blocked by the user" in str(e) or "user is deactivated" in str(e):
                    try:
                        os.remove(os.path.join(USER_DATA_DIR, f"{user_id}.json"))
                    except:
                        pass
                    stats['bloqueados'] += 1
                elif "Too Many Requests" in str(e):
                    time.sleep(5)  
                else:
                    stats['usuarios_nao_recebidos'] += 1
            except Exception:
                stats['usuarios_nao_recebidos'] += 1

            time.sleep(1)   

      
        atualizar_status_envio(bot, status_message_info, stats)

      
        if batch_start + batch_size < total_users:
            bot.send_message(message.chat.id, "Aguardando 10 minutos antes de continuar o envio...")
            time.sleep(600)

  
    status_final = (
        f"â€¢ Mensagens enviadas!\n\n"
        f"Total de usuÃ¡rios processados: {stats['total_users']}\n"
        f"Mensagens enviadas com sucesso: {stats['mensagens_enviadas']}\n"
        f"UsuÃ©rios que bloquearam o bot: {stats['bloqueados']}\n"
        f"UsuÃ©rios que receberam: {stats['usuarios_recebidos']}\n"
        f"UsuÃ©rios que nÃ£o receberam: {stats['usuarios_nao_recebidos']}"
    )
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=sent_status_message.message_id,
        text=status_final,
        parse_mode='HTML'
    )

 
    if photo_file_path and os.path.exists(photo_file_path):
        os.remove(photo_file_path)
    if video_file_path and os.path.exists(video_file_path):
        os.remove(video_file_path)


def _categorizar_nome_produto(nome: str) -> str:
    n = nome.upper()
    if 'TELA' in n:
        return 'Telas'
    if 'CONTA' in n:
        return 'Contas'
    return 'Outros'

def _montar_texto_estoque_agrupado() -> str:
    
    servicos = api.ControleLogins.pegar_servicos()   
     

    agreg = {}
    for s in servicos:
        nome = s.get("nome", "").strip()
        if not nome:
            continue
        agreg[nome] = agreg.get(nome, 0) + 1

    grupos = {'Contas': [], 'Telas': [], 'Outros': []}
    for nome, qtd in agreg.items():
        grupos[_categorizar_nome_produto(nome)].append((nome, qtd))

     
    for k in grupos:
        grupos[k].sort(key=lambda x: x[0].upper())

    linhas = []
    linhas.append("Estoque de Logins:\n")

    if grupos['Contas']:
        linhas.append("Contas:")
        for nome, qtd in grupos['Contas']:
            linhas.append(f"{nome}âš™ï¸: {qtd}")
        linhas.append("")   

    if grupos['Telas']:
        linhas.append("Telas:")
        for nome, qtd in grupos['Telas']:
            linhas.append(f"{nome}âš™ï¸: {qtd}")
        linhas.append("")

    if grupos['Outros']:
        linhas.append("Outros:")
        for nome, qtd in grupos['Outros']:
            linhas.append(f"{nome}âš™ï¸: {qtd}")

    return "\n".join(linhas).strip()

def _formatar_bloco_estoque(titulo: str, emoji: str, itens) -> str:
    if not itens:
        return ''
    linhas = [f"{emoji} <b>{html.escape(titulo.upper())}</b>"]
    for nome, qtd in itens:
        nome_limpo = clean_service_button_name(nome).upper()
        emoji_id = streaming_emoji_id_for_service(nome)
        emoji_servico = custom_emoji(emoji_id, chr(0x2B50)) if emoji_id else ''
        prefixo = f'{emoji_servico} ' if emoji_servico else ''
        linhas.append(
            f"{prefixo}<b>{html.escape(nome_limpo)}</b>: <code>{int(qtd)}</code>"
        )
    return "<blockquote>" + "\n".join(linhas) + "</blockquote>"

def _montar_texto_estoque_agrupado() -> str:
    servicos = api.ControleLogins.pegar_servicos()
    agreg = {}
    for servico in servicos:
        nome = str(servico.get("nome", "")).strip()
        if nome:
            agreg[nome] = agreg.get(nome, 0) + 1

    grupos = {'Contas': [], 'Telas': [], 'Outros': []}
    for nome, qtd in agreg.items():
        grupos[_categorizar_nome_produto(nome)].append((nome, qtd))

    for itens in grupos.values():
        itens.sort(key=lambda item: item[0].upper())

    total_itens = sum(qtd for itens in grupos.values() for _, qtd in itens)
    total_servicos = sum(len(itens) for itens in grupos.values())
    linhas = [
        "&#128230; <b>ESTOQUE DISPONIVEL</b>",
        f"&#8226; <b>Produtos:</b> <code>{total_servicos}</code>  &#8226;  <b>Acessos:</b> <code>{total_itens}</code>",
    ]

    blocos = [
        _formatar_bloco_estoque('Contas', '&#128272;', grupos['Contas']),
        _formatar_bloco_estoque('Telas', '&#128421;&#65039;', grupos['Telas']),
        _formatar_bloco_estoque('Outros', '&#128230;', grupos['Outros']),
    ]
    linhas.extend(bloco for bloco in blocos if bloco)

    if len(linhas) == 2:
        linhas.append("<blockquote>&#9888;&#65039; <b>NENHUM SERVICO DISPONIVEL</b></blockquote>")

    return "\n\n".join(linhas).strip()

@bot.callback_query_handler(func=lambda c: c.data == 'ver_estoque')
def ver_estoque(call):
    texto = _montar_texto_estoque_agrupado()
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(botao_personalizado('voltar_menu_estoque', '[cor:vermelho] ↩️ Voltar ao menu'), callback_data='menu_start'))

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=kb
        )
    except:
        bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=kb)

def transmitir_todos(message):
    processando_msg = bot.send_message(message.chat.id, "Processando mÃ©dia... Por favor, aguarde.")
    
     
    if getattr(message, "forward_date", None) is not None:
        user_files = [f for f in os.listdir(USER_DATA_DIR) if f.endswith('.json')]
        for filename in user_files:
            user_id = int(filename.split('.')[0])
            try:
                bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
            except Exception as e:
                print(f"Erro ao encaminhar mensagem para {user_id}: {e}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processando_msg.message_id,
            text="TransmissÃ£o concluÃ©da!"
        )
        return   

    
    api.FuncaoTransmitir.zerar_infos()
    bt = InlineKeyboardButton('âœ… ADD BOTAO âœ…', callback_data='add_botao')
    bt2 = InlineKeyboardButton('âœ… CONFIRMAR ENVIO', callback_data='confirmar_envio')
    markup = InlineKeyboardMarkup([[bt], [bt2]])
    
    if message.content_type == 'video':
        video = message.video.file_id
        video_info = bot.get_file(video)
        video_path = bot.download_file(video_info.file_path)
        video_file_path = os.path.join(os.getcwd(), 'video.mp4')

        with open(video_file_path, 'wb') as new_file:
            new_file.write(video_path)
        
        api.FuncaoTransmitir.adicionar_video(video_file_path)
        api.FuncaoTransmitir.adicionar_texto(message.caption)

        bot.delete_message(message.chat.id, processando_msg.message_id)

        with open(video_file_path, 'rb') as video_file:
            bot.send_video(
                message.chat.id,
                video=video_file,
                caption=message.caption,
                reply_markup=markup,
                parse_mode='HTML',
                timeout=60
            )

    elif message.content_type == 'photo':
        photo = message.photo[-1].file_id
        photo_info = bot.get_file(photo)
        photo_path = bot.download_file(photo_info.file_path)
        photo_file_path = os.path.join(os.getcwd(), 'image.jpg')

        with open(photo_file_path, 'wb') as new_file:
            new_file.write(photo_path)
        
        api.FuncaoTransmitir.adicionar_foto(photo_file_path)
        api.FuncaoTransmitir.adicionar_texto(message.caption)

        bot.delete_message(message.chat.id, processando_msg.message_id)

        with open(photo_file_path, 'rb') as photo_file:
            bot.send_photo(
                message.chat.id,
                photo=photo_file,
                caption=message.caption,
                reply_markup=markup,
                parse_mode='HTML'
            )

    elif message.content_type == 'animation':
        animation = message.animation.file_id
        animation_info = bot.get_file(animation)
        animation_path = bot.download_file(animation_info.file_path)
        animation_file_path = os.path.join(os.getcwd(), 'animation.gif')

        with open(animation_file_path, 'wb') as new_file:
            new_file.write(animation_path)
        
        api.FuncaoTransmitir.adicionar_video(animation_file_path)
        api.FuncaoTransmitir.adicionar_texto(message.caption)

        bot.delete_message(message.chat.id, processando_msg.message_id)

        with open(animation_file_path, 'rb') as animation_file:
            bot.send_animation(
                message.chat.id,
                animation=animation_file,
                caption=message.caption,
                reply_markup=markup,
                parse_mode='HTML'
            )

    elif message.content_type == 'text':
        api.FuncaoTransmitir.adicionar_texto(message.text)

        bot.delete_message(message.chat.id, processando_msg.message_id)
        bot.send_message(
            message.chat.id,
            text=message.text,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.reply_to(message, "Este tipo de mensagem ainda nÃ£o estÃ© disponÃ©vel para transmitir.")

def add_botao(message):
    try:
        text = message.text
        s = text.split('\n')
        markup = InlineKeyboardMarkup()
        for elemento in s:
            botoes = []
            separar = elemento.split('&&')
            for botao in separar:
                sep = botao.split('-')
                nome = sep[0].strip()
                url = sep[1].strip()
                botoes.append(InlineKeyboardButton(f'{nome}', url=f'{url}'))
            markup.row(*botoes)
        api.FuncaoTransmitir.adicionar_markup(markup)
        bt2 = InlineKeyboardButton('âœ… CONFIRMAR ENVIO', callback_data='confirmar_envio')
        markup.row(bt2)
        if markup != None:
            texto = api.FuncaoTransmitir.pegar_texto()
            photo = api.FuncaoTransmitir.pegar_foto()
            if texto != None and photo == None:
                bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode='HTML')
            elif photo != None and texto == None:
                bot.send_photo(message.chat.id, photo, reply_markup=markup, parse_mode='HTML')
            elif photo != None and texto != None:
                bot.send_photo(message.chat.id, photo, caption=texto, reply_markup=markup, parse_mode='HTML')
            else:
                bot.reply_to(message, "Error!")
    except Exception as e:
        bot.reply_to(message, "Ocorreu um erro ao processar, verifique se enviou o nome e a URL no formato correto.")
        print(e)

def confirmar_envio(message):
    texto = api.FuncaoTransmitir.pegar_texto()
    video_file_path = api.FuncaoTransmitir.pegar_video()
    photo_file_path = api.FuncaoTransmitir.pegar_foto()
    markup = api.FuncaoTransmitir.pegar_markup()

    envio_thread = threading.Thread(
        target=enviar_para_todos_thread,
        args=(message, texto, video_file_path, photo_file_path, markup)
    )
    envio_thread.start()

def confirmar_envio(message):
    texto = api.FuncaoTransmitir.pegar_texto()
    video_file_path = api.FuncaoTransmitir.pegar_video()
    photo_file_path = api.FuncaoTransmitir.pegar_foto()
    markup = api.FuncaoTransmitir.pegar_markup()

    envio_thread = threading.Thread(
        target=enviar_para_todos_thread,
        args=(message, texto, video_file_path, photo_file_path, markup)
    )
    envio_thread.start()

def pesquisar_usuario(message):
    """
    Pesquisa um usuÃ¡rio e exibe as informaÃ§Ãµes se encontrado.
    """
    id = message.text.strip()
    if api.InfoUser.verificar_usuario(id):
        status_ban = "â€¢â€¢â€¢? DESBANIR" if api.InfoUser.verificar_ban(id) else "â€¢â€¢â€¢? BANIR"
        callback_ban = "desbanir" if api.InfoUser.verificar_ban(id) else "banir"
        
        texto = (
            f'â€¢ <b>UsuÃ©rio Encontrado</b> âœ…\n\n'
            f'ðŸ“‹ <b>InformaÃ§Ãµes</b>\n'
            f'â€¢ <b>ID:</b> <code>{id}</code>\n'
            f'â€¢ <b>Saldo:</b> <code>R${api.InfoUser.saldo(id):.2f}</code>\n'
            f'â€¢ <b>Acessos Comprados:</b> <code>{api.InfoUser.total_compras(id)}</code>\n'
            f'â€¢ <b>PIX Inseridos:</b> <code>R${api.InfoUser.pix_inseridos(id):.2f}</code>\n'
            f'â€¢ <b>Indicados:</b> <code>{api.InfoUser.quantidade_afiliados(id)}</code>\n'
            f'â€¢ <b>Gift Resgatado:</b> <code>R${api.InfoUser.gifts_resgatados(id):.2f}</code>'
        )
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(status_ban, callback_data=f'{callback_ban} {id}'))
        markup.row(InlineKeyboardButton('â€¢ Alterar Saldo', callback_data=f'mudar_saldo {id}'),
                   InlineKeyboardButton('â€¢ Baixar HistÃ©rico', callback_data=f'baixar_historico {id}'))
        
        bot.send_message(chat_id=message.chat.id, text=texto, parse_mode='HTML', reply_markup=markup)
    else:
        bot.reply_to(message, "âœ… UsuÃ©rio nÃ£o encontrado.")

def mudar_saldo(message, id):
    saldo = message.text
    try:
        api.InfoUser.mudar_saldo(id, saldo)
        bot.reply_to(message, "Saldo alterado com sucesso!")
    except:
        bot.reply_to(message, "Falha ao alterar, verifique se enviou um valor valido.")


def configurar_pix(message):
    texto = (
        f'â€¢ <b>TOKEN MERCADO PAGO:</b> <code>{api.CredentialsChange.InfoPix.token_mp()}</code>\n'
        f'â€¢ <b>DEPÃ©SITO MÃ©NIMO:</b> <code>R${api.CredentialsChange.InfoPix.deposito_minimo_pix():.2f}</code>\n'
        f'âš™ï¸ <b>DEPÃ©SITO MÃ©XIMO:</b> <code>R${api.CredentialsChange.InfoPix.deposito_maximo_pix():.2f}</code>\n'
        f'â€¢ <b>BÃ©NUS DE DEPÃ©SITO:</b> <code>{api.CredentialsChange.BonusPix.quantidade_bonus()}%</code>\n'
        f'â€¢ <b>DEPÃ©SITO MÃ©NIMO PARA GANHAR O BÃ©NUS:</b> R${api.CredentialsChange.BonusPix.valor_minimo_para_bonus():.2f}'
    )
    bt = InlineKeyboardButton('â€¢ PIX MANUAL', callback_data='trocar_pix_manual')
    bt2 = InlineKeyboardButton('â€¢ PIX AUTOMATICO', callback_data='trocar_pix_automatico')
    if api.CredentialsChange.StatusPix.pix_manual() == True:
        bt = InlineKeyboardButton('â€¢ PIX MANUAL', callback_data='trocar_pix_manual')
    if api.CredentialsChange.StatusPix.pix_auto() == True:
        bt2 = InlineKeyboardButton('â€¢ PIX AUTOMATICO', callback_data='trocar_pix_automatico')
    bt3 = InlineKeyboardButton('â€¢ MUDAR TOKEN', callback_data='mudar_token')
    bt4 = InlineKeyboardButton('â€¢ MUDAR DEPOSITO MIN', callback_data='mudar_deposito_minimo')
    bt5 = InlineKeyboardButton('âš™ï¸ MUDAR DEPOSITO MAX', callback_data='mudar_deposito_maximo')
    bt6 = InlineKeyboardButton('â€¢ MUDAR BONUS', callback_data='mudar_bonus')
    bt7 = InlineKeyboardButton('â€¢ MUDAR MIN PARA BONUS', callback_data='mudar_min_bonus')
    bt8 = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_paineladm')
    markup = InlineKeyboardMarkup([[bt, bt2], [bt3], [bt4], [bt5], [bt6], [bt7], [bt8]])
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )

def mudar_token(message):
    try:
        token = message.text
        api.CredentialsChange.InfoPix.mudar_tokenmp(token)
        bot.reply_to(message, "Alterado com sucesso")
    except Exception as e:
        print(e)
        bot.reply_to(message, "Falha ao alterar")

def mudar_deposito_minimo(message):
    try:
        min = message.text
        api.CredentialsChange.InfoPix.trocar_deposito_minimo_pix(min)
        bot.reply_to(message, "Alterado com sucesso!")
    except Exception as e:
        print(e)
        bot.reply_to(message, "Falha ao alterar")

def mudar_deposito_maximo(message):
    try:
        max = message.text
        api.CredentialsChange.InfoPix.trocar_deposito_maximo_pix(max)
        bot.reply_to(message, "Alterado com sucesso")
    except Exception as e:
        print(e)
        bot.reply_to(message, "Falha ao alterar")

def mudar_expiracao(message):
    if message.text.isdigit() == True:
        expiracao = int(message.text)
        if expiracao < 15:
            bot.reply_to(message, "O tempo de expiracao deve ser maior do que 15 minutos!")
            return
        api.CredentialsChange.InfoPix.mudar_expiracao(expiracao)
        bot.reply_to(message, "Alterado com sucesso!")
    else:
        bot.reply_to(message, "Envie apenas digitos!")

def mudar_bonus(message):
    try:
        p = message.text
        p = p.replace('%', '')
        p = p.strip()
        api.CredentialsChange.BonusPix.mudar_quantidade_bonus(p)
        bot.reply_to(message, "Alterado com sucesso!")
    except Exception as e:
        print(e)
        bot.reply_to(message, "Falha ao alterar")

def mudar_min_bonus(message):
    try:
        min = message.text
        api.CredentialsChange.BonusPix.mudar_valor_minimo_para_bonus(min)
        bot.reply_to(message, "Alterado com sucesso")
    except Exception as e:
        print(e)
        bot.reply_to(message, "Falha ao alterar")

def configurar_notificacoes(message):
    quantidade_servico = api.Notificacoes.quantidade_de_servicos_pra_sortear()
    id_min, id_max = api.Notificacoes.min_max_ids()
    texto = (
        f'â€¢ <b>GRUPO ALVO:</b> {api.Notificacoes.id_grupo()}\n\n\n'
        f'â€¢ <b>NOTIFICAÃ‡Ã•ES FAKES CONFIGURAÃ‡Ã•ES</b> âš™ï¸\n\n'
        f'â€¢ <b>IDs aleatÃ³rios:</b> entre <code>{id_min}</code> e <code>{id_max}</code>\n\n'
        f'â€¢ <b>NOTIFICAÃ‡ÃƒO DE RECARGA:</b>\n'
        f'âš™ï¸ <b>Tempo de espera:</b> selecionando entre {api.Notificacoes.tempo_minimo_saldo()} e {api.Notificacoes.tempo_maximo_saldo()} segundos\n'
        f'â€¢ <b>Selecionando aleatoriamente entre: R${api.Notificacoes.min_max_saldo()[0]:.2f} e R${api.Notificacoes.min_max_saldo()[1]:.2f} de saldo.</b>\n\n\n'
        f'â€¢ <b>NOTIFICAÃ‡Ã•ES DE COMPRA:</b>\n'
        f'â€¢ <b>Quantidade de serviÃ§os para selecionar:</b> {quantidade_servico}\n'
        f'âš™ï¸ <b>Tempo de espera:</b> selecionando entre {api.Notificacoes.tempo_minimo_compras()} e {api.Notificacoes.tempo_maximo_compras()} segundos'
    )
    bt = InlineKeyboardButton('â€¢ NOTIFICACOES', callback_data='status_notificacoes')
    if api.Notificacoes.status_notificacoes() == True:
        bt = InlineKeyboardButton('â€¢ NOTIFICACOES', callback_data='status_notificacoes')
    bt2 = InlineKeyboardButton('â€¢ MUDAR GP ALVO', callback_data='mudar_grupo_alvo')
    bt3 = InlineKeyboardButton('âš™ï¸ TEMPO MIN SALDO', callback_data='tempo_min_saldo')
    bt4 = InlineKeyboardButton('âš™ï¸ TEMPO MAX SALDO', callback_data='tempo_max_saldo')
    bt5 = InlineKeyboardButton('â€¢ TROCAR TEXTO', callback_data='trocar_texto_saldo')
    bt6 = InlineKeyboardButton('â€¢ TROCAR MIN MAX SALDO', callback_data='trocar_min_max_saldo')
    bt7 = InlineKeyboardButton('â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢âš™ï¸', callback_data='poooo')
    bt8 = InlineKeyboardButton('âš™ï¸ TEMPO MIN COMPRAS', callback_data='tempo_min_compra')
    bt9 = InlineKeyboardButton('âš™ï¸ TEMPO MAX COMPRAS', callback_data='tempo_max_compra')
    bt10 = InlineKeyboardButton('â€¢ TROCAR TEXTO', callback_data='trocar_texto_compra')
    bt11 = InlineKeyboardButton('â€¢ TROCAR SERVICOS', callback_data='trocar_servicos')
    bt12 = InlineKeyboardButton('â€¢ TROCAR MIN MAX IDS', callback_data='trocar_min_max_ids')
    bt13 = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_paineladm')
    markup = InlineKeyboardMarkup([
        [bt],
        [bt2], [bt3], [bt4], [bt5], [bt6], [bt7], 
        [bt8],[bt9], [bt10], [bt11], [bt12], [bt13]
    ])
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=texto,
        reply_markup=markup,
        parse_mode='HTML'
    )

def tempo_min_saldo(message):
    min = message.text
    api.Notificacoes.trocar_tempo_minimo_saldo(min)
    bot.reply_to(message, "Alterado com sucesso!")

def tempo_max_saldo(message):
    max = message.text
    api.Notificacoes.trocar_tempo_maximo_saldo(max)
    bot.reply_to(message, "Alterado com sucesso!")

def tempo_min_compra(message):
    min = message.text
    api.Notificacoes.trocar_tempo_minimo_compras(min)
    bot.reply_to(message, "Alterado com sucesso!")

def tempo_max_compra(message):
    max = message.text
    api.Notificacoes.trocar_tempo_maximo_compras(max)
    bot.reply_to(message, "Alterado com sucesso!")

def mudar_grupo_alvo(message):
    gp = message.text
    api.Notificacoes.trocar_id_grupo(gp)
    bot.reply_to(message, "Alterado com sucesso.")

def configurar_destinos_reais(message):
    try:
        destino_logs = api.Log.id_log_destino()
    except Exception:
        destino_logs = api.CredentialsChange.id_dono()

    texto = (
        "📣 <b>DESTINOS REAIS DE NOTIFICAÇÃO</b>\n\n"
        f"🛒 <b>Vendas/recargas:</b> <code>{get_sales_notification_chat_id()}</code>\n"
        f"📋 <b>Logs:</b> <code>{destino_logs}</code>\n\n"
        "Altere aqui os canais ou grupos reais onde o bot envia avisos.\n"
        "Para canal/grupo, use o ID completo, geralmente começando com <code>-100</code>."
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('🛒 Alterar Vendas/Recargas', callback_data='alterar_destino_vendas'))
    markup.row(InlineKeyboardButton('📋 Alterar Logs', callback_data='alterar_destino_logs'))
    markup.row(InlineKeyboardButton('✅ Voltar', callback_data='voltar_paineladm'))

    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

def alterar_destino_vendas(message):
    try:
        chat_id = int((message.text or '').strip())
        set_sales_notification_chat_id(chat_id)
        bot.reply_to(message, f"Destino de vendas/recargas alterado para <code>{chat_id}</code>.", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "Falha ao alterar. Envie apenas o ID numérico do canal/grupo.")

def alterar_destino_logs(message):
    try:
        chat_id = int((message.text or '').strip())
        api.Log.mudar_destino_logs(chat_id)
        bot.reply_to(message, f"Destino de logs alterado para <code>{chat_id}</code>.", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "Falha ao alterar. Envie apenas o ID numérico do canal/grupo.")

def trocar_texto_saldo(message):
    txt = message.text
    api.Notificacoes.mudar_texto_saldo(txt)
    bot.reply_to(message, "Alterado com sucesso!")

def trocar_min_max_saldo(message):
    separador = api.CredentialsChange.separador()
    separar = message.text.strip().split(f'{separador}')
    min = separar[0].strip()
    max = separar[1].strip()
    api.Notificacoes.trocar_min_max_saldo(min, max)
    bot.reply_to(message, "Alterado com sucesso!")

def trocar_min_max_ids(message):
    try:
        separador = api.CredentialsChange.separador()
        partes = message.text.strip().split(f'{separador}')
        if len(partes) != 2:
            bot.reply_to(message, f"Envie no formato: ID_MIN{separador}ID_MAX")
            return
        id_min = partes[0].strip()
        id_max = partes[1].strip()
        api.Notificacoes.trocar_min_max_ids(id_min, id_max)
        bot.reply_to(message, "IDs das notificações alterados com sucesso!")
    except Exception:
        bot.reply_to(message, "Falha ao alterar os IDs. Envie apenas números válidos.")

def trocar_texto_compra(message):
    api.Notificacoes.mudar_texto_compra(message.text)
    bot.reply_to(message, "Alterado com sucesso!")

def trocar_servicos(message):
    lista = message.text
    api.Notificacoes.mudar_servicos_random(lista)
    bot.reply_to(message, "Alterado com sucesso")

def enviar_notificacao_saldo():
    while True:
        time.sleep(70)
        if api.Notificacoes.status_notificacoes() == True:
            minimo = int(api.Notificacoes.tempo_minimo_saldo())
            maximo = int(api.Notificacoes.tempo_maximo_saldo())
            texto = api.Notificacoes.texto_notificacao_saldo()
            gp = int(api.Notificacoes.id_grupo())
            try:
                bot.send_message(chat_id=gp, text=texto, parse_mode='HTML')
            except Exception as e:
                print(e)
                pass
            delay = random.randint(minimo, maximo)
            time.sleep(delay)
        else:
            time.sleep(200)

def enviar_notificacao_compra():
    while True:
        time.sleep(60)
        print('tentando enviar')
        if api.Notificacoes.status_notificacoes() == True:
            minimo = int(api.Notificacoes.tempo_minimo_compras())
            maximo = int(api.Notificacoes.tempo_maximo_compras())
            texto = api.Notificacoes.texto_notificacao_compra()
            gp = int(api.Notificacoes.id_grupo())
            try:
                bot.send_message(chat_id=gp, text=texto, parse_mode='HTML')
            except Exception as e:
                print(f"Erro ao enviar notificaÃ§Ã£o para grupo {gp}: {e}")
                pass
            delay = random.randint(minimo, maximo)
            time.sleep(delay)
        else:
            time.sleep(700)

def mostrar_menu_rank(call):
    texto = "<b>â€¢ Selecione o tipo de ranking que deseja visualizar:</b>"
    bt_balance = InlineKeyboardButton('â€¢ Top 20 UsuÃ©rios por Saldo', callback_data='rank_balance')
    bt_depositors = InlineKeyboardButton('â€¢ Top 10 Depositadores', callback_data='rank_depositors')
    bt_products = InlineKeyboardButton('â€¢ Top 10 Produtos Mais Vendidos (30 dias)', callback_data='rank_products')
    bt_recent_depositors = InlineKeyboardButton('â€¢ Top 10 Depositadores Recentes (30 dias)', callback_data='rank_recent_depositors')
    bt_back = InlineKeyboardButton('â€¢ Voltar', callback_data='menu_start')  # BotÃ©o para voltar ao menu principal

    markup = InlineKeyboardMarkup([
        [bt_balance],
        [bt_depositors],
        [bt_products],
        [bt_recent_depositors],
        [bt_back]
    ])

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )
def gift_card(message):
    bt = InlineKeyboardButton('â€¢ GERAR GIFT CARD', switch_inline_query_current_chat='CREATEGIFT 1')
    bt2 = InlineKeyboardButton('â€¢ GERAR VARIOS GIFT â€¢', switch_inline_query_current_chat='CREATEGIFT 1 10')
    bt4 = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_paineladm')
    markup = InlineKeyboardMarkup([[bt], [bt2], [bt4]])
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text='<i>Selecione a opÃ§Ã£o desejada:</i>',
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.inline_handler(lambda query: query.query.startswith('CREATEGIFT '))
def create_gift_card(inline_query):
    if api.Admin.verificar_admin(inline_query.from_user.id) == False and int(api.CredentialsChange.id_dono()) != int(inline_query.from_user.id):
        return
    if len(inline_query.query.split()) == 2:
        value = inline_query.query.split(' ')[1]
        valor, codigo = gerar_gift_card(value)
        txt = api.TextoInline.giftcard(None, codigo, 1, valor)
        title = f"Criar gift card de {value}"
        description = f"Clique aqui para criar um gift card de {value}."
        reply_markup = telebot.types.InlineKeyboardMarkup()
        button_text = "â€¢ Resgatar agora"
        button = telebot.types.InlineKeyboardButton(button_text, callback_data=f'resgatar {codigo}')
        reply_markup.add(button)
        result_id = '1'
        try:
            result = telebot.types.InlineQueryResultArticle(
                id=result_id,
                title=title,
                description=description,
                input_message_content=telebot.types.InputTextMessageContent(txt, parse_mode='HTML'),
                reply_markup=reply_markup,
                thumbnail_url='https://cdn-icons-png.flaticon.com/512/612/612886.png'
            )
        except:
            result = telebot.types.InlineQueryResultArticle(
                id=result_id,
                title=title,
                description=description,
                input_message_content=telebot.types.InputTextMessageContent(txt, parse_mode='HTML'),
                reply_markup=reply_markup,
                thumb_url='https://cdn-icons-png.flaticon.com/512/612/612886.png'
            )
        bot.answer_inline_query(inline_query.id, [result], cache_time=0)
    else:
        value = inline_query.query.split(' ')[1]
        quantidade = inline_query.query.split(' ')[2]
        codigo = gerar_muito_gift(quantidade, value)
        txt = api.TextoInline.giftcard(None, codigo, quantidade, value)
        title = f"Criar {quantidade} gifts cards de R${float(value):.2f}"
        description = f"Clique aqui para criar {quantidade} gift card de R${float(value):.2f}."
        result_id = '3'
        try:
            result = telebot.types.InlineQueryResultArticle(
                id=result_id,
                title=title,
                description=description,
                input_message_content=telebot.types.InputTextMessageContent(txt, parse_mode='HTML'),
                thumbnail_url='https://cdn-icons-png.flaticon.com/512/1261/1261149.png'
            )
        except:
            result = telebot.types.InlineQueryResultArticle(
                id=result_id,
                title=title,
                description=description,
                input_message_content=telebot.types.InputTextMessageContent(txt, parse_mode='HTML'),
                thumb_url='https://cdn-icons-png.flaticon.com/512/1261/1261149.png'
            )
        bot.answer_inline_query(inline_query.id, [result])

def gerar_muito_gift(quantidade, valor):
    codigos = ''
    for i in range(int(quantidade)):
        while True:
            codigo = random.choices(string.ascii_uppercase + string.digits, k=9)
            codigo = ''.join(codigo)
            if api.GiftCard.validar_gift(codigo)[0] == False:
                api.GiftCard.create_gift(codigo, float(valor))
                codigos += f'\n{codigo}'
                break
            else:
                continue
    return codigos

def gerar_gift_card(valor):
    while True:
        codigo = random.choices(string.ascii_uppercase + string.digits, k=9)
        codigo = ''.join(codigo)
        if api.GiftCard.validar_gift(codigo)[0] == False:
            api.GiftCard.create_gift(codigo, float(valor))
            break
        else:
            continue
    return f'R${int(valor)},00', codigo

@bot.inline_handler(lambda query: query.query.startswith('CREATEPIX '))
def create_pix(query):
    if api.Admin.verificar_admin(query.from_user.id) == False and int(api.CredentialsChange.id_dono()) != int(query.from_user.id):
        return
    valor = query.query.split(' ')[1]
    payment = api.CriarPix.gerar(valor, "inline")
    id_pag = payment['response']['id']
    pix_copia_cola = payment['response']['point_of_interaction']['transaction_data']['qr_code']
    txt = api.TextoInline.pix_gerado_inline(valor, pix_copia_cola, id_pag)
    title = f'Criar um pix de R${float(valor):.2f}'
    descricao = f'Clique aqui para gerar um pix de R${float(valor):.2f}'
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(f'{api.Botoes.aguardando_pagamento()}', callback_data='aguardando')]])
    try:
        result = types.InlineQueryResultArticle(
            id='9',
            title=title,
            description=descricao,
            input_message_content=types.InputTextMessageContent(txt, parse_mode='HTML'),
            thumbnail_url='https://devtools.com.br/img/pix/logo-pix-png-icone-520x520.png',
            reply_markup=markup
        )
    except:
        result = types.InlineQueryResultArticle(
            id='9',
            title=title,
            description=descricao,
            input_message_content=types.InputTextMessageContent(txt, parse_mode='HTML'),
            thumb_url='https://devtools.com.br/img/pix/logo-pix-png-icone-520x520.png',
            reply_markup=markup
        )
    bot.answer_inline_query(query.id, [result], cache_time=0)
    verificar_inline_payment(id_pag, valor, query.from_user.id)

def verificar_inline_payment(id_pag, valor, id):
    while True:
        time.sleep(5)
        result = sdk.payment().get(id_pag)
        payment = result["response"]
        status_pag = payment['status']
        if 'approved' in status_pag:
            txt = api.TextoInline.pagamento_aprovado(None, valor, id_pag)
            bot.send_message(chat_id=id, text=txt, parse_mode='HTML')
            break
        elif 'pending' in status_pag:
            continue
        elif 'cancelled' in status_pag:
            bot.send_message(chat_id=id, text=f'Pagamento {id_pag} expirado!', parse_mode='HTML')
            break


@bot.message_handler(commands=['resgatar'])
def redeem_gift(message):
    if api.Admin.verificar_vencimento() == True:
        ver_se_expirou()
        return
    msg = message.text.strip().split()
    if len(msg) != 2:
        bot.reply_to(message, "Erro, envie no formato correto.\nex: /resgatar 1isjue")
        return
    codigo = msg[1]
    processar_resgate(message.chat.id, codigo)

def processar_resgate(id, codigo):
    verif, valor = api.GiftCard.validar_gift(codigo)
    if verif == True:
        api.GiftCard.del_gift(codigo)
        user_data = load_user_data(id)
        if user_data:
            user_data['saldo'] += float(valor)
            save_user_data(id, user_data)
            bot.send_message(
                int(id),
                f'â€¢ <b>ParabÃ©ns!</b>\nVocÃª resgatou o Gift Card com sucesso âœ…\n\nâ€¢ <b>Valor:</b> R${valor:.2f}\nâ€¢ <b>CÃ©digo: </b>{codigo}',
                parse_mode='HTML'
            )
            bot.send_message(
                int(api.CredentialsChange.id_dono()),
                f'âš™ï¸ <b>GIFT CARD RESGATADO</b> â€¢\nUsuario: {id} acabou de resgatar o gift card: {codigo} e obteve um saldo de R${valor:.2f}',
                parse_mode='HTML'
            )
        else:
            bot.send_message(id, "Erro ao processar resgate. UsuÃ©rio nÃ£o encontrado!")
    else:
        bot.send_message(id, "Gift card invalido ou ja resgatado!")
        return


import re
from telebot.types import Message

# FunÃ§Ã£o utilitÃ©ria para reexibir o painel de pagamentos

def exibir_painel_pagamentos(message):
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
    except Exception:
        cred = {}
    gateway = cred.get('gateway_pagamento', {}).get('selecionada', 'mercado_pago')
    token_mp = cred.get('gateway_pagamento', {}).get('mercado_pago', {}).get('token', 'NÃ©o configurado')
    token_pushinpay = cred.get('gateway_pagamento', {}).get('pushinpay', {}).get('token', 'NÃ©o configurado')
    mistic_ci = cred.get('gateway_pagamento', {}).get('misticpay', {}).get('client_id', 'NÃ©o configurado')
    mistic_cs = cred.get('gateway_pagamento', {}).get('misticpay', {}).get('client_secret', 'NÃ©o configurado')
    icon_mp = chr(0x2705) if gateway == "mercado_pago" else ''
    icon_pushinpay = chr(0x2705) if gateway == "pushinpay" else ''
    icon_mistic = chr(0x2705) if gateway == "misticpay" else ''
    texto = (
        f'<b>ConfiguraÃ§Ã£o de Gateways de Pagamento</b>\n\n'
        f'â€¢ <b>Gateway usada para receber pagamentos PIX pelo comando /pix:</b>\n'
        f'âš™ï¸ <b>{gateway.replace("_", " ").title()}</b>\n\n'
        f'<b>Mercado Pago</b> {icon_mp}\nToken:\n<code>{token_mp}</code>\n\n'
        f'<b>PushinPay</b> {icon_pushinpay}\nToken:\n<code>{token_pushinpay}</code>\n\n'
        f'<b>MisticPay</b> {icon_mistic}\nClient ID:\n<code>{mistic_ci}</code>\nClient Secret:\n<code>{mistic_cs}</code>\n\n'
        f'VocÃª pode alterar as credenciais abaixo. A gateway ativa serÃ© usada para receber pagamentos.'
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âš™ï¸ Alterar Token Mercado Pago', callback_data='alterar_token_mp'))
    markup.row(InlineKeyboardButton('âš™ï¸ Alterar Token PushinPay', callback_data='alterar_token_pushinpay'))
    markup.row(InlineKeyboardButton('âš™ï¸ MisticPay Client ID', callback_data='alterar_mistic_ci'), InlineKeyboardButton('âš™ï¸ MisticPay Client Secret', callback_data='alterar_mistic_cs'))
    markup.row(InlineKeyboardButton('âœ… Usar Mercado Pago', callback_data='selecionar_mp'), InlineKeyboardButton('âœ… Usar PushinPay', callback_data='selecionar_pushinpay'))
    markup.row(InlineKeyboardButton('âœ… Usar MisticPay', callback_data='selecionar_misticpay'))
    markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
    bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)

# FunÃ§Ã£o utilitÃ©ria para salvar novo token Mercado Pago
def salvar_novo_token_mp(message):
    novo_token = message.text.strip()
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
    except Exception:
        cred = {}
    if 'gateway_pagamento' not in cred:
        cred['gateway_pagamento'] = {'selecionada': 'mercado_pago', 'mercado_pago': {}}
    if 'mercado_pago' not in cred['gateway_pagamento']:
        cred['gateway_pagamento']['mercado_pago'] = {}
    cred['gateway_pagamento']['mercado_pago']['token'] = novo_token
    try:
        with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
            json.dump(cred, f, ensure_ascii=False, indent=4)
        bot.reply_to(message, 'âœ… Token Mercado Pago atualizado com sucesso!')
        # Reexibe o painel de pagamentos apÃ©s atualizar
        exibir_painel_pagamentos(message)
    except Exception as e:
        bot.reply_to(message, f'âœ… Erro ao salvar token: {e}')

# FunÃ§Ã£o utilitÃ©ria para salvar novo token PushinPay
def salvar_novo_token_pushinpay(message):
    novo_token = message.text.strip()
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
    except Exception:
        cred = {}
    if 'gateway_pagamento' not in cred:
        cred['gateway_pagamento'] = {'selecionada': 'mercado_pago', 'pushinpay': {}}
    if 'pushinpay' not in cred['gateway_pagamento']:
        cred['gateway_pagamento']['pushinpay'] = {}
    cred['gateway_pagamento']['pushinpay']['token'] = novo_token
    try:
        with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
            json.dump(cred, f, ensure_ascii=False, indent=4)
        bot.reply_to(message, 'âœ… Token PushinPay atualizado com sucesso!')
        # Reexibe o painel de pagamentos apÃ©s atualizar
        exibir_painel_pagamentos(message)
    except Exception as e:
        bot.reply_to(message, f'âœ… Erro ao salvar token: {e}')


def salvar_mistic_ci(message):
    novo_ci = message.text.strip()
    api.CredentialsChange.InfoPix.salvar_misticpay(client_id=novo_ci)
    bot.reply_to(message, 'âœ… Client ID da MisticPay atualizado!')
    exibir_painel_pagamentos(message)


def salvar_mistic_cs(message):
    novo_cs = message.text.strip()
    api.CredentialsChange.InfoPix.salvar_misticpay(client_secret=novo_cs)
    bot.reply_to(message, 'âœ… Client Secret da MisticPay atualizado!')
    exibir_painel_pagamentos(message)


@bot.message_handler(commands=['format'])
def formatar_msg(message):
    if api.Admin.verificar_vencimento() == True:
        ver_se_expirou()
        return
    txt = message.text
    txt = txt.replace('\n', '\\n').split()[1:]
    txt = ' '.join(txt)
    print(txt)
    bot.send_message(message.chat.id, txt)

@bot.message_handler(commands=['adicionar_texto'])
def handle_adicionar_texto(message):
    msg = message.text
    msg = msg.replace('/adicionar_texto', '')
    if len(msg.split(f'{api.CredentialsChange.separador()}')) != 3:
        bot.reply_to(
            message,
            f'Formato incorreto! A mensagem deve estar no formato:\nTEXTO{api.CredentialsChange.separador()}NOME DO BOTÃ©O{api.CredentialsChange.separador()}URL DO BOTÃ©O'
        )
        return
    with open('mensagem_transmissora.txt', 'w') as f:
        f.write(msg)
    bot.reply_to(message, "Alterado com sucesso!")

@bot.inline_handler(lambda query: query.query.startswith('MENSAGEM'))
def inline_message(query):
    if api.Admin.verificar_admin(query.from_user.id) == False and int(api.CredentialsChange.id_dono()) != int(query.from_user.id):
        return
    try:
        with open('mensagem_transmissora.txt',  'r') as f:
            data = f.read()
    except:
        with open('mensagem_transmissora.txt',  'w') as f:
            f.write('')
        with open('mensagem_transmissora.txt',  'r') as f:
            data = f.read()
    if len(data) <= 1:
        try:
            result = types.InlineQueryResultArticle(
                id='110',
                title='Defina uma mensagem!',
                description='VocÃª nÃ£o tem nenhuma mensagem registrada, clique aqui e veja as instruÃ§Ãµes.',
                input_message_content=types.InputTextMessageContent(
                    f"Para definir uma mensagem vocÃ© deve usar o seguinte comando neste formato:\n\n"
                    f"<code>/adicionar_texto TEXTO{api.CredentialsChange.separador()}NOME BOTÃ©O{api.CredentialsChange.separador()}URL BOTÃ©O</code>\n\n"
                    f"VocÃª pode usar <a href=\"http://telegram.me/MDtoHTMLbot?start=html\">HTML.</a> "
                    f"ApÃ©s definir o seu texto, basta dar o mesmo comando inline <code>@{api.CredentialsChange.user_bot()} MENSAGEM</code> - "
                    f"Isso vocÃ© pode utilizar em qualquer chat, para enviar uma mensagem com botÃ©o a partir do seu perfil. "
                    f"E para redefinir a mensagem, basta dar o mesmo comando",
                    parse_mode='HTML'
                ),
                thumbnail_url='https://compras.wiki.ufsc.br/images/5/56/Erro.png'
            )
        except:
            result = types.InlineQueryResultArticle(
                id='110',
                title='Defina uma mensagem!',
                description='VocÃª nÃ£o tem nenhuma mensagem registrada, clique aqui e veja as instruÃ§Ãµes.',
                input_message_content=types.InputTextMessageContent(
                    f"Para definir uma mensagem vocÃ© deve usar o seguinte comando neste formato:\n\n"
                    f"<code>/adicionar_texto TEXTO{api.CredentialsChange.separador()}NOME BOTÃ©O{api.CredentialsChange.separador()}URL BOTÃ©O</code>\n\n"
                    f"VocÃª pode usar <a href=\"http://telegram.me/MDtoHTMLbot?start=html\">HTML.</a> "
                    f"ApÃ©s definir o seu texto, basta dar o mesmo comando inline <code>@{api.CredentialsChange.user_bot()} MENSAGEM</code> - "
                    f"Isso vocÃ© pode utilizar em qualquer chat, para enviar uma mensagem com botÃ©o a partir do seu perfil. "
                    f"E para redefinir a mensagem, basta dar o mesmo comando",
                    parse_mode='HTML'
                ),
                thumb_url='https://compras.wiki.ufsc.br/images/5/56/Erro.png'
            )
    else:
        p = data.replace('/adicionar_texto', '')
        p = p.split(f'{api.CredentialsChange.separador()}')
        text = p[0]
        nome_botao = p[1]
        url_botao = p[2]
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(f'{nome_botao}', url=f'{url_botao}')]])
        title = 'Enviar mensagem'
        description = 'Clique aqui para enviar uma mensagem com botÃ©o!'
        try:
            result = types.InlineQueryResultArticle(
                id=str(random.randint(1, 99999)),
                title=title,
                description=description,
                input_message_content=types.InputTextMessageContent(f'{text}', parse_mode='HTML'),
                reply_markup=markup,
                thumbnail_url='https://png.pngtree.com/png-vector/20190217/ourlarge/pngtree-vector-send-message-icon-png-image_558846.jpg'
            )
        except:
            result = types.InlineQueryResultArticle(
                id=str(random.randint(1, 99999)),
                title=title,
                description=description,
                input_message_content=types.InputTextMessageContent(f'{text}', parse_mode='HTML'),
                reply_markup=markup,
                thumb_url='https://png.pngtree.com/png-vector/20190217/ourlarge/pngtree-vector-send-message-icon-png-image_558846.jpg'
            )
    bot.answer_inline_query(query.id, [result], cache_time=0)

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

@bot.message_handler(commands=['start', f'start@{api.CredentialsChange.user_bot()}'])
def handle_start(message):
    if api.Admin.verificar_vencimento():
        ver_se_expirou()
        return

    if not api.InfoUser.verificar_usuario(message.from_user.id):
        api.InfoUser.novo_usuario(message.from_user.id)
        try:
            bot.send_message(
                chat_id=api.CredentialsChange.id_dono(),
                text=api.Log.log_registro(message),
                parse_mode='HTML'
            )
        except Exception as e:
            bot.send_message(api.CredentialsChange.id_dono(), f"Log nÃ£o enviada!\nMotivo: {e}")

    if len(message.text.split()) == 2:
        referral_id = message.text.split()[1]
        if referral_id.isdigit() and referral_id != str(message.from_user.id):
            api.InfoUser.novo_afiliado(message.from_user.id, referral_id)

    if api.InfoUser.verificar_ban(message.from_user.id):
        bot.reply_to(message, "â€¢ VocÃª estÃ© banido deste bot e nÃ£o pode utilizÃ©-lo!")
        return

    if api.CredentialsChange.status_manutencao():
        if not api.Admin.verificar_admin(message.from_user.id):
            if api.CredentialsChange.id_dono() != int(message.from_user.id):
                bot.reply_to(message, "â€¢ O bot estÃ© em manutenÃ§Ã£o, voltaremos em breve!")
                return
        bot.reply_to(message, "â€¢ O bot estÃ¡ em manutenÃ§Ã£o, mas vocÃª foi identificado como administrador!")

    if not ensure_reserve_access(message.from_user.id, message.chat.id):
        return

    start_payload = ''
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            start_payload = parts[1].strip()
    if start_payload.startswith('mc_'):
        if importar_carrinho_miniapp_start(message, start_payload):
            return

    # VERIFICAÃ‡ÃƒO DE PARTICIPAÃ‡ÃƒO OBRIGATÃ“RIA NO GRUPO/CANAL - COMENTADO
    # try:
    #     member_info = bot.get_chat_member(REQUIRED_GROUP_ID, message.from_user.id)
    #     if getattr(member_info, 'status', 'left') in ['left', 'kicked']:
    #         markup = InlineKeyboardMarkup().add(
    #             InlineKeyboardButton("ðŸ‘¥ Entrar no Grupo", url=JOIN_GROUP_LINK)
    #         )
    #         bot.send_message(
    #             message.chat.id,
    #             "âš ï¸ VocÃª precisa participar do nosso grupo para usar o bot.\n\nEntre no grupo abaixo e depois envie /start novamente!",
    #             reply_markup=markup
    #         )
    #         return
    # except ApiTelegramException:
    #     markup = InlineKeyboardMarkup().add(
    #         InlineKeyboardButton("ðŸ‘¥ Entrar no Grupo", url=JOIN_GROUP_LINK)
    #     )
    #     bot.send_message(
    #         message.chat.id,
    #         "âš ï¸ VocÃª precisa participar do nosso grupo para usar o bot.\n\nEntre no grupo abaixo e depois envie /start novamente!",
    #         reply_markup=markup
    #     )
    #     return

    texto = decorate_start_text(message)

    # Usando a funÃ§Ã£o gerar_menu_principal() para os botÃµes
    markup = gerar_menu_principal()

    # Agenda mensagem de follow-up após 5 minutos
    agendar_followup(message.from_user.id)

    if message.from_user.is_bot:
        edit_html_or_plain(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=texto,
            reply_markup=markup
        )
        return

    send_html_or_plain(
        chat_id=message.chat.id,
        text=texto,
        reply_markup=markup
    )

def perfil(call):
    message = call.message
    user = call.from_user
    markup = InlineKeyboardMarkup()
    bt = InlineKeyboardButton(f'{api.Botoes.download_historico()}', callback_data=f'baixar_historico {user.id}')
    markup.add(bt)
    markup.add(InlineKeyboardButton(botao_personalizado('clube_vip', '👑 CLUBE VIP'), callback_data='clube_vip'))
    markup.add(InlineKeyboardButton(botao_personalizado('indique_ganhe', '👥 INDIQUE E GANHE'), callback_data='indique_ganhe'))
    bt3 = InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='menu_start')
    markup.add(bt3)
    texto = api.Textos.perfil(user)

    try:
        fotos = bot.get_user_profile_photos(user.id, limit=1)
        foto = fotos.photos[0][-1].file_id if fotos.total_count and fotos.photos else None
    except Exception:
        foto = None

    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiTelegramException:
        pass

    if foto:
        bot.send_photo(
            chat_id=message.chat.id,
            photo=foto,
            caption=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )

def enviar_menu_inicial(message):
    texto = decorate_start_text(message)   
    markup = gerar_menu_principal()       
    
    send_html_or_plain(
        chat_id=message.chat.id,
        text=texto,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == 'menu_start')
def callback_menu_start(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except ApiTelegramException:
        pass
    enviar_menu_inicial(call.message)


def menu_categorias_servicos(message):
    servicos = api.ControleLogins.pegar_servicos()
    count_conta = count_tela = count_outros = 0
    ja_foram = []
    for servico in servicos:
        nome = servico["nome"]
        if nome not in ja_foram:
            nome_lower = nome.lower()
            if "conta" in nome_lower:
                count_conta += 1
            elif "tela" in nome_lower:
                count_tela += 1
            else:
                count_outros += 1
            ja_foram.append(nome)
    
   
    markup = InlineKeyboardMarkup(row_width=1)
    bt_conta = set_category_button_icon(
        InlineKeyboardButton(f'â€¢CONTAS COMPLETAS   ({count_conta})', callback_data='servicos_categoria conta'),
        'conta'
    )
    bt_tela = set_category_button_icon(
        InlineKeyboardButton(f'â€¢ TELAS DE STREAMINGS ({count_tela})', callback_data='servicos_categoria tela'),
        'tela'
    )
    bt_outros = set_category_button_icon(
        InlineKeyboardButton(f'â€¢ OUTROS ACESSOS({count_outros})', callback_data='servicos_categoria outros'),
        'outros'
    )
    bt_voltar = InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='menu_start')
    markup.add(bt_conta, bt_tela, bt_outros, bt_voltar)
    
    
    gif_url, texto = ler_texto_e_gif("categoriasservicos")
    
    
    try:
        bot.send_animation(
            chat_id=message.chat.id,
            animation=gif_url,
            caption=texto,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        print("Erro ao enviar a animaÃ§Ã£o do menu de categorias:", e)
        
        bot.send_message(
            chat_id=message.chat.id,
            text=texto,
            parse_mode="HTML",
            reply_markup=markup
        )


def ler_texto_e_gif(nome_arquivo):
 
    caminho = os.path.join("textos", f"{nome_arquivo}.txt")
    gif_url = None
    caption = ""
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            gif_url = lines[0].strip()
            caption = "".join(lines[1:]).strip()
    
    if not gif_url:
        gif_url = "https://iili.io/3CvPAFf.gif"
    if not caption:
        caption = (
            "âœ… <b>Selecione a categoria de serviÃ§os:</b> âœ…\n\n"
            "â€¢ Escolha uma opÃ§Ã£o abaixo para visualizar os logins disponÃ©veis!"
        )
    return gif_url, caption

def safe_edit_message(message, new_content, reply_markup=None):
 
    try:
        if getattr(message, 'caption', None) is not None:
            bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_content,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=new_content,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    except Exception as e:
        error_str = str(e).lower()
        if "message is not modified" in error_str:
            
            return
        print("safe_edit_message error:", e)
        bot.send_message(
            chat_id=message.chat.id,
            text=new_content,
            parse_mode='HTML',
            reply_markup=reply_markup
        )


def voltar_menu_servicos(message):
    texto = api.Textos.menu_comprar(message)   
    markup = gerar_menu_principal()            
    safe_edit_message(message, texto, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == 'voltar')
def callback_voltar(call):
    voltar_menu_servicos(call.message)


@bot.callback_query_handler(func=lambda c: c.data == 'configurar_pagamentos' or c.data in ('selecionar_mp', 'selecionar_pushinpay', 'alterar_token_pushinpay', 'alterar_token_mp', 'selecionar_misticpay', 'alterar_mistic_ci', 'alterar_mistic_cs') or c.data.startswith('consultar_pix_pushinpay_'))
def callback_pagamentos(call):
    if call.data.startswith('consultar_pix_pushinpay_'):
        charge_id = call.data.replace('consultar_pix_pushinpay_', '')
        try:
            with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
                cred = json.load(f)
        except Exception:
            cred = {}
        token = cred.get('gateway_pagamento', {}).get('pushinpay', {}).get('token')
        if not token:
            bot.answer_callback_query(call.id, 'Token PushinPay nÃ£o configurado!', show_alert=True)
            return
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        url = f'https://api.pushinpay.com.br/api/transactions/{charge_id}'
        import requests
        try:
            response = requests.get(url, headers=headers)
            print(f'[DEBUG] Consulta status PushinPay: {response.status_code} - {response.text}')
            if response.status_code == 200:
                status = response.json().get('status')
                if status == 'paid':
                    bot.answer_callback_query(call.id, 'âœ… Pagamento confirmado!', show_alert=True)
                else:
                    bot.answer_callback_query(call.id, f'Status atual: {status}', show_alert=True)
            else:
                bot.answer_callback_query(call.id, f'Erro ao consultar status: {response.status_code}', show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f'Erro ao consultar status: {e}', show_alert=True)
        return
    if call.data == 'configurar_pagamentos':
        bot.answer_callback_query(call.id)
        # Carrega o token e gateway do arquivo de credenciais
        try:
            with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
                cred = json.load(f)
        except Exception:
            cred = {}
        gateway = cred.get('gateway_pagamento', {}).get('selecionada', 'mercado_pago')
        token_mp = cred.get('gateway_pagamento', {}).get('mercado_pago', {}).get('token', 'NÃ©o configurado')
        token_pushinpay = cred.get('gateway_pagamento', {}).get('pushinpay', {}).get('token', 'NÃ©o configurado')
        mistic_ci = cred.get('gateway_pagamento', {}).get('misticpay', {}).get('client_id', 'NÃ©o configurado')
        mistic_cs = cred.get('gateway_pagamento', {}).get('misticpay', {}).get('client_secret', 'NÃ©o configurado')
        icon_mp = chr(0x2705) if gateway == "mercado_pago" else ''
        icon_pushinpay = chr(0x2705) if gateway == "pushinpay" else ''
        icon_mistic = chr(0x2705) if gateway == "misticpay" else ''
        texto = (
            f'<b>ConfiguraÃ§Ã£o de Gateways de Pagamento</b>\n\n'
            f'â€¢ <b>Gateway usada para receber pagamentos PIX pelo comando /pix:</b>\n'
            f'âš™ï¸ <b>{gateway.replace("_", " ").title()}</b>\n\n'
            f'<b>Mercado Pago</b> {icon_mp}\nToken:\n<code>{token_mp}</code>\n\n'
            f'<b>PushinPay</b> {icon_pushinpay}\nToken:\n<code>{token_pushinpay}</code>\n\n'
            f'<b>MisticPay</b> {icon_mistic}\nClient ID:\n<code>{mistic_ci}</code>\nClient Secret:\n<code>{mistic_cs}</code>\n\n'
            f'VocÃª pode alterar as credenciais abaixo. A gateway ativa serÃ© usada para receber pagamentos.'
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âš™ï¸ Alterar Token Mercado Pago', callback_data='alterar_token_mp'))
        markup.row(InlineKeyboardButton('âš™ï¸ Alterar Token PushinPay', callback_data='alterar_token_pushinpay'))
        markup.row(InlineKeyboardButton('âš™ï¸ MisticPay Client ID', callback_data='alterar_mistic_ci'), InlineKeyboardButton('âš™ï¸ MisticPay Client Secret', callback_data='alterar_mistic_cs'))
        markup.row(InlineKeyboardButton('âœ… Usar Mercado Pago', callback_data='selecionar_mp'), InlineKeyboardButton('âœ… Usar PushinPay', callback_data='selecionar_pushinpay'))
        markup.row(InlineKeyboardButton('âœ… Usar MisticPay', callback_data='selecionar_misticpay'))
        markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        return
    if call.data == 'selecionar_mp':
        try:
            with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
                cred = json.load(f)
        except Exception:
            cred = {}
        if 'gateway_pagamento' not in cred:
            cred['gateway_pagamento'] = {'selecionada': 'mercado_pago'}
        cred['gateway_pagamento']['selecionada'] = 'mercado_pago'
        with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
            json.dump(cred, f, ensure_ascii=False, indent=4)
        bot.answer_callback_query(call.id, 'Mercado Pago selecionado!', show_alert=True)
        # Reexibe o painel de pagamentos
        exibir_painel_pagamentos(call.message)
        return
    if call.data == 'selecionar_misticpay':
        bot.answer_callback_query(call.id)
        try:
            with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
                cred = json.load(f)
        except Exception:
            cred = {}
        if 'gateway_pagamento' not in cred:
            cred['gateway_pagamento'] = {}
        cred['gateway_pagamento']['selecionada'] = 'misticpay'
        with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
            json.dump(cred, f, ensure_ascii=False, indent=4)
        bot.answer_callback_query(call.id, 'MisticPay selecionada!', show_alert=True)
        exibir_painel_pagamentos(call.message)
        return
    if call.data == 'alterar_mistic_ci':
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, 'Envie o novo Client ID da MisticPay:', reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, salvar_mistic_ci)
        return
    if call.data == 'alterar_mistic_cs':
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, 'Envie o novo Client Secret da MisticPay:', reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, salvar_mistic_cs)
        return
    if call.data == 'selecionar_pushinpay':
        try:
            with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
                cred = json.load(f)
        except Exception:
            cred = {}
        if 'gateway_pagamento' not in cred:
            cred['gateway_pagamento'] = {'selecionada': 'pushinpay'}
        cred['gateway_pagamento']['selecionada'] = 'pushinpay'
        with open('settings/credenciais.json', 'w', encoding='utf-8') as f:
            json.dump(cred, f, ensure_ascii=False, indent=4)
        bot.answer_callback_query(call.id, 'PushinPay selecionado!', show_alert=True)
        # Reexibe o painel de pagamentos
        exibir_painel_pagamentos(call.message)
        return
    if call.data == 'alterar_token_pushinpay':
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Envie o novo token da PushinPay:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, salvar_novo_token_pushinpay)
        return
    if call.data == 'alterar_token_mp':
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Envie o novo token do Mercado Pago:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(msg, salvar_novo_token_mp)
        return



def servicos_por_categoria(message, categoria):

    servicos = api.ControleLogins.pegar_servicos()
    filtered = []
    ja_foram = []
    for servico in servicos:
        nome = servico["nome"]
        if nome not in ja_foram:
            nome_lower = nome.lower()
            if categoria == "conta" and "conta" in nome_lower:
                filtered.append((nome, servico))
                ja_foram.append(nome)
            elif categoria == "tela" and "tela" in nome_lower:
                filtered.append((nome, servico))
                ja_foram.append(nome)
            elif categoria == "outros" and ("conta" not in nome_lower and "tela" not in nome_lower):
                filtered.append((nome, servico))
                ja_foram.append(nome)
    filtered.sort(key=lambda x: x[0])
    
    markup = InlineKeyboardMarkup()
    if not filtered:
        bt = InlineKeyboardButton("âœ… SEM SERVIÃ©OS", callback_data="oookk")
        markup.add(bt)
    else:
        for nome, servico in filtered:
            valor = servico["valor"]
             
            markup.add(configure_service_button(
                InlineKeyboardButton(service_button_text(nome, valor), callback_data=service_callback_data("exibir_servico", nome)),
                nome
            ))
     
    markup.add(InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='menu_categorias_servicos'))
    
    texto = f"<b>ServiÃ©os na categoria {categoria.capitalize()}:</b>"
    
    try:
         
        if hasattr(message, 'caption') and message.caption:
            bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
    except Exception as e:
      
        print("Erro ao editar a mensagem:", e)



def servicos(message):
    servicos = api.ControleLogins.pegar_servicos()
    markup = InlineKeyboardMarkup()
    ja_foram = []
    lista = []
    for servico in servicos:
        if servico["nome"] not in ja_foram:
            nome = servico["nome"]
            valor = servico["valor"]
            lista.append((nome, configure_service_button(
                InlineKeyboardButton(service_button_text(nome, valor), callback_data=service_callback_data("exibir_servico", nome)),
                nome
            )))
            ja_foram.append(nome)
    lista = sorted(lista, key=lambda x: x[0])
    if len(ja_foram) == 0:
        bt = InlineKeyboardButton('âœ… â€¢â€¢â€¢â€¢â€¢âš™ï¸ â€¢â€¢â€¢â€¢â€¢ âœ…', callback_data='oookk')
        markup.add(bt)
    for _, button in lista:
        markup.add(button)
    bt3 = InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='menu_start')
    markup.add(bt3)
    texto = api.Textos.menu_comprar(message)
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=texto,
        parse_mode='HTML',
        reply_markup=markup
    )

def exibir_servico(message, servico):
    texto, email = api.Textos.exibir_servico(message, servico)
    bt_comprar = configure_service_button(InlineKeyboardButton(f'{api.Botoes.comprar_login()}', callback_data=service_callback_data("comprar", servico)), servico)
    bt_comprar_qtd = configure_service_button(InlineKeyboardButton("â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢ â€¢â€¢ â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢ â€¢", callback_data=service_callback_data("comprar_qtd", servico)), servico)
    bt_carrinho = InlineKeyboardButton("â€¢ ADICIONAR AO CARRINHO", callback_data=service_callback_data("add_carrinho", servico))
#   bt_addsaldo = InlineKeyboardButton(f'{api.Botoes.addsaldo()}', callback_data='addsaldo')
    bt_voltar = InlineKeyboardButton(f'{api.Botoes.voltar()}', callback_data='servicos')
    markup = InlineKeyboardMarkup([[bt_comprar], [bt_comprar_qtd], [bt_carrinho], [bt_voltar]])

    # Se houver Ã­cone do serviÃ§o, envia como foto com a legenda do card
    icon_path = _find_icon_for_service(servico)
    if icon_path and os.path.exists(icon_path):
        try:
            # tenta apagar a mensagem anterior (texto/botÃµes) para ficar somente a foto com legenda
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass
            with open(icon_path, 'rb') as photo:
                bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=texto,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            return
        except Exception as e:
            # se falhar, continua para o fallback de texto
            pass

    # Fallback: sem Ã­cone, apenas edita/enviando o texto com botÃµes
    if getattr(message, 'caption', None):
        try:
            bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, text=texto, parse_mode='HTML', reply_markup=markup)
    else:
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception as e:
            bot.send_message(message.chat.id, text=texto, parse_mode='HTML', reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("comprar_qtd"))
def callback_comprar_qtd(call):
   
    if call.data.startswith("comprar_qtd|"):
        servico = resolve_service_callback_token(call.data.split('|', 1)[1])
    else:
        parts = call.data.split(maxsplit=1)
        servico = parts[1] if len(parts) >= 2 else None
    if not servico:
        bot.answer_callback_query(call.id, "ServiÃ©o nÃ£o especificado.", show_alert=True)
        return
    
    # Perguntar o que fazer: adicionar ao carrinho ou comprar direto
    texto = f"â€¢ <b>COMPRAR NA QUANTIDADE</b>\n\n"
    texto += f"â€¢ <b>Produto:</b> {html.escape(servico)}\n\n"
    texto += "O que deseja fazer?"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('â€¢ Adicionar ao Carrinho', callback_data=service_callback_data("qtd_carrinho_ask", servico)))
    markup.row(InlineKeyboardButton('â€¢ Comprar Direto', callback_data=service_callback_data("qtd_comprar_ask", servico)))
    markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data=service_callback_data("exibir_servico", servico)))
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception:
        bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
    
    bot.answer_callback_query(call.id)


def entregar_carrinho(message, nome, valor, email, senha, descricao, duracao):
    """FunÃ§Ã£o para entregar logins comprados via carrinho"""
    import datetime, pytz
    from telebot import types

    data_atual = datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))
    data_atual_formatada = data_atual.strftime("%d/%m/%Y %H:%M:%S")
    data_vencimento = data_atual + datetime.timedelta(days=int(duracao))
    data_vencimento_formatada = data_vencimento.strftime("%d/%m/%Y %H:%M:%S")

    descricao = descricao.replace('\\n', '\n')
    texto = api.Textos.mensagem_comprou(message, nome, valor, email, senha, descricao, duracao)
    texto = texto.replace('{data_sem_horario}', data_atual_formatada)
    texto = texto.replace('{data_vencimento}', data_vencimento_formatada)

    # Adicionar ao histÃ©rico
    api.MudancaHistorico.add_compra(message.chat.id, nome, valor, email, senha)
    aplicar_cashback_vip(message.chat.id, valor)

    # Enviar login para o cliente
    bot.send_message(message.chat.id, texto, parse_mode='HTML')

    # Notificar grupo de vendas
    horario_brasil = data_atual_formatada
    sale_message = (
        f"ðŸ“‹ Nova venda realizada!\n\n"
        f"â€¢ (ID: {message.chat.id})\n"
        f"â€¢ Login: {nome}\n"
        f"â€¢ Valor: R${valor}\n"
        f"â€¢ HorÃ©rio: {horario_brasil}"
    )
    try:
        bot.send_message(get_sales_notification_chat_id(), sale_message, parse_mode='HTML')
    except:
        pass

    # Notificar admin
    try:
        texto_adm = api.Log.log_compra(message, nome, email, senha, valor, descricao)
        texto_adm = texto_adm.replace('{data_sem_horario}', data_atual_formatada)
        texto_adm = texto_adm.replace('{data_vencimento}', data_vencimento_formatada)
        bot.send_message(chat_id=api.CredentialsChange.id_dono(), text=texto_adm, parse_mode='HTML')
    except:
        pass

    # O log da compra jÃ¡ foi gerado acima via api.Log.log_compra(...)


def processar_compra_quantidade(message, servico):
    try:
        quantidade = int(message.text)
    except ValueError:
        bot.reply_to(message, "Por favor, envie um nÃ©mero vÃ©lido.")
        return
    if quantidade <= 0:
        bot.reply_to(message, "Por favor, envie uma quantidade maior que zero.")
        return

    user_id = message.from_user.id

     
    resultado_peek = api.ControleLogins.peek_primeiro_disponivel(servico)
    if not resultado_peek:
        bot.send_message(message.chat.id, f"Acabaram os logins de {servico}.")
        return

  
    _, valor, _, _, _, _ = resultado_peek
    saldo_user = float(api.InfoUser.saldo(user_id))
    total_necessario = quantidade * float(valor)

    if saldo_user < total_necessario:
        bot.send_message(
            message.chat.id,
            f"Saldo insuficiente! VocÃª precisa de R${total_necessario:.2f} para comprar {quantidade} logins, mas possui apenas R${saldo_user:.2f}."
        )
        return

    solicitar_aceite_termos(
        message,
        'quantidade',
        {'servico': servico, 'quantidade': quantidade}
    )
    return


def executar_compra_quantidade(message, user_id, servico, quantidade):
    # Cancela follow-up pois usuário está fazendo compra
    cancelar_followup(user_id)
    
    resultado_peek = api.ControleLogins.peek_primeiro_disponivel(servico)
    if not resultado_peek:
        bot.send_message(message.chat.id, f"Acabaram os logins de {servico}.")
        return

    _, valor, _, _, _, _ = resultado_peek
    saldo_user = float(api.InfoUser.saldo(user_id))
    total_necessario = quantidade * float(valor)
    if saldo_user < total_necessario:
        bot.send_message(
            message.chat.id,
            f"Saldo insuficiente! VocÃª precisa de R${total_necessario:.2f} para comprar {quantidade} logins, mas possui apenas R${saldo_user:.2f}."
        )
        return

    comprados = 0
    for i in range(quantidade):
         
        resultado = api.ControleLogins.pegar_primeiro_disponivel(servico)
        if not resultado:
            bot.send_message(message.chat.id, f"Acabaram os logins de {servico} apÃ©s comprar {comprados}.")
            break

        nome, valor, email, senha, descricao, duracao = resultado

        
        api.InfoUser.tirar_saldo(user_id, valor)
        entregar(message, nome, valor, email, senha, descricao, duracao)
        comprados += 1
        time.sleep(1.0)

    bot.send_message(message.chat.id, f"Compra finalizada. Você comprou {comprados} logins de {servico}.")
    
    # Atualizar catálogo do miniapp após compra
    if comprados > 0:
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('atualizar estoque após compra')
        except Exception as e:
            print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")


def solicitar_aceite_termos(message, tipo_compra, dados):
    user_id = message.chat.id
    pending_terms_purchase[user_id] = {
        'tipo': tipo_compra,
        'dados': dados,
        'criado_em': time.time()
    }

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœ… Li e aceito os termos', callback_data='aceitar_termos_compra'))
    markup.row(InlineKeyboardButton('âŒ Cancelar compra', callback_data='cancelar_termos_compra'))

    texto = (
        f"{termos_texto}\n\n"
        "<b>Para continuar com a compra, confirme que vocÃª leu e aceita os termos acima.</b>"
    )
    bot.send_message(message.chat.id, texto, parse_mode='HTML', reply_markup=markup)


def executar_compra_direta(message, user_id, servico):
    # Cancela follow-up pois usuário está fazendo compra
    cancelar_followup(user_id)
    
    resultado_peek = api.ControleLogins.peek_primeiro_disponivel(servico)
    if not resultado_peek:
        bot.send_message(message.chat.id, "Serviço esgotado ou não encontrado.")
        return

    _, valor, _, _, _, _ = resultado_peek
    if float(api.InfoUser.saldo(user_id)) < float(valor):
        falta = float(valor) - float(api.InfoUser.saldo(user_id))
        bot.send_message(message.chat.id, f"Saldo insuficiente! Faltam R${falta:.2f}.")
        return

    resultado = api.ControleLogins.pegar_primeiro_disponivel(servico)
    if not resultado:
        bot.send_message(message.chat.id, "Serviço esgotado ou não encontrado.")
        return

    nome, valor, email, senha, descricao, duracao = resultado
    api.InfoUser.tirar_saldo(user_id, valor)
    entregar(message, nome, valor, email, senha, descricao, duracao)
    
    # Atualizar catálogo do miniapp após compra
    try:
        atualizar_catalogo_miniapp()
        publicar_miniapp_no_git('atualizar estoque após compra')
    except Exception as e:
        print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")


def executar_compra_carrinho(message, user_id):
    # Cancela follow-up pois usuário está fazendo compra
    cancelar_followup(user_id)
    
    carrinho = database.get_carrinho(user_id)

    if not carrinho:
        bot.send_message(message.chat.id, "Carrinho vazio.")
        return

    total = database.get_carrinho_total(user_id)
    saldo = database.get_user_balance(user_id)

    if saldo < total:
        bot.send_message(
            message.chat.id,
            f"Saldo insuficiente!\nTotal: R$ {total:.2f}\nSeu saldo: R$ {saldo:.2f}"
        )
        return

    try:
        total_comprado = 0

        for item in carrinho:
            servico = item['servico']
            quantidade = item['quantidade']

            for _ in range(quantidade):
                resultado = api.ControleLogins.pegar_primeiro_disponivel(servico)
                if not resultado:
                    bot.send_message(
                        message.chat.id,
                        f"âš™ï¸ Acabaram os logins de {servico} apÃ³s comprar {total_comprado} itens."
                    )
                    break

                nome, valor, email, senha, descricao, duracao = resultado
                api.InfoUser.tirar_saldo(user_id, valor)
                entregar_carrinho(message, nome, valor, email, senha, descricao, duracao)
                total_comprado += 1
                time.sleep(0.5)

        database.clear_carrinho(user_id)

        # Atualizar catálogo do miniapp após compra do carrinho
        if total_comprado > 0:
            try:
                atualizar_catalogo_miniapp()
                publicar_miniapp_no_git('atualizar estoque após compra carrinho')
            except Exception as e:
                print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")

        saldo_atual = database.get_user_balance(user_id)
        texto = "âœ… <b>COMPRA FINALIZADA COM SUCESSO!</b>\n\n"
        texto += f"â€¢ <b>Itens comprados:</b> {total_comprado}\n"
        texto += f"â€¢ <b>Valor total:</b> R$ {total:.2f}\n"
        texto += f"â€¢ <b>Saldo restante:</b> R$ {saldo_atual:.2f}\n\n"
        texto += "âš™ï¸ Os logins foram enviados acima!"

        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Menu Principal', callback_data='voltar_menu'))

        bot.send_message(
            chat_id=message.chat.id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"Erro ao processar compra: {e}")


def executar_compra_inline(user_id, servico):
    resultado_peek = api.ControleLogins.peek_primeiro_disponivel(servico)
    if not resultado_peek:
        bot.send_message(user_id, "ServiÃ§o esgotado ou nÃ£o encontrado.")
        return

    _, valor, _, _, _, _ = resultado_peek
    saldo_user = api.InfoUser.saldo(user_id)
    if float(saldo_user) < float(valor):
        falta = float(valor) - float(saldo_user)
        bot.send_message(user_id, f"Saldo insuficiente! Faltam R${falta:.2f}.")
        return

    resultado = api.ControleLogins.pegar_primeiro_disponivel(servico)
    if not resultado:
        bot.send_message(user_id, "ServiÃ§o esgotado ou nÃ£o encontrado.")
        return

    nome, valor, email, senha, descricao, duracao = resultado
    api.InfoUser.tirar_saldo(user_id, valor)
    entregar_inline_mesmo_formato(user_id, nome, valor, email, senha, descricao, duracao)


def executar_compra_apos_termos(call):
    user_id = call.from_user.id
    pendente = pending_terms_purchase.pop(user_id, None)
    if not pendente:
        bot.answer_callback_query(call.id, "Nenhuma compra aguardando confirmaÃ§Ã£o.", show_alert=True)
        return

    tipo = pendente['tipo']
    dados = pendente['dados']

    if tipo == 'direta':
        executar_compra_direta(call.message, user_id, dados['servico'])
    elif tipo == 'quantidade':
        executar_compra_quantidade(call.message, user_id, dados['servico'], dados['quantidade'])
    elif tipo == 'carrinho':
        executar_compra_carrinho(call.message, user_id)
    elif tipo == 'inline':
        executar_compra_inline(user_id, dados['servico'])
    else:
        bot.send_message(call.message.chat.id, "Tipo de compra invÃ¡lido.")
        return

    bot.answer_callback_query(call.id, "Termos aceitos. Compra processada!", show_alert=True)




def entregar(message, nome, valor, email, senha, descricao, duracao):
    import datetime, pytz
    from telebot import types

  
    data_atual = datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))
    data_atual_formatada = data_atual.strftime("%d/%m/%Y %H:%M:%S")
    data_vencimento = data_atual + datetime.timedelta(days=int(duracao))
    data_vencimento_formatada = data_vencimento.strftime("%d/%m/%Y %H:%M:%S")

    
    descricao = descricao.replace('\\n', '\n')
    texto = api.Textos.mensagem_comprou(message, nome, valor, email, senha, descricao, duracao)
    texto = texto.replace('{data_sem_horario}', data_atual_formatada)
    texto = texto.replace('{data_vencimento}', data_vencimento_formatada)

   
    api.MudancaHistorico.add_compra(message.chat.id, nome, valor, email, senha)
    aplicar_cashback_vip(message.chat.id, valor)

 
    try:
        if getattr(message, 'caption', None):
            bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=texto,
                parse_mode='HTML'
            )
        else:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=texto,
                parse_mode='HTML'
            )
    except:
        bot.send_message(message.chat.id, texto, parse_mode='HTML')

     
    horario_brasil = data_atual_formatada
    sale_message = (
        f"ðŸ“‹ Nova venda realizada!\n\n"
        f"â€¢ (ID: {message.chat.id})\n"
        f"â€¢ Login: {nome}\n"
        f"â€¢ Valor: R${valor}\n"
        f"â€¢ HorÃ©rio: {horario_brasil}"
    )
    try:
        bot.send_message(get_sales_notification_chat_id(), sale_message, parse_mode='HTML')
    except:
        pass

   
    try:
        texto_adm = api.Log.log_compra(message, nome, email, senha, valor, descricao)
        texto_adm = texto_adm.replace('{data_sem_horario}', data_atual_formatada)
        texto_adm = texto_adm.replace('{data_vencimento}', data_vencimento_formatada)
        bot.send_message(chat_id=api.CredentialsChange.id_dono(), text=texto_adm, parse_mode='HTML')
    except:
        pass

   
    # O log da compra jÃ¡ foi gerado acima via api.Log.log_compra(...)



def pix_auto(message):
    import base64
    import requests
    import json
    import threading
    from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

    valor = message.text.replace('R$', '').replace('R', '') \
                        .replace('$', '').replace(',', '.') \
                        .strip()
    try:
        valor_float = float(valor)
    except ValueError:
        return bot.send_message(
            message.chat.id,
            "Digite um nÃ©mero vÃ©lido!\n\n<b>Ex:</b> 10.00 ou 15",
            parse_mode='HTML'
        )

    minimo = float(api.CredentialsChange.InfoPix.deposito_minimo_pix())
    maximo = float(api.CredentialsChange.InfoPix.deposito_maximo_pix())
    if not (minimo <= valor_float <= maximo):
        return bot.send_message(
            message.chat.id,
            f"Valor invÃ©lido! Digite um valor entre R${minimo:.2f} e R${maximo:.2f}",
            parse_mode='HTML'
        )

    # Descobre o gateway selecionado
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
        gateway = cred.get('gateway_pagamento', {}).get('selecionada', 'mercado_pago')
    except Exception:
        gateway = 'mercado_pago'

    print(f"[pix_auto] Gateway selecionado: {gateway}")

    if gateway == 'mercado_pago':
        try:
            payment = api.CriarPix.gerar(valor_float, message.chat.id)
            resp = payment['response']
            id_pag = resp['id']
            pix_copia_cola = resp['point_of_interaction']['transaction_data']['qr_code']
            qr_base64 = resp['point_of_interaction']['transaction_data']['qr_code_base64']

            header, encoded = qr_base64.split(",", 1) if "data:image" in qr_base64 else ("", qr_base64)
            qr_data = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
            with open('qrcode.png', 'wb') as f:
                f.write(qr_data)

            caption = api.Textos.pix_automatico(message, pix_copia_cola, 15, id_pag, f"{valor_float:.2f}")
            sent = bot.send_photo(
                chat_id=message.chat.id,
                photo=open('qrcode.png', 'rb'),
                caption=caption,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                ])
            )

            print(f'[pix_auto] Iniciando verificaÃ§Ã£o Mercado Pago para chat_id={message.chat.id}, id_pag={id_pag}, valor={valor_float}')
            threading.Thread(
                target=verificar_pagamento,
                args=(message.chat.id, id_pag, valor_float, sent.message_id),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[pix_auto] Erro ao gerar PIX Mercado Pago: {e}")
            bot.reply_to(message, "Ocorreu um erro ao gerar seu Pix Mercado Pago. Tente novamente mais tarde.")

    elif gateway == 'pushinpay':
        try:
            token = cred.get('gateway_pagamento', {}).get('pushinpay', {}).get('token', '')
            if not token:
                raise Exception('Token PushinPay nÃ£o configurado.')
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            valor_centavos = int(round(float(valor_float) * 100))
            data = {
                'value': valor_centavos
            }
            response = requests.post('https://api.pushinpay.com.br/api/pix/cashIn', headers=headers, json=data)
            print(f'[pix_auto] Status code PushinPay: {response.status_code}')
            print(f'[pix_auto] Resposta PushinPay: {response.text}')
            if response.status_code != 200:
                raise Exception(f'Erro PushinPay: {response.text}')
            res_json = response.json()
            charge_id = res_json.get('id')
            pix_copia_cola = res_json.get('qr_code')
            qr_base64 = res_json.get('qr_code_base64')
            expiracao = res_json.get('expiration', 15)

            if not (charge_id and pix_copia_cola and qr_base64):
                raise Exception('Dados insuficientes retornados pela PushinPay.')

            header, encoded = qr_base64.split(",", 1) if "data:image" in qr_base64 else ("", qr_base64)
            qr_data = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
            with open('qrcode.png', 'wb') as f:
                f.write(qr_data)

            caption = api.Textos.pix_automatico(message, pix_copia_cola, expiracao, charge_id, f"{valor_float:.2f}")
            sent = bot.send_photo(
                chat_id=message.chat.id,
                photo=open('qrcode.png', 'rb'),
                caption=caption,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                ])
            )
            print(f'[pix_auto] Iniciando verificaÃ§Ã£o PushinPay para chat_id={message.chat.id}, charge_id={charge_id}, valor={valor_float}')
            threading.Thread(
                target=verificar_pagamento,
                args=(message.chat.id, charge_id, valor_float, sent.message_id, token),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[pix_auto] Erro ao gerar PIX PushinPay: {e}")
            bot.reply_to(message, "Ocorreu um erro ao gerar seu Pix PushinPay. Tente novamente mais tarde.")
    elif gateway == 'misticpay':
        try:
            client_id = api.CredentialsChange.InfoPix.misticpay_client_id()
            client_secret = api.CredentialsChange.InfoPix.misticpay_client_secret()
            if not client_id or not client_secret:
                raise Exception('Client ID ou Client Secret da MisticPay nÃ£o configurados.')
            res = api.CriarPixMisticPay.gerar(valor_float, message.chat.id)
            data = res.get('data', {})
            transaction_id = data.get('transactionId')
            pix_copia_cola = data.get('copyPaste')
            qr_base64 = data.get('qrCodeBase64', '')
            expiracao = api.CredentialsChange.InfoPix.expiracao()

            if not (transaction_id and pix_copia_cola):
                raise Exception(f'Dados insuficientes retornados pela MisticPay: {res}')

            if qr_base64:
                header, encoded = qr_base64.split(",", 1) if "data:image" in qr_base64 else ("", qr_base64)
                qr_data = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
                with open('qrcode.png', 'wb') as f:
                    f.write(qr_data)
                photo = open('qrcode.png', 'rb')
            else:
                photo = None

            caption = api.Textos.pix_automatico(message, pix_copia_cola, expiracao, transaction_id, f"{valor_float:.2f}")
            if photo:
                sent = bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                    ])
                )
            else:
                sent = bot.send_message(
                    chat_id=message.chat.id,
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                    ])
                )

            print(f'[pix_auto] Iniciando verificaÃ§Ã£o MisticPay para chat_id={message.chat.id}, transaction_id={transaction_id}, valor={valor_float}')
            threading.Thread(
                target=verificar_pagamento,
                args=(message.chat.id, f'misticpay_{transaction_id}', valor_float, sent.message_id),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[pix_auto] Erro ao gerar PIX MisticPay: {e}")
            bot.reply_to(message, "Ocorreu um erro ao gerar seu Pix MisticPay. Tente novamente mais tarde.")
    else:
        print(f"[pix_auto] Gateway desconhecido: {gateway}")
        bot.reply_to(message, "MÃ©todo de pagamento indisponÃ©vel no momento.")


def verificar_pagamento(chat_id: int, id_pag: str, valor: float, message_id: int, token: str = None):
    import time
    import re
    import requests
    from database import get_user_balance, add_saldo, add_pagamento
    from pytz import timezone as pytz_timezone
    from datetime import datetime

    admin_id = int(api.CredentialsChange.id_dono())
    tz = pytz_timezone('America/Sao_Paulo')

    time.sleep(3)
    start_time = time.time()
    timeout = 15 * 60

    # Detecta gateway pelo formato do id_pag
    is_misticpay = str(id_pag).startswith('misticpay_')
    if is_misticpay:
        mistic_transaction_id = str(id_pag).replace('misticpay_', '', 1)
        print(f'[verificar_pagamento] Iniciando verificaÃ§Ã£o MisticPay para transaction_id={mistic_transaction_id}, valor={valor}')
    is_pushinpay = (not is_misticpay) and bool(re.match(r'^[0-9a-fA-F-]{36}$', str(id_pag)))
    if is_pushinpay:
        print(f'[verificar_pagamento] Iniciando verificaÃ§Ã£o PushinPay para charge_id={id_pag}, valor={valor}')
    elif not is_misticpay:
        print(f'[verificar_pagamento] Iniciando verificaÃ§Ã£o Mercado Pago para id_pag={id_pag}, valor={valor}')

    while True:
        if time.time() - start_time >= timeout:
            aviso = (
                f"âœ… *Timeout de Pagamento* âœ…\n\n"
                f"â€¢ UsuÃ©rio: `{chat_id}`\n"
                f"â€¢ Valor gerado: `R${valor:.2f}`\n"
                f"â€¢ Pagamento ID: `{id_pag}`\n\n"
                "O pagamento nÃ£o foi concluÃ©do em 15 minutos."
            )
            bot.send_message(chat_id=admin_id, text=aviso, parse_mode='Markdown')
            break

        try:
            if is_misticpay:
                # Verifica MisticPay
                data_resp = api.CriarPixMisticPay.verificar_transacao(mistic_transaction_id)
                transaction_data = data_resp.get('transaction', {})
                status = transaction_data.get('transactionState', '').upper()
                print(f'[verificar_pagamento] Consulta MisticPay: status={status}')
            elif is_pushinpay:
                # Verifica PushinPay
                # Usa o token passado como argumento
                url = f'https://api.pushinpay.com.br/api/transactions/{id_pag}'
                print(f'[verificar_pagamento] Usando token PushinPay: {token}')
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
                resp = requests.get(url, headers=headers)
                print(f'[verificar_pagamento] Consulta PushinPay: {resp.status_code} - {resp.text}')
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get('status', '').lower()
                    print(f'[verificar_pagamento] Status verificado: {status}')
                else:
                    status = ''
            else:
                # Verifica Mercado Pago
                result = sdk.payment().get(id_pag)
                status = result["response"]["status"].lower()
                print(f"[verificar_pagamento] Pagamento {id_pag} status: {status}")
        except Exception as e:
            print(f"[verificar_pagamento] erro ao buscar status de {id_pag}: {e}")
            time.sleep(5)
            continue

        if (is_misticpay and status == 'COMPLETO') or (not is_misticpay and not is_pushinpay and "approved" in status) or (is_pushinpay and status == 'paid'):
            try:
                min_bonus = float(api.CredentialsChange.BonusPix.valor_minimo_para_bonus())
                bonus_pct = float(api.CredentialsChange.BonusPix.quantidade_bonus())
            except:
                min_bonus, bonus_pct = float("inf"), 0.0
            if valor >= min_bonus:
                bonus_amt = valor * bonus_pct / 100
                saldo_deposito = valor + bonus_amt
            else:
                saldo_deposito = valor
            before = get_user_balance(chat_id)
            add_saldo(chat_id, saldo_deposito)
            add_pagamento(chat_id, valor, id_pag)
            comissao_afiliado = pagar_comissao_afiliado(chat_id, valor)
            after = get_user_balance(chat_id)
            print(f"[verificar_pagamento] Saldo de {chat_id} atualizado: {before} -> {after}")
            texto_user = (
                f"<b>âœ… PAGAMENTO APROVADO!</b>\n\n"
                f"â€¢ Valor depositado: R${valor:.2f}\n"
                f"âœ… BÃ©nus: R${(saldo_deposito - valor):.2f}\n"
                f"👥 Comissão afiliado: R${comissao_afiliado:.2f}\n"
                f"â€¢ Saldo antes: R${before:.2f}\n"
                f"â€¢ Saldo atual: R${after:.2f}\n"
                f"â€¢ ID do pagamento: {id_pag}"
            )
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=texto_user, parse_mode='HTML')
            except:
                bot.send_message(chat_id=chat_id, text=texto_user, parse_mode='HTML')
            now = datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S")
            try:
                chat_info = bot.get_chat(chat_id)
                if chat_info.username:
                    usuario_tag = f"@{chat_info.username} ({chat_id})"
                elif chat_info.first_name:
                    usuario_tag = f"{chat_info.first_name} ({chat_id})"
                else:
                    usuario_tag = f"{chat_id}"
            except Exception:
                usuario_tag = f"{chat_id}"
            texto_adm = (
                f"â€¢ *DepÃ©sito Aprovado*\n\n"
                f"â€¢ UsuÃ©rio: `{usuario_tag}`\n"
                f"â€¢ Valor: `R${valor:.2f}`\n"
                f"âœ… BÃ©nus: `R${(saldo_deposito - valor):.2f}`\n"
                f"👥 Comissão afiliado: `R${comissao_afiliado:.2f}`\n"
                f"â€¢ Saldo antes: `R${before:.2f}`\n"
                f"â€¢ Saldo depois: `R${after:.2f}`\n"
                f"â€¢ Data/Hora: `{now}`"
            )
            bot.send_message(chat_id=admin_id, text=texto_adm, parse_mode='Markdown')
            break

        if (is_misticpay and status == 'FALHA') or (not is_misticpay and not is_pushinpay and ("cancelled" in status or "canceled" in status)) or (is_pushinpay and status in ['expired', 'cancelled']):
            texto_cancel = api.Textos.pagamento_expirado(None, id_pag, f"{valor:.2f}")
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=texto_cancel, parse_mode='HTML')
            except:
                bot.send_message(chat_id=chat_id, text=texto_cancel, parse_mode='HTML')
            try:
                chat = bot.get_chat(chat_id)
                nome = f"@{chat.username}" if chat.username else chat.first_name or str(chat_id)
            except:
                nome = str(chat_id)
            aviso = (
                f"âš™ï¸ *PIX NÃ©o Pago / Expirado*\n\n"
                f"â€¢ UsuÃ©rio: `{nome}` (`{chat_id}`)\n"
                f"â€¢ Valor gerado: `R${valor:.2f}`\n"
                f"â€¢ Pagamento ID: `{id_pag}`"
            )
            bot.send_message(chat_id=admin_id, text=aviso, parse_mode='Markdown')
            break
        time.sleep(5)

@bot.message_handler(commands=['get_id'])
def get_id(message):
    if api.Admin.verificar_vencimento() == True:
        ver_se_expirou()
        return
    bot.reply_to(message, f'{message.chat.id}')

@bot.message_handler(commands=['streaming_emojis'])
def handle_streaming_emojis(message):
    chunk_size = 24
    total = len(STREAMING_CUSTOM_EMOJI_IDS)
    for start in range(0, total, chunk_size):
        chunk = STREAMING_CUSTOM_EMOJI_IDS[start:start + chunk_size]
        icons = " ".join(
            f'<tg-emoji emoji-id="{emoji_id}">ðŸ“º</tg-emoji>'
            for emoji_id in chunk
        )
        text = (
            f"<b>Streaming Premium</b> "
            f"<code>{start + 1}-{start + len(chunk)}</code>/<code>{total}</code>\n\n"
            f"{icons}"
        )
        bot.send_message(message.chat.id, text, parse_mode='HTML')

def _extract_custom_emoji_entities(target_message):
    entities = []
    for entity in (getattr(target_message, 'entities', None) or []):
        if getattr(entity, 'type', None) == 'custom_emoji':
            entities.append(entity)
    for entity in (getattr(target_message, 'caption_entities', None) or []):
        if getattr(entity, 'type', None) == 'custom_emoji':
            entities.append(entity)
    return entities

@bot.message_handler(commands=['emojiid'])
def handle_emoji_id(message):
    target_message = getattr(message, 'reply_to_message', None) or message
    lines = ["<b>Resultado da leitura do Telegram:</b>"]

    custom_entities = _extract_custom_emoji_entities(target_message)
    if custom_entities:
        lines.append("")
        lines.append("<b>Custom emojis no texto:</b>")
        for index, entity in enumerate(custom_entities, start=1):
            custom_emoji_id = getattr(entity, 'custom_emoji_id', None)
            lines.append(f"{index}. <code>{html.escape(str(custom_emoji_id))}</code>")
            lines.append(
                f'   HTML: <code>&lt;tg-emoji emoji-id="{html.escape(str(custom_emoji_id))}"&gt;â­&lt;/tg-emoji&gt;</code>'
            )

    sticker = getattr(target_message, 'sticker', None)
    if sticker:
        sticker_type = getattr(sticker, 'type', '')
        custom_emoji_id = getattr(sticker, 'custom_emoji_id', None)
        set_name = getattr(sticker, 'set_name', None)
        file_id = getattr(sticker, 'file_id', '')
        emoji = getattr(sticker, 'emoji', '')

        lines.append("")
        lines.append("<b>Sticker recebido:</b>")
        lines.append(f"â€¢ Tipo: <code>{html.escape(str(sticker_type))}</code>")
        lines.append(f"â€¢ Emoji base: {html.escape(str(emoji or ''))}")
        if set_name:
            lines.append(f"â€¢ Pacote: <code>{html.escape(str(set_name))}</code>")
        if custom_emoji_id:
            lines.append(f"â€¢ custom_emoji_id: <code>{html.escape(str(custom_emoji_id))}</code>")
            lines.append(
                f'â€¢ HTML: <code>&lt;tg-emoji emoji-id="{html.escape(str(custom_emoji_id))}"&gt;{html.escape(str(emoji or "â­"))}&lt;/tg-emoji&gt;</code>'
            )
        else:
            lines.append("â€¢ custom_emoji_id: <b>nÃ£o veio nesse sticker</b>")
            lines.append(f"â€¢ file_id: <code>{html.escape(str(file_id))}</code>")

    if not custom_entities and not sticker:
        lines.append("")
        lines.append("Responda com <code>/emojiid</code> em cima de uma mensagem que tenha emoji premium ou sticker.")

    bot.reply_to(message, "\n".join(lines), parse_mode='HTML')


@bot.message_handler(commands=['criador'])
def handle_criador(message):
    if str(message.from_user.id) == 'ID DO ADM':
        b = InlineKeyboardButton('âœ… ADD EM GRUPO âœ…', url=f'https://t.me/{api.CredentialsChange.user_bot()}?startgroup=start')
        bt = InlineKeyboardButton('â€¢ REINICIAR BOT', callback_data='reiniciar_bot')
        bt1 = InlineKeyboardButton('â€¢â€¢â€¢? PEGAR ADMIN', callback_data='pegar_admin_creator')
        bt2 = InlineKeyboardButton('â€¢ MUDAR TOKEN BOT', callback_data='mudar_token_bot')
        bt3 = InlineKeyboardButton('â€¢ MUDAR USER DO BOT', callback_data='mudar_user_bot')
        bt4 = InlineKeyboardButton('â€¢ MUDAR DONO DO BOT', callback_data='mudar_dono_bot')
        bt43 = InlineKeyboardButton('ðŸ“‹ MUDAR VERSÃ©O DO BOT', callback_data='mudar_versao_bot')
        bt5 = InlineKeyboardButton('âœ… CONFIGURAR VENCIMENTO', callback_data='configurar_vencimento')
        markup = InlineKeyboardMarkup([[b], [bt], [bt1], [bt2], [bt3], [bt4], [bt43], [bt5]])
        txt = (
            f'ðŸ“‹ <b>PAINEL DE CONFIGURAÃ‡Ã•ES DEV</b>\n\n'
            f'â€¢ <b>Tipo de bot:</b> <i>Acessos e logins</i>\n'
            f'â€¢ <b>VersÃ£o:</b> <i>{api.CredentialsChange.versao_bot()}</i>\n'
            f'â€¢ <b>Bot:</b> @{api.CredentialsChange.user_bot()}\n'
            f'â€¢ <b>Dono:</b> <code>{api.CredentialsChange.id_dono()}</code>\n'
            f'â€¢ <b>Token:</b> <code>{api.CredentialsChange.token_bot()}</code>\n'
            f'âœ… <b>Vencimento:</b> <code>{api.Admin.data_vencimento()} faltam {api.Admin.tempo_ate_o_vencimento()} dias!</code>'
        )
        if message.text == '/criador':
            bot.send_message(chat_id=message.chat.id, text=txt, parse_mode='HTML', reply_markup=markup)
        else:
            bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=txt, parse_mode='HTML', reply_markup=markup)

def trocar_token(message):
    api.CredentialsChange.mudar_token_bot(message.text)
    bot.reply_to(message, "Alterado com sucesso! Reiniciando...")
    os._exit(0)

def trocar_user(message):
    api.CredentialsChange.mudar_user_bot(message.text)
    bot.reply_to(message, "Alterado!")
    message.text = '/criador'
    handle_criador(message)

def mudar_dono_bot(message):
    api.CredentialsChange.mudar_dono(message.text)
    bot.reply_to(message, "Alterado!")
    message.text = '/criador'
    handle_criador(message)

def mudar_dias_vencimento(message, tipo):
    if tipo == 'mais':
        api.Admin.aumentar_vencimento(message.text)
    else:
        api.Admin.diminuir_vencimento(message.text)
    bot.reply_to(message, 'Alterado!')
    message.text = '/criador'
    handle_criador(message)

def mudar_versao_bot(message):
    versao = message.text
    api.CredentialsChange.mudar_versao_bot(versao)
    bot.reply_to(message, "Alterado com sucesso!")

def alugarbot(message):
    text = """â€¢ ALUGUE SEU BOT PARA TELEGRAM E TURBINE SUAS VENDAS! â€¢

â€¢ FUNCIONALIDADES EXCLUSIVAS:

â€¢ PIX AUTOMÃ©TICO & MANUAL âœ… Receba pagamentos sem complicaÃ§Ãµes!
ðŸ“‹ GIFT CARDS âœ… Venda e entregue de forma automÃ©tica!
â€¢ NOTIFICAÃ‡Ã•ES EM TEMPO REAL âœ… Acompanhe vendas e saldo instantaneamente!
â€¢ ENTREGA AUTOMÃ©TICA COM VALIDADE âœ… Agilidade e seguranÃ©a na distribuiÃ§Ã£o!
â€¢ REABASTECIMENTO SIMPLIFICADO âœ… Facilidade para manter seu estoque ativo!
ðŸ“‹ PAINEL ADMINISTRATIVO COMPLETO âœ… Gerencie tudo com praticidade!
â€¢ SUPORTE A IMAGENS NOS MENUS âœ… Layout profissional e atrativo!
â€¢ RANKING DOS MAIORES DEPOSITANTES âœ… Engaje seus clientes!

â€¢ BANCOS DISPONÃ©VEIS:

â€¢ Mercado Pago âœ… Seguro, confiÃ©vel e ideal para vendas!
âœ… Virtual Pay âœ… Receba em qualquer chave PIX com saques automÃ©ticos instantÃ©neos!

â€¢ POR QUE USAR NOSSO BOT?

â€¢ AUTOMAÃ‡ÃƒO TOTAL âœ… Menos trabalho manual, mais vendas!
â€¢ EXPERIÃ©NCIA APRIMORADA âœ… Seus clientes satisfeitos com notificaÃ§Ãµes rÃ©pidas e entregas eficientes!
â€¢ GESTÃ©O SIMPLES E INTUITIVA âœ… Controle tudo em um sÃ© lugar!

â€¢ ATUALIZE SEU NEGÃ©CIO AGORA MESMO E AUMENTE SUAS VENDAS COM UM BOT COMPLETO E MODERNO! â€¢"""

    markup = InlineKeyboardMarkup()
    but = InlineKeyboardButton('â€¢ â€¢â€¢â€¢â€¢â€¢â€¢ â€¢â€¢ â€¢â€¢â€¢â€¢â€¢!', url='https://wa.me/5587981594601')
    but2 = InlineKeyboardButton('âš™ï¸ â€¢â€¢â€¢â€¢â€¢â€¢', callback_data='menu_start')
    markup.add(but, but2)
    
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)


icones = {
    
    'netflix': 'https://cdn.icon-icons.com/icons2/3053/PNG/512/netflix_macos_bigsur_icon_189917.png',
    'globo play': 'https://m.media-amazon.com/images/I/71bch7gUsqL.png',
    'prime': 'https://cdn.icon-icons.com/icons2/3914/PNG/512/prime_logo_icon_248780.png',
    'hbo': 'https://cdn.icon-icons.com/icons2/183/PNG/256/HBO_22554.png',
    'max': 'https://cdn.icon-icons.com/icons2/183/PNG/256/HBO_22554.png',
    'canva' : 'https://cdn.icon-icons.com/icons2/3504/PNG/512/canva_icon_220714.png',
    'crunchyroll' : 'https://cdn.icon-icons.com/icons2/3132/PNG/512/crunchyroll_social_network_network_connection_communication_icon_192251.png',
    'crunchyrool' : 'https://cdn.icon-icons.com/icons2/3132/PNG/512/crunchyroll_social_network_network_connection_communication_icon_192251.png',
    'telecine' : 'https://pop.proddigital.com.br/wp-content/uploads/sites/8/elementor/thumbs/telecine-1-pr09zcpscitsxnsglhxs9fgak9j8yqld1snhs0od54.png',
    'cap cut' : 'https://www.moneytimes.com.br/uploads/2024/01/mt-capcut-2-1024x576.jpg',
    'capcut' : 'https://www.moneytimes.com.br/uploads/2024/01/mt-capcut-2-1024x576.jpg',
    'PREMIERE' : 'https://melhorescolha.com/blog/wp-content/uploads/2024/01/preco-do-premiere.jpg',
    'CLARO TV' : 'https://t2.tudocdn.net/601002?w=646&h=284',
    'CLARO' : 'https://t2.tudocdn.net/601002?w=646&h=284',
    
    'padrao': 'https://cdn.icon-icons.com/icons2/72/PNG/256/unknown_alert_14463.png'  # Caso nÃ£o encontre nada
}

@bot.inline_handler(lambda query: query.query.lower().startswith('buscar_loguin '))
def inline_search_logins(inline_query):
    termo = inline_query.query[13:].strip().lower()
    servicos = api.ControleLogins.pegar_servicos()

    dicionario = {}
    for s in servicos:
        nome_lower = s["nome"].lower()
        if termo in nome_lower:
            nome_plataforma = s["nome"]
            if nome_plataforma not in dicionario:
                dicionario[nome_plataforma] = {
                    "nome": s["nome"],
                    "valor": s["valor"],
                    "lista": []
                }
                if "duracao" in s:
                    dicionario[nome_plataforma]["duracao"] = s["duracao"]
            dicionario[nome_plataforma]["lista"].append(s)

    results = []
    count_id = 1

    for nome_serv, info in dicionario.items():
        nome = info["nome"]
        valor = info["valor"]
        qtd_estoque = len(info["lista"])
        duracao = info.get("duracao")

        if duracao:
            linha_duracao = f"\n<b>Validade:</b> {duracao} dias"
        else:
            linha_duracao = ""

        texto = (
            f"<b>â€¢ Tipo:</b> {nome}\n"
            f"<b>â€¢ Valor:</b> R${float(valor):.2f}\n"
            f"<b>â€¢ Quantia em estoque:</b> {qtd_estoque}"
            f"{linha_duracao}\n\n"
            f"<i>â€¢Use os botÃµes abaixo para comprar ou cancelar. â€¢</i>\n"
            f"<i>âš™ï¸Precisa de Ajuda ? @RLFORNECEDOR</i>"
        )

        # BotÃ©es
        buy_btn = types.InlineKeyboardButton("Comprar", callback_data=service_callback_data("comprarInline", nome))
        cancel_btn = types.InlineKeyboardButton("Cancelar", callback_data="cancelarInline")
        kb = types.InlineKeyboardMarkup([[buy_btn, cancel_btn]])

        
        icon_url = icones['padrao']  
        nome_lower = nome.lower()
        for chave, link_icon in icones.items():
            if chave in nome_lower:
                icon_url = link_icon
                break

        title = f"{nome}"
        description = f"Valor: R${float(valor):.2f} | Estoque: {qtd_estoque}"

        result = types.InlineQueryResultArticle(
            id=str(count_id),
            title=title,
            description=description,
            input_message_content=types.InputTextMessageContent(texto, parse_mode='HTML'),
            reply_markup=kb,
            thumbnail_url=icon_url  
        )
        results.append(result)
        count_id += 1

    if not results:
        result_none = types.InlineQueryResultArticle(
            id='99999',
            title="Nenhum resultado encontrado",
            description="NÃ©o hÃ© nenhum login compatÃ©vel com sua busca.",
            input_message_content=types.InputTextMessageContent("NÃ©o encontrei nada. Tente outro termo.")
        )
        results.append(result_none)

    bot.answer_inline_query(inline_query.id, results, cache_time=1)


@bot.callback_query_handler(func=lambda c: c.data.startswith("comprarInline ") or c.data.startswith("comprarInline|"))
def callback_comprar_inline(call):
    if call.data.startswith("comprarInline|"):
        nome_servico = resolve_service_callback_token(call.data.split('|', 1)[1])
    else:
        nome_servico = call.data.replace("comprarInline ", "").strip()
    user_id = call.from_user.id

    if not nome_servico:
        bot.answer_callback_query(
            call.id,
            "ServiÃ§o esgotado ou nÃ£o encontrado!",
            show_alert=True
        )
        return

    
    resultado_peek = api.ControleLogins.peek_primeiro_disponivel(nome_servico)
    if not resultado_peek:
        bot.answer_callback_query(
            call.id,
            "ServiÃ©o esgotado ou nÃ£o encontrado!",
            show_alert=True
        )
        return

    
    _, valor, _, _, _, _ = resultado_peek

    
    saldo_user = api.InfoUser.saldo(user_id)
    if float(saldo_user) < float(valor):
        falta = float(valor) - float(saldo_user)
        bot.answer_callback_query(call.id, f"Saldo insuficiente! Faltam R${falta:.2f}", show_alert=True)
        return

    pending_terms_purchase[user_id] = {
        'tipo': 'inline',
        'dados': {'servico': nome_servico},
        'criado_em': time.time()
    }
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton('âœ… Li e aceito os termos', callback_data='aceitar_termos_compra'))
    markup.row(InlineKeyboardButton('âŒ Cancelar compra', callback_data='cancelar_termos_compra'))
    texto = (
        f"{termos_texto}\n\n"
        "<b>Para continuar com a compra, confirme que vocÃª leu e aceita os termos acima.</b>"
    )
    bot.send_message(user_id, texto, parse_mode='HTML', reply_markup=markup)
    bot.answer_callback_query(call.id, "Confirme os termos para continuar.", show_alert=True)

def entregar_inline_mesmo_formato(user_id, nome, valor, email, senha, descricao, duracao):
 
    import datetime, pytz

    data_atual = datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))
    data_atual_formatada = data_atual.strftime("%d/%m/%Y %H:%M:%S")
    data_venc = data_atual + datetime.timedelta(days=int(duracao))
    data_venc_formatada = data_venc.strftime("%d/%m/%Y")

   
    texto = api.Textos.mensagem_comprou_inline(
        user_id, nome, valor, email, senha, descricao, duracao
    )
    texto = texto.replace('{data_sem_horario}', data_atual_formatada)
    texto = texto.replace('{data_vencimento}',  data_venc_formatada)

   
    bot.send_message(
        chat_id=user_id,
        text=texto,
        parse_mode='HTML'
    )

    
    api.MudancaHistorico.add_compra(user_id, nome, valor, email, senha)
    aplicar_cashback_vip(user_id, valor)

   
    user_data = api.load_user_data(user_id) or {}
    username = user_data.get('username', f"{user_id}")
    horario_brasil = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
    sale_message = (
        f"ðŸ“‹ Nova venda realizada!\n\n"
        f"â€¢ (ID: {user_id})\n"
        f"â€¢ Login: {nome}\n"
        f"â€¢ Valor: R${valor}\n"
        f"â€¢ HorÃ©rio: {horario_brasil}"
    )
    try:
        bot.send_message(get_sales_notification_chat_id(), sale_message, parse_mode='HTML')
    except Exception as e:
        print(f"Erro ao enviar mensagem de venda: {e}")

     
    try:
        
        texto_adm = api.Log.log_compra_inline(user_id, nome, email, senha, valor, descricao)
         
        bot.send_message(api.CredentialsChange.id_dono(), texto_adm, parse_mode='HTML')
    except Exception as e:
        bot.send_message(api.CredentialsChange.id_dono(), f'Falha ao enviar o log!\nMotivo: {e}')



def pegar_primeiro_disponivel(servico):
    logins = pegar_servicos()
    for x in logins:
        if x["nome"].lower() == servico.lower():
             
            remover_login(x["nome"], x["email"])
            return (x["nome"], x["valor"], x["email"], x["senha"], x["descricao"], x["duracao"])
    return None

def entregar_inline(user_id, nome, valor, email, senha, descricao, duracao):
 
    import datetime, pytz

    
    data_atual = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
    data_atual_formatada = data_atual.strftime("%d/%m/%Y %H:%M:%S")
    data_venc = data_atual + datetime.timedelta(days=int(duracao))
    data_venc_formatada = data_venc.strftime("%d/%m/%Y")

    descricao = descricao.replace('\\n', '\n')
    texto_entrega = (
        f"âœ… <b>Login Entregue!</b>\n\n"
        f"<b>Tipo:</b> {nome}\n"
        f"<b>UsuÃ©rio:</b> {email}\n"
        f"<b>Senha:</b> {senha}\n"
        f"<b>Validade:</b> {duracao} dia(s)\n"
        f"(de {data_atual_formatada} atÃ© {data_venc_formatada})\n\n"
        f"<i>{descricao}</i>"
    )

    
    bot.send_message(chat_id=user_id, text=texto_entrega, parse_mode='HTML')

     
    api.MudancaHistorico.add_compra(user_id, nome, valor, email, senha)
    aplicar_cashback_vip(user_id, valor)

   
    user_data = api.load_user_data(user_id) or {}
    username = user_data.get('username', None)
    if not username:
        username = f"{user_id}"

     
    horario_brasil = datetime.datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S")
    sale_msg = (
        f"ðŸ“‹ Nova venda realizada!\n\n"
        f"â€¢ (ID: {user_id})\n"
        f"â€¢ Login: {nome}\n"
        f"â€¢ Valor: R${valor}\n"
        f"â€¢ HorÃ©rio: {horario_brasil}"
    )
    try:
        bot.send_message(get_sales_notification_chat_id(), sale_msg, parse_mode='HTML')
    except Exception as e:
        print(f"Erro ao enviar mensagem de venda no grupo: {e}")

     
    dono_id = api.CredentialsChange.id_dono()
    try:
        log_text = (
            f"<b>LOG DE COMPRA (Inline)</b>\n\n"
            f"ID user: {user_id}\n"
            f"ServiÃ©o: {nome}\n"
            f"Valor: R${valor}\n"
            f"Email: {email}\n"
            f"Senha: {senha}\n"
            f"DescriÃ§Ã£o: {descricao}\n"
            f"Validade: {duracao} dias\n"
            f"Data: {data_atual_formatada}"
        )
        bot.send_message(dono_id, log_text, parse_mode='HTML')
    except Exception as e:
        print(f"Erro ao enviar log pro dono: {e}")



@bot.callback_query_handler(func=lambda c: c.data == "cancelarInline")
def callback_cancelar_inline(call):
 
    handle_start(call.message)
  


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    if call.data == 'dup_login_add':
        adicionados = adicionar_logins_duplicados_confirmados(call.from_user.id)
        bot.answer_callback_query(call.id, "Duplicados adicionados.", show_alert=True)
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass
        bot.send_message(
            call.message.chat.id,
            f"✅ {adicionados} login(s) duplicado(s) adicionado(s) mesmo assim."
        )
        return

    if call.data == 'dup_login_skip':
        pending_duplicate_logins.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id, "Duplicados ignorados.", show_alert=True)
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass
        return

    if call.data == 'reserve_verified_continue':
        try:
            if not is_user_in_reserve_group(call.from_user.id):
                bot.answer_callback_query(call.id, "Entre no grupo reserva antes de continuar.", show_alert=True)
                return
        except Exception:
            bot.answer_callback_query(call.id, "NÃ£o consegui confirmar sua entrada no grupo reserva. Tente de novo em instantes.", show_alert=True)
            return
        mark_reserve_verified(call.from_user.id)
        bot.answer_callback_query(call.id, "VerificaÃ§Ã£o confirmada.", show_alert=True)
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f'{custom_emoji("5350486389806868244", "âœ…")} <b>VerificaÃ§Ã£o concluÃ­da!</b>',
                parse_mode='HTML'
            )
        except Exception:
            pass
        enviar_menu_inicial(call.message)
        return

    if call.data == 'aceitar_termos_compra':
        executar_compra_apos_termos(call)
        return

    if call.data == 'cancelar_termos_compra':
        pending_terms_purchase.pop(call.from_user.id, None)
        bot.answer_callback_query(call.id, "Compra cancelada.", show_alert=True)
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass
        return

    
    if call.data == 'servicos':
        modo_exibicao = api.CredentialsChange.modo_exibicao()
        if modo_exibicao == 'categorizado':
            menu_categorias_servicos(call.message)
        else:
            servicos(call.message)
        return

    
    if call.data.startswith("servicos_categoria"):
        
        parts = call.data.split()
        if len(parts) >= 2:
            categoria = parts[1]
            servicos_por_categoria(call.message, categoria)
        return

    
    if call.data == 'menu_categorias_servicos':
        menu_categorias_servicos(call.message)
        return

    if call.data == 'suporte_user':
        link_suporte = api.CredentialsChange.SuporteInfo.link_suporte()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('â€¢ Acessar Suporte', url=link_suporte))
        markup.add(InlineKeyboardButton('âœ… Voltar', callback_data='menu_start'))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text='â€¢ <b>SUPORTE</b>\n\nClique no botÃ©o abaixo para acessar nosso suporte:',
            parse_mode='HTML',
            reply_markup=markup
        )
        return


    if call.data == 'rank_menu':
        # Exibir o submenu de rankings
        # (Demais cases de ranking mais abaixo...)
        pass

    # =====================
    # Admin: Editor de Textos e Gerenciar Imagens
    # =====================
    # Abrir menu de ediÃ§Ã£o de textos
    if call.data == 'editar_textos':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        try:
            mostrar_menu_textos(call.message)
        except Exception as e:
            bot.answer_callback_query(call.id, f'Erro: {e}', show_alert=True)
        return

    # Abrir menu de ediÃ§Ã£o de botÃµes (arquivos em botoes/)
    if call.data == 'editar_botoes':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        try:
            mostrar_menu_botoes(call.message)
        except Exception as e:
            bot.answer_callback_query(call.id, f'Erro: {e}', show_alert=True)
        return

    if call.data == 'edit_service_buttons':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        mostrar_menu_botoes_servicos(call.message)
        return

    if call.data == 'service_buttons_color_all':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'Sem permissao.', show_alert=True)
            return
        produtos = _get_unique_products()
        if not produtos:
            bot.answer_callback_query(call.id, 'Nenhum produto encontrado.', show_alert=True)
            return
        pending_button_edit[call.message.chat.id] = {
            'kind': 'service_all',
            'filename': 'todos os produtos',
            'color': None,
            'text': '',
        }
        bot.answer_callback_query(call.id)
        mostrar_cores_botao(call.message)
        return

    if call.data.startswith('edit_service_button '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        try:
            index = int(call.data.split(maxsplit=1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, 'Produto invÃ¡lido.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        abrir_editor_botao_servico(call.message, index)
        return

    # Selecionar um arquivo de texto para editar
    if call.data.startswith('edit_text_file '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        parts = call.data.split(maxsplit=1)
        if len(parts) < 2:
            bot.answer_callback_query(call.id, 'Arquivo nÃ£o especificado.', show_alert=True)
            return
        filename = parts[1].strip()
        _send_file_preview_and_wait(call.message, filename)
        return

    # Selecionar um arquivo de botoes para editar
    if call.data.startswith('edit_boto_file '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        parts = call.data.split(maxsplit=1)
        if len(parts) < 2:
            bot.answer_callback_query(call.id, 'Arquivo nÃ£o especificado.', show_alert=True)
            return
        filename = parts[1].strip()
        _send_botoes_file_preview_and_wait(call.message, filename)
        return

    if call.data.startswith('boto_action '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        action = call.data.split(maxsplit=1)[1].strip()
        bot.answer_callback_query(call.id)
        if action == 'texto':
            pedir_texto_botao(call.message)
        elif action == 'cor':
            mostrar_cores_botao(call.message)
        return

    if call.data.startswith('boto_color '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        color = call.data.split(maxsplit=1)[1].strip()
        bot.answer_callback_query(call.id)
        salvar_cor_botao(call.message, color)
        return

    # Abrir menu de gerenciamento de imagens
    if call.data == 'gerenciar_imagens':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        mostrar_menu_imagens(call.message)
        return

    if call.data == 'miniapp_images_menu':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        mostrar_menu_miniapp_imagens(call.message)
        return

    if call.data == 'miniimg_refresh_catalog':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        atualizar_catalogo_miniapp()
        ok, detalhe = publicar_miniapp_no_git('catalogo')
        bot.answer_callback_query(call.id, detalhe[:180], show_alert=True)
        mostrar_menu_miniapp_imagens(call.message)
        return

    if call.data.startswith('miniimg_edit|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        produto = _miniapp_product_by_index(int(call.data.split('|', 1)[1]))
        if not produto:
            bot.answer_callback_query(call.id, 'Produto não encontrado.', show_alert=True)
            return
        mostrar_acoes_imagem_miniapp(call.message, produto)
        return

    if call.data.startswith('miniimg_link|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        produto = _miniapp_product_by_index(int(call.data.split('|', 1)[1]))
        if produto:
            perguntar_link_imagem_miniapp(call.message, produto)
        return

    if call.data.startswith('miniimg_upload|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        produto = _miniapp_product_by_index(int(call.data.split('|', 1)[1]))
        if produto:
            pedir_upload_imagem_miniapp(call.message, produto)
        return

    if call.data.startswith('miniimg_remove|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        produto = _miniapp_product_by_index(int(call.data.split('|', 1)[1]))
        image_map = _load_miniapp_images()
        if produto and produto in image_map:
            image_map.pop(produto, None)
            _save_miniapp_images(image_map)
            atualizar_catalogo_miniapp()
            ok, detalhe = publicar_miniapp_no_git(f'remover imagem {produto}')
            bot.answer_callback_query(call.id, detalhe[:180], show_alert=True)
        mostrar_menu_miniapp_imagens(call.message)
        return

    # Abrir menu de emojis premium por serviÃ§o
    if call.data == 'emojis_servicos_menu':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        mostrar_menu_emojis_servicos(call.message)
        return

    if call.data == 'service_emoji_add':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        perguntar_nome_service_emoji(call.message)
        return

    if call.data == 'service_emoji_remove':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        perguntar_remover_service_emoji(call.message)
        return

    # Listar Ã­cones
    if call.data == 'icons_list':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        texto = _listar_icones_texto()
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='gerenciar_imagens'))
        try:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=texto, parse_mode='HTML', reply_markup=markup)
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        return

    # Adicionar/atualizar Ã­cone
    if call.data == 'icons_add':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        _perguntar_nome_icone_para_upload(call.message)
        return

    # Remover Ã­cone
    if call.data == 'icons_remove':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        _perguntar_nome_icone_para_remover(call.message)
        return

    # Renomear Ã­cone
    if call.data == 'icons_rename':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        _perguntar_renomear_icone(call.message)
        return

    # Abrir menu de gerenciamento de descriÃ§Ãµes
    if call.data == 'gerenciar_descricoes':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        mostrar_menu_descricoes(call.message)
        return

    # Selecionar um produto para editar descriÃ§Ã£o
    if call.data.startswith('edit_desc_product '):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        parts = call.data.split(maxsplit=1)
        if len(parts) < 2:
            bot.answer_callback_query(call.id, 'Produto nÃ£o especificado.', show_alert=True)
            return
        produto = parts[1].strip()
        bot.answer_callback_query(call.id)
        _send_description_preview_and_wait(call.message, produto)
        return

    # =====================
    # Menu de Consulta de Vendas
    # =====================
    if call.data == 'menu_vendas':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        texto = "â€¢ <b>CONSULTAR VENDAS</b>\n\nEscolha uma opÃ§Ã£o:"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Vendas de Hoje', callback_data='vendas_hoje_btn'))
        markup.row(InlineKeyboardButton('â€¢ Vendas por Data', callback_data='vendas_data_btn'))
        markup.row(InlineKeyboardButton('â€¢ EstatÃ©sticas do MÃ©s', callback_data='vendas_mes_btn'))
        markup.row(InlineKeyboardButton('âœ… Voltar', callback_data='voltar_paineladm'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        return

    if call.data == 'vendas_hoje_btn':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        hoje = datetime.datetime.now().strftime("%d/%m/%Y")
        exibir_vendas_do_dia(call.message, hoje)
        return

    if call.data == 'vendas_data_btn':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "â€¢ Digite a data que deseja consultar no formato DD/MM/YYYY\n\nExemplo: 24/02/2026")
        bot.register_next_step_handler(msg, processar_consulta_vendas_dia)
        return

    # NavegaÃ§Ã£o entre vendas
    if call.data.startswith('nav_venda|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        parts = call.data.split('|')
        if len(parts) == 3:
            data = parts[1]
            indice = int(parts[2])
            mostrar_venda_navegavel(call, data, indice)
        return

    # Voltar ao resumo de vendas
    if call.data.startswith('resumo_vendas|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        data = call.data.split('|')[1]
        vendas = database.get_sales_by_date(data)
        total_valor = sum(float(v['valor']) for v in vendas)
        
        resumo = f"â€¢ <b>VENDAS DO DIA {data}</b>\n\n"
        resumo += f"â€¢ <b>Total de vendas:</b> {len(vendas)}\n"
        resumo += f"â€¢ <b>Valor total:</b> R$ {total_valor:.2f}\n"
        resumo += f"{'='*30}\n\n"
        resumo += "Use os botÃµes abaixo para navegar pelas vendas:"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âš™ï¸ Ver Vendas', callback_data=f'nav_venda|{data}|0'))
        markup.row(InlineKeyboardButton('â€¢ Voltar ao Menu', callback_data='menu_vendas'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=resumo,
                parse_mode='HTML',
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
        except Exception:
            bot.send_message(call.message.chat.id, resumo, parse_mode='HTML', reply_markup=markup)
        return

    # Callback vazio para o contador
    if call.data == 'nada':
        bot.answer_callback_query(call.id)
        return

    # =====================
    # Callbacks de NotificaÃ§Ã£o de Reabastecimento
    # =====================
    
    # Adicionar notificaÃ§Ã£o
    if call.data == 'add_notif_reabast':
        user_id = call.from_user.id
        pending_notif_reabast[user_id] = 'add'
        
        bot.send_message(
            call.message.chat.id,
            "â€¢ <b>ADICIONAR NOTIFICAÃ‡ÃƒO</b>\n\n"
            "Digite o nome do produto que deseja ser notificado quando voltar ao estoque:\n\n"
            "Exemplo: Netflix, Spotify, Disney+, etc.",
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
        return
    
    # Remover notificaÃ§Ã£o
    if call.data == 'remove_notif_reabast':
        user_id = call.from_user.id
        notificacoes = database.get_notificacoes_reabastecimento(user_id)
        
        if not notificacoes:
            bot.answer_callback_query(call.id, "VocÃª nÃ£o tem notificaÃ§Ãµes!", show_alert=True)
            return
        
        texto = "â€¢ <b>REMOVER NOTIFICAÃ‡ÃƒO</b>\n\nSelecione o produto:"
        markup = InlineKeyboardMarkup()
        
        for item in notificacoes:
            markup.row(InlineKeyboardButton(
                f"âœ… {item['produto']}", 
                callback_data=f"del_notif|{item['produto']}"
            ))
        
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_notif'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        return
    
    # Deletar notificaÃ§Ã£o especÃ©fica
    if call.data.startswith('del_notif|'):
        produto = call.data.split('|')[1]
        user_id = call.from_user.id
        
        database.remover_notificacao_reabastecimento(user_id, produto)
        bot.answer_callback_query(call.id, f"âœ… NotificaÃ§Ã£o removida: {produto}", show_alert=True)
        
        # Atualizar lista
        notificacoes = database.get_notificacoes_reabastecimento(user_id)
        
        if not notificacoes:
            # Se nÃ£o tem mais, voltar ao menu principal
            texto = "â€¢ <b>NOTIFICAÃ‡Ã•ES DE REABASTECIMENTO</b>\n\n"
            texto += "VocÃª nÃ£o tem notificaÃ§Ãµes ativas."
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton('âœ… Adicionar Produto', callback_data='add_notif_reabast'))
            markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
        else:
            texto = "â€¢ <b>REMOVER NOTIFICAÃ‡ÃƒO</b>\n\nSelecione o produto:"
            markup = InlineKeyboardMarkup()
            
            for item in notificacoes:
                markup.row(InlineKeyboardButton(
                    f"âœ… {item['produto']}", 
                    callback_data=f"del_notif|{item['produto']}"
                ))
            
            markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_notif'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            pass
        return
    
    # Limpar todas as notificaÃ§Ãµes
    if call.data == 'limpar_notif_reabast':
        user_id = call.from_user.id
        database.limpar_notificacoes_reabastecimento(user_id)
        bot.answer_callback_query(call.id, "â€¢ Todas as notificaÃ§Ãµes foram removidas!", show_alert=True)
        
        texto = "â€¢ <b>NOTIFICAÃ‡Ã•ES DE REABASTECIMENTO</b>\n\n"
        texto += "VocÃª nÃ£o tem notificaÃ§Ãµes ativas."
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âœ… Adicionar Produto', callback_data='add_notif_reabast'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        return
    
    # Voltar ao menu de notificaÃ§Ãµes
    if call.data == 'voltar_notif':
        user_id = call.from_user.id
        notificacoes = database.get_notificacoes_reabastecimento(user_id)
        
        texto = "â€¢ <b>NOTIFICAÃ‡Ã•ES DE REABASTECIMENTO</b>\n\n"
        
        if notificacoes:
            texto += f"VocÃª serÃ© notificado quando estes produtos voltarem ao estoque:\n\n"
            for i, item in enumerate(notificacoes, 1):
                texto += f"{i}. {html.escape(item['produto'])}\n"
            texto += f"\nâ€¢ Total: {len(notificacoes)} produto(s)"
        else:
            texto += "VocÃª nÃ£o tem notificaÃ§Ãµes ativas."
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('âœ… Adicionar Produto', callback_data='add_notif_reabast'))
        if notificacoes:
            markup.row(InlineKeyboardButton('â€¢ Remover Produto', callback_data='remove_notif_reabast'))
            markup.row(InlineKeyboardButton('â€¢ Limpar Todas', callback_data='limpar_notif_reabast'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_menu'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        return

    # =====================
    # Callbacks de Gerenciamento de Backups
    # =====================
    
    # Menu principal de backups
    if call.data == 'menu_backups':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        status = backup_manager.get_status()
        
        texto = "â€¢ <b>GERENCIAMENTO DE BACKUPS</b>\n\n"
        texto += f"â€¢ <b>Backup AutomÃ©tico:</b> {'âœ… Ativado' if status['auto_backup_enabled'] else 'âœ… Desativado'}\n"
        texto += f"âœ… <b>Intervalo:</b> {status['backup_interval_hours']} horas\n"
        texto += f"â€¢ <b>MÃ©ximo de backups:</b> {status['max_backups']}\n"
        texto += f"â€¢ <b>Total de backups:</b> {status['total_backups']}\n"
        
        if status['last_backup']:
            try:
                last_backup = datetime.datetime.fromisoformat(status['last_backup'])
                texto += f"â€¢ <b>Ã©ltimo backup:</b> {last_backup.strftime('%d/%m/%Y %H:%M:%S')}\n"
            except:
                texto += f"â€¢ <b>Ã©ltimo backup:</b> N/A\n"
        else:
            texto += f"â€¢ <b>Ã©ltimo backup:</b> Nunca\n"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Criar Backup Agora', callback_data='criar_backup'))
        markup.row(InlineKeyboardButton('â€¢ Ver Backups', callback_data='listar_backups'))
        markup.row(InlineKeyboardButton('â€¢ Importar Database ZIP', callback_data='importar_database_zip'))
        
        if status['auto_backup_enabled']:
            markup.row(InlineKeyboardButton('âœ… Desativar Auto-Backup', callback_data='desativar_auto_backup'))
        else:
            markup.row(InlineKeyboardButton('âœ… Ativar Auto-Backup', callback_data='ativar_auto_backup'))
        
        markup.row(InlineKeyboardButton('âš™ï¸ Configurar Intervalo', callback_data='config_intervalo_backup'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_paineladm'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        return

    if call.data == 'importar_database_zip':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return

        bot.answer_callback_query(call.id)
        pedir_importar_database(call.message)
        return

    if call.data == 'admin_roleta':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        mostrar_admin_roleta(call.message)
        return

    if call.data == 'admin_vip':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        mostrar_admin_vip(call.message)
        return

    if call.data == 'vip_toggle':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        ativo = api.ClubeVIP.mudar_status()
        bot.answer_callback_query(call.id, "Clube VIP ativado." if ativo else "Clube VIP desativado.", show_alert=True)
        mostrar_admin_vip(call.message)
        return

    if call.data.startswith('vip_edit|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        try:
            index = int(call.data.split('|', 1)[1])
            nivel = api.ClubeVIP.config().get('niveis', [])[index]
        except Exception:
            bot.answer_callback_query(call.id, "Nível não encontrado.", show_alert=True)
            return
        pending_vip_level_edit[call.message.chat.id] = {'index': index}
        bot.send_message(
            call.message.chat.id,
            (
                f"Editando {html.escape(str(nivel.get('nome', 'VIP')))}.\n\n"
                "Envie o valor mínimo e a porcentagem de cashback:\n"
                "<code>50/2</code>\n\n"
                "Também aceito quebrado: <code>50,00/2,5</code>"
            ),
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, receber_edicao_nivel_vip)
        bot.answer_callback_query(call.id)
        return

    if call.data == 'roleta_admin_toggle':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        config = carregar_config_roleta()
        config["status"] = "off" if config.get("status") == "on" else "on"
        salvar_config_roleta(config)
        bot.answer_callback_query(call.id, "Status da roleta atualizado.", show_alert=True)
        mostrar_admin_roleta(call.message)
        return

    if call.data == 'roleta_admin_min':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        pedir_config_roleta(call.message, 'valor_min', 'valor mínimo')
        return

    if call.data == 'roleta_admin_max':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        pedir_config_roleta(call.message, 'valor_max', 'valor máximo')
        return

    if call.data == 'roleta_admin_chance':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        pedir_config_roleta(call.message, 'chance_ganhar', 'chance de ganhar em %')
        return

    if call.data == 'roleta_admin_tempo_toggle':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        config = carregar_config_roleta()
        config["limite_tempo"] = "off" if config.get("limite_tempo") == "on" else "on"
        salvar_config_roleta(config)
        bot.answer_callback_query(call.id, "Limite de tempo atualizado.", show_alert=True)
        mostrar_admin_roleta(call.message)
        return

    if call.data == 'roleta_admin_tempo_horas':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        pedir_config_roleta(call.message, 'tempo_horas', 'tempo entre giros em horas')
        return
    
    # Criar backup manual
    if call.data == 'criar_backup':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "âœ… Criando backup...", show_alert=True)
        
        backup_path = backup_manager.create_backup()
        
        if backup_path and os.path.exists(backup_path):
            # Enviar arquivo
            try:
                with open(backup_path, 'rb') as f:
                    bot.send_document(
                        call.message.chat.id,
                        f,
                        caption=f"â€¢ <b>Backup criado com sucesso!</b>\n\nâ€¢ {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                        parse_mode='HTML'
                    )
            except Exception as e:
                bot.send_message(call.message.chat.id, f"âœ… Backup criado mas erro ao enviar: {e}")
        else:
            bot.send_message(call.message.chat.id, "âœ… Erro ao criar backup!")
        
        return
    
    # Listar backups
    if call.data == 'listar_backups':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        backups = backup_manager.list_backups()
        
        if not backups:
            texto = "â€¢ <b>LISTA DE BACKUPS</b>\n\nNenhum backup encontrado."
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='menu_backups'))
        else:
            texto = f"â€¢ <b>LISTA DE BACKUPS</b>\n\n"
            texto += f"Total: {len(backups)} backup(s)\n\n"
            
            for i, backup in enumerate(backups[:10], 1):
                size_mb = backup['size'] / (1024 * 1024)
                texto += f"{i}. <b>{backup['name']}</b>\n"
                texto += f"   â€¢ {backup['date'].strftime('%d/%m/%Y %H:%M:%S')}\n"
                texto += f"   â€¢ {size_mb:.2f} MB\n\n"
            
            markup = InlineKeyboardMarkup()
            for backup in backups[:5]:
                markup.row(InlineKeyboardButton(
                    f"â€¢ {backup['name'][:30]}...",
                    callback_data=f"download_backup|{backup['name']}"
                ))
            markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='menu_backups'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        return
    
    # Download de backup especÃ©fico
    if call.data.startswith('download_backup|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        backup_name = call.data.split('|')[1]
        backup_path = os.path.join('backups', backup_name)
        
        if os.path.exists(backup_path):
            bot.answer_callback_query(call.id, "â€¢ Enviando backup...", show_alert=True)
            try:
                with open(backup_path, 'rb') as f:
                    bot.send_document(call.message.chat.id, f, caption=f"â€¢ Backup: {backup_name}")
            except Exception as e:
                bot.send_message(call.message.chat.id, f"âœ… Erro ao enviar: {e}")
        else:
            bot.answer_callback_query(call.id, "âœ… Backup nÃ£o encontrado!", show_alert=True)
        
        return
    
    # Ativar auto-backup
    if call.data == 'ativar_auto_backup':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        backup_manager.enable_auto_backup()
        bot.answer_callback_query(call.id, "âœ… Backup automÃ©tico ativado!", show_alert=True)
        
        # Atualizar menu
        status = backup_manager.get_status()
        texto = "â€¢ <b>GERENCIAMENTO DE BACKUPS</b>\n\n"
        texto += f"â€¢ <b>Backup AutomÃ©tico:</b> {'âœ… Ativado' if status['auto_backup_enabled'] else 'âœ… Desativado'}\n"
        texto += f"âœ… <b>Intervalo:</b> {status['backup_interval_hours']} horas\n"
        texto += f"â€¢ <b>MÃ©ximo de backups:</b> {status['max_backups']}\n"
        texto += f"â€¢ <b>Total de backups:</b> {status['total_backups']}\n"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Criar Backup Agora', callback_data='criar_backup'))
        markup.row(InlineKeyboardButton('â€¢ Ver Backups', callback_data='listar_backups'))
        markup.row(InlineKeyboardButton('âœ… Desativar Auto-Backup', callback_data='desativar_auto_backup'))
        markup.row(InlineKeyboardButton('âš™ï¸ Configurar Intervalo', callback_data='config_intervalo_backup'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_paineladm'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            pass
        
        return
    
    # Desativar auto-backup
    if call.data == 'desativar_auto_backup':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        backup_manager.disable_auto_backup()
        bot.answer_callback_query(call.id, "âœ… Backup automÃ©tico desativado!", show_alert=True)
        
        # Atualizar menu
        status = backup_manager.get_status()
        texto = "â€¢ <b>GERENCIAMENTO DE BACKUPS</b>\n\n"
        texto += f"â€¢ <b>Backup AutomÃ©tico:</b> {'âœ… Ativado' if status['auto_backup_enabled'] else 'âœ… Desativado'}\n"
        texto += f"âœ… <b>Intervalo:</b> {status['backup_interval_hours']} horas\n"
        texto += f"â€¢ <b>MÃ©ximo de backups:</b> {status['max_backups']}\n"
        texto += f"â€¢ <b>Total de backups:</b> {status['total_backups']}\n"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Criar Backup Agora', callback_data='criar_backup'))
        markup.row(InlineKeyboardButton('â€¢ Ver Backups', callback_data='listar_backups'))
        markup.row(InlineKeyboardButton('âœ… Ativar Auto-Backup', callback_data='ativar_auto_backup'))
        markup.row(InlineKeyboardButton('âš™ï¸ Configurar Intervalo', callback_data='config_intervalo_backup'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_paineladm'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            pass
        
        return
    
    # Configurar intervalo
    if call.data == 'config_intervalo_backup':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        texto = "âš™ï¸ <b>CONFIGURAR INTERVALO</b>\n\nEscolha o intervalo entre backups automÃ©ticos:"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('1 hora', callback_data='set_interval|1'))
        markup.row(InlineKeyboardButton('3 horas', callback_data='set_interval|3'))
        markup.row(InlineKeyboardButton('6 horas', callback_data='set_interval|6'))
        markup.row(InlineKeyboardButton('12 horas', callback_data='set_interval|12'))
        markup.row(InlineKeyboardButton('24 horas', callback_data='set_interval|24'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='menu_backups'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        return
    
    # Definir intervalo
    if call.data.startswith('set_interval|'):
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        
        hours = int(call.data.split('|')[1])
        backup_manager.config['backup_interval_hours'] = hours
        backup_manager.save_config()
        
        bot.answer_callback_query(call.id, f"âœ… Intervalo definido para {hours} hora(s)!", show_alert=True)
        
        # Voltar ao menu
        status = backup_manager.get_status()
        texto = "â€¢ <b>GERENCIAMENTO DE BACKUPS</b>\n\n"
        texto += f"â€¢ <b>Backup AutomÃ©tico:</b> {'âœ… Ativado' if status['auto_backup_enabled'] else 'âœ… Desativado'}\n"
        texto += f"âœ… <b>Intervalo:</b> {status['backup_interval_hours']} horas\n"
        texto += f"â€¢ <b>MÃ©ximo de backups:</b> {status['max_backups']}\n"
        texto += f"â€¢ <b>Total de backups:</b> {status['total_backups']}\n"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('â€¢ Criar Backup Agora', callback_data='criar_backup'))
        markup.row(InlineKeyboardButton('â€¢ Ver Backups', callback_data='listar_backups'))
        
        if status['auto_backup_enabled']:
            markup.row(InlineKeyboardButton('âœ… Desativar Auto-Backup', callback_data='desativar_auto_backup'))
        else:
            markup.row(InlineKeyboardButton('âœ… Ativar Auto-Backup', callback_data='ativar_auto_backup'))
        
        markup.row(InlineKeyboardButton('âš™ï¸ Configurar Intervalo', callback_data='config_intervalo_backup'))
        markup.row(InlineKeyboardButton('â€¢ Voltar', callback_data='voltar_paineladm'))
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=texto,
                parse_mode='HTML',
                reply_markup=markup
            )
        except Exception:
            pass
        
        return

    # =====================
    # Callbacks do Carrinho de Compras
    # =====================
    
    # Perguntar quantidade para adicionar ao carrinho
    if call.data.startswith('qtd_carrinho_ask|'):
        servico = resolve_service_callback_token(call.data.split('|', 1)[1]) or call.data.split('|', 1)[1]
        user_id = call.from_user.id
        
        # Marcar que estÃ© esperando quantidade
        pending_carrinho_qtd[user_id] = servico
        
        bot.send_message(
            call.message.chat.id,
            f"â€¢ Quantos logins de <b>{html.escape(servico)}</b> deseja adicionar ao carrinho?\n\nDigite a quantidade:",
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
        return
    
    # Perguntar quantidade para comprar direto
    if call.data.startswith('qtd_comprar_ask|'):
        servico = resolve_service_callback_token(call.data.split('|', 1)[1]) or call.data.split('|', 1)[1]
        msg = bot.send_message(
            call.message.chat.id,
            f"Quantos logins de {servico} vocÃ© deseja comprar?",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(msg, processar_compra_quantidade, servico)
        bot.answer_callback_query(call.id)
        return
    
    # Adicionar ao carrinho
    if call.data.startswith('add_carrinho|') or call.data.startswith('add_carrinho '):
        if call.data.startswith('add_carrinho|'):
            servico = resolve_service_callback_token(call.data.split('|', 1)[1])
        else:
            servico = call.data.replace('add_carrinho ', '')
        if not servico:
            bot.answer_callback_query(call.id, "ServiÃ©o esgotado ou nÃ£o encontrado!", show_alert=True)
            return
        user_id = call.from_user.id
        
        # Pegar valor do serviÃ§o
        try:
            nome_servico, valor, descricao, duracao, email = api.ControleLogins.pegar_info(servico)
            database.add_to_carrinho(user_id, servico, valor)
            
            qtd_carrinho = database.get_carrinho_quantidade_total(user_id)
            total_carrinho = database.get_carrinho_total(user_id)
            
            # Mostrar mensagem com opÃ§Ãµes
            texto = f"âœ… <b>PRODUTO ADICIONADO AO CARRINHO!</b>\n\n"
            texto += f"â€¢ <b>Produto:</b> {html.escape(servico)}\n"
            texto += f"â€¢ <b>Valor:</b> R$ {valor}\n\n"
            texto += f"â€¢ <b>Total no carrinho:</b> {qtd_carrinho} itens\n"
            texto += f"â€¢ <b>Valor total:</b> R$ {total_carrinho:.2f}\n\n"
            texto += "O que deseja fazer?"
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton('â€¢ Ver Carrinho', callback_data='ver_carrinho'))
            markup.row(InlineKeyboardButton('âœ… Adicionar Mais Produtos', callback_data='servicos'))
            markup.row(InlineKeyboardButton('âœ… Finalizar Compra', callback_data='finalizar_carrinho'))
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=texto,
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except Exception:
                bot.send_message(call.message.chat.id, texto, parse_mode='HTML', reply_markup=markup)
            
            bot.answer_callback_query(call.id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"âœ… Erro: {str(e)}", show_alert=True)
        return
    
    # Ver carrinho
    if call.data == 'ver_carrinho':
        exibir_carrinho(call)
        return
    
    # Limpar carrinho
    if call.data == 'limpar_carrinho':
        user_id = call.from_user.id
        database.clear_carrinho(user_id)
        bot.answer_callback_query(call.id, "â€¢ Carrinho limpo!", show_alert=True)
        exibir_carrinho(call)
        return
    
    # Editar carrinho
    if call.data == 'editar_carrinho':
        exibir_editar_carrinho(call)
        return
    
    # Editar item especÃ©fico
    if call.data.startswith('edit_item_carrinho|'):
        servico = call.data.split('|')[1]
        exibir_opcoes_item_carrinho(call, servico)
        return
    
    # Alterar quantidade
    if call.data.startswith('qtd_carrinho|'):
        parts = call.data.split('|')
        servico = parts[1]
        operacao = parts[2]
        user_id = call.from_user.id
        
        carrinho = database.get_carrinho(user_id)
        item = next((i for i in carrinho if i['servico'] == servico), None)
        
        if item:
            nova_qtd = item['quantidade'] + (1 if operacao == '+1' else -1)
            if nova_qtd > 0:
                database.update_quantidade_carrinho(user_id, servico, nova_qtd)
                exibir_opcoes_item_carrinho(call, servico)
            else:
                database.remove_from_carrinho(user_id, servico)
                bot.answer_callback_query(call.id, "Item removido!", show_alert=True)
                exibir_editar_carrinho(call)
        return
    
    # Remover item
    if call.data.startswith('remove_carrinho|'):
        servico = call.data.split('|')[1]
        user_id = call.from_user.id
        database.remove_from_carrinho(user_id, servico)
        bot.answer_callback_query(call.id, "â€¢ Item removido!", show_alert=True)
        exibir_editar_carrinho(call)
        return
    
    # Finalizar compra do carrinho
    if call.data == 'finalizar_carrinho':
        user_id = call.from_user.id
        carrinho = database.get_carrinho(user_id)
        
        if not carrinho:
            bot.answer_callback_query(call.id, "Carrinho vazio!", show_alert=True)
            return
        
        total = database.get_carrinho_total(user_id)
        saldo = database.get_user_balance(user_id)
        
        if saldo < total:
            bot.answer_callback_query(
                call.id,
                f"âœ… Saldo insuficiente!\nTotal: R$ {total:.2f}\nSeu saldo: R$ {saldo:.2f}",
                show_alert=True
            )
            return
        
        solicitar_aceite_termos(call.message, 'carrinho', {})
        bot.answer_callback_query(call.id, "Confirme os termos para continuar.", show_alert=True)
        return

    if call.data == 'vendas_mes_btn':
        if not _admin_only(call):
            bot.answer_callback_query(call.id, 'â€¢ Sem permissÃ£o.', show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        # Calcular inÃ©cio e fim do mÃ©s
        agora = datetime.datetime.now()
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Calcular Ã©ltimo dia do mÃ©s
        if agora.month == 12:
            fim_mes = agora.replace(year=agora.year + 1, month=1, day=1, hour=23, minute=59, second=59)
        else:
            fim_mes = agora.replace(month=agora.month + 1, day=1, hour=23, minute=59, second=59)
        fim_mes = fim_mes - datetime.timedelta(seconds=1)
        
        # Buscar estatÃ©sticas
        stats = database.get_sales_stats(inicio_mes, fim_mes)
        
        texto = f"â€¢ <b>ESTATÃ©STICAS DO MÃ©S ({agora.strftime('%m/%Y')})</b>\n\n"
        texto += f"â€¢ <b>Total de vendas:</b> {stats['total_vendas']}\n"
        texto += f"â€¢ <b>Valor total:</b> R$ {stats['total_valor']:.2f}\n"
        if stats['total_vendas'] > 0:
            texto += f"â€¢ <b>Ticket mÃ©dio:</b> R$ {(stats['total_valor'] / stats['total_vendas']):.2f}\n"
        texto += f"\n{'='*30}\n\n"
        texto += f"<b>â€¢ PRODUTOS MAIS VENDIDOS:</b>\n\n"
        
        # Ordenar produtos por quantidade
        produtos_ordenados = sorted(
            stats['produtos_vendidos'].items(),
            key=lambda x: x[1]['quantidade'],
            reverse=True
        )
        
        for i, (produto, info) in enumerate(produtos_ordenados[:10], 1):
            texto += f"{i}. <b>{produto}</b>\n"
            texto += f"   â€¢ Quantidade: {info['quantidade']}\n"
            texto += f"   â€¢ Total: R$ {info['valor_total']:.2f}\n\n"
        
        bot.send_message(call.message.chat.id, texto, parse_mode='HTML')
        return


    # Definir os tipos de rankings disponÃ©veis
    tipos_rankings = ['rank_balance', 'rank_depositors', 'rank_products', 'rank_recent_depositors']

    if call.data in tipos_rankings:
        atualizar_mensagem_rank(call, call.data)
        return

    if call.data == 'menu_start':
        # Voltar ao menu principal
        texto = api.Textos.start(call.message)
        markup = gerar_menu_principal()
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto,
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    if call.data == 'roleta_sorte':
        mostrar_roleta(call)
        bot.answer_callback_query(call.id)
        return

    if call.data == 'roleta_girar':
        girar_roleta(call)
        return

    if call.data == 'indique_ganhe':
        mostrar_indique_ganhe(call)
        bot.answer_callback_query(call.id)
        return

    if call.data == 'clube_vip':
        mostrar_clube_vip(call)
        bot.answer_callback_query(call.id)
        return
        
    if call.data == 'ver_termos':
        bot.send_message(call.message.chat.id, termos_texto, parse_mode='HTML')

    if call.data == 'termos_inatividade':
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='voltar_inatividade'))
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=termos_texto,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == 'voltar_inatividade':
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=texto_inatividade_cliente(),
            parse_mode='HTML',
            reply_markup=markup_inatividade_cliente()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == 'jogos_hoje':
        texto_jogos = jf_final.formatar_jogos_telegram()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('â€¢ Ver CatÃ¡logo', callback_data='servicos'))
        markup.add(InlineKeyboardButton('âœ… Voltar', callback_data='menu_start'))
        bot.send_message(call.message.chat.id, texto_jogos, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)
    
    if call.data == 'filmes_alta':
        texto_filmes = jf_final.formatar_filmes_telegram()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('â€¢ Ver CatÃ¡logo', callback_data='servicos'))
        markup.add(InlineKeyboardButton('âœ… Voltar', callback_data='menu_start'))
        bot.send_message(call.message.chat.id, texto_filmes, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

  
    if call.data == 'ver_rank':
      handle_rank(call.message)
  
    if call.data == 'mudar_token_bot':
        bot.send_message(call.message.chat.id, "Envie o novo token do bot:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(call.message, trocar_token)
        return
    if call.data == 'pegar_admin_creator':
        if api.Admin.verificar_admin(call.message.chat.id) == False:
            api.Admin.add_admin(call.message.chat.id)
            bot.answer_callback_query(call.id, "Feito!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "VocÃª jÃ¡ Ã© um admin!", show_alert=True)
    if call.data == 'mudar_user_bot':
        bot.send_message(call.message.chat.id, "Me envie o novo @ do bot:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(call.message, trocar_user)
        return
    if call.data == 'mudar_dono_bot':
        bot.send_message(call.message.chat.id, "Digite o id do novo dono:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(call.message, mudar_dono_bot)
        return
    if call.data == 'configurar_vencimento':
        txt = '<i>Selecione abaixo a opÃ§Ã£o desejada:</i>'
        bt = InlineKeyboardButton('âœ… AUMENTAR DIAS', callback_data='modificar_dias mais')
        bs = InlineKeyboardButton('âœ… DIMINUIR DIAS', callback_data='modificar_dias menos')
        bp = InlineKeyboardButton('âœ… ZERAR DIAS', callback_data='parar_dias_creator')
        vo = InlineKeyboardButton('âœ… VOLTAR', callback_data='voltar_painel_creator')
        markup = InlineKeyboardMarkup([[bt], [bs], [bp], [vo]])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=txt,
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    if call.data == 'parar_dias_creator':
        api.Admin.zerar_vencimento()
        bot.reply_to(call.message, "Os dias foram zerados!")
        return
    if call.data.split()[0] == 'modificar_dias':
        tipo = call.data.split()[1]
        bot.send_message(call.message.chat.id, "Digite a quantidade de dias:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(call.message, mudar_dias_vencimento, tipo)
        return
    if call.data == 'mudar_versao_bot':
        bot.send_message(call.message.chat.id, "Digite a nova versÃ£o do bot:", reply_markup=types.ForceReply())
        bot.register_next_step_handler(call.message, mudar_versao_bot)
    if call.data == 'voltar_painel_creator':
        handle_criador(call.message)
        return
    try:
        if api.InfoUser.verificar_ban(call.message.chat.id) == True:
            bot.reply_to(call.message, "VocÃª estÃ© banido neste bot e nÃ£o pode utiliza-lo!")
            return
    except:
        if api.InfoUser.verificar_ban(call.from_user.id) == True:
            bot.reply_to(call.message, "VocÃª estÃ© banido neste bot e nÃ£o pode utiliza-lo!")
            return

    if api.CredentialsChange.status_manutencao() == True:
        if api.Admin.verificar_admin(call.message.chat.id) == False:
            if api.CredentialsChange.id_dono() != int(call.message.chat.id):
                bot.answer_callback_query(call.id, "O bot esta em manutenÃ§Ã£o, voltaremos em breve!", show_alert=True)
                return
        bot.answer_callback_query(call.id, "O bot estÃ© em manutenÃ§Ã£o, mas vocÃ© foi identificado como administrador!", show_alert=True)

    if api.Admin.verificar_vencimento() == True:
        ver_se_expirou()
        return

    if call.data != 'reserve_verified_continue' and not is_owner_or_admin(call.from_user.id):
        if not ensure_reserve_access(call.from_user.id, call.message.chat.id):
            bot.answer_callback_query(call.id, "Entre no grupo reserva para continuar.", show_alert=True)
            return

    # =============== Voltar painel adm
    if call.data == 'voltar_paineladm':
        painel_admin(call.message)

    # =============== Menu inicial
    if call.data == 'perfil':
        perfil(call)
    if call.data == 'servicos':
        servicos(call.message)
    if call.data == 'addsaldo':
        addsaldo(call.message)

    # =============== Menu Pix
    if call.data == 'pix_manu':
        if api.CredentialsChange.StatusPix.pix_manual() == True:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f'{api.Textos.pix_manual(call.message)}',
                parse_mode='HTML'
            )
    if call.data == 'pix_auto':
        if api.CredentialsChange.StatusPix.pix_auto() == True:
            bot.send_message(
                chat_id=call.message.chat.id,
                text=(
                    f"Digite o valor que deseja recarregar!\n"
                    f"mÃ©nimo: R${api.CredentialsChange.InfoPix.deposito_minimo_pix():.2f}\n"
                    f"mÃ©ximo: R${api.CredentialsChange.InfoPix.deposito_maximo_pix():.2f}"
                ),
                reply_markup=types.ForceReply()
            )
            bot.register_next_step_handler(call.message, pix_auto)

    # =============== Menu serviÃ§os
    if call.data.startswith('exibir_servico|') or call.data.split()[0] == 'exibir_servico':
        if call.data.startswith('exibir_servico|'):
            nome = resolve_service_callback_token(call.data.split('|', 1)[1])
        else:
            nome = call.data.split()[1:]
            nome = ' '.join(nome)
        if not nome:
            bot.answer_callback_query(call.id, "ServiÃ§o esgotado ou nÃ£o encontrado!", show_alert=True)
            return
        exibir_servico(call.message, nome)
    if call.data.startswith('comprar|') or call.data.split()[0] == 'comprar':
        if call.data.startswith('comprar|'):
            servico = resolve_service_callback_token(call.data.split('|', 1)[1])
        else:
            servico = call.data.replace('comprar', '').strip()
        if not servico:
            bot.answer_callback_query(call.id, "ServiÃ§o esgotado ou nÃ£o encontrado!", show_alert=True)
            return
         
        resultado_peek = api.ControleLogins.peek_primeiro_disponivel(servico)
        if not resultado_peek:
            bot.answer_callback_query(
                call.id,
                "ServiÃ©o esgotado ou nÃ£o encontrado!",
                show_alert=True
            )
            return
        _, valor, _, _, _, _ = resultado_peek
        
        if float(api.InfoUser.saldo(call.message.chat.id)) < float(valor):
            falta = float(valor) - float(api.InfoUser.saldo(call.message.chat.id))
            bot.answer_callback_query(
                call.id,
                f"Saldo insuficiente! Faltam R${falta:.2f}. FaÃ©a uma recarga e tente novamente.",
                show_alert=True
            )
            return
       
        solicitar_aceite_termos(
            call.message,
            'direta',
            {'servico': servico}
        )
        bot.answer_callback_query(call.id, "Confirme os termos para continuar.", show_alert=True)


    # =============== Menu perfil
    if call.data == 'trocar_pontos':
        bot.answer_callback_query(
            call.id,
            "Agora a comissão de indicação cai direto no saldo, automaticamente.",
            show_alert=True
        )
        return
    if call.data == 'menu_start':
        handle_start(call.message)
    if call.data == 'alugarbot':
        alugarbot(call.message)

    # =============== ConfiguraÃ§Ãµes gerais
    if call.data == 'reiniciar_bot':
        bot.answer_callback_query(call.id, "Reiniciando...", show_alert=True)
        os._exit(0)
    if call.data == 'configuracoes_geral':
        configuracoes_geral(call.message)
    if call.data == 'manutencao':
        api.CredentialsChange.mudar_status_manutencao()
        bot.answer_callback_query(call.id, "Status de manutenÃ§Ã£o atualizado com sucesso!", show_alert=True)
        configuracoes_geral(call.message)
    if call.data == 'configurar_modo_exibicao':
        configurar_modo_exibicao(call.message)
    if call.data == 'set_modo_categorizado':
        api.CredentialsChange.mudar_modo_exibicao('categorizado')
        bot.answer_callback_query(call.id, "âœ… Modo Categorizado ativado!", show_alert=True)
        configurar_modo_exibicao(call.message)
    if call.data == 'set_modo_lista_direta':
        api.CredentialsChange.mudar_modo_exibicao('lista_direta')
        bot.answer_callback_query(call.id, "âœ… Modo Lista Direta ativado!", show_alert=True)
        configurar_modo_exibicao(call.message)
    if call.data == 'toggle_bot_reserva':
        status = toggle_reserve_verification()
        texto_status = "ativada" if status == "on" else "desativada"
        bot.answer_callback_query(call.id, f"VerificaÃ§Ã£o do bot reserva {texto_status}!", show_alert=True)
        configuracoes_geral(call.message)
    if call.data == 'alterar_bot_reserva':
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Me envie o link ou @ do bot reserva:\n\nExemplo: https://t.me/seu_bot_reserva",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_bot_reserva, call.id)
    if call.data == 'alterar_grupo_reserva':
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Me envie o link ou @ do grupo reserva:\n\nExemplo: https://t.me/seu_grupo_reserva",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_grupo_reserva, call.id)
    if call.data == 'alterar_id_grupo_reserva':
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Me envie o ID do grupo reserva:\n\nExemplo: -1001234567890\n\nDica: adicione o bot nesse grupo para ele conseguir verificar os membros.",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_id_grupo_reserva, call.id)
    if call.data == 'alterar_emojis_servicos':
        bot.send_message(
            chat_id=call.message.chat.id,
            text=(
                "Me envie o link do pacote de emojis premium que serÃ¡ usado nos serviÃ§os:\n\n"
                "Exemplo: https://t.me/addemoji/seu_pacote"
            ),
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_emojis_servicos, call.id)
    if call.data == 'limpar_verificacoes_reserva':
        clear_reserve_verified_users()
        bot.answer_callback_query(call.id, "VerificaÃ§Ãµes limpas. Todos precisarÃ£o verificar novamente.", show_alert=True)
        configuracoes_geral(call.message)
    if call.data == 'suporte':
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Me envie o novo link do suporte:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, trocar_suporte, call.id)
    if call.data == 'mudar_separador':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo separador:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_separador, call.id)

    # =============== ConfiguraÃ§Ãµes de login
    if call.data == 'configurar_logins':
        configurar_logins(call.message)
    if call.data == 'adicionar_login':
        separador = api.CredentialsChange.separador()
        bot.send_message(
            call.message.chat.id,
            f"Envie os acessos que deseja adicionar, no formato:\nNOME{separador}VALOR{separador}DESCRICAO{separador}EMAIL{separador}SENHA{separador}DURACAO",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, adicionar_login)
    if call.data == 'pesquisar_estoque_admin':
        bot.send_message(
            call.message.chat.id,
            "Envie o nome do serviÃ§o, email ou palavra da descriÃ§Ã£o que deseja pesquisar no estoque:",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, pesquisar_estoque_admin)
    if call.data == 'remover_login':
        bot.send_message(
            call.message.chat.id,
            f"Envie o login que deseja remover, no formato:\nNETFLIX{api.CredentialsChange.separador()}EMAIL",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, remover_login)
    if call.data == 'remover_por_plataforma':
        bot.send_message(
            call.message.chat.id,
            "Envie o nome da plataforma que deseja remover do estoque:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, remover_por_plataforma)
    if call.data == 'zerar_estoque':
        try:
            api.ControleLogins.zerar_estoque()
            bot.answer_callback_query(call.id, text="Estoque zerado com sucesso!", show_alert=True)
        except:
            bot.answer_callback_query(call.id, text="Falha ao zerar o estoque.", show_alert=True)
    if call.data == 'mudar_valor_servico':
        bot.send_message(
            call.message.chat.id,
            f"Digite o serviÃ§o e o novo valor, separados por {api.CredentialsChange.separador()}\nEx: NETFLIX{api.CredentialsChange.separador()}12.99",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_valor_servico)
    if call.data == 'mudar_valor_todos':
        bot.send_message(
            call.message.chat.id,
            "Me envie o novo valor dos acessos. Exemplo: 12.99",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_valor_todos)

    # =============== ConfiguraÃ§Ãµes de adms
    if call.data == 'configurar_admins':
        configurar_admins(call.message)
    if call.data == 'adicionar_adm':
        bot.send_message(
            call.message.chat.id,
            "Digite o id do novo adm:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, adicionar_adm)
    if call.data == 'remover_adm':
        bot.send_message(
            call.message.chat.id,
            "Digite o id do admin que serÃ© removido:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, remover_adm)
    if call.data == 'lista_adm':
        try:
            lista = api.Admin.listar_admins()
            bot.send_message(call.message.chat.id, text=lista, parse_mode='HTML')
        except:
            bot.send_message(call.message.chat.id, "Erro ao buscar lista de admin")

    # =============== ConfiguraÃ§Ãµes dos afiliados
    if call.data == 'configurar_afiliados':
        try:
            configurar_afiliados(call.message)
            bot.answer_callback_query(call.id)
        except Exception as error:
            print(f'[AFILIADOS] Erro ao abrir configuração: {error}')
            bot.answer_callback_query(call.id, 'Não foi possível abrir agora.', show_alert=True)
        return
    if call.data == 'mudar_status_afiliados':
        try:
            api.AfiliadosInfo.mudar_status_afiliado()
            bot.answer_callback_query(call.id, "Status alterado com sucesso!", show_alert=True)
            configurar_afiliados(call.message)
        except Exception:
            bot.answer_callback_query(call.id, "Falha ao mudar o status.", show_alert=True)
        return
    if call.data == 'pontos_por_recarga':
        bot.send_message(
            call.message.chat.id,
            "Me envie a quantidade de pontos que o usuÃ¡rio ganharÃ©, cada vez que o seu indicado fizer uma recarga:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, pontos_por_recarga)
    if call.data == 'pontos_minimo_converter':
        bot.send_message(
            call.message.chat.id,
            "Ok, me envie a quantidade de pontos minimo que o usuÃ¡rio precisa ter para converter seus pontos em saldo:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, pontos_minimo_converter)
    if call.data == 'multiplicador_para_converter':
        bot.send_message(
            call.message.chat.id,
            "Me envie o novo multiplicador:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, multiplicador_para_converter)

    # =============== ConfiguraÃ§Ãµes de usuarios
    if call.data == 'configurar_usuarios':
        configurar_usuarios(call.message)
    if call.data == 'transmitir_todos':
        if api.Admin.verificar_admin(call.message.chat.id) == True or int(call.message.chat.id) == int(api.CredentialsChange.id_dono()):
            api.FuncaoTransmitir.zerar_infos()
            bot.send_message(
                call.message.chat.id,
                "Me envie a mensagem que deseja transmitir:",
                reply_markup=types.ForceReply(),
                parse_mode='HTML'
            )
            bot.register_next_step_handler(call.message, transmitir_todos)
    if call.data == 'add_botao':
        if api.Admin.verificar_admin(call.message.chat.id) == True or int(call.message.chat.id) == int(api.CredentialsChange.id_dono()):
            bot.send_message(
                call.message.chat.id,
                "â€¢â€¢ <b>Agora envie a lista de botÃµes</b> para inserir no teclado embutido, com textos e links, "
                "<b>usando esta anÃ©lise:\n\n</b><code>Texto do botÃ©o - example.com\nTexto do botÃ©o - example.net\n\n</code>"
                "âœ… Se vocÃ© deseja configurar 2 botÃµes na mesma linha, separe-os com <code>&amp;&amp;</code>.\n\n"
                "<b>Exemplo:\n</b><code>Grupo - t.me/username &amp;&amp; Canal - t.me/username\nWhatsapp - wa.link/lo1oy6</code>",
                disable_web_page_preview=True,
                reply_markup=types.ForceReply(),
                parse_mode='HTML'
            )
            bot.register_next_step_handler(call.message, add_botao)
    if call.data == 'confirmar_envio':
        if api.Admin.verificar_admin(call.message.chat.id) == True or int(call.message.chat.id) == int(api.CredentialsChange.id_dono()):
            confirmar_envio(call.message)
    if call.data == 'pesquisar_usuario':
        bot.send_message(
            call.message.chat.id,
            "Digite o id do usuario:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, pesquisar_usuario)

    if call.data.split()[0] == 'banir':
        id = call.data.split()[1]
        if api.InfoUser.verificar_ban(id) == True:
            api.InfoUser.tirar_ban(id)
            bot.answer_callback_query(call.id, "Usuario desbanido!", show_alert=True)
            return
        else:
            api.InfoUser.dar_ban(id)
            bot.answer_callback_query(call.id, "Usuario banido!", show_alert=True)
            return
    if call.data.split()[0] == 'mudar_saldo':
        id = call.data.split()[1]
        bot.send_message(
            call.message.chat.id,
            f"Digite o novo saldo do usuario {id}:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_saldo, id)
    if call.data.split()[0] == 'baixar_historico':
        id = call.data.split()[1]
        api.InfoUser.fazer_txt_do_historico(id)
        with open(f'historicos/{id}.txt', 'rb') as file:
            bot.send_document(call.message.chat.id, document=file)

    # =============== ConfiguraÃ§Ãµes pix
    if call.data == 'configurar_pix':
        configurar_pix(call.message)
    if call.data == 'trocar_pix_manual':
        api.CredentialsChange.ChangeStatusPix.change_pix_manual()
        bot.answer_callback_query(call.id, "Alterado!", show_alert=True)
        configurar_pix(call.message)
    if call.data == 'trocar_pix_automatico':
        api.CredentialsChange.ChangeStatusPix.change_pix_auto()
        bot.answer_callback_query(call.id, "Alterado!", show_alert=True)
        configurar_pix(call.message)
    if call.data == 'mudar_token':
        bot.send_message(
            call.message.chat.id,
            "Me envie o novo token do mercado pago:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_token)
    if call.data == 'mudar_expiracao':
        bot.send_message(
            call.message.chat.id,
            f'Digite agora o novo tempo de expiraÃ§Ã£o (EM MINUTOS)',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_expiracao)
    if call.data == 'mudar_deposito_minimo':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo valor minimo:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_deposito_minimo)
    if call.data == 'mudar_deposito_maximo':
        bot.send_message(
            call.message.chat.id,
            "Envie o novo deposito maximo:",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_deposito_maximo)
    if call.data == 'mudar_bonus':
        bot.send_message(
            call.message.chat.id,
            'Me envie a porcentagem de bonus que o usuario ganharÃ© por cada depÃ©sito:\n\nPor favor, envie sem o caractÃ©r (%)',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_bonus)
    if call.data == 'mudar_min_bonus':
        bot.send_message(
            call.message.chat.id,
            "Digite o valor mÃ©nimo que o usuÃ¡rio precisa depositar para ganhar o bÃ©nus:",
            reply_markup=types.ForceReply()
        )

    # =============== ConfiguraÃ§Ãµes notificaÃ§Ã£o
    if call.data == 'config_destinos_reais':
        configurar_destinos_reais(call.message)
    if call.data == 'alterar_destino_vendas':
        bot.send_message(
            call.message.chat.id,
            "Me envie o ID do canal/grupo real para receber notificações de vendas e recargas:\n\n"
            "Exemplo: <code>-1001234567890</code>",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, alterar_destino_vendas)
    if call.data == 'alterar_destino_logs':
        bot.send_message(
            call.message.chat.id,
            "Me envie o ID do canal/grupo real para receber logs:\n\n"
            "Exemplo: <code>-1001234567890</code>",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, alterar_destino_logs)
    if call.data == 'configurar_notificacoes_fake':
        configurar_notificacoes(call.message)
    if call.data == 'status_notificacoes':
        api.Notificacoes.mudar_status_notificacoes()
        configurar_notificacoes(call.message)
    if call.data == 'mudar_grupo_alvo':
        bot.send_message(
            call.message.chat.id,
            'Me envie o id do novo grupo:',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, mudar_grupo_alvo)
    if call.data == 'tempo_min_saldo':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo tempo mÃ©nimo das notificaÃ§Ãµes (em segundos):",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, tempo_min_saldo)
    if call.data == 'tempo_max_saldo':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo tempo mÃ©ximo das notificaÃ§Ãµes (em segundos):",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, tempo_max_saldo)
    if call.data == 'trocar_texto_saldo':
        bot.send_message(
            call.message.chat.id,
            '<b>Envie agora a mensagem de notificaÃ§Ã£o de saldo!</b>\n\n'
            'VocÃª pode usar <a href="http://telegram.me/MDtoHTMLbot?start=html">HTML</a> e:\n\n'
            'âœ… <code>{id}</code> = ID aleatÃ©rio\n'
            'âœ… <code>{saldo}</code> = saldo aleatorio',
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, trocar_texto_saldo)
    if call.data == 'trocar_min_max_saldo':
        bot.send_message(
            call.message.chat.id,
            f"Envie o minimo e o maximo se saldo que as notificaÃ§Ãµes escolherÃ©o, separados por {api.CredentialsChange.separador()}\n"
            f"<b>Ex:</b> 5{api.CredentialsChange.separador()}20",
            reply_markup=types.ForceReply(),
            parse_mode='HTML'
        )
        bot.register_next_step_handler(call.message, trocar_min_max_saldo)
    if call.data == 'trocar_min_max_ids':
        bot.send_message(
            call.message.chat.id,
            f"Envie o ID mínimo e o ID máximo para o campo {{id}}, separados por {api.CredentialsChange.separador()}\n"
            f"<b>Ex:</b> 1000000000{api.CredentialsChange.separador()}9999999999",
            reply_markup=types.ForceReply(),
            parse_mode='HTML'
        )
        bot.register_next_step_handler(call.message, trocar_min_max_ids)
    if call.data == 'tempo_min_compra':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo tempo mÃ©nimo das notificaÃ§Ãµes (em segundos):",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, tempo_min_compra)
    if call.data == 'tempo_max_compra':
        bot.send_message(
            call.message.chat.id,
            "Digite o novo tempo mÃ©ximo das notificaÃ§Ãµes (em segundos):",
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, tempo_max_compra)
    if call.data == 'trocar_texto_compra':
        bot.send_message(
            call.message.chat.id,
            '<b>Envie agora a mensagem de start!</b>\n\n'
            'VocÃª pode usar <a href="http://telegram.me/MDtoHTMLbot?start=html">HTML</a> e:\n\n'
            'âœ… <code>{id}</code> = ID aleatÃ©rio\n'
            'âœ… <code>{servico}</code> = serviÃ§o aleatÃ©rio\n'
            'âœ… <code>{valor}</code> = valor do serviÃ§o aleatÃ©rio',
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, trocar_texto_compra)
    if call.data == 'trocar_servicos':
        bot.send_message(
            call.message.chat.id,
            "Digite a lista dos serviÃ§os que serÃ©o sorteados nas notificaÃ§Ãµes fakes, "
            "lembre-se de enviar o valor na frente no serviÃ§o com 'R$' e pular uma linha.\n\n"
            "Ex:\nnetflix R$9,00\nglobo play + premiere R$9,00",
            parse_mode='HTML',
            reply_markup=types.ForceReply()
        )
        bot.register_next_step_handler(call.message, trocar_servicos)
    if call.data == 'mudar_tipo_servico':
        api.Notificacoes.mudar_modo_servico()
        configurar_notificacoes(call.message)

    # =============== ConfiguraÃ§Ãµes gift card
    if call.data == 'gift_card':
        gift_card(call.message)
    if 'resgatar' in call.data.strip().split()[0]:
        id = call.from_user.id
        codigo = call.data.strip().split()[1]
        processar_resgate(int(id), codigo)


from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import threading, time
import json
import requests


@bot.message_handler(commands=['pix', f'pix@{api.CredentialsChange.user_bot()}'])
def gerar_pix_por_comando(message: Message):
    
    if api.Admin.verificar_vencimento():
        ver_se_expirou()
        return
    if api.InfoUser.verificar_ban(message.from_user.id):
        bot.reply_to(message, "VocÃª estÃ© banido e nÃ£o pode usar o bot!")
        return

    partes = message.text.strip().split()
  
    if len(partes) != 2:
        return

     
    valor_str = partes[1].replace("R$", "").replace(",", ".").strip()
    try:
        valor = float(valor_str)
    except ValueError:
        bot.reply_to(message, "Valor invÃ©lido! Digite algo como /pix 10 ou /pix 10.00")
        return

    
    minimo = float(api.CredentialsChange.InfoPix.deposito_minimo_pix())
    maximo = float(api.CredentialsChange.InfoPix.deposito_maximo_pix())
    if not (minimo <= valor <= maximo):
        bot.reply_to(
            message,
            f"Valor invÃ©lido! Digite um valor entre R${minimo:.2f} e R${maximo:.2f}"
        )
        return

    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8') as f:
            cred = json.load(f)
    except Exception:
        cred = {}
    if 'gateway_pagamento' not in cred:
        cred['gateway_pagamento'] = {'selecionada': 'mercado_pago', 'mercado_pago': {}}
    if 'pushinpay' not in cred['gateway_pagamento']:
        cred['gateway_pagamento']['pushinpay'] = {}

    gateway_selecionada = cred['gateway_pagamento']['selecionada']
    print(f'[DEBUG] Gateway selecionada: {gateway_selecionada}')
    if gateway_selecionada == 'mercado_pago':
        print('[DEBUG] Iniciando fluxo Mercado Pago')
        payment = api.CriarPix.gerar(valor, message.chat.id)
        resp = payment['response']
        id_pag = resp['id']
        pix_copia_cola = resp['point_of_interaction']['transaction_data']['qr_code']
        qr_code_base64 = resp['point_of_interaction']['transaction_data']['qr_code_base64']

         
        import base64  # Garante o import no escopo correto
        header, encoded = qr_code_base64.split(",", 1) if qr_code_base64.startswith("data:image") else ("", qr_code_base64)
        qr_image = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
        with open('qrcode.png', 'wb') as f:
            f.write(qr_image)

      
        caption = api.Textos.pix_automatico(message, pix_copia_cola, 15, id_pag, f"{valor:.2f}")
        sent = bot.send_photo(
            chat_id=message.chat.id,
            photo=open('qrcode.png', 'rb'),
            caption=caption,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
            ])
        )

       
        import threading  # Garante o import correto no escopo
        print('[DEBUG] Iniciando verificaÃ§Ã£o Mercado Pago')
        threading.Thread(
            target=verificar_pagamento,
            args=(message.chat.id, id_pag, valor, sent.message_id),
            daemon=True
        ).start()

    elif gateway_selecionada == 'pushinpay':
        import random
        try:
            with open('pessoas.json', 'r', encoding='utf-8') as f:
                pessoas = json.load(f).get('pessoa', [])
            pessoa = random.choice(pessoas)
            nome = pessoa['nome']
            cpf = pessoa['cpf']
            print(f'[DEBUG] Pessoa sorteada: nome={nome}, cpf={cpf}')
        except Exception as e:
            print(f'[ERRO] Falha ao ler pessoas.json: {e}')
            bot.send_message(message.chat.id, f'âœ… Erro ao obter dados de pessoa para o Pix: {e}')
            return

        headers = {
            'Authorization': f'Bearer {cred["gateway_pagamento"]["pushinpay"]["token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        print(f'[DEBUG] Headers PushinPay: {headers}')

        # PushinPay espera o valor em centavos (int)
        valor_centavos = int(round(float(valor) * 100))
        data = {
            'value': valor_centavos
            # 'webhook_url': 'https://seusite.com' # opcional, adicione se desejar receber notificaÃ§Ãµes
            # 'split_rules': [] # opcional
        }
        print(f'[DEBUG] Payload enviado para PushinPay: {data}')

        import requests  # Garante o import correto no escopo
        try:
            response = requests.post('https://api.pushinpay.com.br/api/pix/cashIn', headers=headers, json=data)
            print(f'[DEBUG] Status code PushinPay: {response.status_code}')
            print(f'[DEBUG] Resposta PushinPay: {response.text}')
        except Exception as e:
            print(f'[ERRO] Falha ao requisitar PushinPay: {e}')
            bot.send_message(message.chat.id, f'âœ… Erro ao criar cobranÃ©a na PushinPay: {e}')
            return

        if response.status_code == 200:
            res_json = response.json()
            charge_id = res_json.get('id')
            qr_code = res_json.get('qr_code')
            qr_code_base64 = res_json.get('qr_code_base64')
            print(f'[DEBUG] CobranÃ©a criada com sucesso: id={charge_id}, qr_code={qr_code}')
            # Monta texto a partir do template
            with open('textos/pix_automatico.txt', 'r', encoding='utf-8') as f:
                texto_pix = f.read()
            expiracao = 15  # ou pegue do config
            valor_formatado = f'R${float(valor):.2f}'
            texto_pix = texto_pix.format(
                expiracao=expiracao,
                valor=valor_formatado,
                id_pagamento=charge_id,
                pix_copia_cola=qr_code
            )
            # BotÃ©o para consultar status
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton('â€¢ Consultar pagamento', callback_data=f'consultar_pix_pushinpay_{charge_id}'))
            if qr_code_base64:
                import base64
                from io import BytesIO
                from PIL import Image
                img_data = base64.b64decode(qr_code_base64.split(',')[-1])
                bio = BytesIO(img_data)
                bio.seek(0)
                # Redimensionar imagem para largura menor (ex: 350px), mantendo proporÃ§Ã£o
                try:
                    bio.seek(0)
                    img = Image.open(bio)
                    max_width = 350
                    if img.width > max_width:
                        ratio = max_width / float(img.width)
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height), Image.LANCZOS)
                        bio_resized = BytesIO()
                        img.save(bio_resized, format='PNG')
                        bio_resized.seek(0)
                        bot.send_photo(message.chat.id, bio_resized, caption=texto_pix, parse_mode='HTML', reply_markup=markup)
                    else:
                        bio.seek(0)
                        bot.send_photo(message.chat.id, bio, caption=texto_pix, parse_mode='HTML', reply_markup=markup)
                except Exception as e:
                    print(f'[ERRO] Falha ao redimensionar/enviar QRCode: {e}')
                    bio.seek(0)
                    bot.send_photo(message.chat.id, bio, caption=texto_pix, parse_mode='HTML', reply_markup=markup)
            else:
                bot.send_message(message.chat.id, texto_pix, parse_mode='HTML', reply_markup=markup)

            # --- Consulta automÃ©tica do status do pagamento ---
            import threading, time, requests

            def verificar_pagamento_automatico(chat_id, charge_id, token, valor):
                print(f'[DEBUG] Iniciando verificaÃ§Ã£o automÃ©tica PushinPay para chat_id={chat_id}, charge_id={charge_id}, valor={valor}')
                admin_id = int(api.CredentialsChange.id_dono())
                tz = pytz.timezone('America/Sao_Paulo')
                url = f'https://api.pushinpay.com.br/api/transactions/{charge_id}'
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
                tentativas = 300  # 15min / 3s
                for i in range(tentativas):
                    try:
                        print(f'[DEBUG] [AUTO] Tentativa {i+1}/{tentativas}: verificando pagamento PushinPay para charge_id={charge_id}')
                        resp = requests.get(url, headers=headers)
                        print(f'[DEBUG] [AUTO] Consulta status PushinPay: {resp.status_code} - {resp.text}')
                        if resp.status_code == 200:
                            data = resp.json()
                            print(f'[DEBUG] [AUTO] JSON retornado: {data}')
                            status = data.get('status', '').lower()
                            print(f'[DEBUG] [AUTO] Status verificado: {status}')
                            if status == 'paid':
                                print(f'[DEBUG] [AUTO] Pagamento identificado como PAID (pago) para charge_id={charge_id}')
                                try:
                                    min_bonus = float(api.CredentialsChange.BonusPix.valor_minimo_para_bonus())
                                    bonus_pct = float(api.CredentialsChange.BonusPix.quantidade_bonus())
                                except:
                                    min_bonus, bonus_pct = float("inf"), 0.0
                                bonus_amt = valor * bonus_pct / 100 if valor >= min_bonus else 0.0
                                add_saldo(chat_id, valor + bonus_amt)
                                add_pagamento(chat_id, valor, 'pushinpay')
                                pagar_comissao_afiliado(chat_id, valor)
                                bot.send_message(chat_id, f'âœ… Pagamento aprovado! Saldo adicionado: R${valor:.2f}' + (f' (+BÃ©nus R${bonus_amt:.2f})' if bonus_amt else ''))
                                try:
                                    chat_info = bot.get_chat(chat_id)
                                    if chat_info.username:
                                        user_display = f"@{chat_info.username}"
                                    elif chat_info.first_name:
                                        user_display = chat_info.first_name
                                        if getattr(chat_info, 'last_name', None):
                                            user_display += f" {chat_info.last_name}"
                                    else:
                                        user_display = str(chat_id)
                                except Exception:
                                    user_display = str(chat_id)
                                
                                print('[DEBUG] [AUTO] Pagamento aprovado e saldo atualizado.')
                                try:
                                    bot.send_message(chat_id=admin_id, text=texto_adm, parse_mode='Markdown')
                                except Exception as e:
                                    print(f"[PushinPay] Falha ao notificar admin: {e}")
                                return
                            elif status in ['expired', 'cancelled']:
                                print(f'[DEBUG] [AUTO] Pagamento expirado/cancelado para charge_id={charge_id}')
                                try:
                                    with open('textos/pagamento_expirado.txt', 'r', encoding='utf-8') as f:
                                        template_expirado = f.read()
                                    texto_expirado = template_expirado.format(id_pagamento=charge_id)
                                except Exception as e:
                                    print(f"[PushinPay] Falha ao ler template de pagamento expirado: {e}")
                                    texto_expirado = f'âœ… Pagamento expirou/cancelado.\nID: {charge_id}'
                                bot.send_message(chat_id, texto_expirado, parse_mode='HTML')
                                return
                            else:
                                print(f'[DEBUG] [AUTO] Status atual: {status} (aguardando pagamento)')
                        else:
                            print(f'[DEBUG] [AUTO] Resposta HTTP nÃ£o OK: {resp.status_code}')
                    except Exception as e:
                        print(f'[ERRO] [AUTO] Falha ao consultar status PushinPay: {e}')
                    time.sleep(3)

                # Usa template de pagamento expirado para timeout tambÃ©m
                try:
                    with open('textos/pagamento_expirado.txt', 'r', encoding='utf-8') as f:
                        template_expirado = f.read()
                    texto_expirado = template_expirado.format(id_pagamento=charge_id)
                except Exception as e:
                    print(f"[PushinPay] Falha ao ler template de pagamento expirado: {e}")
                    texto_expirado = f'âœ… Pagamento nÃ£o foi confirmado em atÃ© 30 minutos e foi cancelado.\nID: {charge_id}'
                bot.send_message(chat_id, texto_expirado, parse_mode='HTML')
            # Inicia thread de verificaÃ§Ã£o automÃ©tica
            threading.Thread(target=verificar_pagamento_automatico, args=(message.chat.id, charge_id, cred["gateway_pagamento"]["pushinpay"]["token"], valor), daemon=True).start()
        else:
            print(f'[ERRO] Erro ao criar cobranÃ©a na PushinPay: {response.status_code} - {response.text}')
            bot.send_message(message.chat.id, f'âœ… Erro ao criar cobranÃ©a na PushinPay: {response.status_code} - {response.text}')
    
    elif gateway_selecionada == 'misticpay':
        print('[DEBUG] Iniciando fluxo MisticPay')
        try:
            res = api.CriarPixMisticPay.gerar(valor, message.chat.id)
            data = res.get('data', {})
            transaction_id = data.get('transactionId')
            pix_copia_cola = data.get('copyPaste')
            qr_base64 = data.get('qrCodeBase64', '')
            expiracao = api.CredentialsChange.InfoPix.expiracao()

            if not (transaction_id and pix_copia_cola):
                raise Exception(f'Dados insuficientes retornados pela MisticPay: {res}')

            caption = api.Textos.pix_automatico(message, pix_copia_cola, expiracao, transaction_id, f"{valor:.2f}")
            
            if qr_base64:
                import base64
                header, encoded = qr_base64.split(",", 1) if "data:image" in qr_base64 else ("", qr_base64)
                qr_data = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
                with open('qrcode.png', 'wb') as f:
                    f.write(qr_data)
                sent = bot.send_photo(
                    chat_id=message.chat.id,
                    photo=open('qrcode.png', 'rb'),
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                    ])
                )
            else:
                sent = bot.send_message(
                    chat_id=message.chat.id,
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(api.Botoes.aguardando_pagamento(), callback_data='aguardando')]
                    ])
                )

            print(f'[DEBUG] Iniciando verificaÃ§Ã£o MisticPay para transaction_id={transaction_id}')
            import threading
            threading.Thread(
                target=verificar_pagamento,
                args=(message.chat.id, f'misticpay_{transaction_id}', valor, sent.message_id),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[ERRO] Erro ao gerar PIX MisticPay: {e}")
            bot.send_message(message.chat.id, "Ocorreu um erro ao gerar seu Pix MisticPay. Tente novamente mais tarde.")
    
    else:
        bot.send_message(message.chat.id, f"Gateway '{gateway_selecionada}' nÃ£o suportado.")


@bot.message_handler(commands=['rank'])
def handle_rank(message):
    top_users = rankings.get_top_users_by_balance()
    if top_users:
        medals = ['â€¢', 'â€¢', 'â€¢']
        output = "<b>â€¢ Top 20 UsuÃ©rios por Saldo â€¢</b>\n\n"
        for idx, user in enumerate(top_users):
            medal = medals[idx] if idx < 3 else f"{idx+1}Ã©"
            username = user.get('username') or f"User{user.get('id')}"
            saldo = float(user.get('saldo', 0.0))
            output += f"{medal} <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Saldo:</b> R${saldo:.2f}\n"
        bot.send_message(chat_id=message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.chat.id, text='NÃ©o hÃ© usuÃ¡rios para exibir no ranking.')

 
@bot.message_handler(commands=['top_depositors'])
def handle_top_depositors(message):
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "âœ… VocÃª nÃ£o tem permissÃ£o para usar este comando.")
        return

    top_depositors = rankings.get_top_depositors()
    if top_depositors:
        output = "<b>â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos â€¢</b>\n\n"
        for idx, user in enumerate(top_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_pagos = float(user.get('total_pagos', 0.0))
            output += f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>Total DepÃ©sitos:</b> R${total_pagos:.2f}\n"
        bot.send_message(chat_id=message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.chat.id, text='NÃ©o hÃ© depositadores para exibir no ranking.')

 
@bot.message_handler(commands=['top_products'])
def handle_top_products(message):
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "âœ… VocÃª nÃ£o tem permissÃ£o para usar este comando.")
        return

    top_products = rankings.get_top_products_last_30_days()
    if top_products:
        output = "<b>â€¢ Top 10 Produtos Mais Vendidos nos Ã©ltimos 30 Dias â€¢</b>\n\n"
        for idx, (produto, vendas) in enumerate(top_products, start=1):
            output += f"{idx}. <b>{produto}</b> - <b>Vendas:</b> {vendas}\n"
        bot.send_message(chat_id=message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.chat.id, text='Nenhum produto vendido nos Ã©ltimos 30 dias.')

 
@bot.message_handler(commands=['top_recent_depositors'])
def handle_top_recent_depositors(message):
    if not (api.Admin.verificar_admin(message.chat.id) or int(message.chat.id) == int(api.CredentialsChange.id_dono())):
        bot.reply_to(message, "âœ… VocÃª nÃ£o tem permissÃ£o para usar este comando.")
        return

    top_recent_depositors = rankings.get_top_recent_depositors()
    if top_recent_depositors:
        output = "<b>â€¢ Top 10 UsuÃ©rios com Mais DepÃ©sitos nos Ã©ltimos 30 Dias â€¢</b>\n\n"
        for idx, user in enumerate(top_recent_depositors, start=1):
            username = user.get('username') or f"User{user.get('id')}"
            total_recent_pagos = float(user.get('total_recent_pagos', 0.0))
            output += f"{idx}. <b>{username}</b> (ID: <code>{user.get('id')}</code>) - <b>DepÃ©sitos Recentes:</b> R${total_recent_pagos:.2f}\n"
        bot.send_message(chat_id=message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.chat.id, text='Nenhum depÃ©sito recente registrado nos Ã©ltimos 30 dias.')

@bot.message_handler(commands=['rank'])
def handle_rank(message):
    top_users = get_top_users()
    if top_users:
        medals = ['â€¢', 'â€¢', 'â€¢']
        output = "â€¢ *Top 20 UsuÃ©rios por Saldo* â€¢\n\n"
        for idx, user in enumerate(top_users):
            medal = medals[idx] if idx < 3 else f"{idx+1}Ã©"
            output += f"{medal} @{user['username']} (ID: {user['id']}) - Saldo: R${user['saldo']:.2f}\n"
        bot.send_message(chat_id=message.chat.id, text=output, parse_mode='HTML')
    else:
        bot.send_message(chat_id=message.chat.id, text='NÃ©o hÃ© usuÃ¡rios para exibir no ranking.')

 
def is_admin(message):
    return api.Admin.verificar_admin(message.chat.id) == True or int(message.chat.id) == int(api.CredentialsChange.id_dono())

@bot.message_handler(commands=['logins'])
def iniciar_adicao_logins(message):
    user_id = message.from_user.id
    if not is_admin(message):
        bot.reply_to(message, "âœ… VocÃª nÃ£o tem permissÃ£o para usar este comando.")
        return

    adding_logins[user_id] = True
    temp_logins[user_id] = []
    
    bot.send_message(
        user_id,
        "â€¢ *Modo de AdiÃ§Ã£o de Logins Ativado!*\nEnvie os logins no formato:\n`NOME/VALOR/DESCRIÃ‡ÃƒO/EMAIL/SENHA/DURAÃ‡ÃƒO`\nEnvie quantos logins desejar. Quando terminar, envie `/done` para finalizar.",
        parse_mode='Markdown',
        reply_markup=types.ForceReply()
    )

     
    timer = Timer(300, finalizar_adicao_logins, args=[user_id])
    timer.start()
    add_login_timers[user_id] = timer

@bot.message_handler(commands=['done'])
def finalizar_comando(message):
    user_id = message.from_user.id
    if adding_logins.get(user_id, False):
        finalizar_adicao_logins(user_id)
    else:
        bot.reply_to(message, "âœ… VocÃª nÃ£o estÃ© no modo de adiÃ§Ã£o de logins.")

@bot.message_handler(func=lambda message: adding_logins.get(message.from_user.id, False) and not message.text.startswith('/'))
def receber_logins(message):
    user_id = message.from_user.id
    if not adding_logins.get(user_id, False):
        return

    login_text = message.text.strip()
    separador = '/'   

  
    linhas = login_text.split('\n')
    logins_adicionados = 0
    logins_invalidos = 0
    logins_processados = []

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue  

        partes = linha.split(separador)
        if len(partes) != 6:
            logins_invalidos += 1
            bot.reply_to(message, f"âœ… Formato invÃ©lido na linha: `{linha}`\nEnvie no formato: `NOME/VALOR/DESCRIÃ‡ÃƒO/EMAIL/SENHA/DURAÃ‡ÃƒO`", parse_mode='Markdown')
            continue

       

       
        temp_logins[user_id].append(linha)
        logins_adicionados += 1
        logins_processados.append(linha)

    quantidade_total = len(temp_logins[user_id])

 
    feedback = f"âœ… Adicionados {logins_adicionados} login(s) com sucesso!"
    if logins_invalidos > 0:
        feedback += f"\nâœ… {logins_invalidos} login(s) com formato invÃ©lido foram ignorados."
    feedback += "\nEnvie mais logins ou envie `/done` para finalizar."

    bot.reply_to(message, feedback, parse_mode='Markdown')

 
    if user_id in add_login_timers:
        add_login_timers[user_id].cancel()

    timer = Timer(300, finalizar_adicao_logins, args=[user_id])
    timer.start()
    add_login_timers[user_id] = timer

def finalizar_adicao_logins(user_id):
    if adding_logins.get(user_id, False):
        logins = temp_logins.get(user_id, [])
        quantidade = len(logins)
        
        if quantidade > 0:
            notificacoes = {}
            adicionados = 0
            duplicados = 0
            invalidos = 0
            duplicados_pendentes = []
            separador = api.CredentialsChange.separador()
         
            for login in logins:
                try:
                    partes = login.split(separador)
                    if len(partes) != 6 and separador != '/':
                        partes = login.split('/')
                    if len(partes) != 6:
                        raise ValueError
                    nome, valor_texto, descricao, email, senha, duracao = [parte.strip() for parte in partes]
                    valor = parse_valor_monetario(valor_texto)
                    if not api.ControleLogins.add_login(nome=nome, valor=valor, descricao=descricao, email=email, senha=senha, duracao=duracao):
                        duplicados += 1
                        duplicados_pendentes.append({
                            'nome': nome,
                            'valor': valor,
                            'descricao': descricao,
                            'email': email,
                            'senha': senha,
                            'duracao': duracao
                        })
                        continue
                    adicionados += 1
                    notificacoes[nome] = notificacoes.get(nome, 0) + 1
                except ValueError:
                    invalidos += 1
                    continue  

            resumo = f"✅ Adição finalizada: {adicionados} login(s) adicionado(s)."
            if duplicados:
                resumo += f"\n⚠️ {duplicados} duplicado(s) aguardando sua confirmação."
            if invalidos:
                resumo += f"\n❌ {invalidos} linha(s) com valor ou formato inválido foram ignoradas."
            bot.send_message(
                user_id,
                resumo
            )
            perguntar_adicionar_logins_duplicados(user_id, user_id, duplicados_pendentes)
            for prod, qtd in notificacoes.items():
                notificar_novos_logins(prod, qtd)
        else:
            bot.send_message(user_id, "âœ… Nenhum login foi adicionado.")

         
        adding_logins[user_id] = False
        temp_logins[user_id] = []
        
        
        if user_id in add_login_timers:
            add_login_timers[user_id].cancel()
            del add_login_timers[user_id]

 
adding_logins = {}

 
temp_logins = {}

 
add_login_timers = {}

@bot.message_handler(commands=['getchatid'])
def get_chat_id(message):
    chat_id = message.chat.id
    bot.reply_to(message, f'O ID deste chat Ã©: {chat_id}')

@bot.message_handler(commands=['gift'])
def handle_gift_command(message):
    admin_id = 7240103075 #ID DO ADMINSTRADOR
    if message.from_user.id != admin_id:
        bot.reply_to(message, "âœ… VocÃª nÃ£o tem permissÃ£o para usar este comando.")
        return

    try:
        valor = float(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "âš™ï¸ Use o comando corretamente:\n/gift <valor>\nExemplo: /gift 10")
        return

    while True:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        if not api.GiftCard.validar_gift(codigo)[0]:
            api.GiftCard.create_gift(codigo, valor)
            break

    texto_gift = (
        f"â€¢ <b>GIFT CARD GERADO!</b>\n"
        f"â€¢ <b>GIFT CARD:</b> <code>/resgatar {codigo}</code>\n"
        f"â€¢ <b>VALOR:</b> R$ {valor:.2f}\n"
        f"â€¢ <b>RESGATE:</b> @{api.CredentialsChange.user_bot()}"
    )
    bot.reply_to(message, texto_gift, parse_mode='HTML')

def iniciar_verificacao():
    while True:
        time.sleep(240)
        ver_se_expirou()
        time.sleep(43200)

threading.Thread(target=iniciar_verificacao).start()
# NOTIFICAÃ‡Ã•ES FAKE DESATIVADAS - Deixavam o bot lento
# threading.Thread(target=enviar_notificacao_saldo).start()
# threading.Thread(target=enviar_notificacao_compra).start()

# Inicializar sistema de sincronizaÃ§Ã£o de acessos em thread separada
def iniciar_sync_acessos():
    try:
        from acessos_sync import start_ramon_sync
        start_ramon_sync()
        print("Ã© Sistema de sincronizaÃ©o de acessos iniciado (Ramon)")
    except Exception as e:
        print(f"Ã© Erro ao iniciar sincronizaÃ©o: {e}")


try:
    with open('settings/credenciais.json', 'r', encoding='utf-8-sig') as f:
        _sync_credentials = json.load(f)
    _uses_central_stock = bool(
        str(_sync_credentials.get('central_stock_api_url', '')).strip()
        and str(_sync_credentials.get('central_stock_api_key', '')).strip()
    )
except Exception:
    _uses_central_stock = False

# Bots filhos com estoque central nao precisam enviar acessos locais para sync antiga.
if _uses_central_stock:
    print("[ESTOQUE CENTRAL] Sync antiga de acessos desativada para bot filho.")
else:
    threading.Thread(target=iniciar_sync_acessos, daemon=True).start()

print("? Bot iniciado e pronto para receber mensagens!")
bot.infinity_polling()

