"""Operações WhatsApp executadas pelo checkout/PIX do site, no mesmo cadastro Telegram.
Pedidos são persistidos antes de executar efeitos externos e nunca repetidos após falha incerta.
"""
import hashlib
import json
import math
import re
from types import SimpleNamespace
from urllib.parse import unquote

import database


def linked(api, number):
    number = api.phone(number)
    with api.connect() as con:
        row = con.execute('SELECT user_id FROM links WHERE whatsapp=?', (number,)).fetchone()
    user = database.load_user_data(row['user_id']) if row else None
    if not user:
        raise api.APIError(404, 'cliente nao vinculado')
    if str(user.get('banned')).lower() == 'true':
        raise api.APIError(403, 'cliente indisponivel')
    return row['user_id'], SimpleNamespace(id=int(row['user_id']), nome=user.get('username') or 'Cliente', username=user.get('username'))


def init(con):
    con.execute('CREATE TABLE IF NOT EXISTS whatsapp_operations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, fingerprint TEXT NOT NULL, state TEXT NOT NULL, result TEXT, error_status INTEGER)')


def operation(api, uid, kind, operation_id, payload, callback):
    if not isinstance(operation_id, str) or not re.fullmatch(r'[a-f0-9]{64}', operation_id):
        raise api.APIError(400, 'operacao invalida')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    with api.connect() as con:
        init(con)
        con.execute('BEGIN IMMEDIATE')
        existing = con.execute('SELECT * FROM whatsapp_operations WHERE id=?', (operation_id,)).fetchone()
        if existing:
            if existing['user_id'] != uid or existing['kind'] != kind or existing['fingerprint'] != fingerprint:
                raise api.APIError(409, 'operacao ja utilizada')
            return response(existing)
        pending = con.execute("SELECT id FROM whatsapp_operations WHERE user_id=? AND kind=? AND state IN ('PROCESSING','REVIEW')", (uid, kind)).fetchone()
        if pending:
            raise api.APIError(409, 'operacao anterior pendente; consulte seu pedido')
        con.execute('INSERT INTO whatsapp_operations(id,user_id,kind,fingerprint,state) VALUES(?,?,?,?,?)', (operation_id, uid, kind, fingerprint, 'PROCESSING'))
    try:
        result = callback()
        if not isinstance(result, dict):
            raise RuntimeError('resultado invalido')
        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        # Só erros conhecidos de validação do site são rejeições definitivas.
        status = getattr(exc, 'status', None)
        status = status if isinstance(status, int) and 400 <= status < 500 else None
        state = 'REJECTED' if status else 'REVIEW'
        with api.connect() as con:
            con.execute('UPDATE whatsapp_operations SET state=?,error_status=? WHERE id=?', (state, status, operation_id))
        return {'operacao': operation_id, 'status': state, 'erro_status': status}
    with api.connect() as con:
        con.execute('UPDATE whatsapp_operations SET state=?,result=? WHERE id=?', ('DONE', serialized, operation_id))
    return {'operacao': operation_id, 'status': 'DONE', 'resultado': result}


def response(row):
    result = {'operacao': row['id'], 'status': row['state']}
    if row['result'] is not None:
        result['resultado'] = json.loads(row['result'])
    if row['error_status'] is not None:
        result['erro_status'] = row['error_status']
    return result


def dispatch(api, method, path, body, services):
    match = re.fullmatch(r'/api/whatsapp/v1/clientes/([1-9][0-9]{9,14})/(comprar|pix|operacoes/([a-f0-9]{64})|pix/([^/]+)/status)', path)
    if not match:
        return None
    if not services:
        raise api.APIError(503, 'operacoes compartilhadas nao configuradas')
    uid, user = linked(api, match[1])
    action = match[2]
    if method == 'GET' and match[3]:
        with api.connect() as con:
            init(con)
            row = con.execute('SELECT * FROM whatsapp_operations WHERE id=? AND user_id=?', (match[3], uid)).fetchone()
        if not row:
            raise api.APIError(404, 'operacao nao encontrada')
        return response(row)
    if method == 'GET' and match[4]:
        payment = unquote(match[4])
        if len(payment) > 200:
            raise api.APIError(400, 'pagamento invalido')
        with api.connect() as con:
            init(con)
            rows = con.execute('SELECT result FROM whatsapp_operations WHERE user_id=? AND kind=? AND state=?', (uid, 'pix', 'DONE')).fetchall()
        if not any(str(json.loads(row['result']).get('id_pag')) == payment for row in rows):
            raise api.APIError(404, 'pagamento nao encontrado')
        return services['status_pix'](user, payment)
    if method != 'POST' or action not in ('comprar', 'pix'):
        raise api.APIError(404, 'rota nao encontrada')
    if action == 'comprar':
        name, price = body.get('produto'), body.get('preco')
        if not isinstance(name, str) or not name.strip() or len(name) > 300 or isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise api.APIError(400, 'produto ou preco invalido')
        payload = {'produto': name, 'preco': price}
        callback = lambda: services['comprar'](user, [{'nome': name, 'preco': price, 'qtd': 1}])
    else:
        value = body.get('valor')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise api.APIError(400, 'valor invalido')
        payload = {'valor': value}
        callback = lambda: services['pix'](user, value)
    return operation(api, uid, action, body.get('operacao'), payload, callback)
