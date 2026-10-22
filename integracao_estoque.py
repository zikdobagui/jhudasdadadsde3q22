# -*- coding: utf-8 -*-
"""Conexão segura da lojinha com a API central de estoque.

A chave nunca é devolvida ao navegador: este módulo só é chamado pelo backend.
"""
import json
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_ARQ = 'settings/integracao_estoque.json'
_LOCK = threading.RLock()


class ErroIntegracao(Exception):
    def __init__(self, msg, status=502):
        super().__init__(msg)
        self.msg, self.status = msg, status


def configurar(url, chave):
    url = str(url or '').strip().rstrip('/')
    chave = str(chave or '').strip()
    if not url:
        raise ErroIntegracao('Informe a URL da API.', 400)
    if not url.startswith(('https://', 'http://')):
        raise ErroIntegracao('A URL da API deve começar com https:// ou http://.', 400)
    if len(url) > 500 or len(chave) > 500:
        raise ErroIntegracao('Configuração inválida.', 400)
    if not chave:
        raise ErroIntegracao('Informe a API key.', 400)
    os.makedirs('settings', exist_ok=True)
    with _LOCK:
        tmp = _ARQ + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'url': url, 'key': chave}, f)
        os.replace(tmp, _ARQ)


def desconectar():
    with _LOCK:
        try:
            os.remove(_ARQ)
        except FileNotFoundError:
            pass


def estado():
    cfg = _ler()
    return {'conectada': bool(cfg), 'url': cfg.get('url', '') if cfg else ''}


def _ler():
    try:
        with open(_ARQ, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get('url') and d.get('key'):
            return d
    except Exception:
        pass
    return {}


def _pedido(metodo, rota, corpo=None):
    cfg = _ler()
    if not cfg:
        return None
    data = json.dumps(corpo).encode('utf-8') if corpo is not None else None
    req = Request(cfg['url'] + rota, data=data, method=metodo, headers={
        'X-Stock-Key': cfg['key'], 'Accept': 'application/json',
        'Content-Type': 'application/json' if data else 'application/json',
    })
    try:
        with urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode('utf-8'))
    except HTTPError as e:
        try:
            detalhe = json.loads(e.read().decode('utf-8')).get('error', '')
        except Exception:
            detalhe = ''
        if e.code in (401, 403):
            raise ErroIntegracao('A API recusou a chave configurada.', 502)
        if e.code == 404 or detalhe == 'out_of_stock':
            raise ErroIntegracao('Produto esgotado na API.', 409)
        raise ErroIntegracao('A API respondeu com erro. Tente novamente.', 502)
    except (URLError, ValueError, TimeoutError):
        raise ErroIntegracao('Não foi possível conectar à API de estoque.', 502)


def catalogo():
    """Retorna None quando a integração não está ativa; lista normalizada quando está."""
    d = _pedido('GET', '/api/stock')
    if d is None:
        return None
    produtos = d.get('stock', d) if isinstance(d, dict) else d
    if not isinstance(produtos, list):
        raise ErroIntegracao('A API retornou um catálogo inválido.')
    saida = []
    for p in produtos:
        if not isinstance(p, dict):
            continue
        nome = str(p.get('nome') or p.get('name') or '').strip()
        if not nome:
            continue
        try:
            preco, estoque = float(p.get('preco', p.get('price', p.get('valor', 0))) or 0), int(p.get('estoque', p.get('stock', 0)) or 0)
        except (TypeError, ValueError):
            continue
        saida.append({'nome': nome, 'preco': round(preco, 2), 'valor': round(preco, 2),
                      'estoque': max(0, estoque), 'descricao': str(p.get('descricao', ''))[:300],
                      'duracao': int(p.get('duracao', 30) or 30), 'img_externa': p.get('img') or p.get('image')})
    return saida


def reservar(servico, comprador_id, venda_id):
    d = _pedido('POST', '/api/stock/reserve', {'service': servico, 'buyer_id': str(comprador_id), 'sale_id': venda_id})
    acesso = d.get('access') if isinstance(d, dict) else None
    if not isinstance(acesso, dict):
        raise ErroIntegracao('A API não retornou o acesso reservado.')
    return acesso
