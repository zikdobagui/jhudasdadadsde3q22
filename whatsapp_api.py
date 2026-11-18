"""Integração servidor a servidor com o bot WhatsApp; sem copiar saldos."""
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import urlparse

import database

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'database', 'whatsapp_links.sqlite3')


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15, factory=Connection)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS links (user_id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, expires INTEGER NOT NULL, whatsapp TEXT UNIQUE)')
    return con


def profile_code(user_id):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM links WHERE user_id=?', (str(user_id),)).fetchone()
        if row and (row['whatsapp'] or row['expires'] > time.time()):
            return {'codigo': None if row['whatsapp'] else row['code'], 'expira_em': row['expires'], 'vinculado': bool(row['whatsapp'])}
        code = secrets.token_hex(16).upper()
        expires = int(time.time()) + 86400
        con.execute('INSERT INTO links(user_id,code,expires) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET code=excluded.code, expires=excluded.expires', (str(user_id), code, expires))
        return {'codigo': code, 'expira_em': expires, 'vinculado': False}


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def phone(value):
    value = str(value or '')
    if not re.fullmatch(r'[1-9][0-9]{9,14}', value):
        raise APIError(400, 'whatsapp deve conter DDI e apenas 10 a 15 digitos')
    return value


def dispatch(method, path, body, catalog):
    if path == '/api/whatsapp/v1/vincular' and method == 'POST':
        number = phone(body.get('whatsapp'))
        code = str(body.get('codigo', '')).strip().upper()
        with connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM links WHERE code=?', (code,)).fetchone()
            if not row or row['expires'] <= time.time() or row['whatsapp']:
                raise APIError(409, 'codigo invalido, expirado ou ja utilizado')
            user = database.load_user_data(row['user_id'])
            if not user or str(user.get('banned')).lower() == 'true':
                raise APIError(403, 'cliente indisponivel')
            try:
                con.execute('UPDATE links SET whatsapp=? WHERE user_id=?', (number, row['user_id']))
            except sqlite3.IntegrityError:
                raise APIError(409, 'whatsapp ja vinculado')
        return {'vinculado': True, 'cliente_id': row['user_id']}
    if path == '/api/whatsapp/v1/produtos' and method == 'GET':
        products = catalog()
        # Lista explícita: jamais exportar credenciais do estoque.
        return {'moeda': 'BRL', 'produtos': [dict(id=p.get('id') or p.get('nome'), nome=p.get('nome'), preco=p.get('preco'), estoque=p.get('estoque'), descricao=p.get('descricao')) for p in products]}
    match = re.fullmatch(r'/api/whatsapp/v1/clientes/([1-9][0-9]{9,14})(/historico)?', path)
    if match and method == 'GET':
        with connect() as con:
            row = con.execute('SELECT user_id FROM links WHERE whatsapp=?', (match[1],)).fetchone()
        user = database.load_user_data(row['user_id']) if row else None
        if not user:
            raise APIError(404, 'cliente nao vinculado')
        if str(user.get('banned')).lower() == 'true':
            raise APIError(403, 'cliente indisponivel')
        if match[2]:
            def safe(items):
                return [{k: x.get(k) for k in ('servico', 'produto', 'valor', 'data')} for x in reversed(items) if isinstance(x, dict)]
            return {'cliente_id': row['user_id'], 'compras': safe(user.get('compras', [])), 'pagamentos': safe(user.get('pagamentos', []))}
        return {'cliente_id': row['user_id'], 'username': user.get('username'), 'whatsapp': match[1], 'saldo': round(float(user.get('saldo', 0)), 2), 'moeda': 'BRL', 'total_compras': user.get('total_compras', 0)}
    raise APIError(404, 'rota nao encontrada')


def handle(handler, catalog):
    path = urlparse(handler.path).path
    if not path.startswith('/api/whatsapp/'):
        return False
    status = 200
    try:
        field = 'whatsapp_catalog_api_key' if path == '/api/whatsapp/v1/produtos' else 'whatsapp_api_key'
        key = os.environ.get(field.upper(), '')
        if not key:
            with open(os.path.join(BASE, 'settings', 'credenciais.json'), encoding='utf-8-sig') as f:
                key = str(json.load(f).get(field, ''))
        if not key:
            raise APIError(503, 'integracao nao configurada')
        received = handler.headers.get('Authorization', '')
        if not hmac.compare_digest(received.encode(), ('Bearer ' + key).encode()):
            raise APIError(401, 'nao autorizado')
        body = {}
        if handler.command == 'POST':
            try:
                length = int(handler.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError()
                body = json.loads(handler.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError()
            except (ValueError, json.JSONDecodeError):
                raise APIError(400, 'corpo JSON invalido ou maior que 4096 bytes')
        result = dispatch(handler.command, path, body, catalog)
    except APIError as exc:
        status, result = exc.status, {'erro': exc.message}
    except Exception:
        status, result = 503, {'erro': 'servico temporariamente indisponivel'}
    data = json.dumps(result, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(data)))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Connection', 'close')
    handler.end_headers()
    handler.wfile.write(data)
    handler.close_connection = True
    return True
