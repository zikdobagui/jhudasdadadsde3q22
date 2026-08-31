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
import json
import os
import sys
import traceback
import mimetypes
import tempfile
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

MINIAPP_DIR = os.path.join(BASE_DIR, 'miniapp')
ACESSOS_FILE = os.path.join(BASE_DIR, 'database', 'acessos.json')
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'settings', 'credenciais.json')
stock_lock = threading.Lock()


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
            agrupados[nome] = {'name': nome, 'price': valor, 'stock': 0}
        agrupados[nome]['stock'] += 1

    catalogo = []
    for produto in sorted(agrupados.values(), key=lambda x: x['name']):
        img = image_map.get(produto['name'])
        if img:
            produto['image'] = img
        catalogo.append(produto)

    return catalogo


def reservar_primeiro_acesso(servico, child_bot_id='', buyer_id='', sale_id=''):
    servico_key = str(servico or '').strip().casefold()
    if not servico_key:
        return None

    with stock_lock:
        data = _load_acessos()
        acessos = data.get('acessos', [])

        for index, acesso in enumerate(acessos):
            if str(acesso.get('nome', '')).strip().casefold() == servico_key:
                reservado = acessos.pop(index)
                _save_acessos(data)
                return {
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
                    }
                }
    return None


def adicionar_acesso(payload):
    obrigatorios = ('nome', 'valor', 'email', 'senha')
    faltando = [campo for campo in obrigatorios if not str(payload.get(campo, '')).strip()]
    if faltando:
        return False, f"Campos obrigatórios faltando: {', '.join(faltando)}"

    item = {
        'nome': payload.get('nome', ''),
        'valor': payload.get('valor', 0),
        'descricao': payload.get('descricao', ''),
        'email': payload.get('email', ''),
        'senha': payload.get('senha', ''),
        'duracao': payload.get('duracao', ''),
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

        if path not in ('/api/stock/reserve', '/api/stock/add'):
            self._responder_json(404, {'error': 'not_found'})
            return

        if not self._autorizado():
            self._responder_json(401, {'error': 'unauthorized'})
            return

        payload = self._ler_json()
        if payload is None:
            self._responder_json(400, {'error': 'invalid_json'})
            return

        if path == '/api/stock/reserve':
            acesso = reservar_primeiro_acesso(
                payload.get('service'),
                payload.get('child_bot_id', ''),
                payload.get('buyer_id', ''),
                payload.get('sale_id', ''),
            )
            if not acesso:
                self._responder_json(404, {'error': 'out_of_stock'})
                return
            self._responder_json(200, {'access': acesso})
            return

        ok, resultado = adicionar_acesso(payload)
        if not ok:
            self._responder_json(400, {'error': resultado})
            return
        self._responder_json(201, {'access': resultado})

    def _autorizado(self):
        expected_key = _stock_api_key()
        received_key = self.headers.get('X-Stock-Key', '')
        return bool(expected_key) and received_key == expected_key

    def _ler_json(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
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
