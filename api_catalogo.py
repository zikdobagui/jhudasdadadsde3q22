#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API HTTP que retorna o catálogo em tempo real
lendo direto do database/acessos.json da instância.
Roda na porta 80 (obrigatório SquareCloud).
NÃO expõe email/senha — só nome, preço, estoque e imagem.
"""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

ACESSOS_FILE = os.path.join(BASE_DIR, 'database', 'acessos.json')
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')


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
    """Lê acessos.json, agrupa por nome e retorna lista segura (sem credenciais)."""
    with open(ACESSOS_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    acessos = raw.get('acessos', []) if isinstance(raw, dict) else raw
    image_map = _load_images()

    agrupados = {}
    for acesso in acessos:
        nome = acesso.get('nome', '').strip()
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


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/')

        if path in ('', '/catalog', '/catalog.json'):
            try:
                catalogo = gerar_catalogo()
                body = json.dumps(catalogo, ensure_ascii=False).encode('utf-8')

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                traceback.print_exc()
                err = json.dumps({'error': 'Falha ao carregar estoque'}).encode('utf-8')
                self.send_response(503)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(err)))
                self.end_headers()
                self.wfile.write(err)

        elif path == '/health':
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def log_message(self, fmt, *args):
        # silencia logs HTTP repetitivos
        pass


def iniciar(porta=80):
    server = ThreadingHTTPServer(('0.0.0.0', porta), Handler)
    print(f"[API] Catálogo rodando na porta {porta}")
    server.serve_forever()


if __name__ == '__main__':
    porta = int(os.getenv('PORT', '80'))
    iniciar(porta)
