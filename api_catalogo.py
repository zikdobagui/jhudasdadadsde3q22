#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor HTTP único que:
1. Serve o site do miniapp (HTML/CSS/JS/imagens) direto da pasta miniapp/
2. Serve o estoque em tempo real (/catalog.json) lendo direto do
   database/acessos.json local, sem gerar nada, sem GitHub, sem depender
   de nada externo.

Roda na porta 80 (obrigatório na SquareCloud) junto do bot.
NÃO expõe email/senha — só nome, preço, estoque e imagem.
"""

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from collections import defaultdict, deque
import hmac
import json
import os
import sys
import traceback
import mimetypes
import tempfile
import threading
import time
import hashlib

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

MINIAPP_DIR = os.path.join(BASE_DIR, 'miniapp')
ACESSOS_FILE = os.path.join(BASE_DIR, 'database', 'acessos.json')
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'settings', 'credenciais.json')
stock_lock = threading.Lock()
rate_lock = threading.Lock()
request_log = defaultdict(deque)

MAX_BODY_BYTES = 16 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 120
RATE_LIMIT_MAX_RESERVES = 30
MAX_FIELD_LENGTH = 200
MAX_SECRET_FIELD_LENGTH = 2000
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self' https://api.telegram.org https://t.me",
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}


def _reseller_billing_enabled():
    return _load_credentials().get('reseller_billing_enabled', True) is not False


def _load_user_for_billing(user_id):
    user_data = database.load_user_data(user_id)
    if user_data is None:
        return None
    user_data['saldo'] = float(user_data.get('saldo', 0) or 0)
    return user_data


def _save_user_for_billing(user_id, user_data):
    database.save_user_data(user_id, user_data)


def _load_credentials():
    try:
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        traceback.print_exc()
    return {}


def _stock_api_key():
    return str(_load_credentials().get('stock_api_key', '')).strip()


def _same_secret(left, right):
    left = str(left or '').strip()
    right = str(right or '').strip()
    return bool(left) and hmac.compare_digest(left, right)


def _sha256(text):
    return hashlib.sha256(str(text or '').encode('utf-8')).hexdigest()


def _find_public_api_owner(received_key):
    received_key = str(received_key or '').strip()
    if not received_key:
        return None
    users_dir = os.path.join(BASE_DIR, 'database', 'users')
    if not os.path.isdir(users_dir):
        return None
    for filename in os.listdir(users_dir):
        if not filename.endswith('.json'):
            continue
        user_id = filename[:-5]
        try:
            user_data = database.load_user_data(user_id)
        except Exception:
            continue
        credencial = user_data.get('api_publica', {}) if isinstance(user_data, dict) else {}
        if not isinstance(credencial, dict) or credencial.get('active') is not True:
            continue
        stored_hash = str(credencial.get('key_hash', '')).strip()
        if stored_hash and _same_secret(stored_hash, _sha256(received_key)):
            return str(user_data.get('id', user_id))
        if _same_secret(credencial.get('key', ''), received_key):
            return str(user_data.get('id', user_id))
    return None


def _client_ip(handler):
    forwarded = handler.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',', 1)[0].strip()
    return handler.client_address[0] if handler.client_address else 'unknown'


def _rate_limited(identity, bucket='default', limit=RATE_LIMIT_MAX_REQUESTS):
    now = time.time()
    key = f'{bucket}:{identity}'
    with rate_lock:
        events = request_log[key]
        while events and now - events[0] > RATE_LIMIT_WINDOW_SECONDS:
            events.popleft()
        if len(events) >= limit:
            return True
        events.append(now)
    return False


def _clean_text(value, max_length=MAX_FIELD_LENGTH):
    text = str(value or '').strip()
    if len(text) > max_length:
        text = text[:max_length]
    return text.replace('\x00', '')


def _public_error(reason):
    if reason == 'out_of_stock':
        return 404, {'error': reason}
    if reason == 'insufficient_reseller_balance':
        return 402, {'error': reason}
    return 400, {'error': reason}


def _save_acessos(data):
    os.makedirs(os.path.dirname(ACESSOS_FILE), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix='acessos-', suffix='.json', dir=os.path.dirname(ACESSOS_FILE))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, ACESSOS_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _load_acessos():
    if not os.path.exists(ACESSOS_FILE):
        data = {'acessos': []}
        _save_acessos(data)
        return data

    with open(ACESSOS_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return {'acessos': raw}
    if not isinstance(raw, dict):
        return {'acessos': []}
    raw.setdefault('acessos', [])
    return raw


def _load_images():
    try:
        if os.path.exists(MINIAPP_IMAGES_FILE):
            with open(MINIAPP_IMAGES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def gerar_catalogo():
    """Lê acessos.json AGORA (sempre atualizado) e retorna lista segura."""
    with open(ACESSOS_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    acessos = raw.get('acessos', []) if isinstance(raw, dict) else raw
    image_map = _load_images()

    agrupados = {}
    for acesso in acessos:
        nome = (acesso.get('nome') or '').strip()
        if not nome:
            continue
        valor = float(acesso.get('valor', 0))
        if nome not in agrupados:
            agrupados[nome] = {
                'name': nome,
                'price': valor,
                'stock': 0,
                'descricao': acesso.get('descricao', ''),
                'duracao': acesso.get('duracao', '')
            }
        agrupados[nome]['stock'] += 1

    catalogo = []
    for produto in sorted(agrupados.values(), key=lambda x: x['name']):
        img = image_map.get(produto['name'])
        if img:
            produto['image'] = img
        catalogo.append(produto)

    return catalogo


def reservar_primeiro_acesso(servico, child_bot_id='', buyer_id='', sale_id='', reseller_admin_id=''):
    servico = _clean_text(servico)
    child_bot_id = _clean_text(child_bot_id)
    buyer_id = _clean_text(buyer_id)
    sale_id = _clean_text(sale_id)
    reseller_admin_id = _clean_text(reseller_admin_id, 32)
    servico_key = servico.casefold()
    if not servico_key:
        return False, 'invalid_service', None

    with stock_lock:
        data = _load_acessos()
        acessos = data.get('acessos', [])

        for index, acesso in enumerate(acessos):
            if str(acesso.get('nome', '')).strip().casefold() == servico_key:
                valor = float(acesso.get('valor', 0) or 0)
                if _reseller_billing_enabled():
                    if not reseller_admin_id:
                        return False, 'missing_reseller_admin_id', None
                    reseller = _load_user_for_billing(reseller_admin_id)
                    if reseller is None:
                        return False, 'reseller_not_found', {'required_balance': valor}
                    if float(reseller.get('saldo', 0) or 0) < valor:
                        return False, 'insufficient_reseller_balance', {
                            'required_balance': valor,
                            'current_balance': float(reseller.get('saldo', 0) or 0)
                        }
                    reseller['saldo'] = round(float(reseller.get('saldo', 0) or 0) - valor, 2)
                    reseller.setdefault('compras_fornecedor', []).append({
                        'servico': acesso.get('nome', ''),
                        'valor': valor,
                        'child_bot_id': child_bot_id,
                        'buyer_id': buyer_id,
                        'sale_id': sale_id,
                    })
                    _save_user_for_billing(reseller_admin_id, reseller)

                reservado = acessos.pop(index)
                _save_acessos(data)
                return True, 'reserved', {
                    'nome': reservado.get('nome', ''),
                    'valor': reservado.get('valor', 0),
                    'email': reservado.get('email', ''),
                    'senha': reservado.get('senha', ''),
                    'descricao': reservado.get('descricao', ''),
                    'duracao': reservado.get('duracao', ''),
                    'reserved_by': {
                        'child_bot_id': child_bot_id,
                        'buyer_id': buyer_id,
                        'sale_id': sale_id,
                        'reseller_admin_id': reseller_admin_id,
                    },
                    'billing': {
                        'charged': _reseller_billing_enabled(),
                        'reseller_admin_id': reseller_admin_id,
                        'amount': valor,
                    },
                }
    return False, 'out_of_stock', None


def adicionar_acesso(payload):
    if not isinstance(payload, dict):
        return False, 'Payload invalido'
    obrigatorios = ('nome', 'valor', 'email', 'senha')
    faltando = [campo for campo in obrigatorios if not str(payload.get(campo, '')).strip()]
    if faltando:
        return False, f"Campos obrigatórios faltando: {', '.join(faltando)}"

    item = {
        'nome': _clean_text(payload.get('nome', '')),
        'valor': payload.get('valor', 0),
        'descricao': _clean_text(payload.get('descricao', ''), MAX_SECRET_FIELD_LENGTH),
        'email': _clean_text(payload.get('email', ''), MAX_SECRET_FIELD_LENGTH),
        'senha': _clean_text(payload.get('senha', ''), MAX_SECRET_FIELD_LENGTH),
        'duracao': _clean_text(payload.get('duracao', '')),
    }

    with stock_lock:
        data = _load_acessos()
        data.setdefault('acessos', []).append(item)
        _save_acessos(data)

    return True, item


class Handler(SimpleHTTPRequestHandler):
    """Serve os arquivos estáticos do miniapp e o endpoint /catalog.json."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MINIAPP_DIR, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if _rate_limited(_client_ip(self), 'get'):
            self._responder_json(429, {'error': 'rate_limited'})
            return

        if path in ('/catalog', '/catalog.json'):
            self._responder_catalogo()
            return

        if path in ('/api/stock', '/api/stock/summary'):
            if not self._autorizado():
                self._responder_json(401, {'error': 'unauthorized'})
                return
            self._responder_json(200, {'stock': gerar_catalogo()})
            return

        if path == '/health':
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Qualquer outra rota: serve arquivo estático da pasta miniapp/
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if _rate_limited(_client_ip(self), 'post'):
            self._responder_json(429, {'error': 'rate_limited'})
            return

        if path not in ('/api/stock/reserve', '/api/stock/add'):
            self._responder_json(404, {'error': 'not_found'})
            return

        auth = self._autorizado()
        if not auth:
            self._responder_json(401, {'error': 'unauthorized'})
            return

        payload = self._ler_json()
        if payload is None:
            self._responder_json(400, {'error': 'invalid_json'})
            return

        if path == '/api/stock/reserve':
            public_owner_id = auth if auth != 'global' else ''
            rate_identity = public_owner_id or _client_ip(self)
            if _rate_limited(rate_identity, 'reserve', RATE_LIMIT_MAX_RESERVES):
                self._responder_json(429, {'error': 'rate_limited'})
                return
            ok, reason, acesso = reservar_primeiro_acesso(
                payload.get('service'),
                payload.get('child_bot_id', ''),
                payload.get('buyer_id', ''),
                payload.get('sale_id', ''),
                public_owner_id or payload.get('reseller_admin_id', ''),
            )
            if not ok:
                status, payload = _public_error(reason)
                self._responder_json(status, payload)
                return
            self._responder_json(200, {'access': acesso})
            return

        if auth != 'global':
            self._responder_json(403, {'error': 'admin_key_required'})
            return

        ok, resultado = adicionar_acesso(payload)
        if not ok:
            self._responder_json(400, {'error': resultado})
            return
        self._responder_json(201, {'access': resultado})

    def _autorizado(self):
        expected_key = _stock_api_key()
        received_key = self.headers.get('X-Stock-Key', '')
        if _same_secret(expected_key, received_key):
            return 'global'
        return _find_public_api_owner(received_key)

    def _ler_json(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > MAX_BODY_BYTES:
                return None
            raw = self.rfile.read(length)
            return json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            return None

    def _responder_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self._send_security_headers()
        super().end_headers()

    def _send_security_headers(self):
        for header, value in SECURITY_HEADERS.items():
            self.send_header(header, value)

    def list_directory(self, path):
        self.send_error(403, 'Directory listing disabled')
        return None

    def _responder_catalogo(self):
        try:
            catalogo = gerar_catalogo()
            body = json.dumps(catalogo, ensure_ascii=False).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            traceback.print_exc()
            err = json.dumps({'error': 'Falha ao carregar estoque'}).encode('utf-8')
            self.send_response(503)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def log_message(self, fmt, *args):
        # silencia logs HTTP repetitivos no console do bot
        pass


def iniciar(porta=80):
    server = ThreadingHTTPServer(('0.0.0.0', porta), Handler)
    print(f"[MINIAPP] Servidor rodando na porta {porta} — servindo site + estoque em tempo real")
    server.serve_forever()


if __name__ == '__main__':
    porta = int(os.getenv('PORT', '80'))
    iniciar(porta)
