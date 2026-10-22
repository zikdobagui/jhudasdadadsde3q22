# -*- coding: utf-8 -*-
"""
Central de notificações do ADM (o "sininho" do painel do site).

Como funciona
-------------
Tudo que o bot já manda para o dono/admins no Telegram — PIX GERADO, PAGAMENTO APROVADO, NOVA VENDA,
novo cadastro, novo ticket — também é gravado aqui. É feito "escutando" o send_message/send_photo do
bot (instalar), então NÃO precisa mexer nos módulos de pagamento/venda, e qualquer aviso novo que
siga os mesmos títulos entra sozinho no sininho.

Os eventos ficam em database/eventos_admin.db (SQLite, só os últimos 3000). O "lido até" é guardado
por admin, então o contador do sino é o mesmo no celular e no computador.
"""
import os
import re
import time
import sqlite3
import hashlib
import threading

_ARQ = os.path.join('database', 'eventos_admin.db')
_lock = threading.Lock()
_MAX = 3000
_vistos = {}          # hash -> ts (evita gravar 2x o mesmo aviso mandado ao dono e a outro admin)
_ids_cache = {'ts': 0, 'ids': set()}

TIPOS = {
    'pix_gerado': ('💸', 'PIX gerado'),
    'pix_pago': ('✅', 'PIX pago'),
    'venda': ('🛍️', 'Venda'),
    'cadastro': ('🆕', 'Novo cadastro'),
    'ticket': ('💬', 'Ticket / ocorrência'),
}


def _con():
    os.makedirs(os.path.dirname(_ARQ), exist_ok=True)
    c = sqlite3.connect(_ARQ, timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _iniciar():
    with _lock:
        c = _con()
        try:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, tipo TEXT, '
                      'titulo TEXT, texto TEXT, user_id INTEGER, valor REAL, ref TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS lidos (uid INTEGER PRIMARY KEY, ate INTEGER)')
            c.commit()
        finally:
            c.close()


# ------------------------------------------------------------------ gravar
def _limpar_html(t):
    t = re.sub(r'<[^>]+>', '', str(t or ''))
    return t.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').strip()


def _classificar(txt):
    u = txt.upper()
    if 'PIX GERADO' in u:
        return 'pix_gerado'
    if 'PAGAMENTO APROVADO' in u:
        return 'pix_pago'
    if 'NOVA VENDA' in u or 'NOVA COMPRA' in u or 'LOG DE COMPRA' in u or 'VENDA REGISTRADA' in u:
        return 'venda'
    if 'NOVA OCORR' in u:
        return 'ticket'
    if 'NOVO CADASTRO' in u or 'NOVO USUÁRIO' in u or 'NOVO USUARIO' in u:
        return 'cadastro'
    if 'NOVO TICKET' in u:
        return 'ticket'
    return None


_SENSIVEL = re.compile(r'(senha|password|e-?mail:|usu[aá]rio:|acesso entregue|seu acesso)', re.I)
_EMAIL_SENHA = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+\s*[:|]\s*\S+')


def _sem_credenciais(txt):
    """O aviso de venda chega com o login/senha entregue — isso NUNCA vai para o sininho."""
    return '\n'.join(l for l in txt.splitlines() if not _SENSIVEL.search(l) and not _EMAIL_SENHA.search(l))


def _extrair(txt):
    uid = None
    m = re.search(r'\bID\b[^\d\n]{0,12}(\d{5,15})', txt, re.I) or re.search(r'🆔[^\d\n]{0,6}(\d{5,15})', txt)
    if m:
        uid = int(m.group(1))
    valor = None
    m = re.search(r'(?:Total Creditado|Valor Recebido|Valor|Total|Pre[çc]o)[^R\n]{0,12}R\$\s*([\d.]+,\d{2}|\d+(?:\.\d{1,2})?)', txt, re.I) \
        or re.search(r'R\$\s*([\d.]+,\d{2}|\d+(?:\.\d{1,2})?)', txt)
    if m:
        s = m.group(1)
        s = s.replace('.', '').replace(',', '.') if ',' in s else s
        try:
            valor = float(s)
        except Exception:
            valor = None
    ref = None
    m = re.search(r'(?:Pagamento ID|ID do Pagamento|Refer[eê]ncia[^:\n]*:|🧾)\s*[:]?\s*[^\w\n]{0,3}\s*([A-Za-z0-9_\-]{6,60})', txt, re.I)
    if m:
        ref = m.group(1)
    return uid, valor, ref


def registrar(tipo, titulo, texto, user_id=None, valor=None, ref=None, ts=None):
    try:
        with _lock:
            c = _con()
            try:
                cur = c.execute('INSERT INTO eventos (ts, tipo, titulo, texto, user_id, valor, ref) VALUES (?,?,?,?,?,?,?)',
                                (ts or time.strftime('%Y-%m-%d %H:%M:%S'), tipo, titulo, str(texto)[:1500], user_id, valor, ref))
                novo = cur.lastrowid
                if novo % 200 == 0:
                    c.execute('DELETE FROM eventos WHERE id <= ?', (novo - _MAX,))
                c.commit()
                return novo
            finally:
                c.close()
    except Exception as e:
        print(f'[EVENTOS_ADM] falha ao gravar: {e}')
        return None


def _registrar_texto(txt_html):
    txt = _limpar_html(txt_html)
    tipo = _classificar(txt)
    if not tipo:
        return
    txt = _sem_credenciais(txt)
    h = hashlib.md5((tipo + txt).encode('utf-8', 'ignore')).hexdigest()
    agora = time.time()
    for k in [k for k, t in _vistos.items() if agora - t > 30]:
        _vistos.pop(k, None)
    if h in _vistos:
        return
    _vistos[h] = agora
    uid, valor, ref = _extrair(txt)
    linhas = [l.strip() for l in txt.splitlines() if l.strip()]
    titulo = re.sub(r'^[^\w\[(]+', '', linhas[0]) if linhas else TIPOS[tipo][1]
    registrar(tipo, titulo[:90], '\n'.join(linhas[1:]) if len(linhas) > 1 else '', uid, valor, ref)


def _alvos(api):
    """IDs que recebem avisos privados (dono + admins). Atualiza a cada 60 s."""
    if time.time() - _ids_cache['ts'] > 60:
        ids = set()
        try:
            ids.add(int(api.CredentialsChange.id_dono()))
        except Exception:
            pass
        try:
            ids.update(int(i) for i in api.Admin.obter_ids_admins())
        except Exception:
            pass
        _ids_cache.update(ts=time.time(), ids=ids)
    return _ids_cache['ids']


def instalar(bot, api):
    """Liga a escuta no bot. Seguro chamar mais de uma vez."""
    if getattr(bot, '_eventos_adm', False):
        return
    _iniciar()
    _semear()

    def _env(nome, campo_texto):
        orig = getattr(bot, nome, None)
        if orig is None:
            return

        def f(*a, **k):
            r = orig(*a, **k)
            try:
                cid = a[0] if a else k.get('chat_id')
                if int(cid) in _alvos(api):
                    texto = k.get(campo_texto)
                    if texto is None and nome == 'send_message' and len(a) > 1:
                        texto = a[1]
                    if texto:
                        _registrar_texto(texto)
            except Exception:
                pass
            return r
        f.__name__ = nome
        setattr(bot, nome, f)

    _env('send_message', 'text')
    _env('send_photo', 'caption')
    bot._eventos_adm = True
    print('[EVENTOS_ADM] sininho do painel ligado')


def _semear():
    """Primeira vez: já enche o sino com as últimas vendas e PIX pagos do banco."""
    try:
        c = _con()
        n = c.execute('SELECT COUNT(*) FROM eventos').fetchone()[0]
        c.close()
        if n:
            return
        import database
        con = database._connect()
        itens = []
        for r in con.execute('SELECT user_id, produto, valor, data FROM compras ORDER BY rowid_ai DESC LIMIT 25'):
            itens.append((str(r['data'] or ''), 'venda', 'Nova venda', f"📦 {r['produto']}", r['user_id'], r['valor']))
        for r in con.execute('SELECT id_pagamento, user_id, valor, data FROM pagamentos ORDER BY rowid DESC LIMIT 25'):
            itens.append((str(r['data'] or ''), 'pix_pago', 'Pagamento aprovado', 'PIX confirmado', r['user_id'], r['valor'], r['id_pagamento']))
        itens.sort(key=lambda x: x[0])
        ult = 0
        for it in itens:
            ult = registrar(it[1], it[2], it[3], it[4], it[5], it[6] if len(it) > 6 else None, ts=it[0][:19] or None) or ult
        if ult:
            c = _con()
            c.execute('INSERT OR REPLACE INTO lidos (uid, ate) VALUES (0, ?)', (int(ult),))
            c.commit()
            c.close()
    except Exception as e:
        print(f'[EVENTOS_ADM] semente ignorada: {e}')


# ------------------------------------------------------------------ ler (usado pela API do painel)
def listar(uid, tipo=None, apos=0, limite=40):
    _iniciar()
    c = _con()
    try:
        where, par = ['1=1'], []
        if tipo and tipo in TIPOS:
            where.append('tipo = ?')
            par.append(tipo)
        if apos:
            where.append('id > ?')
            par.append(int(apos))
        rows = [dict(r) for r in c.execute(
            f"SELECT * FROM eventos WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?", par + [int(limite)])]
        ult = c.execute('SELECT COALESCE(MAX(id),0) m FROM eventos').fetchone()['m']
        lido = c.execute('SELECT ate FROM lidos WHERE uid=?', (int(uid),)).fetchone()
        if not lido:      # admin novo no sino: o histórico semeado conta como já lido
            lido = c.execute('SELECT ate FROM lidos WHERE uid=0').fetchone()
        lido = int(lido['ate']) if lido else 0
        nao = c.execute('SELECT COUNT(*) n FROM eventos WHERE id > ?', (lido,)).fetchone()['n']
        for r in rows:
            r['icone'] = TIPOS.get(r['tipo'], ('🔔', ''))[0]
            r['rotulo'] = TIPOS.get(r['tipo'], ('', 'Aviso'))[1]
            r['novo'] = r['id'] > lido
        return {'itens': rows, 'ultimo_id': int(ult), 'lido_ate': lido, 'nao_lidas': int(nao)}
    finally:
        c.close()


def marcar_lidas(uid):
    _iniciar()
    with _lock:
        c = _con()
        try:
            m = c.execute('SELECT COALESCE(MAX(id),0) m FROM eventos').fetchone()['m']
            c.execute('INSERT INTO lidos (uid, ate) VALUES (?,?) ON CONFLICT(uid) DO UPDATE SET ate=excluded.ate', (int(uid), int(m)))
            c.commit()
            return int(m)
        finally:
            c.close()
