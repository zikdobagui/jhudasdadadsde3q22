# -*- coding: utf-8 -*-
"""
WEBAPP.PY — Site (Telegram Mini App) da loja, rodando DENTRO do processo do bot.

Por que dentro do bot: estoque (database/acessos.json), saldo e vendas (bot.db)
são os mesmos arquivos do bot. Rodando no mesmo processo, o site usa as mesmas
funções (ControleLogins, InfoUser, entregar, gerar_pix_com_failover...) e
"o que sai no bot sai no site, o que sai no site sai no bot".

Cliente = (a) ID do Telegram, validado pela assinatura (initData) do próprio Telegram
(Mini App), ou (b) conta criada no site com E-MAIL + SENHA, para quem não tem Telegram.
Conta de e-mail ganha um ID interno >= WEB_BASE (10**13) e vive na mesma tabela `users` do bot.

Configuração: settings/webapp.json  ->  {"url": "https://SEU-SITE", "porta": 8080}
(ou variáveis de ambiente WEBAPP_URL e PORT).
"""
import os
import json
import hmac
import time
import base64
import hashlib
import threading
import re
import sys
import secrets
import unicodedata
import traceback
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qsl, parse_qs, quote
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

G = {}
_PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp_static')
_VER_CACHE = {'chave': None, 'v': '0'}


def _versao_site():
    """Identificador da versão do site (muda quando index.html, sw.js ou manifest mudam)."""
    try:
        import hashlib
        arqs = [os.path.join(_PASTA, 'index.html'), os.path.join(_PASTA, 'pwa', 'sw.js'),
                os.path.join(_PASTA, 'pwa', 'manifest.webmanifest')]
        chave = tuple((os.path.getmtime(a), os.path.getsize(a)) for a in arqs if os.path.exists(a))
        if chave != _VER_CACHE['chave']:
            h = hashlib.sha1()
            for a in arqs:
                if os.path.exists(a):
                    with open(a, 'rb') as f:
                        h.update(f.read())
            _VER_CACHE['chave'], _VER_CACHE['v'] = chave, h.hexdigest()[:12]
        return _VER_CACHE['v']
    except Exception:
        return '0'
_LOCK_COMPRA = threading.RLock()
_ultimo = {}


class Erro(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


# ----------------------------------------------------------------- config
def _cfg():
    try:
        with open('settings/webapp.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def url_publica():
    """URL do site (usada pelo botão 'Abrir Loja'). None = botão não aparece."""
    return (os.environ.get('WEBAPP_URL') or _cfg().get('url') or '').strip() or None


# ------------------------------------------------------------------- auth
def _fake_msg(u):
    return SimpleNamespace(
        chat=SimpleNamespace(id=u.id, first_name=u.nome),
        from_user=SimpleNamespace(id=u.id, first_name=u.nome, username=u.username),
        text='',
    )


def _auth(init_data, token=None):
    api = G['api']
    if not init_data and token:
        return _auth_token(token)
    if not init_data:
        raise Erro('Faça login para continuar.', 401)
    pares = dict(parse_qsl(init_data, keep_blank_values=True))
    recebido = pares.pop('hash', '')
    dcs = '\n'.join(f'{k}={v}' for k, v in sorted(pares.items()))
    segredo = hmac.new(b'WebAppData', str(api.CredentialsChange.token_bot()).encode(), hashlib.sha256).digest()
    calc = hmac.new(segredo, dcs.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, recebido):
        raise Erro('Assinatura inválida.', 401)
    if time.time() - int(pares.get('auth_date', 0) or 0) > 86400:
        raise Erro('Sessão expirada. Feche e abra a loja de novo.', 401)
    info = json.loads(pares.get('user', '{}'))
    uid = int(info['id'])
    if api.InfoUser.verificar_ban(uid):
        raise Erro('Você está banido e não pode usar a loja.', 403)
    if not G['database'].load_user_data(uid):
        G['database'].initialize_user(uid, info.get('username'))
    return SimpleNamespace(id=uid, nome=info.get('first_name') or 'Cliente', username=info.get('username'))



# ------------------------------------------------- login pelo navegador
# Cliente fora do Telegram: informa ID/@usuário, o BOT manda um código de 6 dígitos no
# chat dele, ele digita no site e recebe um token de sessão (guardado só como hash).
_ARQ_SESSOES = 'settings/webapp_sessoes.json'
_SESSAO_DIAS = 30
_codigos = {}      # uid -> {'h': hash, 'exp': ts, 'tent': n}
_pedidos_ip = {}   # ip -> [timestamps]
_lock_sessoes = threading.Lock()


def _hash(txt):
    return hashlib.sha256(str(txt).encode()).hexdigest()


def _sessoes_ler():
    try:
        with open(_ARQ_SESSOES, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _sessoes_gravar(d):
    tmp = _ARQ_SESSOES + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f)
    os.replace(tmp, _ARQ_SESSOES)


def _auth_token(token):
    api = G['api']
    h = _hash(token)
    with _lock_sessoes:
        ses = _sessoes_ler().get(h)
    if not ses or ses['exp'] < time.time():
        raise Erro('Sessão expirada. Entre novamente.', 401)
    uid = int(ses['uid'])
    if api.InfoUser.verificar_ban(uid):
        raise Erro('Você está banido e não pode usar a loja.', 403)
    if not G['database'].load_user_data(uid):
        raise Erro('Conta não encontrada. Entre novamente.', 401)
    return SimpleNamespace(id=uid, nome=ses.get('nome') or 'Cliente', username=ses.get('username'),
                           email=ses.get('email'))


def _criar_sessao(uid, nome, username=None, email=None, dias=None):
    """Cria o token de sessão (30 dias; o painel ADM usa 10 anos). No disco fica só o hash dele."""
    token = secrets.token_urlsafe(32)
    with _lock_sessoes:
        ses = {h: v for h, v in _sessoes_ler().items() if v['exp'] > time.time()}
        ses[_hash(token)] = {'uid': uid, 'nome': nome, 'username': username, 'email': email,
                             'exp': time.time() + (dias or _SESSAO_DIAS) * 86400}
        _sessoes_gravar(ses)
    return token


def _encerrar_sessoes(uid):
    """Derruba todas as sessões abertas de uma conta (usado ao trocar/redefinir a senha)."""
    with _lock_sessoes:
        ses = _sessoes_ler()
        novo = {h: v for h, v in ses.items() if int(v.get('uid', 0)) != int(uid)}
        if len(novo) != len(ses):
            _sessoes_gravar(novo)


# ------------------------------------------------- conta com e-mail e senha
# Cliente sem Telegram: cria conta com e-mail + senha. Cada conta recebe um ID interno
# (WEB_BASE + número) que nunca colide com ID do Telegram, e passa a existir na mesma
# tabela `users` do bot — então saldo, compras, PIX e estoque são exatamente os mesmos.
WEB_BASE = 10 ** 13
_RE_EMAIL = re.compile(r'^[a-z0-9._%+\-]{1,64}@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$')
_falhas_login = {}        # email -> [timestamps de senha errada]
_hist_ip = {}             # (rota, ip) -> [timestamps]
_cod_reset = {}           # email -> {'h', 'exp', 'tent', 'ts'}
_sem_hash = threading.BoundedSemaphore(4)   # no máx. 4 scrypt ao mesmo tempo (memória)


def _eh_web(uid):
    try:
        return int(uid) >= WEB_BASE
    except Exception:
        return False


def _init_contas():
    _escrever("""CREATE TABLE IF NOT EXISTS site_contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        nome TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        criado_em TEXT,
        ultimo_login TEXT)""")
    _escrever("""CREATE TABLE IF NOT EXISTS site_perfil (
        uid INTEGER PRIMARY KEY,
        dados TEXT NOT NULL,
        atualizado_em TEXT)""")


def _escrever(sql, params=()):
    """Grava no banco do bot com a mesma trava dele. Se der erro, desfaz (rollback): sem isso, um INSERT que falha
    (ex.: e-mail repetido) deixaria a conexão com a gravação aberta e TRAVARIA o banco do bot inteiro."""
    db = G['database']
    conn = db._connect()
    with db._write_lock:
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


def _derivar(senha, salt, metodo):
    if metodo == 'scrypt':
        return hashlib.scrypt(senha.encode('utf-8'), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 300_000, dklen=32)


def _hash_senha(senha):
    """scrypt (ou PBKDF2 se o Python do servidor não tiver scrypt). Nunca guardamos a senha em texto."""
    salt = os.urandom(16)
    metodo = 'scrypt' if hasattr(hashlib, 'scrypt') else 'pbkdf2'
    with _sem_hash:
        try:
            h = _derivar(senha, salt, metodo)
        except Exception:
            metodo = 'pbkdf2'
            h = _derivar(senha, salt, metodo)
    return f'{metodo}${salt.hex()}${h.hex()}'


def _conferir_senha(senha, guardado):
    try:
        metodo, s, h = str(guardado).split('$')
        with _sem_hash:
            calc = _derivar(str(senha), bytes.fromhex(s), metodo)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


_SENHA_FALSA = None


def _limite_ip(rota, ip, maximo, janela):
    agora = time.time()
    k = (rota, ip)
    hist = [t for t in _hist_ip.get(k, []) if agora - t < janela]
    if len(hist) >= maximo:
        raise Erro('Muitas tentativas. Aguarde alguns minutos e tente de novo.', 429)
    hist.append(agora)
    _hist_ip[k] = hist
    if len(_hist_ip) > 5000:                      # faxina simples
        for kk in [x for x, v in _hist_ip.items() if not v or agora - v[-1] > 3600]:
            _hist_ip.pop(kk, None)


def _validar_email(email):
    e = str(email or '').strip().lower()
    if len(e) > 254 or not _RE_EMAIL.match(e):
        raise Erro('Digite um e-mail válido (ex.: nome@gmail.com).')
    return e


def _validar_senha(senha):
    s = str(senha or '')
    if len(s) < 6:
        raise Erro('A senha precisa ter pelo menos 6 caracteres.')
    if len(s) > 100:
        raise Erro('Senha muito longa (máximo 100 caracteres).')
    return s


def _limpar_nome(nome, email):
    n = re.sub(r'[<>&"\'`\\]', '', str(nome or '')).strip()
    n = re.sub(r'\s+', ' ', n)[:40]
    if len(n) < 2:
        n = email.split('@')[0][:20]
    return n


def _conta_por_email(email):
    conn = G['database']._connect()
    linhas = conn.execute('SELECT * FROM site_contas WHERE email=?', (email,)).fetchall()   # fetchall: não deixa leitura aberta
    return linhas[0] if linhas else None


def _criar_usuario_bot(uid, nome, email):
    """Cria o cliente na tabela de usuários do bot (sem bônus de cadastro: evita farmar bônus com e-mails falsos)."""
    db = G['database']
    if db.load_user_data(uid):
        return
    d = db.initialize_user(uid, nome)
    d.update({'banned': False, 'invite_sent': False, 'nome': nome, 'site_email': email, 'origem': 'site'})
    db.save_user_data(uid, d)


def _cadastrar(ip, nome, email, senha):
    _manutencao()
    _limite_ip('cadastro', ip, 30, 3600)
    email = _validar_email(email)
    senha = _validar_senha(senha)
    nome = _limpar_nome(nome, email)
    ph = _hash_senha(senha)
    agora = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        cid = _escrever('INSERT INTO site_contas (email, nome, senha_hash, criado_em) VALUES (?,?,?,?)',
                        (email, nome, ph, agora))
    except Exception as e:
        if 'UNIQUE' in str(e).upper():
            raise Erro('Este e-mail já tem cadastro. Toque em "Entrar" ou "Esqueci minha senha".', 409)
        raise
    uid = WEB_BASE + int(cid)
    _criar_usuario_bot(uid, nome, email)
    try:
        G['bot'].send_message(G['api'].CredentialsChange.id_dono(),
                              f'🆕 <b>NOVO CADASTRO NO SITE</b>\n👤 {nome}\n📧 <code>{email}</code>\n🆔 <code>{uid}</code>',
                              parse_mode='HTML')
    except Exception:
        pass
    return {'token': _criar_sessao(uid, nome, None, email), 'nome': nome}


def _entrar_email(ip, email, senha):
    global _SENHA_FALSA
    _limite_ip('login', ip, 60, 600)
    email = _validar_email(email) if email else ''
    agora = time.time()
    falhas = [t for t in _falhas_login.get(email, []) if agora - t < 900]
    if len(falhas) >= 8:
        raise Erro('Muitas tentativas erradas. Aguarde 15 minutos ou use "Esqueci minha senha".', 429)
    conta = _conta_por_email(email) if email else None
    if _SENHA_FALSA is None:
        _SENHA_FALSA = _hash_senha('senha-falsa-para-igualar-o-tempo')
    ok = _conferir_senha(senha, conta['senha_hash'] if conta else _SENHA_FALSA) and conta is not None
    if not ok:
        falhas.append(agora)
        _falhas_login[email] = falhas
        raise Erro('E-mail ou senha incorretos.', 401)
    _falhas_login.pop(email, None)
    uid = WEB_BASE + int(conta['id'])
    if G['api'].InfoUser.verificar_ban(uid):
        raise Erro('Você está banido e não pode usar a loja.', 403)
    _criar_usuario_bot(uid, conta['nome'], email)      # garante o cadastro no bot (ex.: banco restaurado)
    try:
        _escrever('UPDATE site_contas SET ultimo_login=? WHERE id=?', (time.strftime('%Y-%m-%d %H:%M:%S'), conta['id']))
    except Exception:
        pass
    return {'token': _criar_sessao(uid, conta['nome'], None, email), 'nome': conta['nome']}


def _definir_senha(email, nova):
    conta = _conta_por_email(email)
    if not conta:
        raise Erro('Conta não encontrada.', 404)
    ph = _hash_senha(_validar_senha(nova))
    _escrever('UPDATE site_contas SET senha_hash=? WHERE id=?', (ph, conta['id']))
    _falhas_login.pop(email, None)
    _encerrar_sessoes(WEB_BASE + int(conta['id']))
    return conta


def _exigir_senha(u, senha, msg='Senha incorreta.'):
    """Confere a senha da conta logada (ações sensíveis). Conta as tentativas erradas como no login."""
    if not getattr(u, 'email', None) or not _eh_web(u.id):
        raise Erro('Sua conta usa o Telegram; não tem senha no site.')
    agora = time.time()
    falhas = [t for t in _falhas_login.get(u.email, []) if agora - t < 900]
    if len(falhas) >= 8:
        raise Erro('Muitas tentativas erradas. Aguarde 15 minutos.', 429)
    conta = _conta_por_email(u.email)
    if not conta or not _conferir_senha(senha, conta['senha_hash']):
        falhas.append(agora)
        _falhas_login[u.email] = falhas
        raise Erro(msg, 403)
    _falhas_login.pop(u.email, None)
    return conta


def _atualizar_sessoes(uid, **campos):
    """Atualiza nome/e-mail guardados nas sessões abertas da conta."""
    with _lock_sessoes:
        ses = _sessoes_ler()
        mudou = False
        for h, v in ses.items():
            if int(v.get('uid', 0)) == int(uid):
                v.update(campos)
                mudou = True
        if mudou:
            _sessoes_gravar(ses)


def _contar_sessoes(uid):
    with _lock_sessoes:
        ses = _sessoes_ler()
    return sum(1 for v in ses.values() if int(v.get('uid', 0)) == int(uid) and v.get('exp', 0) > time.time())


def _trocar_senha(u, atual, nova):
    conta = _exigir_senha(u, atual, 'A senha atual está incorreta.')
    if str(atual) == str(nova):
        raise Erro('A nova senha precisa ser diferente da atual.')
    _definir_senha(u.email, nova)
    return {'ok': True, 'token': _criar_sessao(u.id, u.nome, None, u.email)}   # a sessão atual continua valendo


def _trocar_email(u, senha, novo):
    _exigir_senha(u, senha)
    novo = _validar_email(novo)
    if novo == u.email:
        raise Erro('Esse já é o seu e-mail atual.')
    if _conta_por_email(novo):
        raise Erro('Este e-mail já está em uso por outra conta.', 409)
    conta = _conta_por_email(u.email)
    try:
        _escrever('UPDATE site_contas SET email=? WHERE id=?', (novo, conta['id']))
    except Exception as e:
        if 'UNIQUE' in str(e).upper():
            raise Erro('Este e-mail já está em uso por outra conta.', 409)
        raise
    _user_json_set(u.id, {'site_email': novo})
    _atualizar_sessoes(u.id, email=novo)
    return {'ok': True, 'email': novo}


def _sair_outros(u):
    """Derruba todos os outros aparelhos e mantém só este (com uma sessão nova)."""
    if not _eh_web(u.id):
        raise Erro('Disponível só para contas do site.')
    _encerrar_sessoes(u.id)
    return {'ok': True, 'token': _criar_sessao(u.id, u.nome, None, getattr(u, 'email', None))}


# ---- recuperação de senha por e-mail (precisa de "smtp" em settings/webapp.json)
def _smtp():
    c = _cfg().get('smtp') or {}
    return c if c.get('host') and c.get('usuario') and c.get('senha') else None


def _enviar_email(para, assunto, corpo):
    import smtplib
    from email.message import EmailMessage
    c = _smtp()
    msg = EmailMessage()
    msg['Subject'] = assunto
    msg['From'] = c.get('remetente') or c['usuario']
    msg['To'] = para
    msg.set_content(corpo)
    porta = int(c.get('porta') or 465)
    if porta == 465:
        with smtplib.SMTP_SSL(c['host'], porta, timeout=20) as s:
            s.login(c['usuario'], c['senha'])
            s.send_message(msg)
    else:
        with smtplib.SMTP(c['host'], porta, timeout=20) as s:
            s.starttls()
            s.login(c['usuario'], c['senha'])
            s.send_message(msg)


def _esqueci_senha(ip, email):
    _limite_ip('esqueci', ip, 10, 3600)
    email = _validar_email(email)
    agora = time.time()
    atual = _cod_reset.get(email)
    if atual and agora - atual['ts'] < 60:
        raise Erro('Código já enviado. Aguarde 1 minuto para pedir outro.', 429)
    if _conta_por_email(email):                 # resposta igual exista a conta ou não (não revela quem tem cadastro)
        codigo = f'{secrets.randbelow(1000000):06d}'
        _cod_reset[email] = {'h': _hash(f'{email}:{codigo}'), 'exp': agora + 900, 'tent': 0, 'ts': agora}

        def _env():
            try:
                if not _smtp():       # sem e-mail configurado: o código vai para o admin no Telegram, que repassa ao cliente
                    G['bot'].send_message(G['api'].CredentialsChange.id_dono(),
                        f'🔑 <b>PEDIDO DE REDEFINIÇÃO DE SENHA (SITE)</b>\n📧 <code>{email}</code>\n🔢 Código: <code>{codigo}</code>\n'
                        'Valido por 15 min. Só passe o código se for o dono do e-mail. Ou use /resetsenha email novasenha.',
                        parse_mode='HTML')
                    return
                _enviar_email(email, 'RAMON STORE - código para redefinir sua senha',
                              f'Seu código para redefinir a senha é: {codigo}\n\nValido por 15 minutos.\n'
                              'Se não foi você que pediu, ignore este e-mail.')
            except Exception as e:
                print(f'[WEBAPP] falha ao enviar e-mail de recuperação: {e}')
        threading.Thread(target=_env, daemon=True).start()
    else:                                       # conta inexistente: mesma resposta e mesmo intervalo de 60s
        _cod_reset[email] = {'h': '', 'exp': 0, 'tent': 99, 'ts': agora}
    return {'ok': True, 'via': 'email' if _smtp() else 'suporte'}


def _redefinir_senha(ip, email, codigo, nova):
    _limite_ip('redefinir', ip, 20, 3600)
    email = _validar_email(email)
    c = _cod_reset.get(email)
    codigo = re.sub(r'\D', '', str(codigo or ''))
    if not c or c['exp'] < time.time() or not c['h']:
        raise Erro('Código inválido ou expirado. Peça um novo.', 400)
    c['tent'] += 1
    if c['tent'] > 5:
        _cod_reset.pop(email, None)
        raise Erro('Muitas tentativas erradas. Peça um novo código.', 429)
    if not hmac.compare_digest(c['h'], _hash(f'{email}:{codigo}')):
        raise Erro('Código incorreto.', 400)
    _validar_senha(nova)
    _cod_reset.pop(email, None)
    conta = _definir_senha(email, nova)
    return {'token': _criar_sessao(WEB_BASE + int(conta['id']), conta['nome'], None, email), 'nome': conta['nome']}


# ---- entrar com o Google (precisa de "google_client_id" em settings/webapp.json)
def _google_id():
    return str(_cfg().get('google_client_id') or '').strip()


def _google_entrar(ip, credential):
    """Confere o token do Google (Google Identity Services) e entra/cria a conta pelo e-mail verificado."""
    import urllib.request
    import urllib.parse
    cid = _google_id()
    if not cid:
        raise Erro('Login com Google ainda não está ligado.', 503)
    _limite_ip('google', ip, 40, 600)
    cred = str(credential or '')
    if not cred or len(cred) > 4096:
        raise Erro('Não foi possível entrar com o Google. Tente de novo.', 400)
    try:
        url = 'https://oauth2.googleapis.com/tokeninfo?id_token=' + urllib.parse.quote(cred, safe='')
        with urllib.request.urlopen(url, timeout=10) as r:
            info = json.loads(r.read().decode('utf-8'))
    except Exception:
        raise Erro('O Google não confirmou o login. Tente de novo.', 401)
    if info.get('aud') != cid or info.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise Erro('Login do Google inválido.', 401)
    if str(info.get('email_verified')).lower() != 'true' or float(info.get('exp') or 0) < time.time():
        raise Erro('E-mail do Google não verificado ou token expirado.', 401)
    email = _validar_email(info.get('email'))
    conta = _conta_por_email(email)
    if not conta:
        nome = _limpar_nome(info.get('name'), email)
        ph = _hash_senha(secrets.token_urlsafe(24))          # senha aleatória: só entra pelo Google (ou "Esqueci minha senha")
        agora = time.strftime('%Y-%m-%d %H:%M:%S')
        try:
            _escrever('INSERT INTO site_contas (email, nome, senha_hash, criado_em) VALUES (?,?,?,?)', (email, nome, ph, agora))
        except Exception as e:
            if 'UNIQUE' not in str(e).upper():
                raise
        conta = _conta_por_email(email)
        novo = True
    else:
        novo = False
    uid = WEB_BASE + int(conta['id'])
    if G['api'].InfoUser.verificar_ban(uid):
        raise Erro('Você está banido e não pode usar a loja.', 403)
    _criar_usuario_bot(uid, conta['nome'], email)
    try:
        _escrever('UPDATE site_contas SET ultimo_login=? WHERE id=?', (time.strftime('%Y-%m-%d %H:%M:%S'), conta['id']))
    except Exception:
        pass
    if novo:
        try:
            G['bot'].send_message(G['api'].CredentialsChange.id_dono(),
                                  f'🆕 <b>NOVO CADASTRO NO SITE (Google)</b>\n👤 {conta["nome"]}\n📧 <code>{email}</code>\n🆔 <code>{uid}</code>',
                                  parse_mode='HTML')
        except Exception:
            pass
    return {'token': _criar_sessao(uid, conta['nome'], None, email), 'nome': conta['nome']}


# ---- o bot não consegue falar com quem não tem Telegram
def _blindar_bot(bot):
    """Contas do site não têm chat no Telegram. Para elas, as chamadas do bot (enviar mensagem, editar
    a mensagem do PIX, get_chat...) viram 'não faz nada' em vez de erro. Assim TODO o fluxo existente
    (entrega, PIX, crédito de saldo, aviso ao admin) funciona igual, sem mexer nos outros arquivos."""
    if getattr(bot, '_site_blindado', False):
        return

    def _cid(a, k):
        v = a[0] if a else k.get('chat_id')
        try:
            return int(v)
        except Exception:
            return None

    def _nome_site(uid):
        try:
            d = G['database'].load_user_data(uid) or {}
            return d.get('nome') or 'Cliente', d.get('site_email') or ''
        except Exception:
            return 'Cliente', ''

    def _envolver(nome, falso):
        orig = getattr(bot, nome, None)
        if orig is None:
            return

        def f(*a, **k):
            cid = _cid(a, k)
            if cid is not None and cid >= WEB_BASE:
                return falso(cid)
            return orig(*a, **k)
        f.__name__ = nome
        setattr(bot, nome, f)

    def _msg(cid):
        return SimpleNamespace(message_id=0, chat=SimpleNamespace(id=cid), date=0, text='', caption='')

    def _chat(cid):
        nome, email = _nome_site(cid)
        return SimpleNamespace(id=cid, type='private', first_name=nome,
                               last_name=f'[SITE] {email}'.strip(), username=None)

    for m in ('send_message', 'send_photo', 'send_document', 'send_video', 'send_animation', 'send_audio',
              'send_voice', 'send_sticker', 'send_poll', 'send_contact', 'send_location', 'copy_message',
              'forward_message', 'edit_message_text', 'edit_message_caption', 'edit_message_reply_markup',
              'edit_message_media'):
        _envolver(m, _msg)
    for m in ('delete_message', 'send_chat_action', 'pin_chat_message', 'unpin_chat_message'):
        _envolver(m, lambda cid: True)
    _envolver('send_media_group', lambda cid: [])
    _envolver('get_chat', _chat)
    bot._site_blindado = True


def _comando_resetsenha(g):
    """/resetsenha email novasenha  (só admin) — redefine a senha de um cliente do site."""
    bot = g['bot']
    eh_admin = g.get('is_admin_user')

    @bot.message_handler(commands=['resetsenha'])
    def _h(message):
        try:
            if not (eh_admin and eh_admin(message.from_user.id)):
                return
            partes = (message.text or '').split()
            if len(partes) != 3:
                return bot.reply_to(message, 'Use: /resetsenha email novasenha\nEx.: /resetsenha maria@gmail.com 123456')
            email = _validar_email(partes[1])
            _definir_senha(email, partes[2])
            try:
                bot.delete_message(message.chat.id, message.message_id)   # apaga a mensagem com a senha
            except Exception:
                pass
            bot.send_message(message.chat.id, f'✅ Senha de <code>{email}</code> redefinida. A mensagem com a senha foi apagada.',
                             parse_mode='HTML')
        except Erro as e:
            bot.reply_to(message, f'❌ {e.msg}')
        except Exception as e:
            bot.reply_to(message, f'❌ Erro: {e}')


# ---- painel de admin: link PERMANENTE pedido pelo /painel no Telegram
# O link não expira e pode ser aberto quantas vezes quiser (celular, computador...). Ele é derivado
# do token do bot + ID do admin + uma "versão": nada é guardado em claro no disco. Para invalidar o
# link antigo e gerar outro, o admin manda "/painel novo". Se o admin for removido, o link morre junto.
_ARQ_LINK_ADM = 'settings/admin_links.json'
_ADM_DIAS = 3650


def _adm_versao(uid, incrementar=False):
    try:
        with open(_ARQ_LINK_ADM, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    v = int(d.get(str(uid), 1))
    if incrementar:
        v += 1
        d[str(uid)] = v
        tmp = _ARQ_LINK_ADM + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(d, f)
        os.replace(tmp, _ARQ_LINK_ADM)
    return v


def _adm_chave(uid, versao):
    seg = str(G['api'].CredentialsChange.token_bot()).encode()
    return hmac.new(seg, f'admin-link:{int(uid)}:{int(versao)}'.encode(), hashlib.sha256).hexdigest()[:40]


def _admin_entrar_chave(ip, chave):
    _limite_ip('admin_link', ip, 15, 600)
    try:
        uid_s, k = str(chave or '').split('.', 1)
        uid = int(uid_s)
    except Exception:
        raise Erro('Link inválido. Envie /painel no bot para receber o link.', 401)
    ok = hmac.compare_digest(_adm_chave(uid, _adm_versao(uid)), k)
    api = G['api']
    eh = False
    try:
        eh = api.Admin.verificar_admin(uid) or str(uid) == str(api.CredentialsChange.id_dono())
    except Exception:
        pass
    if not (ok and eh):
        raise Erro('Link inválido ou desativado. Envie /painel no bot para receber o atual.', 401)
    try:
        nome = (G['database'].load_user_data(uid) or {}).get('nome') or 'Admin'
    except Exception:
        nome = 'Admin'
    return {'token': _criar_sessao(uid, nome, None, None, dias=_ADM_DIAS), 'nome': nome}


def _admin_entrar_link(ip, codigo):
    # compatível com links antigos de uso único; novos links usam "chave"
    _limite_ip('admin_link', ip, 15, 600)
    h = _hash(str(codigo or ''))
    for k in [k for k, v in _links_painel.items() if v['exp'] < time.time()]:
        _links_painel.pop(k, None)
    v = _links_painel.pop(h, None)
    if not v or v['exp'] < time.time():
        raise Erro('Link inválido ou expirado. Envie /painel no bot para gerar outro.', 401)
    return {'token': _criar_sessao(v['uid'], v['nome'], v.get('username'), None, dias=_ADM_DIAS), 'nome': v['nome']}


_links_painel = {}     # links antigos de uso único (hash -> dados); mantido só por compatibilidade


def _comando_painel(g):
    """/painel (só admin) — o bot responde com o link permanente do painel. "/painel novo" troca o link."""
    bot = g['bot']
    eh_admin = g.get('is_admin_user')

    @bot.message_handler(commands=['painel', 'adminsite'])
    def _h(message):
        try:
            if not (eh_admin and eh_admin(message.from_user.id)):
                return
            base = url_publica()
            if not base:
                return bot.reply_to(message, '❌ Configure a "url" do site em settings/webapp.json.')
            uid = int(message.from_user.id)
            partes = (message.text or '').split()
            novo = len(partes) > 1 and partes[1].lower() in ('novo', 'trocar', 'resetar', 'revogar')
            ver = _adm_versao(uid, incrementar=novo)
            link = f'{base.rstrip("/")}/admin#k={uid}.{_adm_chave(uid, ver)}'
            aviso = ('🔄 <b>Link antigo desativado.</b> Este é o novo:\n\n' if novo else '')
            bot.send_message(message.chat.id,
                             f'{aviso}🖤 <b>Painel ADM do site</b>\n♾️ Link permanente — não expira e abre quantas vezes quiser:\n{link}\n\n'
                             '⚠️ Quem tiver este link entra no painel como você. Não compartilhe.\n'
                             'Se vazar, envie <code>/painel novo</code> para desativar este e gerar outro.',
                             parse_mode='HTML', disable_web_page_preview=True)
        except Exception as e:
            print(f'[WEBAPP] /painel falhou: {e}')


def _achar_uid(texto):
    t = str(texto or '').strip().lstrip('@')
    if not t or len(t) > 40:
        raise Erro('Informe seu ID numérico ou @usuário do Telegram.')
    if t.isdigit():
        uid = int(t)
        if uid < WEB_BASE and G['database'].load_user_data(uid):
            return uid
    else:
        try:
            conn = G['database']._connect()
            row = conn.execute('SELECT user_id FROM users WHERE lower(username)=? LIMIT 1', (t.lower(),)).fetchone()
            if row:
                return int(row['user_id'])
        except Exception as e:
            print(f'[WEBAPP] busca por username falhou: {e}')
    raise Erro('Não encontramos essa conta. Abra o bot no Telegram, envie /start e tente de novo.', 404)


def _pedir_codigo(ip, texto):
    _manutencao()
    agora = time.time()
    hist = [t for t in _pedidos_ip.get(ip, []) if agora - t < 3600]
    if len(hist) >= 8:
        raise Erro('Muitas tentativas. Aguarde um pouco.', 429)
    hist.append(agora)
    _pedidos_ip[ip] = hist
    uid = _achar_uid(texto)
    atual = _codigos.get(uid)
    if atual and atual['exp'] - 540 > agora:   # no máx. 1 código a cada 60s
        raise Erro('Código já enviado. Veja o chat do bot e aguarde 1 minuto para pedir outro.', 429)
    if G['api'].InfoUser.verificar_ban(uid):
        raise Erro('Você está banido e não pode usar a loja.', 403)
    codigo = f'{secrets.randbelow(1000000):06d}'
    try:
        G['bot'].send_message(uid, f'🔐 <b>Código de acesso ao site</b>\n\n<code>{codigo}</code>\n\nVálido por 10 minutos. '
                              'Se não foi você, ignore esta mensagem e <b>não compartilhe</b> o código com ninguém.', parse_mode='HTML')
    except Exception:
        raise Erro('Não conseguimos falar com você pelo bot. Abra o bot no Telegram, envie /start e tente de novo.', 400)
    _codigos[uid] = {'h': _hash(f'{uid}:{codigo}'), 'exp': agora + 600, 'tent': 0}
    return {'ok': True}


def _entrar(texto, codigo):
    uid = _achar_uid(texto)
    c = _codigos.get(uid)
    codigo = re.sub(r'\D', '', str(codigo or ''))
    if not c or c['exp'] < time.time():
        raise Erro('Código expirado. Peça um novo.', 400)
    c['tent'] += 1
    if c['tent'] > 5:
        _codigos.pop(uid, None)
        raise Erro('Muitas tentativas erradas. Peça um novo código.', 429)
    if not hmac.compare_digest(c['h'], _hash(f'{uid}:{codigo}')):
        raise Erro('Código incorreto.', 400)
    _codigos.pop(uid, None)
    nome, user = 'Cliente', None
    try:
        ch = G['bot'].get_chat(uid)
        nome, user = ch.first_name or 'Cliente', getattr(ch, 'username', None)
    except Exception:
        pass
    token = secrets.token_urlsafe(32)
    with _lock_sessoes:
        ses = {h: v for h, v in _sessoes_ler().items() if v['exp'] > time.time()}
        ses[_hash(token)] = {'uid': uid, 'nome': nome, 'username': user, 'exp': time.time() + _SESSAO_DIAS * 86400}
        _sessoes_gravar(ses)
    return {'token': token}


def _sair(token):
    with _lock_sessoes:
        ses = _sessoes_ler()
        if ses.pop(_hash(token), None) is not None:
            _sessoes_gravar(ses)
    return {'ok': True}


def _limitar(u, rota, intervalo=1.0):
    k = (u.id, rota)
    agora = time.time()
    if agora - _ultimo.get(k, 0) < intervalo:
        raise Erro('Calma, aguarde um instante.', 429)
    _ultimo[k] = agora


def _manutencao():
    try:
        from rl_maintenance import is_on
        if is_on():
            raise Erro('Loja em manutenção. Volte já já!', 503)
    except Erro:
        raise
    except Exception:
        pass



# ----------------------------------------------------------------- imagens
_BASE = os.path.dirname(os.path.abspath(__file__))
_ICONES = os.path.join(_BASE, 'assets', 'icones')
_CACHE_FOTOS = os.path.join(_BASE, 'webapp_cache')
_img_mem = {}


def _norm(nome):
    """'🌺PRIME VIDEO' -> 'prime video' (mesma regra do bot para achar o ícone)."""
    limpo = re.sub(r'[^\w\s+&]', ' ', str(nome or ''), flags=re.UNICODE)
    return re.sub(r'\s+', ' ', limpo).strip().lower()


def _sem_acento(t):
    t = unicodedata.normalize('NFKD', str(t))
    return ''.join(c for c in t if not unicodedata.combining(c))


_ALIAS = {'paramount': 'paramout'}           # o arquivo do bot é "paramout"
_GENERICAS = {'premium', 'padrao', 'conta', 'anuncio', 'com', 'sem', 'tela', 'extra', 'nova', 'novo', 'link',
              'adicionais', 'add', 'basica', 'debitada', 'avancado', 'individual', 'plus', 'tv', 'video'}
_idx = {'t': 0, 'arqs': []}


def _arquivos_icones():
    """Lista (chave, caminho) de assets/icones; relê a pasta a cada 60s (foto nova entra sem reiniciar)."""
    if time.time() - _idx['t'] > 60:
        arqs = []
        try:
            for fn in os.listdir(_ICONES):
                base, ext = os.path.splitext(fn)
                if ext.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
                    continue
                # nomes com acento corrompido ("padr#U95c1...") perdem os trechos estranhos
                chave = _sem_acento(re.sub(r'#U[0-9a-fA-F]{4}', '', base)).lower()
                if chave and chave != 'padrao':
                    arqs.append((chave, os.path.join(_ICONES, fn)))
        except Exception:
            pass
        _idx['arqs'], _idx['t'] = arqs, time.time()
    return _idx['arqs']


def _icone_local(nome):
    """Acha a foto do serviço em assets/icones, sem depender do nome exato:
    1) nome igual/prefixo ('hbo max com anuncio' -> hbo_max.jpg; 'disney padrao...' -> disney_padr*.jpg)
    2) mesma marca (primeira palavra) -> prefere a versão 'premium'
    Sem palavra-chave solta: foto de outra marca é pior do que nenhuma."""
    arqs = _arquivos_icones()
    if not arqs:
        return None
    t = _sem_acento(_norm(nome)).replace('+', ' + ')
    pal = [_ALIAS.get(w, w) for w in t.split() if w]
    if not pal:
        return None
    s = '_'.join(pal).replace('_+_', '+')
    # 1) prefixo (vence a chave mais longa)
    cand = [(c, p) for c, p in arqs if s.startswith(c) or s.startswith(c.rstrip('_'))]
    melhor = max(cand, key=lambda x: len(x[0])) if cand else None
    if melhor and '+' in melhor[0]:
        return melhor[1]
    if '+' in s:        # combo ('globo premium+telecine' -> globo+telecine.jpg): arquivo com todas as partes
        partes = [x.split('_')[0] for x in s.split('+') if x]
        partes = [x for x in partes if x and not x.isdigit() and x not in _GENERICAS]
        if len(partes) >= 2:
            comb = []
            for c, pth in arqs:
                toks = [y.split('_')[0] for y in c.split('+')]
                if all(any(tk == pt or tk.startswith(pt) or pt.startswith(tk) for tk in toks) for pt in partes) and len(toks) >= len(partes):
                    comb.append((c, pth))
            if comb:
                return min(comb, key=lambda x: len(x[0]))[1]
    if melhor:
        return melhor[1]
    # 2) mesma marca
    marca = pal[0]
    fam = [(c, p) for c, p in arqs if c.split('_')[0].split('+')[0] == marca]
    if fam:
        pref = [x for x in fam if 'premium' in x[0]] or fam
        return min(pref, key=lambda x: len(x[0]))[1]
    return None



_GEN_URL = {'color', 'fill', 'draw', 'stock', 'scan', 'fuse', 'rush', 'spark', 'preview', 'capture', 'comp', 'bridge',
            'animate', 'origin', 'aero', 'xd', 'fonts', 'portfolio', 'sketch', 'max'}
_neg = {}   # url -> ts da última falha (não insiste por 6h)


def _tabela_icones():
    for nome in ('modulo_servicos_estoque', 'modulo_entrega_carrinho_alertas'):
        m = sys.modules.get(nome)
        t = getattr(m, 'icones', None) if m else None
        if isinstance(t, dict) and len(t) > 5:
            return t
    return {}


def _url_icone(nome):
    """URL da tabela de ícones do bot, mas só se a MARCA bater de verdade (palavra inteira):
    'vivo tv premiere' -> 'vivo tv'; 'claro tv+premiere' -> 'claro tv' (e não 'premiere'); 'sky+ 5 adicionais' -> 'sky'."""
    tab = _tabela_icones()
    if not tab:
        return None
    pal = [w for w in re.split(r'[^a-z0-9]+', _sem_acento(_norm(nome))) if w]
    melhor, chave_melhor = None, None
    for chave, url in tab.items():
        if chave == 'padrao' or chave in _GEN_URL:
            continue
        kw = [w for w in re.split(r'[^a-z0-9]+', _sem_acento(chave)) if w]
        req = [w for w in kw if w not in ('tv', 'plus', 'play', 'go')] or kw   # 'vivo tv' casa com 'VIVO AVANÇADO'
        if not kw or not all(w in pal for w in req):
            continue
        pos = min(pal.index(w) for w in req)          # a marca costuma vir primeiro
        rank = (pos, -sum(w in pal for w in kw))
        if melhor is None or rank < melhor:
            melhor, chave_melhor = rank, url
    return chave_melhor


def _baixar_url(url):
    """Baixa uma vez e guarda em webapp_cache/. Devolve caminho ou None (e não insiste por 6h se falhar)."""
    try:
        os.makedirs(_CACHE_FOTOS, exist_ok=True)
        arq = os.path.join(_CACHE_FOTOS, 'u_' + hashlib.sha1(url.encode()).hexdigest() + '.img')
        if os.path.isfile(arq):
            return arq
        if time.time() - _neg.get(url, 0) < 21600:
            return None
        import requests
        r = requests.get(url, timeout=7, headers={'User-Agent': 'Mozilla/5.0 (Ramon-Store)'})
        ct = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if r.status_code != 200 or not ct.startswith('image/') or 'svg' in ct or not (500 < len(r.content) < 3_000_000):
            raise ValueError(f'resposta inválida ({r.status_code} {ct} {len(r.content)}b)')
        with open(arq, 'wb') as f:
            f.write(r.content)
        return arq
    except Exception as e:
        _neg[url] = time.time()
        print(f'[WEBAPP] ícone por URL falhou ({url[:70]}): {e}')
        return None



# ------------------------------------------------ foto da internet (fallback)
# Quem não tem foto própria (nem /setfoto, nem assets/icones) busca o logo da marca na internet,
# padroniza num ícone quadrado 512x512 e guarda em webapp_cache/. Funciona sozinho para produtos
# que forem abastecidos no futuro. Se nada funcionar, o site desenha um ícone 3D com o emoji.
_DOMINIOS = {
    'claro': 'claro.com.br', 'sky': 'sky.com.br', 'vivo': 'vivo.com.br', 'oi': 'oi.com.br', 'directv': 'directv.com.br',
    'unitv': 'unitv.com.br', 'viki': 'viki.com', 'record': 'recordplus.com', 'telecine': 'telecineplay.com.br',
    'globo': 'globoplay.globo.com', 'globoplay': 'globoplay.globo.com', 'premiere': 'premiere.globo.com',
    'sportv': 'sportv.globo.com', 'combate': 'combate.globo.com', 'netflix': 'netflix.com', 'prime': 'primevideo.com',
    'hbo': 'max.com', 'max': 'max.com', 'disney': 'disneyplus.com', 'paramount': 'paramountplus.com',
    'paramout': 'paramountplus.com', 'spotify': 'spotify.com', 'crunchyroll': 'crunchyroll.com', 'canva': 'canva.com',
    'youtube': 'youtube.com', 'chatgpt': 'chatgpt.com', 'gpt': 'chatgpt.com', 'zapping': 'zapping.com.br',
    'deezer': 'deezer.com', 'tidal': 'tidal.com', 'apple': 'apple.com', 'hulu': 'hulu.com', 'dazn': 'dazn.com',
    'espn': 'espn.com.br', 'peacock': 'peacocktv.com', 'discovery': 'discoveryplus.com', 'starz': 'starz.com',
    'tubi': 'tubitv.com', 'pluto': 'pluto.tv', 'xbox': 'xbox.com', 'playstation': 'playstation.com', 'steam': 'steampowered.com',
    'discord': 'discord.com', 'twitch': 'twitch.tv', 'capcut': 'capcut.com', 'adobe': 'adobe.com', 'photoshop': 'adobe.com',
    'microsoft': 'microsoft.com', 'office': 'office.com', 'duolingo': 'duolingo.com', 'tinder': 'tinder.com',
    'wattpad': 'wattpad.com', 'picsart': 'picsart.com', 'vpn': 'nordvpn.com', 'nordvpn': 'nordvpn.com',
    'funimation': 'funimation.com', 'showtime': 'sho.com', 'amazon': 'amazon.com.br', 'telegram': 'telegram.org',
}
_neg_dom = {}              # nome normalizado -> quando falhou (não tenta de novo por 3h)
_nomes_ok = {'t': 0, 'v': set()}


def _nomes_do_estoque():
    """Só busca na internet nomes que existem no estoque (evita alguém forçar downloads com /img?n=qualquer-coisa)."""
    if time.time() - _nomes_ok['t'] > 30:
        try:
            _nomes_ok['v'] = {_norm(a.get('nome')) for a in G['api'].ControleLogins.pegar_servicos() if a.get('nome')}
        except Exception:
            pass
        _nomes_ok['t'] = time.time()
    return _nomes_ok['v']


def _baixar(url, limite=3_000_000):
    try:
        import requests
        r = requests.get(url, timeout=6, headers={'User-Agent': 'Mozilla/5.0 (RLStore)'}, stream=True)
        if r.status_code != 200:
            return None
        dados = r.raw.read(limite + 1, decode_content=True)
        return dados if 0 < len(dados) <= limite else None
    except Exception:
        return None


def _padronizar(dados):
    """Bytes de qualquer logo -> PNG 512x512 (logo centralizado sobre fundo claro). None se não for imagem útil."""
    try:
        from PIL import Image
        im = Image.open(BytesIO(dados))
        im.load()
        if min(im.size) < 40:
            return None
        im = im.convert('RGBA')
        tela = Image.new('RGBA', (512, 512), (246, 246, 251, 255))
        alvo = 400
        im.thumbnail((alvo, alvo), Image.LANCZOS)
        tela.alpha_composite(im, ((512 - im.width) // 2, (512 - im.height) // 2))
        out = BytesIO()
        tela.convert('RGB').save(out, 'PNG', optimize=True)
        return out.getvalue()
    except Exception:
        return None


def _urls_candidatas(nome):
    palavras = [w for w in _sem_acento(_norm(nome)).replace('+', ' ').split() if w]
    urls, vistos = [], set()
    for w in palavras:
        d = _DOMINIOS.get(_ALIAS.get(w, w))
        if d and d not in vistos:
            vistos.add(d)
            urls.append(f'https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&url=https://{d}&size=256')
            urls.append(f'https://www.google.com/s2/favicons?domain={d}&sz=256')
            break          # a 1ª marca do nome manda ("claro tv+premiere" => Claro)
    # URLs que o próprio bot já usa (dicionário `icones`), só com correspondência exata de marca
    try:
        for modname in ('modulo_servicos_estoque', 'modulo_entrega_carrinho_alertas'):
            ic = getattr(sys.modules.get(modname), 'icones', None)
            if isinstance(ic, dict):
                alvo = ' '.join(palavras)
                for k in sorted((k for k in ic if k != 'padrao'), key=len, reverse=True):
                    if re.search(r'(^| )' + re.escape(_sem_acento(k).replace('+', ' ').strip()) + r'( |$)', alvo):
                        urls.append(ic[k])
                        break
                break
    except Exception:
        pass
    return urls


def _foto_online(nome):
    chave = _norm(nome)
    if not chave or chave not in _nomes_do_estoque():
        return None
    arq = os.path.join(_CACHE_FOTOS, 'web_' + hashlib.sha1(chave.encode()).hexdigest() + '.png')
    if os.path.isfile(arq):
        return arq
    if time.time() - _neg_dom.get(chave, 0) < 3 * 3600:
        return None
    for url in _urls_candidatas(nome):
        png = _padronizar(_baixar(url) or b'')
        if png:
            os.makedirs(_CACHE_FOTOS, exist_ok=True)
            with open(arq, 'wb') as f:
                f.write(png)
            return arq
    _neg_dom[chave] = time.time()
    return None


def _foto_customizada(nome):
    """Foto definida pelo admin com /setfoto (file_id do Telegram). Baixa uma vez e guarda em disco."""
    try:
        import fotos_produtos
        fid = fotos_produtos.obter_foto_customizada(nome)
        if not fid:
            # o bot salva com emoji no nome; tenta também sem normalizar
            alvo = _norm(nome)
            for k, v in fotos_produtos.carregar_fotos_produtos().items():
                if _norm(k) == alvo:
                    fid = v
                    break
        if not fid:
            return None
        os.makedirs(_CACHE_FOTOS, exist_ok=True)
        arq = os.path.join(_CACHE_FOTOS, hashlib.sha1(fid.encode()).hexdigest() + '.jpg')
        if not os.path.isfile(arq):
            bot = G['bot']
            info = bot.get_file(fid)
            with open(arq, 'wb') as f:
                f.write(bot.download_file(info.file_path))
        return arq
    except Exception as e:
        print(f'[WEBAPP] foto customizada falhou ({nome}): {e}')
        return None


def _icone_ramon(nome):
    """Imagens que o Ramon já usa no mini app antigo: database/miniapp_images.json -> miniapp/assets/..."""
    try:
        with open(os.path.join(_BASE, 'database', 'miniapp_images.json'), 'r', encoding='utf-8-sig') as f:
            mapa = json.load(f)
        rel = mapa.get(nome)
        if not rel:
            alvo = _norm(nome)
            for k, v in mapa.items():
                if _norm(k) == alvo:
                    rel = v
                    break
        if not rel:
            return None
        raiz = os.path.join(_BASE, 'miniapp')
        caminho = os.path.normpath(os.path.join(raiz, str(rel).lstrip('/')))
        return caminho if caminho.startswith(raiz) and os.path.isfile(caminho) else None
    except Exception:
        return None


def _imagem(nome):
    """Ordem: painel ADM -> /setfoto -> assets/icones -> URL da tabela do bot (marca exata) -> logo da marca na internet. (bytes, tipo) ou None."""
    chave = _norm(nome)
    try:
        import webapp_imagens
        ver = webapp_imagens.versao(nome)
    except Exception:
        webapp_imagens, ver = None, 0
    hit = _img_mem.get(chave)
    if hit and time.time() - hit[0] < 120 and hit[2] == ver:      # 2 min: /setfoto novo aparece logo
        return hit[1]
    # nada achou => 404 e o site desenha um ícone 3D com o emoji (o padrao.jpg do bot não entra aqui)
    fontes = (lambda: webapp_imagens.caminho(nome) if webapp_imagens else None,     # 1º: imagem enviada pelo painel ADM
              lambda: _icone_ramon(nome), lambda: _foto_customizada(nome), lambda: _icone_local(nome),
              lambda: (lambda u: _baixar_url(u) if u else None)(_url_icone(nome)),
              lambda: _foto_online(nome))
    for obter in fontes:
        caminho = obter()
        if caminho and os.path.isfile(caminho):
            with open(caminho, 'rb') as f:
                dados = f.read()
            ctype = 'image/png' if dados[:4] == b'\x89PNG' else 'image/webp' if dados[8:12] == b'WEBP' else 'image/jpeg'
            if len(_img_mem) < 300:
                _img_mem[chave] = (time.time(), (dados, ctype), ver)
            return dados, ctype
    return None


# ------------------------------------------------------------ favoritos etc.
def _favoritos(uid):
    try:
        import sistema_favoritos
        return [str(x) for x in sistema_favoritos.carregar_favoritos(uid)]
    except Exception:
        return []


def _suporte():
    try:
        return str(G['api'].CredentialsChange.SuporteInfo.link_suporte())
    except Exception:
        return ''


# ------------------------------------------------------------ perfil personalizado
_AV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp_avatars')
_RE_AVF = re.compile(r'^[a-f0-9]{24}\.jpg$')
_lock_prefs = threading.Lock()
_PREFS_PADRAO = {'nome': '', 'bio': '', 'whatsapp': '', 'banner': 0, 'acento': 0,
                 'avatar': {'tipo': 'inicial', 'emoji': '😎', 'cor': 0, 'foto': ''}}


def _prefs(uid):
    try:
        l = G['database']._connect().execute('SELECT dados FROM site_perfil WHERE uid=?', (int(uid),)).fetchall()
        d = json.loads(l[0]['dados']) if l else {}
    except Exception:
        d = {}
    out = json.loads(json.dumps(_PREFS_PADRAO))
    for k in ('nome', 'bio', 'whatsapp', 'banner', 'acento'):
        if k in d:
            out[k] = d[k]
    if isinstance(d.get('avatar'), dict):
        out['avatar'].update(d['avatar'])
    return out


def _gravar_prefs(uid, p):
    _escrever('INSERT INTO site_perfil (uid, dados, atualizado_em) VALUES (?,?,?) '
              'ON CONFLICT(uid) DO UPDATE SET dados=excluded.dados, atualizado_em=excluded.atualizado_em',
              (int(uid), json.dumps(p, ensure_ascii=False), time.strftime('%Y-%m-%d %H:%M:%S')))


def _user_json_set(uid, campos):
    """Muda campos soltos no cadastro do cliente (arquivo JSON do bot)."""
    try:
        db = G['database']
        d = db.load_user_data(uid)
        if d is None:
            return
        for k, v in campos.items():
            d[k] = v
        db.save_user_data(uid, d)
    except Exception as e:
        print(f'[WEBAPP] não consegui atualizar dados do cliente {uid}: {e}')


def _avatar_pub(p):
    a = p.get('avatar') or {}
    foto = str(a.get('foto') or '')
    ok = bool(_RE_AVF.match(foto)) and os.path.isfile(os.path.join(_AV_DIR, foto))
    tipo = a.get('tipo') if a.get('tipo') in ('foto', 'emoji', 'inicial') else 'inicial'
    if tipo == 'foto' and not ok:
        tipo = 'inicial'
    try:
        cor = int(a.get('cor') or 0)
    except Exception:
        cor = 0
    return {'tipo': tipo, 'emoji': str(a.get('emoji') or '😎'), 'cor': cor,
            'url': ('/avatar/' + foto) if ok else '', 'tem_foto': ok}


def _nome_exib(u, p=None):
    p = p or _prefs(u.id)
    return p.get('nome') or u.nome


def _apagar_foto(nome):
    if _RE_AVF.match(str(nome or '')):
        try:
            os.remove(os.path.join(_AV_DIR, nome))
        except Exception:
            pass


def _int_faixa(v, lo, hi, campo):
    try:
        n = int(v)
    except Exception:
        raise Erro(f'Valor inválido em {campo}.')
    if not (lo <= n <= hi):
        raise Erro(f'Valor inválido em {campo}.')
    return n


def _editar_perfil(u, d):
    zap_novo = nome_novo = None
    with _lock_prefs:
        p = _prefs(u.id)
        if 'nome' in d:
            n = re.sub(r'[<>&"\'`\\]', '', str(d.get('nome') or ''))
            n = re.sub(r'\s+', ' ', n).strip()[:40]
            if len(n) < 2:
                raise Erro('Digite um nome com pelo menos 2 letras.')
            p['nome'] = nome_novo = n
        if 'bio' in d:
            b = re.sub(r'[<>`\\]', '', str(d.get('bio') or ''))
            p['bio'] = re.sub(r'\s+', ' ', b).strip()[:80]
        if 'whatsapp' in d:
            w = re.sub(r'\D', '', str(d.get('whatsapp') or ''))
            if w and not (10 <= len(w) <= 13):
                raise Erro('WhatsApp inválido. Use DDD + número, ex.: (11) 91234-5678.')
            if w and len(w) <= 11:
                w = '55' + w                      # o bot guarda com o 55 na frente
            p['whatsapp'] = zap_novo = w
        if 'banner' in d:
            p['banner'] = _int_faixa(d.get('banner'), 0, 15, 'banner')
        if 'acento' in d:
            p['acento'] = _int_faixa(d.get('acento'), 0, 15, 'cor de destaque')
        av = p['avatar']
        if 'avatar_emoji' in d:
            e = str(d.get('avatar_emoji') or '')
            if not (1 <= len(e) <= 16) or re.search(r'[A-Za-z0-9<>&"\'\\\s]', e):
                raise Erro('Emoji inválido.')
            av['emoji'] = e
        if 'avatar_cor' in d:
            av['cor'] = _int_faixa(d.get('avatar_cor'), 0, 31, 'cor do avatar')
        if 'avatar_tipo' in d:
            t = d.get('avatar_tipo')
            if t not in ('foto', 'emoji', 'inicial'):
                raise Erro('Tipo de avatar inválido.')
            if t == 'foto' and not _avatar_pub(p)['tem_foto']:
                raise Erro('Envie uma foto primeiro.')
            av['tipo'] = t
        if d.get('remover_foto'):
            _apagar_foto(av.get('foto'))
            av['foto'] = ''
            if av.get('tipo') == 'foto':
                av['tipo'] = 'inicial'
        _gravar_prefs(u.id, p)
    if nome_novo:
        if _eh_web(u.id):
            conta = _conta_por_email(u.email) if getattr(u, 'email', None) else None
            if conta:
                try:
                    _escrever('UPDATE site_contas SET nome=? WHERE id=?', (nome_novo, conta['id']))
                except Exception:
                    pass
            _atualizar_sessoes(u.id, nome=nome_novo)
        _user_json_set(u.id, {'nome': nome_novo})
    if zap_novo is not None:
        _user_json_set(u.id, {'whatsapp': zap_novo or 'Não informado'})
    return _perfil(u)


def _salvar_foto(u, dataurl):
    m = re.match(r'^data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)$', str(dataurl or ''))
    if not m:
        raise Erro('Imagem inválida.')
    try:
        raw = base64.b64decode(m.group(1), validate=True)
    except Exception:
        raise Erro('Imagem inválida.')
    if len(raw) > 350_000:
        raise Erro('Imagem muito grande.', 413)
    try:
        from PIL import Image, ImageOps
        im = Image.open(BytesIO(raw))
        if im.width * im.height > 16_000_000:
            raise Erro('Imagem muito grande.', 413)
        im = ImageOps.exif_transpose(im).convert('RGB')
        im = ImageOps.fit(im, (320, 320), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, 'JPEG', quality=86, optimize=True)      # recodifica: nada do arquivo original sobrevive
    except Erro:
        raise
    except Exception:
        raise Erro('Não consegui ler essa imagem. Tente outra (JPG ou PNG).')
    os.makedirs(_AV_DIR, exist_ok=True)
    arq = secrets.token_hex(12) + '.jpg'
    with open(os.path.join(_AV_DIR, arq), 'wb') as f:
        f.write(buf.getvalue())
    with _lock_prefs:
        p = _prefs(u.id)
        _apagar_foto(p['avatar'].get('foto'))
        p['avatar'].update({'tipo': 'foto', 'foto': arq})
        _gravar_prefs(u.id, p)
    return _perfil(u)


def _vip(d):
    try:
        import sistema_cashback_vip as v
        cfg = v.carregar_config()
        if not cfg.get('ativo', True):
            return None
        gasto = float(d.get('gasto_semanal_vip', 0) or 0)
        atual, prox, falta = v.obter_nivel_vip(gasto)
        niveis = cfg.get('niveis_vip') or getattr(v, 'NIVEIS_VIP_PADRAO', {})
        proximo = None
        if prox:
            nome = next((k for k, x in niveis.items() if float(x.get('gasto_minimo', -1)) == float(prox['gasto_minimo'])), '')
            proximo = {'nome': nome, 'emoji': prox.get('emoji', ''), 'cashback': prox.get('cashback', 0),
                       'gasto_minimo': float(prox['gasto_minimo']), 'falta': round(max(0.0, float(falta)), 2)}
        reset = ''
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(str(cfg.get('data_proximo_reset')))
            if dt > datetime.now():
                reset = dt.strftime('%d/%m/%Y')
        except Exception:
            pass
        return {'atual': atual, 'proximo': proximo, 'gasto': round(gasto, 2), 'reset': reset,
                'cashback_total': round(float(d.get('cashback_total_ganho', 0) or 0), 2)}
    except Exception:
        return None


def _indicacoes(u, d):
    try:
        db, api = G['database'], G['api']
        if not db.verificar_sistema_afiliados_ativo():
            return {'ativo': False}
        return {'ativo': True, 'link': f'https://t.me/{api.CredentialsChange.user_bot()}?start={u.id}',
                'indicados': len(d.get('afiliados', []) or []),
                'ganho': round(float(d.get('total_ganho_indicacoes', 0) or 0), 2),
                'valor': round(float(db.get_valor_por_indicacao()), 2)}
    except Exception:
        return {'ativo': False}


def _soma(lista, chave='valor'):
    t = 0.0
    for x in lista or []:
        try:
            t += float(x.get(chave) or 0)
        except Exception:
            pass
    return round(t, 2)


def _perfil(u):
    import whatsapp_api
    api, db = G['api'], G['database']
    d = db.load_user_data(u.id) or {}
    p = _prefs(u.id)
    todas = d.get('compras', []) or []
    pags = d.get('pagamentos', []) or []
    compras = []
    for c in reversed(todas[-60:]):
        compras.append({'nome': str(c.get('servico') or c.get('produto') or ''), 'valor': c.get('valor'),
                        'email': c.get('email'), 'senha': c.get('senha'), 'data': str(c.get('data') or '')})
    pagamentos = [{'valor': x.get('valor'), 'data': str(x.get('data') or '')} for x in reversed(pags[-30:])]
    try:
        pontos = float(d.get('pontos_indicado', 0) or 0)
    except Exception:
        pontos = 0
    site = _eh_web(u.id)
    desde = str(d.get('data_registro') or '')
    if site and getattr(u, 'email', None):
        try:
            c = _conta_por_email(u.email)
            desde = str(c['criado_em'] or desde) if c else desde
        except Exception:
            pass
    zap = re.sub(r'\D', '', str(p.get('whatsapp') or d.get('whatsapp') or ''))
    return {'id': u.id, 'nome': _nome_exib(u, p), 'username': u.username, 'email': getattr(u, 'email', None),
            'site': site, 'bio': p.get('bio') or '', 'whatsapp': zap,
            'vinculo_whatsapp': whatsapp_api.profile_code(u.id),
            'avatar': _avatar_pub(p), 'banner': int(p.get('banner') or 0), 'acento': int(p.get('acento') or 0),
            'membro_desde': desde,
            'saldo': round(float(api.InfoUser.saldo(u.id)), 2),
            'total_compras': len(todas), 'total_pagos': len(pags), 'total_gasto': _soma(todas),
            'total_recarregado': _soma(pags),
            'gifts': round(float(d.get('gift_redeemed', 0) or 0), 2), 'pontos': pontos,
            'vip': _vip(d), 'indicacoes': _indicacoes(u, d),
            'sessoes': _contar_sessoes(u.id) if site else 0,
            'compras': compras, 'pagamentos': pagamentos}


def _favoritar(u, nome):
    import sistema_favoritos
    nome = str(nome or '').strip()
    if not nome or len(nome) > 120:
        raise Erro('Produto inválido.')
    favs = sistema_favoritos.carregar_favoritos(u.id)
    if nome in favs:
        favs.remove(nome)
        ligado = False
    else:
        if nome not in {g['nome'] for g in _catalogo()}:
            raise Erro('Produto indisponível.', 404)
        favs.append(nome)
        ligado = True
    sistema_favoritos.salvar_favoritos(u.id, favs)
    return {'ligado': ligado, 'favoritos': favs}


def _gift(u, codigo):
    api = G['api']
    _manutencao()
    codigo = str(codigo or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{4,32}', codigo):
        raise Erro('Código inválido.')
    with _LOCK_COMPRA:
        ok, valor = api.GiftCard.validar_gift(codigo)
        if not ok or valor <= 0:
            raise Erro('Gift card inválido ou já usado.', 404)
        # apaga primeiro: se dois pedidos chegarem juntos, só um consegue apagar (e creditar)
        if not api.GiftCard.del_gift(codigo):
            raise Erro('Gift card inválido ou já usado.', 404)
        api.InfoUser.add_saldo(u.id, valor)
        try:
            api.MudancaHistorico.mudar_gift_resgatado(u.id, valor)
        except Exception:
            pass
    saldo = round(float(api.InfoUser.saldo(u.id)), 2)
    try:
        G['bot'].send_message(u.id, f'✅ <b>Gift Card resgatado no site!</b>\n💰 +R$ {valor:.2f}\nNovo saldo: <b>R$ {saldo:.2f}</b>',
                              parse_mode='HTML')
        G['bot'].send_message(api.CredentialsChange.id_dono(),
                              f'🎁 <b>GIFT RESGATADO (SITE)</b>\n🆔 <code>{u.id}</code>\n💰 R$ {valor:.2f}\n🎟 <code>{codigo}</code>',
                              parse_mode='HTML')
    except Exception:
        pass
    return {'valor': round(float(valor), 2), 'saldo': saldo}


def _ranking():
    try:
        itens = G['database'].top_produtos_site(8, 30)
    except Exception:
        itens = []
    return {'produtos': [{'nome': i['produto'], 'vendas': i['vendas'], 'img': _img_url(i['produto'])} for i in itens]}


def _nomes_com_foto_customizada():
    try:
        import fotos_produtos
        return {_norm(k) for k in fotos_produtos.carregar_fotos_produtos()}
    except Exception:
        return set()


def _img_url(nome):
    u = '/img?n=' + quote(str(nome), safe='')
    try:
        import webapp_imagens
        v = webapp_imagens.versao(nome)
        if v:
            u += '&v=' + str(v)      # troca pelo painel ADM: muda a URL e o celular baixa a imagem nova
    except Exception:
        pass
    return u


# --------------------------------------------------------------- catálogo
def _oferta(nome):
    try:
        import Oferta_relampago
        return Oferta_relampago._achar_oferta(nome)
    except Exception:
        return None


def _catalogo_global():
    """Catálogo Player para o site; nunca expõe a chave da integração."""
    import player_api
    import player_categories
    if not player_api.is_player_enabled():
        return []
    saida = []
    for categoria, produtos in player_categories.group_products(player_api.get_products() or []).items():
        for produto in produtos:
            estoque = max(0, int(produto.get('stock') or 0))
            if not estoque or not produto.get('id'):
                continue
            nome = '🌐 ' + str(produto.get('name') or 'Conta Global')
            preco = player_api.get_sale_price(produto.get('price', 0))
            if preco <= 0:
                continue
            saida.append({'nome': nome, 'preco': preco, 'valor': preco,
                          'estoque': estoque, 'descricao': player_api.product_description(produto),
                          'duracao': 0, 'img': _img_url(produto.get('name') or nome),
                          'categoria': 'global', 'subcategoria': categoria, 'promo': False,
                          'player_id': str(produto['id'])})
    return saida


def _reservar_global(g, uid):
    import player_api
    pedido = player_api.create_order(g['player_id'], quantity=1, user_telegram_id=uid)
    if not isinstance(pedido, dict) or pedido.get('success') is False:
        return None
    dados = pedido.get('data', pedido)
    if not isinstance(dados, dict):
        return None
    credenciais = dados.get('credentials') or {}
    if not isinstance(credenciais, dict):
        credenciais = {'acesso': credenciais}
    acesso = '\n'.join(f'{k}: {v}' for k, v in credenciais.items()
                       if k not in ('password', 'senha') and v is not None)
    senha = str(credenciais.get('password') or credenciais.get('senha') or '')
    descricao = g['descricao']
    if dados.get('id'):
        descricao += '\nPedido: ' + str(dados['id'])
    if not acesso and not senha:
        acesso = 'Pedido recebido. Consulte o suporte com o número do pedido.'
    return (g['nome'], g['preco'], acesso, senha, descricao, 0)


def _catalogo():
    """Um item por serviço: preço do 1º login do estoque (igual ao bot), com oferta relâmpago."""
    # Quando o administrador conectou a API central, ela passa a ser a fonte de
    # catálogo/estoque. A key fica apenas no servidor (integracao_estoque.py).
    import integracao_estoque as ie
    remoto = ie.catalogo()
    if remoto is not None:
        for p in remoto:
            p['img'] = _img_url(p['nome'])
            p['categoria'] = 'tela' if 'tela' in p['nome'].lower() else 'conta'
            p['promo'] = False
        remoto.sort(key=lambda x: x['nome'].lower())
        return remoto + _catalogo_global()
    grupos = {}
    custom = _nomes_com_foto_customizada()
    for a in G['api'].ControleLogins.pegar_servicos():
        nome = a.get('nome')
        if not nome:
            continue
        g = grupos.get(nome)
        if not g:
            g = grupos[nome] = {
                'nome': nome,
                'valor': float(a.get('valor') or 0),
                'descricao': str(a.get('descricao') or '').replace('\n', ' ')[:300],
                'duracao': int(a.get('duracao') or 30),
                'estoque': 0,
                'img': _img_url(nome),
                'categoria': 'tela' if 'tela' in nome.lower() else 'conta',
            }
        g['estoque'] += 1
    saida = []
    for g in grupos.values():
        preco = g['valor']
        of = _oferta(g['nome'])
        if of:
            preco = float(of['preco_promocional'])
            g['limite'] = int(of.get('limite_quantidade', 0) or 0)
            g['fim'] = str(of.get('fim_promocao') or '')
        g['preco'] = round(preco, 2)
        g['promo'] = preco < g['valor']
        saida.append(g)
    saida.sort(key=lambda x: x['nome'].lower())
    return saida + _catalogo_global()


def _loja(u):
    _p = _prefs(u.id)
    return {
        'saldo': round(float(G['api'].InfoUser.saldo(u.id)), 2),
        'nome': _nome_exib(u, _p),
        'avatar': _avatar_pub(_p), 'acento': int(_p.get('acento') or 0), 'banner': int(_p.get('banner') or 0),
        'produtos': _catalogo(),
        'favoritos': _favoritos(u.id),
        'suporte': _suporte(),
        'site': _eh_web(u.id),
        'email': getattr(u, 'email', None),
    }


# ----------------------------------------------------------------- compra
_LOCK_SALDO = threading.Lock()


def _debitar(uid, valor):
    """Tira o saldo só se houver o suficiente (o tirar_saldo do Ramon não confere nem devolve resultado)."""
    api = G['api']
    with _LOCK_SALDO:
        if round(float(api.InfoUser.saldo(uid)), 2) + 0.001 < float(valor):
            return False
        api.InfoUser.tirar_saldo(uid, valor)
        return True


def _comprar(u, itens):
    api = G['api']
    _manutencao()
    if not isinstance(itens, list) or not itens or len(itens) > 30:
        raise Erro('Carrinho vazio.')
    with _LOCK_COMPRA:
        cat = {g['nome']: g for g in _catalogo()}
        plano, total = [], 0.0
        for it in itens:
            nome, qtd = it.get('nome'), int(it.get('qtd', 0))
            g = cat.get(nome)
            if not g:
                raise Erro(f'{nome} esgotou.', 409)
            if qtd < 1 or qtd > 50:
                raise Erro('Quantidade inválida.')
            if qtd > g['estoque']:
                raise Erro(f'Só temos {g["estoque"]} de {nome}.', 409)
            if abs(float(it.get('preco', -1)) - g['preco']) > 0.001:
                raise Erro(f'O preço de {nome} mudou para R$ {g["preco"]:.2f}. Atualize a loja.', 409)
            if g.get('limite') and qtd > g['limite']:
                raise Erro(f'Oferta de {nome}: máximo {g["limite"]} por vez.')
            plano.append((g, qtd))
            total += g['preco'] * qtd
        total = round(total, 2)
        saldo = round(float(api.InfoUser.saldo(u.id)), 2)
        if saldo < total:
            raise Erro(f'Saldo insuficiente. Faltam R$ {total - saldo:.2f}.', 402)

        entregues, aviso, msg = [], '', _fake_msg(u)
        for g, qtd in plano:
            for _ in range(qtd):
                if not _debitar(u.id, g['preco']):
                    aviso = 'Saldo insuficiente para concluir. Parte do pedido foi entregue.'
                    break
                if g.get('player_id'):
                    res = _reservar_global(g, u.id)
                else:
                    try:
                        import integracao_estoque as ie
                        venda_id = f'web-{u.id}-{int(time.time() * 1000)}-{secrets.token_hex(4)}'
                        acesso_remoto = ie.reservar(g['nome'], u.id, venda_id)
                        res = (acesso_remoto.get('nome', g['nome']), acesso_remoto.get('valor', g['preco']),
                               acesso_remoto.get('email', ''), acesso_remoto.get('senha', ''),
                               acesso_remoto.get('descricao', ''), acesso_remoto.get('duracao', 30))
                    except ie.ErroIntegracao as e:
                        # Se a integração não estiver ligada, preserva o funcionamento atual.
                        if ie.estado()['conectada']:
                            api.InfoUser.add_saldo(u.id, g['preco'])
                            aviso = e.msg
                            break
                        res = api.ControleLogins.pegar_primeiro_disponivel(g['nome'])
                if not res:
                    api.InfoUser.add_saldo(u.id, g['preco'])  # estorna
                    aviso = f'{g["nome"]} esgotou durante a compra. O valor foi devolvido ao saldo.'
                    break
                nome, _v, email, senha, desc, dur = res
                duracao = int(dur or 0) if g.get('player_id') else int(dur or 30)
                try:
                    # Mesma entrega do bot: mensagem no chat, histórico, aviso de venda, etc.
                    G['entregar'](msg, nome, g['preco'], email, senha, desc or '', duracao)
                except Exception:
                    print(f'[WEBAPP] erro em entregar() uid={u.id}:\n{traceback.format_exc()}')
                entregues.append({'nome': nome, 'email': email, 'senha': senha,
                                  'descricao': str(desc or ''), 'duracao': duracao, 'valor': g['preco']})
            if aviso:
                break
        if entregues:
            try:
                total_ent = round(sum(e['valor'] for e in entregues), 2)
                linhas = '\n'.join(f'• {e["nome"]} — R$ {e["valor"]:.2f}' for e in entregues[:15])
                quem = getattr(u, 'nome', '') or str(u.id)
                if getattr(u, 'email', None):
                    quem += f' [SITE] {u.email}'
                G['bot'].send_message(api.CredentialsChange.id_dono(),
                                      f'🛒 <b>COMPRA FEITA NO SITE</b>\n👤 {quem}\n🆔 <code>{u.id}</code>\n{linhas}\n💰 Total: <b>R$ {total_ent:.2f}</b>',
                                      parse_mode='HTML')
            except Exception:
                pass
        return {'entregues': entregues, 'aviso': aviso,
                'saldo': round(float(api.InfoUser.saldo(u.id)), 2), 'produtos': _catalogo()}


# -------------------------------------------------------------------- PIX
def _gerar_pix(u, valor):
    api, bot = G['api'], G['bot']
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    _manutencao()
    valor = round(float(valor), 2)
    minimo = float(api.CredentialsChange.InfoPix.deposito_minimo_pix())
    maximo = float(api.CredentialsChange.InfoPix.deposito_maximo_pix())
    if not (minimo <= valor <= maximo):
        raise Erro(f'Digite um valor entre R$ {minimo:.2f} e R$ {maximo:.2f}.')
    msg = _fake_msg(u)
    try:
        r = G['gerar_pix_com_failover'](valor, msg)  # mesmo failover entre gateways do bot
    except G['PixDuplicadoError']:
        raise Erro('Você acabou de gerar um PIX desse valor. Aguarde alguns segundos.', 429)
    except Exception as e:
        print(f'[WEBAPP] PIX falhou uid={u.id}: {e}')
        try:
            bot.send_message(api.CredentialsChange.id_dono(),
                             f'🚨 <b>PIX falhou no SITE</b>\nUsuário: <code>{u.id}</code>\nValor: R$ {valor:.2f}\n{str(e)[:400]}',
                             parse_mode='HTML')
        except Exception:
            pass
        raise Erro('Pagamentos indisponíveis no momento. Tente novamente em alguns minutos.', 503)

    gw, id_pag, copia = r['gateway'], r['id_pag'], r['pix_copia_cola']
    try:
        from config_pagamentos import calcular_taxa_pix
        taxa = float(calcular_taxa_pix(valor))
    except Exception:
        taxa = 0.0
    total = round(valor + taxa, 2)

    # O PIX também vai para o chat do bot: a verificação já existente credita o saldo,
    # atualiza essa mensagem e avisa o admin — igual ao /pix.
    try:
        expira = api.CredentialsChange.InfoPix.expiracao() if gw == 'misticpay' else 15
        legenda = api.Textos.pix_automatico(msg, copia, expira, id_pag, f'{valor:.2f}')
    except Exception:
        legenda = f'💸 <b>PIX de R$ {total:.2f}</b>\n\n<code>{copia}</code>'
    if taxa > 0:
        legenda += f'\n\n⚠️ Valor total do PIX: <b>R$ {total:.2f}</b> (taxa do intermediador R$ {taxa:.2f}).'
    sent = bot.send_photo(
        chat_id=u.id, photo=BytesIO(r['qr_bytes']), caption=legenda, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏰ Aguardando Pagamento...', callback_data='aguardando')]]))

    verif = G.get('verificar_pagamento_' + gw)
    if verif:
        threading.Thread(target=verif, args=(u.id, id_pag, valor, sent.message_id), daemon=True).start()
    try:
        bot.send_message(api.CredentialsChange.id_dono(),
                         f'💸 <b>PIX GERADO (SITE)</b> ({gw})\n🆔 <code>{u.id}</code>\n💰 R$ {valor:.2f}\n🧾 <code>{id_pag}</code>',
                         parse_mode='HTML')
    except Exception:
        pass
    return {'id_pag': str(id_pag), 'copia': copia, 'qr': base64.b64encode(r['qr_bytes']).decode(),
            'valor': valor, 'total': total}


def _status_pix(u, id_pag):
    pago = bool(G['check_pagamento_ja_processado'](str(id_pag), u.id))
    return {'pago': pago, 'saldo': round(float(G['api'].InfoUser.saldo(u.id)), 2)}


# ------------------------------------------------------------------- HTTP
class _H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _resp(self, status, corpo, ctype='application/json; charset=utf-8', cache='no-store'):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        import whatsapp_api
        if whatsapp_api.handle(self, _catalogo):
            return
        p = self.path.split('?')[0]
        if _rota_antiga_get(p):
            return _api_antiga.Handler.do_GET(self)
        if p in ('/', '/index.html'):
            try:
                with open(os.path.join(_PASTA, 'index.html'), 'rb') as f:
                    return self._resp(200, f.read().replace(b'__RL_VERSAO__', _versao_site().encode()), 'text/html; charset=utf-8')
            except Exception:
                return self._resp(500, {'erro': 'index.html não encontrado'})
        if p == '/versao.json':
            return self._resp(200, {'v': _versao_site()})
        if p in ('/manifest.webmanifest', '/sw.js') or p.startswith('/pwa/'):
            _tipos = {'.webmanifest': 'application/manifest+json; charset=utf-8',
                      '.js': 'application/javascript; charset=utf-8', '.png': 'image/png'}
            nome = os.path.basename(p)
            ext = os.path.splitext(nome)[1]
            if ext not in _tipos or not re.match(r'^[A-Za-z0-9._-]+$', nome):
                return self._resp(404, {'erro': 'não encontrado'})
            try:
                with open(os.path.join(_PASTA, 'pwa', nome), 'rb') as f:
                    return self._resp(200, f.read(), _tipos[ext],
                                      cache='no-cache' if ext != '.png' else 'public, max-age=86400')
            except Exception:
                return self._resp(404, {'erro': 'não encontrado'})
        if p == '/img':
            nome = (parse_qs(self.path.partition('?')[2]).get('n') or [''])[0][:150]
            r = _imagem(nome)
            if not r:
                return self._resp(404, {'erro': 'sem imagem'})
            return self._resp(200, r[0], r[1], cache='public, max-age=600')
        if p.startswith('/avatar/'):
            arq = p[len('/avatar/'):]
            if not _RE_AVF.match(arq):
                return self._resp(404, {'erro': 'sem imagem'})
            try:
                with open(os.path.join(_AV_DIR, arq), 'rb') as f:
                    return self._resp(200, f.read(), 'image/jpeg', cache='public, max-age=31536000, immutable')
            except Exception:
                return self._resp(404, {'erro': 'sem imagem'})
        if p in ('/admin', '/admin/'):
            try:
                with open(os.path.join(_PASTA, 'admin.html'), 'rb') as f:
                    return self._resp(200, f.read(), 'text/html; charset=utf-8')
            except Exception:
                return self._resp(404, {'erro': 'admin.html não encontrado'})
        if p == '/api/config':
            return self._resp(200, {'google': _google_id()})
        if p == '/health':
            return self._resp(200, {'ok': True})
        return self._resp(404, {'erro': 'não encontrado'})

    def do_POST(self):
        import whatsapp_api
        if whatsapp_api.handle(self, _catalogo):
            return
        if _api_antiga is not None and self.path.split('?')[0] in _ROTAS_ANTIGAS_POST:
            return _api_antiga.Handler.do_POST(self)
        try:
            n = int(self.headers.get('Content-Length') or 0)
            rota = self.path.split('?')[0]
            if n > (750_000 if rota == '/api/admin/imagens/definir' else 450_000 if rota == '/api/perfil/foto' else 20000):
                raise Erro('Pedido grande demais.', 413)
            d = json.loads(self.rfile.read(n) or b'{}')
            ip = (self.headers.get('X-Forwarded-For') or self.client_address[0]).split(',')[-1].strip()
            if rota == '/api/login/codigo':
                return self._resp(200, _pedir_codigo(ip, d.get('telegram')))
            if rota == '/api/login/entrar':
                return self._resp(200, _entrar(d.get('telegram'), d.get('codigo')))
            if rota == '/api/conta/cadastrar':
                return self._resp(200, _cadastrar(ip, d.get('nome'), d.get('email'), d.get('senha')))
            if rota == '/api/conta/entrar':
                return self._resp(200, _entrar_email(ip, d.get('email'), d.get('senha')))
            if rota == '/api/conta/google':
                return self._resp(200, _google_entrar(ip, d.get('credential')))
            if rota == '/api/conta/esqueci':
                return self._resp(200, _esqueci_senha(ip, d.get('email')))
            if rota == '/api/conta/redefinir':
                return self._resp(200, _redefinir_senha(ip, d.get('email'), d.get('codigo'), d.get('senha')))
            if rota == '/api/logout':
                return self._resp(200, _sair(d.get('token') or ''))
            if rota == '/api/admin/entrar_link':
                if d.get('chave'):
                    return self._resp(200, _admin_entrar_chave(ip, d.get('chave')))
                return self._resp(200, _admin_entrar_link(ip, d.get('codigo')))
            u = _auth(d.get('initData'), d.get('token'))
            if rota.startswith('/api/admin/'):
                import admin_painel
                if not admin_painel.eh_admin(G, _cfg(), u):
                    raise Erro('Acesso restrito a administradores.', 403)
                try:
                    return self._resp(200, admin_painel.tratar(G, _cfg(), WEB_BASE, rota, d, u))
                except admin_painel.ErroAdmin as e:
                    raise Erro(e.msg, e.status)
            if rota == '/api/loja':
                out = _loja(u)
            elif rota == '/api/comprar':
                _limitar(u, rota)
                out = _comprar(u, d.get('itens'))
            elif rota == '/api/pix':
                _limitar(u, rota, 2.0)
                out = _gerar_pix(u, d.get('valor'))
            elif rota == '/api/pix/status':
                out = _status_pix(u, d.get('id_pag'))
            elif rota == '/api/perfil':
                out = _perfil(u)
            elif rota == '/api/perfil/editar':
                _limitar(u, rota, 0.8)
                out = _editar_perfil(u, d)
            elif rota == '/api/perfil/foto':
                _limitar(u, rota, 3.0)
                out = _salvar_foto(u, d.get('imagem'))
            elif rota == '/api/conta/trocar_email':
                _limitar(u, rota, 2.0)
                out = _trocar_email(u, d.get('senha'), d.get('email'))
            elif rota == '/api/conta/sair_outros':
                _limitar(u, rota, 2.0)
                out = _sair_outros(u)
            elif rota == '/api/favorito':
                _limitar(u, rota, 0.4)
                out = _favoritar(u, d.get('nome'))
            elif rota == '/api/gift':
                _limitar(u, rota, 3.0)
                out = _gift(u, d.get('codigo'))
            elif rota == '/api/ranking':
                out = _ranking()
            elif rota.startswith('/api/ent/'):
                import webapp_entretenimento as went
                _iv = went.intervalo(rota)
                if _iv:
                    _limitar(u, rota, _iv)
                try:
                    out = went.tratar(rota, d, _catalogo)
                except went.ErroEnt as e:
                    raise Erro(e.msg, e.status)
            elif rota == '/api/conta/trocar_senha':
                _limitar(u, rota, 2.0)
                out = _trocar_senha(u, d.get('atual'), d.get('nova'))
            else:
                raise Erro('Rota inexistente.', 404)
            self._resp(200, out)
        except Erro as e:
            self._resp(e.status, {'erro': e.msg})
        except Exception:
            print(f'[WEBAPP] erro:\n{traceback.format_exc()}')
            self._resp(500, {'erro': 'Erro interno. Tente novamente.'})


# -------------------------------------------------- rotas antigas (api_catalogo.py)
# O api_catalogo.py não sobe mais sozinho (o site agora é este webapp.py, na porta 80),
# mas o bot de CÓDIGOS (/api/user/<id>, /api/acessos, /api/produtos) e os bots filhos
# (/api/stock...) ainda dependem das rotas dele. Elas são atendidas aqui pelo próprio
# api_catalogo.py; se ele faltar, o site segue normal e só essas rotas ficam fora.
_ROTAS_ANTIGAS_POST = ('/api/stock/reserve', '/api/stock/add')
try:
    import api_catalogo as _api_antiga
    for _nome in ('_responder_json', '_autorizado', '_autorizado_codigos',
                  '_responder_api_codigos', '_ler_json'):
        setattr(_H, _nome, getattr(_api_antiga.Handler, _nome))
except Exception:
    _api_antiga = None
    print(f'[WEBAPP] rotas antigas do api_catalogo.py fora do ar:\n{traceback.format_exc()}')


def _rota_antiga_get(p):
    return _api_antiga is not None and (
        p in ('/api/acessos', '/api/produtos', '/api/stock', '/api/stock/summary')
        or re.fullmatch(r'/api/user/\d+(/exists)?', p) is not None)


def iniciar(g):
    """Chamado no final do bot.py com globals(): sobe o site numa thread do próprio bot."""
    G.update(
        api=g['api'], bot=g['bot'], database=g['database'],
        entregar=g['entregar'],
        gerar_pix_com_failover=g['gerar_pix_com_failover'], PixDuplicadoError=g['PixDuplicadoError'],
        check_pagamento_ja_processado=g['check_pagamento_ja_processado'] if 'check_pagamento_ja_processado' in g
        else __import__('database').check_pagamento_ja_processado,
    )
    try:
        _init_contas()
        _blindar_bot(G['bot'])
        try:
            import eventos_admin
            eventos_admin.instalar(G['bot'], G['api'])
        except Exception as e:
            print(f'[WEBAPP] sininho do ADM não iniciou: {e}')
        _comando_resetsenha(g)
        _comando_painel(g)
    except Exception as e:
        print(f'[WEBAPP] contas por e-mail não iniciaram: {e}\n{traceback.format_exc()}')
    for gw in ('promissepay', 'misticpay', 'mercadopago', 'pushinpay'):
        if 'verificar_pagamento_' + gw in g:
            G['verificar_pagamento_' + gw] = g['verificar_pagamento_' + gw]
    porta = int(os.environ.get('PORT') or _cfg().get('porta') or 8080)
    ThreadingHTTPServer.request_queue_size = 128      # aguenta vários acessos ao mesmo tempo (padrão é 5)
    srv = ThreadingHTTPServer(('0.0.0.0', porta), _H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True, name='webapp').start()
    print(f'[WEBAPP] Site no ar na porta {porta} (URL do botão: {url_publica() or "não configurada"})')
