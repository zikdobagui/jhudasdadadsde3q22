# -*- coding: utf-8 -*-
"""
Painel de ADMIN do site (página /admin, tema preto).

Só quem é admin entra:
  • admin do bot (database/admins.json ou o dono) → pede /painel no Telegram e abre o link que o bot manda
    (link de uso único, vale 5 minutos);
  • ou conta do site cujo e-mail esteja em "admin_emails" no settings/webapp.json.

Tudo usa as mesmas funções/arquivos do bot (estoque, saldos, ofertas, gift cards, tickets, manutenção),
então o que muda aqui muda no bot e vice-versa.
"""
import os
import re
import json
import time
import threading
import traceback
from datetime import datetime, timedelta

_LOG = 'log/painel_admin.txt'
_cache = {}
_transm = {'rodando': False, 'total': 0, 'ok': 0, 'falha': 0, 'inicio': 0, 'fim': 0}


class ErroAdmin(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


# ------------------------------------------------------------------ util
def _registrar(u, acao, detalhe=''):
    try:
        os.makedirs('log', exist_ok=True)
        with open(_LOG, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} | {getattr(u, "id", "?")} {getattr(u, "nome", "")} | {acao} | {detalhe}\n')
    except Exception:
        pass


def _num(v, minimo=None, maximo=None, nome='valor'):
    try:
        x = float(str(v).replace(',', '.'))
    except Exception:
        raise ErroAdmin(f'Digite um {nome} válido.')
    if x != x or x in (float('inf'), float('-inf')):
        raise ErroAdmin(f'Digite um {nome} válido.')
    if minimo is not None and x < minimo:
        raise ErroAdmin(f'O {nome} mínimo é {minimo}.')
    if maximo is not None and x > maximo:
        raise ErroAdmin(f'O {nome} máximo é {maximo}.')
    return round(x, 2)


def _inteiro(v, nome='número', minimo=None, maximo=None):
    try:
        x = int(float(str(v).strip()))
    except Exception:
        raise ErroAdmin(f'Digite um {nome} válido.')
    if minimo is not None and x < minimo:
        raise ErroAdmin(f'O {nome} mínimo é {minimo}.')
    if maximo is not None and x > maximo:
        raise ErroAdmin(f'O {nome} máximo é {maximo}.')
    return x


def _texto(v, maximo=300):
    return str(v or '').strip()[:maximo]


def _con(G):
    return G['database']._connect()


def _agora():
    """Data/hora de Brasília (as vendas e depósitos são gravados nesse horário;
    o servidor roda em UTC, então datetime.now() virava o dia 3h antes e zerava 'hoje')."""
    try:
        import pytz
        return datetime.now(pytz.timezone('America/Sao_Paulo')).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow() - timedelta(hours=3)


def _dia(dt):
    return dt.strftime('%Y-%m-%d')


def _cache_get(chave, ttl, fn):
    agora = time.time()
    c = _cache.get(chave)
    if c and agora - c[0] < ttl:
        return c[1]
    v = fn()
    _cache[chave] = (agora, v)
    return v


# ------------------------------------------------------------------ acesso
def eh_admin(G, cfg, u):
    try:
        if G['api'].Admin.verificar_admin(u.id) or str(u.id) == str(G['api'].CredentialsChange.id_dono()):
            return True
    except Exception:
        pass
    email = str(getattr(u, 'email', '') or '').lower()
    emails = [str(e).strip().lower() for e in (cfg.get('admin_emails') or [])]
    return bool(email and email in emails)


# ------------------------------------------------------------------ dashboard
def _dashboard(G):
    def calc():
        con = _con(G)
        hoje = _agora()
        d0 = _dia(hoje)
        d7 = _dia(hoje - timedelta(days=6))
        d30 = _dia(hoje - timedelta(days=29))
        iso = "data GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*'"

        def soma(tabela, desde):
            r = con.execute(f"SELECT COUNT(*) c, COALESCE(SUM(valor),0) v FROM {tabela} WHERE {iso} AND substr(data,1,10) >= ?", (desde,)).fetchone()
            return {'qtd': int(r['c']), 'valor': round(float(r['v']), 2)}

        serie = []
        vendas_dia = {r['d']: (r['c'], r['v']) for r in con.execute(
            f"SELECT substr(data,1,10) d, COUNT(*) c, COALESCE(SUM(valor),0) v FROM compras WHERE {iso} AND substr(data,1,10) >= ? GROUP BY d",
            (_dia(hoje - timedelta(days=13)),))}
        dep_dia = {r['d']: (r['c'], r['v']) for r in con.execute(
            f"SELECT substr(data,1,10) d, COUNT(*) c, COALESCE(SUM(valor),0) v FROM pagamentos WHERE {iso} AND substr(data,1,10) >= ? GROUP BY d",
            (_dia(hoje - timedelta(days=13)),))}
        for i in range(13, -1, -1):
            dd = _dia(hoje - timedelta(days=i))
            serie.append({'dia': dd[5:], 'vendas': round(float(vendas_dia.get(dd, (0, 0))[1]), 2),
                          'qtd': int(vendas_dia.get(dd, (0, 0))[0]), 'depositos': round(float(dep_dia.get(dd, (0, 0))[1]), 2)})
        top = [{'produto': r['produto'], 'qtd': int(r['c']), 'valor': round(float(r['v']), 2)} for r in con.execute(
            f"SELECT produto, COUNT(*) c, COALESCE(SUM(valor),0) v FROM compras WHERE {iso} AND substr(data,1,10) >= ? "
            "GROUP BY produto ORDER BY c DESC LIMIT 8", (d30,))]
        u = con.execute("SELECT COUNT(*) c, COALESCE(SUM(saldo),0) s FROM users WHERE user_id > 0").fetchone()
        ban = con.execute("SELECT COUNT(*) c FROM users WHERE banned IN ('True','true','1')").fetchone()['c']
        try:
            novos = int(con.execute("SELECT COUNT(*) c FROM site_contas").fetchone()['c'])
        except Exception:
            novos = 0
        try:
            tk = int(con.execute("SELECT COUNT(*) c FROM tickets WHERE status='aberto'").fetchone()['c'])
        except Exception:
            tk = 0
        grupos = {}
        for a in G['api'].ControleLogins.pegar_servicos():
            grupos[a.get('nome')] = grupos.get(a.get('nome'), 0) + 1
        baixo = sorted([{'nome': n, 'qtd': q} for n, q in grupos.items() if q <= 3], key=lambda x: x['qtd'])[:8]
        ult = [dict(r) for r in con.execute(
            "SELECT c.rowid_ai id, c.user_id, c.produto, c.valor, c.data, u.username FROM compras c LEFT JOIN users u ON u.user_id=c.user_id "
            "ORDER BY c.rowid_ai DESC LIMIT 8")]
        return {
            'hoje': {'vendas': soma('compras', d0), 'depositos': soma('pagamentos', d0)},
            'sete': {'vendas': soma('compras', d7), 'depositos': soma('pagamentos', d7)},
            'trinta': {'vendas': soma('compras', d30), 'depositos': soma('pagamentos', d30)},
            'clientes': int(u['c']), 'saldo_total': round(float(u['s']), 2), 'banidos': int(ban), 'contas_site': novos,
            'estoque_total': sum(grupos.values()), 'servicos': len(grupos), 'tickets_abertos': tk,
            'serie': serie, 'top': top, 'estoque_baixo': baixo, 'ultimas': ult,
        }
    return _cache_get('dash', 20, calc)


# ------------------------------------------------------------------ estoque
def _acessos(G):
    return G['api'].ControleLogins


# ---- Serviços salvos (catálogo): ficam gravados mesmo com estoque zerado ----
# Usa o MESMO arquivo do bot (database/templates_servicos.json), então o modo rápido do bot e o painel enxergam a mesma lista.
_CAT_PATH = os.path.join('database', 'templates_servicos.json')
_CAT_LOCK = threading.RLock()


def _cat_carregar():
    try:
        with open(_CAT_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _cat_salvar(cat):
    os.makedirs('database', exist_ok=True)
    tmp = _CAT_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cat, f, indent=4, ensure_ascii=False)
    os.replace(tmp, _CAT_PATH)


def _cat_chave(cat, nome):
    alvo = str(nome or '').strip().lower()
    for k in cat:
        if k.strip().lower() == alvo:
            return k
    return None


def _cat_gravar(nome, valor=None, duracao=None, descricao=None, antigo=None):
    """Cria/atualiza o serviço salvo. `antigo` = nome anterior (renomear). Campos None = mantém o que já estava."""
    nome = str(nome).strip()
    with _CAT_LOCK:
        cat = _cat_carregar()
        k_ant = _cat_chave(cat, antigo or nome)
        base = dict(cat.pop(k_ant)) if k_ant else {}
        k_novo = _cat_chave(cat, nome)
        if k_novo and k_novo != k_ant:
            base = {**cat.pop(k_novo), **base} if not k_ant else base
        if valor is not None:
            base['valor'] = str(valor)
        if duracao is not None:
            base['duracao'] = str(duracao)
        if descricao is not None:
            base['descricao'] = '' if descricao == '-' else str(descricao)
        base.setdefault('valor', '0')
        base.setdefault('duracao', '30')
        base.setdefault('descricao', '')
        cat[nome] = base
        _cat_salvar(cat)


def _cat_remover(nome):
    with _CAT_LOCK:
        cat = _cat_carregar()
        k = _cat_chave(cat, nome)
        if k is None:
            return False
        cat.pop(k)
        _cat_salvar(cat)
        return True


def _estoque_listar(G, oferta_fn):
    grupos = {}
    for a in _acessos(G).pegar_servicos():
        n = a.get('nome') or ''
        g = grupos.get(n)
        if not g:
            g = grupos[n] = {'nome': n, 'qtd': 0, 'valor': float(a.get('valor') or 0),
                             'duracao': int(a.get('duracao') or 30), 'descricao': str(a.get('descricao') or '')[:300]}
        g['qtd'] += 1
    # junta com os serviços salvos (inclui os que estão com estoque 0)
    with _CAT_LOCK:
        cat = _cat_carregar()
        mudou = False
        for n, g in grupos.items():           # tudo que já teve estoque passa a ficar gravado
            if n.strip() and _cat_chave(cat, n) is None:
                cat[n] = {'valor': str(g['valor']), 'descricao': '' if g['descricao'] == '-' else g['descricao'], 'duracao': str(g['duracao'])}
                mudou = True
        if mudou:
            try:
                _cat_salvar(cat)
            except Exception:
                pass
    em_estoque = {n.strip().lower() for n in grupos}
    for n, t in cat.items():
        if n.strip().lower() in em_estoque:
            continue
        try:
            v = float(str(t.get('valor') or 0).replace(',', '.'))
        except Exception:
            v = 0.0
        try:
            du = int(float(str(t.get('duracao') or 30)))
        except Exception:
            du = 30
        grupos[n] = {'nome': n, 'qtd': 0, 'valor': v, 'duracao': du, 'descricao': str(t.get('descricao') or '')[:300]}
    out = []
    for g in grupos.values():
        of = oferta_fn(g['nome']) if g['qtd'] else None
        g['oferta'] = float(of['preco_promocional']) if of else None
        g['salvo'] = _cat_chave(cat, g['nome']) is not None
        out.append(g)
    out.sort(key=lambda x: x['nome'].lower())
    return out


def _servico_salvar(G, u, d):
    """Cria (ou atualiza) um serviço salvo SEM precisar de logins."""
    nome = _texto(d.get('nome'), 120)
    if not nome:
        raise ErroAdmin('Digite o nome do serviço.')
    valor = _num(d.get('valor'), 0.01, 100000, 'preço')
    duracao = _inteiro(d.get('duracao') or 30, 'prazo (dias)', 1, 3650)
    descricao = _texto(d.get('descricao'), 300)
    _cat_gravar(nome, valor, duracao, descricao)
    _cache.pop('dash', None)
    _registrar(u, 'servico_salvar', f'{nome} valor={valor} dur={duracao}')
    return {'ok': True}


_RE_LINHA = re.compile(r'^\s*(?P<e>\S+?)\s*(?:[:|;]|\s{1,}|,)\s*(?P<s>\S.*?)\s*$')


def _estoque_adicionar(G, u, d):
    nome = _texto(d.get('nome'), 120)
    if not nome:
        raise ErroAdmin('Digite o nome do serviço.')
    valor = _num(d.get('valor'), 0.01, 100000, 'preço')
    duracao = _inteiro(d.get('duracao') or 30, 'prazo (dias)', 1, 3650)
    descricao = _texto(d.get('descricao'), 300) or '-'
    linhas = [l for l in str(d.get('linhas') or '').splitlines() if l.strip()]
    if not linhas:
        raise ErroAdmin('Cole os logins (um por linha, no formato email:senha).')
    if len(linhas) > 2000:
        raise ErroAdmin('No máximo 2000 logins por vez.')
    CL = _acessos(G)
    ok, invalidas, repetidas = 0, [], 0
    with CL._LOCK:
        data = CL._load_acessos()
        ja = {(str(a.get('nome', '')).lower(), str(a.get('email', '')).lower()) for a in data['acessos']}
        for i, l in enumerate(linhas, 1):
            m = _RE_LINHA.match(l)
            if not m:
                invalidas.append(i)
                continue
            e, s = m.group('e'), m.group('s')
            chave = (nome.lower(), e.lower())
            if chave in ja:
                repetidas += 1
                continue
            ja.add(chave)
            data['acessos'].append({'nome': nome, 'valor': valor, 'descricao': descricao, 'email': e, 'senha': s, 'duracao': duracao})
            ok += 1
        if ok and not CL._save_acessos(data):
            raise ErroAdmin('Não foi possível gravar o estoque. Tente de novo.', 500)
    try:
        _cat_gravar(nome, valor, duracao, descricao)   # deixa o serviço salvo para as próximas vezes
    except Exception:
        traceback.print_exc()
    _cache.pop('dash', None)
    _registrar(u, 'estoque_adicionar', f'{nome} +{ok} (repetidos {repetidas}, inválidos {len(invalidas)})')
    return {'adicionados': ok, 'repetidos': repetidas, 'invalidas': invalidas[:20]}


def _estoque_logins(G, nome):
    n = str(nome or '').lower()
    return [{'email': a.get('email'), 'senha': a.get('senha')} for a in _acessos(G).pegar_servicos()
            if str(a.get('nome', '')).lower() == n][:1000]


def _estoque_remover(G, u, d):
    nome, email = _texto(d.get('nome'), 120), _texto(d.get('email'), 200)
    CL = _acessos(G)
    with CL._LOCK:
        ok = CL.remover_login(nome, email)
    if not ok:
        raise ErroAdmin('Login não encontrado (talvez já tenha sido vendido).', 404)
    _cache.pop('dash', None)
    _registrar(u, 'estoque_remover', f'{nome} {email}')
    return {'ok': True}


def _estoque_editar(G, u, d):
    nome = _texto(d.get('nome'), 120)
    if not nome:
        raise ErroAdmin('Serviço inválido.')
    novo_nome = _texto(d.get('novo_nome'), 120) if d.get('novo_nome') not in (None, '') else None
    valor = _num(d.get('valor'), 0.01, 100000, 'preço') if d.get('valor') not in (None, '') else None
    duracao = _inteiro(d.get('duracao'), 'prazo (dias)', 1, 3650) if d.get('duracao') not in (None, '') else None
    descricao = _texto(d.get('descricao'), 300) if d.get('descricao') is not None else None
    CL = _acessos(G)
    n = 0
    with CL._LOCK:
        data = CL._load_acessos()
        trocou_nome = bool(novo_nome and novo_nome.lower() != nome.lower())
        if trocou_nome:
            if any(str(a.get('nome', '')).lower() == novo_nome.lower() for a in data['acessos']) or _cat_chave(_cat_carregar(), novo_nome):
                raise ErroAdmin('Já existe um serviço com esse novo nome.', 409)
        for a in data['acessos']:
            if str(a.get('nome', '')).lower() == nome.lower():
                if valor is not None:
                    a['valor'] = valor
                if duracao is not None:
                    a['duracao'] = duracao
                if descricao is not None:
                    a['descricao'] = descricao or '-'
                if novo_nome:
                    a['nome'] = novo_nome
                n += 1
        if not n and _cat_chave(_cat_carregar(), nome) is None:
            raise ErroAdmin('Serviço não encontrado.', 404)
        if n and not CL._save_acessos(data):
            raise ErroAdmin('Não foi possível gravar o estoque.', 500)
    _cat_gravar(novo_nome or nome, valor, duracao, descricao, antigo=nome)
    _cache.pop('dash', None)
    _registrar(u, 'estoque_editar', f'{nome} -> {novo_nome or nome} valor={valor} dur={duracao} ({n} logins)')
    return {'alterados': n}


def _estoque_remover_servico(G, u, d):
    """Exclui o serviço salvo E todos os logins dele que ainda estão no estoque."""
    nome = _texto(d.get('nome'), 120)
    if not nome:
        raise ErroAdmin('Serviço inválido.')
    CL = _acessos(G)
    n = 0
    with CL._LOCK:
        data = CL._load_acessos()
        antes = len(data['acessos'])
        data['acessos'] = [a for a in data['acessos'] if str(a.get('nome', '')).lower() != nome.lower()]
        n = antes - len(data['acessos'])
        if n and not CL._save_acessos(data):
            raise ErroAdmin('Não foi possível gravar o estoque.', 500)
    salvo = _cat_remover(nome)
    if not n and not salvo:
        raise ErroAdmin('Serviço não encontrado.', 404)
    _cache.pop('dash', None)
    _registrar(u, 'estoque_remover_servico', f'{nome} ({n} logins, salvo={salvo})')
    return {'removidos': n}


# ------------------------------------------------------------------ clientes
def _tipo_usuario(uid, wb):
    return 'site' if uid >= wb else 'telegram'


def _cliente_linha(r, wb, emails):
    uid = int(r['user_id'])
    return {'id': uid, 'username': r['username'], 'saldo': round(float(r['saldo'] or 0), 2),
            'compras': int(r['total_compras'] or 0), 'pagos': round(float(r['total_pagos'] or 0), 2),
            'banido': str(r['banned']).lower() in ('true', '1'), 'origem': _tipo_usuario(uid, wb),
            'email': emails.get(uid)}


def _clientes_listar(G, d, wb):
    con = _con(G)
    q = _texto(d.get('q'), 60)
    ordem = {'saldo': 'saldo DESC', 'compras': 'total_compras DESC', 'pagos': 'total_pagos DESC', 'recentes': 'rowid DESC'}.get(d.get('ordem'), 'saldo DESC')
    pag = _inteiro(d.get('pagina') or 1, 'página', 1, 100000)
    por = 25
    where, par = ['user_id > 0'], []
    if q:
        ids = []
        like = f'%{q.lower()}%'
        try:
            ids = [int(r['id']) for r in con.execute("SELECT id FROM site_contas WHERE lower(email) LIKE ? OR lower(nome) LIKE ? LIMIT 50", (like, like))]
            ids = [wb + i for i in ids]
        except Exception:
            pass
        cond = ['lower(username) LIKE ?']
        par.append(like)
        if q.lstrip('-').isdigit():
            cond.append('user_id = ?')
            par.append(int(q))
        if ids:
            cond.append('user_id IN (%s)' % ','.join('?' * len(ids)))
            par += ids
        where.append('(' + ' OR '.join(cond) + ')')
    w = ' AND '.join(where)
    total = con.execute(f'SELECT COUNT(*) c FROM users WHERE {w}', par).fetchone()['c']
    rows = con.execute(f'SELECT user_id, username, banned, saldo, total_pagos, total_compras FROM users WHERE {w} ORDER BY {ordem} LIMIT ? OFFSET ?',
                       par + [por, (pag - 1) * por]).fetchall()
    emails = {}
    site_ids = [int(r['user_id']) - wb for r in rows if int(r['user_id']) >= wb]
    if site_ids:
        try:
            for r in con.execute('SELECT id, email FROM site_contas WHERE id IN (%s)' % ','.join('?' * len(site_ids)), site_ids):
                emails[wb + int(r['id'])] = r['email']
        except Exception:
            pass
    return {'total': int(total), 'pagina': pag, 'por_pagina': por, 'itens': [_cliente_linha(r, wb, emails) for r in rows]}


def _cliente_ver(G, uid, wb):
    con = _con(G)
    r = con.execute('SELECT user_id, username, banned, saldo, total_pagos, total_compras FROM users WHERE user_id=?', (uid,)).fetchone()
    if not r:
        raise ErroAdmin('Cliente não encontrado.', 404)
    emails = {}
    if uid >= wb:
        try:
            x = con.execute('SELECT email, nome, criado_em, ultimo_login FROM site_contas WHERE id=?', (uid - wb,)).fetchone()
            if x:
                emails[uid] = x['email']
        except Exception:
            x = None
    base = _cliente_linha(r, wb, emails)
    base['compras_lista'] = [dict(x) for x in con.execute(
        'SELECT rowid_ai id, produto, valor, data, email, senha FROM compras WHERE user_id=? ORDER BY rowid_ai DESC LIMIT 30', (uid,))]
    base['pagamentos_lista'] = [dict(x) for x in con.execute(
        'SELECT id_pagamento, valor, data FROM pagamentos WHERE user_id=? ORDER BY rowid DESC LIMIT 20', (uid,))]
    base['movimentacoes'] = [dict(x) for x in con.execute(
        'SELECT tipo, valor, saldo_anterior, saldo_novo, admin_id, motivo, data FROM movimentacoes_saldo WHERE user_id=? ORDER BY rowid_ai DESC LIMIT 20', (uid,))]
    return base


def _cliente_saldo(G, u, d):
    uid = _inteiro(d.get('id'), 'ID')
    acao = d.get('acao')
    valor = _num(d.get('valor'), 0, 1000000, 'valor')
    motivo = _texto(d.get('motivo'), 150) or 'Ajuste pelo painel do site'
    api = G['api']
    if not G['database'].load_user_data(uid):
        raise ErroAdmin('Cliente não encontrado.', 404)
    antes = round(float(api.InfoUser.saldo(uid)), 2)
    if acao == 'add':
        if valor <= 0:
            raise ErroAdmin('Digite um valor maior que zero.')
        api.InfoUser.add_saldo(uid, valor)
        tipo = 'adicao'
    elif acao == 'remove':
        if valor <= 0:
            raise ErroAdmin('Digite um valor maior que zero.')
        if valor > antes + 0.001:
            raise ErroAdmin(f'O cliente só tem R$ {antes:.2f}.')
        api.InfoUser.mudar_saldo(uid, round(antes - valor, 2))
        tipo = 'remocao'
    elif acao == 'set':
        api.InfoUser.mudar_saldo(uid, valor)
        tipo = 'ajuste'
    else:
        raise ErroAdmin('Ação inválida.')
    depois = round(float(api.InfoUser.saldo(uid)), 2)
    try:
        G['database'].registrar_movimentacao_saldo(uid, tipo, abs(round(depois - antes, 2)), antes, depois, u.id, motivo)
    except Exception:
        print(f'[PAINEL] log de saldo falhou:\n{traceback.format_exc()}')
    _cache.pop('dash', None)
    _registrar(u, 'saldo', f'{uid} {tipo} {antes}->{depois} ({motivo})')
    return {'antes': antes, 'depois': depois}


def _cliente_ban(G, u, d):
    uid = _inteiro(d.get('id'), 'ID')
    api = G['api']
    if not G['database'].load_user_data(uid):
        raise ErroAdmin('Cliente não encontrado.', 404)
    if d.get('ban'):
        if api.Admin.verificar_admin(uid) or str(uid) == str(api.CredentialsChange.id_dono()):
            raise ErroAdmin('Não dá para banir um administrador.')
        api.InfoUser.dar_ban(uid)
    else:
        api.InfoUser.tirar_ban(uid)
    _cache.pop('dash', None)
    _registrar(u, 'banir' if d.get('ban') else 'desbanir', str(uid))
    return {'ok': True}


# ------------------------------------------------------------------ vendas / pagamentos
def _vendas_listar(G, d):
    con = _con(G)
    pag = _inteiro(d.get('pagina') or 1, 'página', 1, 100000)
    por = 30
    q = _texto(d.get('q'), 60)
    de, ate = _texto(d.get('de'), 10), _texto(d.get('ate'), 10)
    where, par = ['1=1'], []
    if q:
        where.append('(lower(c.produto) LIKE ? OR lower(u.username) LIKE ? OR CAST(c.user_id AS TEXT) = ? OR lower(c.email) LIKE ?)')
        like = f'%{q.lower()}%'
        par += [like, like, q, like]
    if re.match(r'^\d{4}-\d{2}-\d{2}$', de):
        where.append('substr(c.data,1,10) >= ?')
        par.append(de)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', ate):
        where.append('substr(c.data,1,10) <= ?')
        par.append(ate)
    w = ' AND '.join(where)
    base = 'FROM compras c LEFT JOIN users u ON u.user_id=c.user_id WHERE ' + w
    r = con.execute(f'SELECT COUNT(*) c, COALESCE(SUM(c.valor),0) v {base}', par).fetchone()
    rows = [dict(x) for x in con.execute(
        f'SELECT c.rowid_ai id, c.user_id, c.produto, c.valor, c.data, c.email, c.senha, u.username {base} ORDER BY c.rowid_ai DESC LIMIT ? OFFSET ?',
        par + [por, (pag - 1) * por])]
    return {'total': int(r['c']), 'soma': round(float(r['v']), 2), 'pagina': pag, 'por_pagina': por, 'itens': rows}


def _pagamentos_listar(G, d):
    con = _con(G)
    pag = _inteiro(d.get('pagina') or 1, 'página', 1, 100000)
    por = 30
    total = con.execute('SELECT COUNT(*) c, COALESCE(SUM(valor),0) v FROM pagamentos').fetchone()
    rows = [dict(x) for x in con.execute(
        'SELECT p.id_pagamento, p.user_id, p.valor, p.data, u.username FROM pagamentos p LEFT JOIN users u ON u.user_id=p.user_id '
        'ORDER BY p.rowid DESC LIMIT ? OFFSET ?', (por, (pag - 1) * por))]
    return {'total': int(total['c']), 'soma': round(float(total['v']), 2), 'pagina': pag, 'por_pagina': por, 'itens': rows}


# ------------------------------------------------------------------ ofertas
def _ofertas_listar():
    import Oferta_relampago as O
    return [{'servico': o['servico'], 'original': float(o['preco_original']), 'promo': float(o['preco_promocional']),
             'fim': o['fim_promocao'], 'limite': int(o.get('limite_quantidade', 0) or 0)} for o in O.verificar_ofertas_ativas()]


def _ofertas_criar(G, u, d):
    import Oferta_relampago as O
    nomes = [str(n) for n in (d.get('servicos') or []) if str(n).strip()]
    if not nomes or len(nomes) > 50:
        raise ErroAdmin('Escolha ao menos um serviço.')
    minutos = _inteiro(d.get('minutos') or 60, 'duração (minutos)', 1, 60 * 24 * 30)
    limite = _inteiro(d.get('limite') or 0, 'limite', 0, 10000)
    modo = d.get('modo')
    catalogo = {str(s['nome']).lower(): s for s in _estoque_listar(G, lambda n: None) if s['qtd'] > 0}
    lista = []
    for n in nomes:
        s = catalogo.get(n.lower())
        if not s:
            raise ErroAdmin(f'Serviço "{n}" não está no estoque.', 404)
        orig = float(s['valor'])
        if modo == 'percentual':
            pct = _num(d.get('valor'), 1, 95, 'desconto (%)')
            promo = round(orig * (1 - pct / 100), 2)
        else:
            promo = _num(d.get('valor'), 0.01, 100000, 'preço promocional')
        if promo >= orig:
            raise ErroAdmin(f'O preço promocional de {s["nome"]} precisa ser menor que R$ {orig:.2f}.')
        lista.append({'servico': s['nome'], 'preco_original': orig, 'preco_promocional': promo})
    fim = O.configurar_ofertas(lista, minutos, limite)
    _registrar(u, 'oferta_criar', f'{[x["servico"] for x in lista]} {minutos}min')
    return {'ok': True, 'fim': fim.isoformat(), 'qtd': len(lista)}


def _ofertas_remover(G, u, d):
    import Oferta_relampago as O
    if d.get('todas'):
        O.desativar_oferta(None)
    else:
        O.desativar_oferta(_texto(d.get('servico'), 120))
    _registrar(u, 'oferta_remover', 'todas' if d.get('todas') else _texto(d.get('servico'), 120))
    return {'ok': True}


# ------------------------------------------------------------------ gift cards
def _gift_ler():
    try:
        with open('database/gift_card.json', 'r', encoding='utf-8') as f:
            d = json.load(f)
        return [g for g in d.get('gift', []) if isinstance(g, dict)]
    except Exception:
        return []


def _gift_criar(G, u, d):
    import secrets
    import string
    valor = _num(d.get('valor'), 0.01, 100000, 'valor')
    qtd = _inteiro(d.get('quantidade') or 1, 'quantidade', 1, 200)
    existentes = {g.get('codigo') for g in _gift_ler()}
    novos = []
    alfabeto = string.ascii_uppercase + string.digits
    for i in range(qtd):
        cod = _texto(d.get('codigo'), 30).upper() if (qtd == 1 and d.get('codigo')) else ''.join(secrets.choice(alfabeto) for _ in range(10))
        if not re.match(r'^[A-Z0-9_-]{4,30}$', cod):
            raise ErroAdmin('Código inválido (use 4 a 30 letras/números).')
        if cod in existentes:
            raise ErroAdmin(f'O código {cod} já existe.', 409)
        existentes.add(cod)
        if not G['api'].GiftCard.create_gift(cod, valor):
            raise ErroAdmin('Não foi possível criar o gift card.', 500)
        novos.append(cod)
    _registrar(u, 'gift_criar', f'{qtd}x R$ {valor}')
    return {'codigos': novos, 'valor': valor}


def _gift_remover(G, u, d):
    cod = _texto(d.get('codigo'), 40)
    antes = len(_gift_ler())
    G['api'].GiftCard.del_gift(cod)
    if len(_gift_ler()) >= antes:
        raise ErroAdmin('Gift card não encontrado.', 404)
    _registrar(u, 'gift_remover', cod)
    return {'ok': True}


# ------------------------------------------------------------------ tickets
def _tickets_listar(G, d):
    con = _con(G)
    st = _texto(d.get('status'), 20)
    where, par = '1=1', []
    if st:
        where, par = 'status=?', [st]
    rows = [dict(r) for r in con.execute(
        f'SELECT id, numero, user_id, nome, username, categoria, status, criado_em, atualizado_em FROM tickets WHERE {where} ORDER BY id DESC LIMIT 100', par)]
    return {'itens': rows}


def _ticket_ver(G, tid):
    con = _con(G)
    t = con.execute('SELECT * FROM tickets WHERE id=?', (tid,)).fetchone()
    if not t:
        raise ErroAdmin('Ticket não encontrado.', 404)
    ok = ('remetente', 'autor_nome', 'tipo', 'conteudo', 'criado_em', 'data')
    msgs = [{k: r[k] for k in r.keys() if k in ok} for r in con.execute('SELECT * FROM ticket_mensagens WHERE ticket_id=? ORDER BY id LIMIT 300', (tid,))]
    return {'ticket': {k: t[k] for k in ('id', 'numero', 'user_id', 'nome', 'username', 'categoria', 'status', 'criado_em', 'atualizado_em')},
            'mensagens': msgs}


# ------------------------------------------------------------------ configurações / transmissão
def _manutencao_estado():
    try:
        from rl_maintenance import is_on
        return bool(is_on())
    except Exception:
        return False


def _manutencao_definir(u, on):
    from rl_maintenance import maintenance_on, maintenance_off
    (maintenance_on if on else maintenance_off)()
    _registrar(u, 'manutencao', 'ligada' if on else 'desligada')
    return {'manutencao': bool(on)}


def _integracao_estoque_estado():
    import integracao_estoque as ie
    return ie.estado()


def _integracao_estoque_salvar(u, d):
    import integracao_estoque as ie
    try:
        ie.configurar(d.get('url'), d.get('key'))
    except ie.ErroIntegracao as e:
        raise ErroAdmin(e.msg, e.status)
    _registrar(u, 'api_estoque_conectada', str(d.get('url') or '')[:300])
    return ie.estado()


def _integracao_estoque_desconectar(u):
    import integracao_estoque as ie
    ie.desconectar()
    _registrar(u, 'api_estoque_desconectada')
    return ie.estado()


def _integracao_estoque_testar():
    import integracao_estoque as ie
    try:
        produtos = ie.catalogo()
    except ie.ErroIntegracao as e:
        raise ErroAdmin(e.msg, e.status)
    if produtos is None:
        raise ErroAdmin('Nenhuma API está conectada.', 400)
    return {'ok': True, 'produtos': len(produtos)}


def _transmitir(G, u, d, wb):
    if _transm['rodando']:
        raise ErroAdmin('Já tem uma transmissão em andamento.', 409)
    texto = str(d.get('texto') or '').strip()
    if len(texto) < 3 or len(texto) > 3500:
        raise ErroAdmin('Escreva a mensagem (3 a 3500 caracteres).')
    if not d.get('confirmar'):
        raise ErroAdmin('Confirme o envio.')
    ids = [int(r['user_id']) for r in _con(G).execute(
        "SELECT user_id, banned FROM users WHERE user_id > 0 AND user_id < ?", (wb,)).fetchall()
        if str(r['banned']).lower() not in ('true', '1')]
    bot = G['bot']
    _transm.update({'rodando': True, 'total': len(ids), 'ok': 0, 'falha': 0, 'inicio': time.time(), 'fim': 0})

    def _run():
        try:
            for i in ids:
                try:
                    bot.send_message(i, texto, parse_mode='HTML', disable_web_page_preview=True)
                    _transm['ok'] += 1
                except Exception:
                    _transm['falha'] += 1
                time.sleep(0.06)
        finally:
            _transm['rodando'] = False
            _transm['fim'] = time.time()
    threading.Thread(target=_run, daemon=True, name='painel-transmissao').start()
    _registrar(u, 'transmissao', f'{len(ids)} clientes: {texto[:80]}')
    return {'total': len(ids)}


# ------------------------------------------------------------------ roteador
def _imagens_listar(G):
    """Serviços (do estoque e dos salvos) com a informação de qual tem imagem trocada pelo painel."""
    import webapp_imagens as wi
    itens = _estoque_listar(G, lambda n: None)
    return {'itens': [{'nome': i['nome'], 'qtd': i['qtd'], 'custom': wi.personalizada(i['nome']),
                       'v': wi.versao(i['nome'])} for i in itens if str(i['nome']).strip()]}


def _imagem_definir(u, d):
    import webapp_imagens as wi
    nome = _texto(d.get('nome'), 120)
    if not nome:
        raise ErroAdmin('Informe o serviço.')
    try:
        v = wi.salvar(nome, d.get('imagem'))
    except wi.ErroImagem as e:
        raise ErroAdmin(e.msg, e.status)
    _registrar(u, 'imagem_definir', nome)
    return {'ok': True, 'v': v}


def _imagem_remover(u, d):
    import webapp_imagens as wi
    nome = _texto(d.get('nome'), 120)
    try:
        v = wi.remover(nome)
    except wi.ErroImagem as e:
        raise ErroAdmin(e.msg, e.status)
    _registrar(u, 'imagem_remover', nome)
    return {'ok': True, 'v': v}



# ------------------------------------------------------------------ notificações (sininho)
def _notif_listar(G, u, d):
    import eventos_admin as E
    return E.listar(u.id, _texto(d.get('tipo'), 20) or None, _inteiro(d.get('apos') or 0, 'id', 0), _inteiro(d.get('limite') or 40, 'limite', 1, 100))


def _notif_lidas(G, u, d):
    import eventos_admin as E
    return {'ok': True, 'lido_ate': E.marcar_lidas(u.id)}


# ------------------------------------------------------------------ pagamentos (mesmas opções do bot)
_GW_NOMES = {'promissepay': 'PromissePay', 'misticpay': 'MisticPay', 'mercadopago': 'Mercado Pago'}


_GW_NOMES = {'misticpay': 'MisticPay', 'mercadopago': 'Mercado Pago', 'pushinpay': 'PushinPay'}
_GW_CHAVE = {'misticpay': 'misticpay', 'mercadopago': 'mercado_pago', 'pushinpay': 'pushinpay'}
_lock_cred = threading.Lock()


def _cred_ler():
    with open('settings/credenciais.json', 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def _cred_gravar(d):
    tmp = 'settings/credenciais.json.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=4)
    os.replace(tmp, 'settings/credenciais.json')


def _cred_mudar(fn):
    with _lock_cred:
        d = _cred_ler()
        fn(d)
        _cred_gravar(d)


def _pg_configurado(d, g):
    gw = d.get('gateway_pagamento', {}) or {}
    if g == 'misticpay':
        m = gw.get('misticpay', {}) or {}
        return bool(m.get('client_id') and m.get('client_secret'))
    if g == 'pushinpay':
        return bool((gw.get('pushinpay', {}) or {}).get('token'))
    return bool(d.get('token_mp') or (gw.get('mercado_pago', {}) or {}).get('token'))


def _pg_estado():
    d = _cred_ler()
    sel = (d.get('gateway_pagamento', {}) or {}).get('selecionada', 'mercado_pago')
    ativo = next((k for k, v in _GW_CHAVE.items() if v == sel), 'mercadopago')
    gws = [{'id': k, 'nome': n, 'configurado': _pg_configurado(d, k), 'estavel': True, 'falhas': 0, 'instavel_ate': 0}
           for k, n in _GW_NOMES.items()]
    return {
        'gateway_ativo': ativo, 'ordem': [ativo], 'gateways': gws,
        'troca_automatica': False,
        'taxa': {'ativa': False, 'valor': 0, 'limite': 0},
        'pix': {'manual': str(d.get('status_pix_manu')) == 'on', 'automatico': str(d.get('status_pix_auto')) == 'on',
                'minimo': float(d.get('min_pix', 0) or 0), 'maximo': float(d.get('max_pix', 0) or 0),
                'expiracao': int(d.get('expiracao_pix', 15) or 15),
                'bonus_pct': int(d.get('bonus_pix', 0) or 0), 'bonus_min': float(d.get('bonus_pix_min', 0) or 0)},
    }


def _pg_salvar(G, u, d):
    campo = _texto(d.get('campo'), 30)
    v = d.get('valor')
    atual = _cred_ler()
    if campo == 'gateway':
        g = _texto(v, 20)
        if g not in _GW_NOMES:
            raise ErroAdmin('Gateway inválido.')
        if not _pg_configurado(atual, g):
            raise ErroAdmin(f'{_GW_NOMES[g]} ainda não tem credenciais salvas.')
        _cred_mudar(lambda c: c.setdefault('gateway_pagamento', {}).__setitem__('selecionada', _GW_CHAVE[g]))
    elif campo in ('pix_manual', 'pix_automatico'):
        chave = 'status_pix_manu' if campo == 'pix_manual' else 'status_pix_auto'
        _cred_mudar(lambda c: c.__setitem__(chave, 'on' if bool(v) else 'off'))
    elif campo == 'minimo':
        x = _num(v, 0.01, 100000, 'depósito mínimo')
        if x > float(atual.get('max_pix', 0) or 0):
            raise ErroAdmin('O mínimo não pode ser maior que o máximo.')
        _cred_mudar(lambda c: c.__setitem__('min_pix', x))
    elif campo == 'maximo':
        x = _num(v, 0.01, 1000000, 'depósito máximo')
        if x < float(atual.get('min_pix', 0) or 0):
            raise ErroAdmin('O máximo não pode ser menor que o mínimo.')
        _cred_mudar(lambda c: c.__setitem__('max_pix', x))
    elif campo == 'expiracao':
        x = _inteiro(v, 'tempo de expiração', 1, 1440)
        _cred_mudar(lambda c: c.__setitem__('expiracao_pix', x))
    elif campo == 'bonus_pct':
        x = _inteiro(v, 'bônus', 0, 500)
        _cred_mudar(lambda c: c.__setitem__('bonus_pix', x))
    elif campo == 'bonus_min':
        x = int(_num(v, 0, 100000, 'valor mínimo do bônus'))
        _cred_mudar(lambda c: c.__setitem__('bonus_pix_min', x))
    else:
        raise ErroAdmin('Opção inválida.')
    _registrar(u, 'pagamentos', f'{campo}={v}')
    return _pg_estado()


def _pg_credenciais(G, u, d):
    """Só grava (nunca devolve) as chaves dos gateways."""
    g = _texto(d.get('gateway'), 20)
    if g == 'mercadopago':
        t = _texto(d.get('token'), 400)
        if len(t) < 8:
            raise ErroAdmin('Cole o Access Token completo.')

        def f(c):
            c['token_mp'] = t
            c.setdefault('gateway_pagamento', {}).setdefault('mercado_pago', {})['token'] = t
        _cred_mudar(f)
    elif g == 'pushinpay':
        t = _texto(d.get('token'), 400)
        if len(t) < 8:
            raise ErroAdmin('Cole o token completo.')
        _cred_mudar(lambda c: c.setdefault('gateway_pagamento', {}).setdefault('pushinpay', {}).__setitem__('token', t))
    elif g == 'misticpay':
        ci, cs = _texto(d.get('client_id'), 300), _texto(d.get('client_secret'), 300)
        if len(ci) < 4 or len(cs) < 4:
            raise ErroAdmin('Informe o Client ID e o Client Secret.')

        def f(c):
            m = c.setdefault('gateway_pagamento', {}).setdefault('misticpay', {})
            m['client_id'], m['client_secret'] = ci, cs
        _cred_mudar(f)
    else:
        raise ErroAdmin('Gateway inválido.')
    _registrar(u, 'pagamentos_credenciais', g)      # a chave em si nunca vai para o log
    return _pg_estado()


def _pg_pendentes(G):
    return {'itens': []}


# ------------------------------------------------------------------ admins (igual 🕵️ Admins do bot)
def _admins_listar(G):
    api = G['api']
    dono = int(api.CredentialsChange.id_dono())
    ids = []
    try:
        ids = [int(i) for i in api.Admin.obter_ids_admins()]
    except Exception:
        pass
    if dono not in ids:
        ids.insert(0, dono)
    con = _con(G)
    out = []
    for i in ids:
        r = con.execute('SELECT username FROM users WHERE user_id=?', (i,)).fetchone()
        out.append({'id': i, 'username': (r['username'] if r else None), 'dono': i == dono})
    return {'itens': out}


def _admin_adicionar(G, u, d):
    uid = _inteiro(d.get('id'), 'ID do Telegram', 1)
    if not G['api'].Admin.add_admin(uid):
        raise ErroAdmin('Não consegui adicionar esse admin.')
    _registrar(u, 'admin_add', str(uid))
    return _admins_listar(G)


def _admin_remover(G, u, d):
    uid = _inteiro(d.get('id'), 'ID do Telegram', 1)
    if uid == int(G['api'].CredentialsChange.id_dono()):
        raise ErroAdmin('O dono não pode ser removido.')
    if uid == int(u.id):
        raise ErroAdmin('Você não pode remover você mesmo (ficaria sem acesso).')
    G['api'].Admin.remover_admin(uid)
    _registrar(u, 'admin_remover', str(uid))
    return _admins_listar(G)


# ------------------------------------------------------------------ backup e canal obrigatório
def _backup_estado():
    raise ErroAdmin('Backup pelo painel não está disponível neste bot.', 404)


def _backup_acao(G, u, d, wb):
    raise ErroAdmin('Backup pelo painel não está disponível neste bot.', 404)


def _canal_estado(G):
    if not hasattr(G['api'], 'CanalObrigatorio'):
        raise ErroAdmin('Grupo obrigatório não está disponível neste bot.', 404)
    CO = G['api'].CanalObrigatorio
    return {'ativo': bool(CO.status_ativo()), 'id': str(CO.get_id_canal())}


def _canal_definir(G, u, d):
    if not hasattr(G['api'], 'CanalObrigatorio'):
        raise ErroAdmin('Grupo obrigatório não está disponível neste bot.', 404)
    CO = G['api'].CanalObrigatorio
    if bool(d.get('on')) != bool(CO.status_ativo()):
        CO.alternar_status()
    _registrar(u, 'canal_obrigatorio', str(bool(d.get('on'))))
    return _canal_estado(G)


def tratar(G, cfg, wb, rota, d, u):
    """Chamado pelo webapp para /api/admin/*. Só admins chegam aqui."""
    r = rota[len('/api/admin/'):]
    if r == 'eu':
        return {'id': u.id, 'nome': u.nome, 'manutencao': _manutencao_estado()}
    if r == 'dashboard':
        return _dashboard(G)
    if r == 'estoque/listar':
        return {'itens': _estoque_listar(G, lambda n: __import__('Oferta_relampago')._achar_oferta(n))}
    if r == 'estoque/logins':
        return {'itens': _estoque_logins(G, d.get('nome'))}
    if r == 'estoque/adicionar':
        return _estoque_adicionar(G, u, d)
    if r == 'estoque/remover':
        return _estoque_remover(G, u, d)
    if r == 'estoque/editar':
        return _estoque_editar(G, u, d)
    if r == 'estoque/salvar_servico':
        return _servico_salvar(G, u, d)
    if r == 'estoque/remover_servico':
        return _estoque_remover_servico(G, u, d)
    if r == 'imagens/listar':
        return _imagens_listar(G)
    if r == 'imagens/definir':
        return _imagem_definir(u, d)
    if r == 'imagens/remover':
        return _imagem_remover(u, d)
    if r == 'clientes/listar':
        return _clientes_listar(G, d, wb)
    if r == 'clientes/ver':
        return _cliente_ver(G, _inteiro(d.get('id'), 'ID'), wb)
    if r == 'clientes/saldo':
        return _cliente_saldo(G, u, d)
    if r == 'clientes/ban':
        return _cliente_ban(G, u, d)
    if r == 'vendas/listar':
        return _vendas_listar(G, d)
    if r == 'pagamentos/listar':
        return _pagamentos_listar(G, d)
    if r == 'ofertas/listar':
        return {'itens': _ofertas_listar()}
    if r == 'ofertas/criar':
        return _ofertas_criar(G, u, d)
    if r == 'ofertas/remover':
        return _ofertas_remover(G, u, d)
    if r == 'gifts/listar':
        return {'itens': _gift_ler()}
    if r == 'gifts/criar':
        return _gift_criar(G, u, d)
    if r == 'gifts/remover':
        return _gift_remover(G, u, d)
    if r == 'tickets/listar':
        return _tickets_listar(G, d)
    if r == 'tickets/ver':
        return _ticket_ver(G, _inteiro(d.get('id'), 'ticket'))
    if r == 'config/ver':
        return {'manutencao': _manutencao_estado(), 'admin_emails': cfg.get('admin_emails') or [], 'transmissao': dict(_transm),
                'integracao_estoque': _integracao_estoque_estado()}
    if r == 'config/manutencao':
        return _manutencao_definir(u, bool(d.get('on')))
    if r == 'integracao_estoque/salvar':
        return _integracao_estoque_salvar(u, d)
    if r == 'integracao_estoque/desconectar':
        return _integracao_estoque_desconectar(u)
    if r == 'integracao_estoque/testar':
        return _integracao_estoque_testar()
    if r == 'transmitir':
        return _transmitir(G, u, d, wb)
    if r == 'transmitir/status':
        return dict(_transm)
    if r == 'notificacoes/listar':
        return _notif_listar(G, u, d)
    if r == 'notificacoes/lidas':
        return _notif_lidas(G, u, d)
    if r == 'pagamentos/config':
        return _pg_estado()
    if r == 'pagamentos/salvar':
        return _pg_salvar(G, u, d)
    if r == 'pagamentos/credenciais':
        return _pg_credenciais(G, u, d)
    if r == 'pagamentos/pendentes':
        return _pg_pendentes(G)
    if r == 'admins/listar':
        return _admins_listar(G)
    if r == 'admins/adicionar':
        return _admin_adicionar(G, u, d)
    if r == 'admins/remover':
        return _admin_remover(G, u, d)
    if r == 'backup/estado':
        return _backup_estado()
    if r == 'backup/acao':
        return _backup_acao(G, u, d, wb)
    if r == 'canal/estado':
        return _canal_estado(G)
    if r == 'canal/definir':
        return _canal_definir(G, u, d)
    raise ErroAdmin('Rota inexistente.', 404)
