# -*- coding: utf-8 -*-
"""
site_ponte.py  —  liga o SITE/PAINEL (webapp.py) ao bot do Ramon.

O site foi feito para outro bot. Aqui ficam as peças que o bot do Ramon não tinha:
  * espelho SQLite dos clientes (site_espelho.py) e as funções de `database` que o site chama;
  * gerar PIX usando o gateway que o Ramon já usa (MisticPay / Mercado Pago / PushinPay);
  * verificação do PIX reaproveitando a verificar_pagamento() do próprio bot (credita saldo);
  * trava no estoque para o bot e o site nunca entregarem o mesmo login;
  * is_admin_user / lista de admins.

Uso (final do bot.py, antes do polling):
    import site_ponte; site_ponte.instalar(globals())
Se qualquer coisa aqui falhar, o bot continua funcionando normalmente (só o site fica fora).
"""
import os
import io
import json
import time
import base64
import threading
import traceback

import requests

import site_espelho


class PixDuplicadoError(Exception):
    """Mesmo cliente pediu PIX do mesmo valor em poucos segundos."""


_recentes = {}
_lock_recentes = threading.Lock()
_lock_estoque = threading.RLock()


def _cred():
    try:
        with open('settings/credenciais.json', 'r', encoding='utf-8-sig') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _b64_png(qr_base64):
    if not qr_base64:
        return b''
    enc = qr_base64.split(',', 1)[1] if str(qr_base64).startswith('data:image') else qr_base64
    return base64.b64decode(enc + '=' * (-len(enc) % 4))


def _qr_do_texto(texto):
    """Gera o QR a partir do copia-e-cola quando o gateway não devolve a imagem."""
    try:
        import qrcode
        img = qrcode.make(texto)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception as e:
        print(f'[PONTE] não consegui gerar o QR code: {e}')
        return b''


def instalar(g):
    """g = globals() do bot.py."""
    api = g['api']
    database = g['database']
    bot = g['bot']

    # 1) espelho + funções de database que o site espera ------------------------------------
    site_espelho.iniciar()
    database._connect = site_espelho.conectar
    database._write_lock = site_espelho._write_lock
    database.get_all_user_ids = site_espelho.get_all_user_ids
    database.check_pagamento_ja_processado = site_espelho.check_pagamento_ja_processado
    database.registrar_movimentacao_saldo = site_espelho.registrar_movimentacao_saldo
    database.buscar_uid_por_username = site_espelho.buscar_uid_por_username
    database.get_top_products_last_30_days = site_espelho.get_top_products_last_30_days
    database.top_produtos_site = site_espelho.top_produtos
    database.verificar_sistema_afiliados_ativo = lambda: False   # afiliados do Ramon são por pontos
    database.get_valor_por_indicacao = lambda: 0.0

    # 2) admins ------------------------------------------------------------------------------
    def obter_ids_admins():
        ids = set()
        try:
            with open('database/admins.json', 'r', encoding='utf-8-sig') as f:
                for a in (json.load(f).get('admins') or []):
                    try:
                        ids.add(int(a.get('id')))
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            ids.add(int(api.CredentialsChange.id_dono()))
        except Exception:
            pass
        return sorted(ids)

    api.Admin.obter_ids_admins = staticmethod(obter_ids_admins)

    def is_admin_user(uid):
        try:
            uid = int(uid)
            return uid == int(api.CredentialsChange.id_dono()) or bool(api.Admin.verificar_admin(uid))
        except Exception:
            return False

    g.setdefault('is_admin_user', is_admin_user)

    # 3) trava no estoque (bot e site pegam login um de cada vez) -----------------------------
    if not getattr(api.ControleLogins, '_site_trava', False):
        _orig = api.ControleLogins.pegar_primeiro_disponivel

        def pegar_primeiro_disponivel(servico):
            with _lock_estoque:
                return _orig(servico)

        api.ControleLogins.pegar_primeiro_disponivel = staticmethod(pegar_primeiro_disponivel)
        api.ControleLogins._site_trava = True

    # 4) PIX ---------------------------------------------------------------------------------
    def gerar_pix_com_failover(valor, msg):
        uid = int(msg.chat.id)
        valor = round(float(valor), 2)
        agora = time.time()
        with _lock_recentes:
            for k in [k for k, t in _recentes.items() if agora - t > 30]:
                _recentes.pop(k, None)
            if agora - _recentes.get((uid, valor), 0) < 8:
                raise PixDuplicadoError()
            _recentes[(uid, valor)] = agora

        gateway = (_cred().get('gateway_pagamento', {}) or {}).get('selecionada', 'mercado_pago')

        if gateway == 'misticpay':
            res = api.CriarPixMisticPay.gerar(valor, uid)
            data = (res or {}).get('data', {}) or {}
            tid, copia = data.get('transactionId'), data.get('copyPaste')
            if not (tid and copia):
                raise Exception(f'MisticPay não devolveu os dados do PIX: {str(res)[:200]}')
            qr = _b64_png(data.get('qrCodeBase64', '')) or _qr_do_texto(copia)
            return {'gateway': 'misticpay', 'id_pag': f'misticpay_{tid}', 'pix_copia_cola': copia, 'qr_bytes': qr}

        if gateway == 'pushinpay':
            token = ((_cred().get('gateway_pagamento', {}) or {}).get('pushinpay', {}) or {}).get('token', '')
            if not token:
                raise Exception('Token PushinPay não configurado.')
            r = requests.post('https://api.pushinpay.com.br/api/pix/cashIn',
                              headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                                       'Accept': 'application/json'},
                              json={'value': int(round(valor * 100))}, timeout=30)
            if r.status_code != 200:
                raise Exception(f'PushinPay: {r.text[:200]}')
            j = r.json()
            cid, copia = j.get('id'), j.get('qr_code')
            if not (cid and copia):
                raise Exception('PushinPay não devolveu os dados do PIX.')
            qr = _b64_png(j.get('qr_code_base64', '')) or _qr_do_texto(copia)
            return {'gateway': 'pushinpay', 'id_pag': str(cid), 'pix_copia_cola': copia, 'qr_bytes': qr}

        # Mercado Pago (padrão do bot)
        pay = api.CriarPix.gerar(valor, uid)
        resp = pay['response']
        td = resp['point_of_interaction']['transaction_data']
        qr = _b64_png(td.get('qr_code_base64', '')) or _qr_do_texto(td['qr_code'])
        return {'gateway': 'mercadopago', 'id_pag': str(resp['id']), 'pix_copia_cola': td['qr_code'], 'qr_bytes': qr}

    def _verificador(gw):
        def verificar(chat_id, id_pag, valor, message_id):
            # a verificar_pagamento do bot descobre o gateway pelo formato do id e credita o saldo
            token = None
            if gw == 'pushinpay':
                token = ((_cred().get('gateway_pagamento', {}) or {}).get('pushinpay', {}) or {}).get('token', '')
            return g['verificar_pagamento'](chat_id, id_pag, valor, message_id, token)
        return verificar

    g['gerar_pix_com_failover'] = gerar_pix_com_failover
    g['PixDuplicadoError'] = PixDuplicadoError
    g['check_pagamento_ja_processado'] = site_espelho.check_pagamento_ja_processado
    for gw in ('misticpay', 'mercadopago', 'pushinpay'):
        g['verificar_pagamento_' + gw] = _verificador(gw)

    # 5) sobe o site ----------------------------------------------------------------------------
    import webapp
    webapp.iniciar(g)


def instalar_seguro(g):
    try:
        instalar(g)
    except Exception:
        print('[PONTE] o site não iniciou (o bot segue normal):\n' + traceback.format_exc())
