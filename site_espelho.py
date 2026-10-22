# -*- coding: utf-8 -*-
"""
site_espelho.py  —  banco SQLite do SITE e do PAINEL do Ramon.

O bot do Ramon guarda cada cliente em database/users/<id>.json. O site e o painel
(webapp.py / admin_painel.py) trabalham com SQL (listar clientes, vendas, pagamentos,
dashboard...). Este módulo cria um ESPELHO desses JSONs em database/site_espelho.db:

  * NÃO substitui nada: os JSONs continuam sendo a fonte de verdade do bot.
  * Se o espelho for apagado, ele é refeito sozinho na próxima vez que o bot ligar.
  * Guarda também as contas por e-mail do site (site_contas) e o perfil (site_perfil),
    que só existem no site.

Como se mantém atualizado:
  1) database.save_user_data() chama sincronizar_usuario() a cada gravação;
  2) uma thread confere os arquivos a cada 5 minutos (pega o que algum código gravou direto).
"""
import os
import re
import json
import sqlite3
import threading
import time
from datetime import datetime

DB_DIR = "database"
DB_FILE = os.path.join(DB_DIR, "site_espelho.db")
USERS_DIR = os.path.join(DB_DIR, "users")

_write_lock = threading.RLock()
_local = threading.local()
_pronto = False
_status = {"importando": False, "total": 0, "feitos": 0, "ultimo": None}

_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4}).*?(\d{2}:\d{2}:\d{2})")


# ------------------------------------------------------------------ conexão
def conectar():
    """Conexão SQLite por thread (reaproveitada)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        _local.conn = conn
    return conn


def _add_column_if_missing(conn, table, column, coltype):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def iniciar_esquema():
    conn = conectar()
    with _write_lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                banned TEXT DEFAULT 'False',
                saldo REAL DEFAULT 0.0,
                total_pagos REAL DEFAULT 0.0,
                total_compras INTEGER DEFAULT 0,
                total_ganho_indicacoes REAL DEFAULT 0.0,
                indicado_por INTEGER,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_saldo ON users(saldo);
            CREATE INDEX IF NOT EXISTS idx_users_total_pagos ON users(total_pagos);

            CREATE TABLE IF NOT EXISTS pagamentos (
                id_pagamento TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                valor REAL NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pagamentos_user ON pagamentos(user_id);
            CREATE INDEX IF NOT EXISTS idx_pagamentos_data ON pagamentos(data);

            CREATE TABLE IF NOT EXISTS compras (
                rowid_ai INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                produto TEXT,
                data TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_compras_user ON compras(user_id);
            CREATE INDEX IF NOT EXISTS idx_compras_data ON compras(data);
            CREATE INDEX IF NOT EXISTS idx_compras_produto ON compras(produto);

            CREATE TABLE IF NOT EXISTS movimentacoes_saldo (
                rowid_ai INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor REAL NOT NULL,
                saldo_anterior REAL,
                saldo_novo REAL,
                admin_id INTEGER,
                motivo TEXT,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_movsaldo_user ON movimentacoes_saldo(user_id);

            CREATE TABLE IF NOT EXISTS espelho_meta (
                user_id INTEGER PRIMARY KEY,
                mtime REAL
            );

            -- o Ramon não tem tickets: tabelas vazias só para a aba do painel não dar erro
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT, user_id INTEGER, nome TEXT,
                username TEXT, categoria TEXT, status TEXT, criado_em TEXT, atualizado_em TEXT
            );
            CREATE TABLE IF NOT EXISTS ticket_mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, remetente TEXT,
                autor_nome TEXT, tipo TEXT, conteudo TEXT, criado_em TEXT, data TEXT
            );
            """
        )
        _add_column_if_missing(conn, "compras", "valor", "REAL")
        _add_column_if_missing(conn, "compras", "email", "TEXT")
        _add_column_if_missing(conn, "compras", "senha", "TEXT")
        _add_column_if_missing(conn, "compras", "data_raw", "TEXT")
        _add_column_if_missing(conn, "pagamentos", "data_raw", "TEXT")
        conn.commit()


# ------------------------------------------------------------------ datas
def _parse_date_safe(date_str):
    if not date_str:
        return None
    m = _DATE_RE.search(str(date_str))
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _to_iso(date_str):
    dt = _parse_date_safe(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(date_str) if date_str else datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _num(v, padrao=0.0):
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return padrao


# ------------------------------------------------------------------ sincronização
def _sync_compras(conn, user_id, compras):
    """Insere só o 'rabo' novo da lista (compras só crescem por append)."""
    if not compras:
        return
    row = conn.execute("SELECT COUNT(*) AS n FROM compras WHERE user_id = ?", (user_id,)).fetchone()
    ja = row["n"] if row else 0
    if ja > len(compras):  # lista encolheu (apagaram histórico): refaz esse usuário
        conn.execute("DELETE FROM compras WHERE user_id = ?", (user_id,))
        ja = 0
    for c in compras[ja:]:
        if not isinstance(c, dict):
            continue
        data_raw = c.get("data")
        conn.execute(
            "INSERT INTO compras (user_id, produto, valor, email, senha, data, data_raw) VALUES (?,?,?,?,?,?,?)",
            (user_id, c.get("servico") or c.get("produto"), _num(c.get("valor")),
             c.get("email"), c.get("senha"), _to_iso(data_raw), data_raw))


def _sync_pagamentos(conn, user_id, pagamentos):
    if not pagamentos:
        return
    row = conn.execute("SELECT COUNT(*) AS n FROM pagamentos WHERE user_id = ?", (user_id,)).fetchone()
    ja = row["n"] if row else 0
    for p in pagamentos[ja:]:
        if not isinstance(p, dict):
            continue
        idp = p.get("id_pagamento") or p.get("id")
        if not idp:
            continue
        data_raw = p.get("data")
        conn.execute(
            "INSERT OR IGNORE INTO pagamentos (id_pagamento, user_id, valor, data, data_raw) VALUES (?,?,?,?,?)",
            (str(idp), user_id, _num(p.get("valor")), _to_iso(data_raw), data_raw))


def _gravar_usuario(conn, user_id, d):
    _sync_compras(conn, user_id, d.get("compras") or [])
    _sync_pagamentos(conn, user_id, d.get("pagamentos") or [])
    slim = {k: v for k, v in d.items() if k not in ("compras", "pagamentos")}
    conn.execute(
        """INSERT INTO users (user_id, username, banned, saldo, total_pagos, total_compras,
                              total_ganho_indicacoes, indicado_por, data)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             username=excluded.username, banned=excluded.banned, saldo=excluded.saldo,
             total_pagos=excluded.total_pagos, total_compras=excluded.total_compras,
             total_ganho_indicacoes=excluded.total_ganho_indicacoes,
             indicado_por=excluded.indicado_por, data=excluded.data""",
        (user_id,
         str(d.get("username") or d.get("first_name") or f"User{user_id}"),
         str(d.get("banned", "False")),
         _num(d.get("saldo")), _num(d.get("total_pagos")),
         int(_num(d.get("total_compras"), len(d.get("compras") or []))),
         _num(d.get("total_ganho_indicacoes")),
         d.get("afiliado_por") if isinstance(d.get("afiliado_por"), int) else d.get("indicado_por"),
         json.dumps(slim, ensure_ascii=False)))


def sincronizar_usuario(user_id, user_data, mtime=None):
    """Chamado por database.save_user_data() a cada gravação. Nunca levanta erro."""
    try:
        uid = int(user_id)
        conn = conectar()
        with _write_lock:
            _gravar_usuario(conn, uid, user_data or {})
            if mtime is None:
                try:
                    mtime = os.path.getmtime(os.path.join(USERS_DIR, f"{uid}.json"))
                except Exception:
                    mtime = time.time()
            conn.execute("INSERT OR REPLACE INTO espelho_meta (user_id, mtime) VALUES (?,?)", (uid, mtime))
            conn.commit()
    except Exception as e:
        print(f"[ESPELHO] falha ao sincronizar {user_id}: {e}")


def importar_tudo():
    """Lê database/users/*.json e põe no espelho só o que é novo/alterado (compara a data do arquivo)."""
    if _status["importando"] or not os.path.isdir(USERS_DIR):
        return
    _status["importando"] = True
    try:
        conn = conectar()
        meta = {r["user_id"]: r["mtime"] for r in conn.execute("SELECT user_id, mtime FROM espelho_meta")}
        arquivos = []
        with os.scandir(USERS_DIR) as it:
            for e in it:
                if e.name.endswith(".json") and e.name[:-5].isdigit():
                    mt = e.stat().st_mtime
                    uid = int(e.name[:-5])
                    if meta.get(uid) is None or mt > meta[uid] + 0.001:
                        arquivos.append((uid, e.path, mt))
        _status["total"], _status["feitos"] = len(arquivos), 0
        for i, (uid, caminho, mt) in enumerate(arquivos, 1):
            try:
                with open(caminho, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    with _write_lock:
                        _gravar_usuario(conn, uid, d)
                        conn.execute("INSERT OR REPLACE INTO espelho_meta (user_id, mtime) VALUES (?,?)", (uid, mt))
                        if i % 200 == 0:
                            conn.commit()
            except Exception as e:
                print(f"[ESPELHO] pulei {caminho}: {e}")
            _status["feitos"] = i
        with _write_lock:
            conn.commit()
        _status["ultimo"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if arquivos:
            print(f"[ESPELHO] {len(arquivos)} cliente(s) sincronizado(s) para o site/painel.")
    except Exception as e:
        print(f"[ESPELHO] importação falhou: {e}")
    finally:
        _status["importando"] = False


def _laco():
    importar_tudo()
    while True:
        time.sleep(300)
        importar_tudo()


def iniciar():
    """Cria o esquema e liga a thread de sincronização (uma vez)."""
    global _pronto
    if _pronto:
        return
    iniciar_esquema()
    _pronto = True
    threading.Thread(target=_laco, daemon=True, name="espelho").start()


# ------------------------------------------------------------------ funções que o site/painel esperam em `database`
def get_all_user_ids():
    ids = []
    try:
        with os.scandir(USERS_DIR) as it:
            for e in it:
                if e.name.endswith(".json") and e.name[:-5].isdigit():
                    ids.append(int(e.name[:-5]))
    except Exception:
        pass
    return ids


def check_pagamento_ja_processado(id_pagamento, user_id=None):
    """True se esse pagamento já foi creditado. Com user_id confere só o arquivo do cliente (rápido)."""
    idp = str(id_pagamento)
    if user_id is not None:
        try:
            with open(os.path.join(USERS_DIR, f"{int(user_id)}.json"), "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            return any(str(p.get("id_pagamento")) == idp for p in (d.get("pagamentos") or []) if isinstance(p, dict))
        except Exception:
            return False
    try:
        r = conectar().execute("SELECT 1 FROM pagamentos WHERE id_pagamento=? LIMIT 1", (idp,)).fetchone()
        return bool(r)
    except Exception:
        return False


def registrar_movimentacao_saldo(user_id, tipo, valor, saldo_anterior, saldo_novo, admin_id=None, motivo=None):
    conn = conectar()
    with _write_lock:
        conn.execute(
            """INSERT INTO movimentacoes_saldo
               (user_id, tipo, valor, saldo_anterior, saldo_novo, admin_id, motivo, data)
               VALUES (?,?,?,?,?,?,?,?)""",
            (int(user_id), tipo, float(valor), float(saldo_anterior or 0.0), float(saldo_novo or 0.0),
             admin_id, motivo, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()


def buscar_uid_por_username(username):
    """@usuario -> id do Telegram (procura no espelho)."""
    try:
        r = conectar().execute("SELECT user_id FROM users WHERE lower(username)=? LIMIT 1",
                               (str(username).lstrip("@").lower(),)).fetchone()
        return int(r["user_id"]) if r else None
    except Exception:
        return None


def top_produtos(top_n=8, days=30):
    """Mais vendidos nos últimos N dias: [{'produto', 'vendas'}]."""
    try:
        desde = datetime.fromtimestamp(time.time() - days * 86400).strftime("%Y-%m-%d %H:%M:%S")
        rows = conectar().execute(
            "SELECT produto, COUNT(*) AS vendas FROM compras WHERE data >= ? AND produto IS NOT NULL AND produto != '' "
            "GROUP BY produto ORDER BY vendas DESC LIMIT ?", (desde, int(top_n))).fetchall()
        return [{'produto': r['produto'], 'vendas': int(r['vendas'])} for r in rows]
    except Exception:
        return []


def get_top_products_last_30_days(top_n=10, days=30):
    """Mais vendidos dos últimos dias (lê o espelho; o do database.py antigo não entende as datas do Ramon)."""
    try:
        corte = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - int(days) * 86400))
        rows = conectar().execute(
            "SELECT produto, COUNT(*) AS vendas FROM compras WHERE data >= ? AND produto IS NOT NULL AND produto != '' "
            "GROUP BY produto ORDER BY vendas DESC LIMIT ?", (corte, int(top_n))).fetchall()
        return [{"produto": r["produto"], "vendas": int(r["vendas"])} for r in rows]
    except Exception:
        return []
