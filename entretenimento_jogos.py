# =============================================================================
# entretenimento_jogos.py — ⚽ JOGOS COMPLETO (placar, agenda, países, tabela,
#                            onde assistir, meus times e avisos)
# -----------------------------------------------------------------------------
# Substitui a parte de jogos do entretenimento_midia.py (que agora só delega
# para este arquivo). Fonte dos dados: ESPN (pública, sem chave).
#
# O QUE O CLIENTE VÊ  (Entretenimento -> ⚽ JOGOS DO BRASIL E DO MUNDO)
#   🔴 Ao vivo · ⭐ Principais · 🇧🇷 Brasil · 🌍 Mundo · 🌐 Todos
#   🗺️ Por país/campeonato (Brasil, Inglaterra, Espanha, Itália, Alemanha...)
#   📅 Navegação de dias (3 dias atrás até 7 dias à frente) — horário de Brasília
#   🔢 Toque no número do jogo -> detalhe: estádio, fase, gols, cartões,
#      onde passa, 🔔 avisar, ⭐ seguir time
#   📊 Classificação (tabela) de cada campeonato
#   ⭐ Meus times: próximos jogos dos times que o cliente segue
#   🔔 Aviso no privado 15 min antes do jogo e o resultado final
#   📺 Onde assistir: guia de apps/canais e lista por campeonato
#
# ONDE PASSA: a ESPN não informa os canais do Brasil. O texto por campeonato
# fica em database/entretenimento_config.json -> "jogos_transmissao"
# (slug -> texto) e o guia de apps em "jogos_apps". Direitos mudam: edite à mão.
# =============================================================================
import os
import re
import json
import html
import time
import threading
import unicodedata
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, wait

import pytz
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TZ = pytz.timezone('America/Sao_Paulo')
ARQ_USUARIOS = os.path.join('database', 'entretenimento_jogos_usuarios.json')

DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
OFF_MIN, OFF_MAX = -3, 7
POR_PAGINA = 12
MAX_TIMES = 10
MAX_AVISOS = 20

ING = '\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F'   # 🏴 Inglaterra
ESC = '\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F'   # 🏴 Escócia


# ----------------------------- CAMPEONATOS ------------------------------------
def _L(slug, nome, pais, flag, grupo='mundo', top=False, cont=False, reg=''):
    return {'slug': slug, 'nome': nome, 'pais': pais, 'bandeira': flag, 'grupo': grupo,
            'destaque': top, 'cont': cont, 'reg': reg}


_BR = ('Brasil', '🇧🇷')
_SUL = ('América do Sul', '🌎')
_EUR = ('Europa (UEFA)', '🇪🇺')
_SEL = ('Seleções e Mundiais', '🌍')

LIGAS_PADRAO = [
    # ---- Brasil ----
    _L('bra.1', 'Brasileirão Série A', *_BR, grupo='br', top=True, reg='sul'),
    _L('bra.2', 'Brasileirão Série B', *_BR, grupo='br', reg='sul'),
    _L('bra.3', 'Brasileirão Série C', *_BR, grupo='br', reg='sul'),
    _L('bra.copa_do_brazil', 'Copa do Brasil', *_BR, grupo='br', top=True, reg='sul'),
    _L('bra.camp.paulista', 'Campeonato Paulista', *_BR, grupo='br', reg='sul'),
    _L('bra.camp.carioca', 'Campeonato Carioca', *_BR, grupo='br', reg='sul'),
    _L('bra.camp.mineiro', 'Campeonato Mineiro', *_BR, grupo='br', reg='sul'),
    _L('bra.camp.gaucho', 'Campeonato Gaúcho', *_BR, grupo='br', reg='sul'),
    _L('bra.copa_do_nordeste', 'Copa do Nordeste', *_BR, grupo='br', reg='sul'),
    # ---- América do Sul (continentais) ----
    _L('conmebol.libertadores', 'Libertadores', *_SUL, grupo='br', top=True, cont=True, reg='sul'),
    _L('conmebol.sudamericana', 'Sul-Americana', *_SUL, grupo='br', top=True, cont=True, reg='sul'),
    _L('conmebol.recopa', 'Recopa Sul-Americana', *_SUL, grupo='br', cont=True, reg='sul'),
    # ---- Europa (continentais) ----
    _L('uefa.champions', 'Champions League', *_EUR, top=True, cont=True, reg='eu'),
    _L('uefa.europa', 'Europa League', *_EUR, cont=True, reg='eu'),
    _L('uefa.europa.conf', 'Conference League', *_EUR, cont=True, reg='eu'),
    _L('uefa.nations', 'Liga das Nações UEFA', *_EUR),
    # ---- Seleções e mundiais ----
    _L('fifa.world', 'Copa do Mundo', *_SEL, top=True),
    _L('fifa.cwc', 'Mundial de Clubes', *_SEL),
    _L('fifa.worldq.conmebol', 'Eliminatórias Sul-Americanas', *_SEL),
    _L('fifa.worldq.uefa', 'Eliminatórias Europeias', *_SEL),
    _L('fifa.friendly', 'Amistosos de Seleções', *_SEL),
    _L('uefa.euro', 'Eurocopa', *_SEL),
    _L('conmebol.america', 'Copa América', *_SEL),
    _L('concacaf.gold', 'Copa Ouro', *_SEL),
    # ---- Inglaterra ----
    _L('eng.1', 'Premier League', 'Inglaterra', ING, top=True, reg='eu'),
    _L('eng.2', 'Championship', 'Inglaterra', ING, reg='eu'),
    _L('eng.fa', 'FA Cup', 'Inglaterra', ING, reg='eu'),
    _L('eng.league_cup', 'Copa da Liga (Carabao)', 'Inglaterra', ING, reg='eu'),
    # ---- Espanha ----
    _L('esp.1', 'La Liga', 'Espanha', '🇪🇸', top=True, reg='eu'),
    _L('esp.2', 'La Liga 2', 'Espanha', '🇪🇸', reg='eu'),
    _L('esp.copa_del_rey', 'Copa del Rey', 'Espanha', '🇪🇸', reg='eu'),
    # ---- Itália ----
    _L('ita.1', 'Serie A (Itália)', 'Itália', '🇮🇹', top=True, reg='eu'),
    _L('ita.2', 'Serie B (Itália)', 'Itália', '🇮🇹', reg='eu'),
    _L('ita.coppa_italia', 'Copa da Itália', 'Itália', '🇮🇹', reg='eu'),
    # ---- Alemanha ----
    _L('ger.1', 'Bundesliga', 'Alemanha', '🇩🇪', top=True, reg='eu'),
    _L('ger.2', '2. Bundesliga', 'Alemanha', '🇩🇪', reg='eu'),
    _L('ger.dfb_pokal', 'Copa da Alemanha', 'Alemanha', '🇩🇪', reg='eu'),
    # ---- França ----
    _L('fra.1', 'Ligue 1', 'França', '🇫🇷', top=True, reg='eu'),
    _L('fra.2', 'Ligue 2', 'França', '🇫🇷', reg='eu'),
    _L('fra.coupe_de_france', 'Copa da França', 'França', '🇫🇷', reg='eu'),
    # ---- Outros europeus ----
    _L('por.1', 'Liga Portugal', 'Portugal', '🇵🇹', reg='eu'),
    _L('ned.1', 'Eredivisie', 'Holanda', '🇳🇱', reg='eu'),
    _L('tur.1', 'Süper Lig', 'Turquia', '🇹🇷', reg='eu'),
    _L('sco.1', 'Premiership (Escócia)', 'Escócia', ESC, reg='eu'),
    _L('bel.1', 'Pro League', 'Bélgica', '🇧🇪', reg='eu'),
    # ---- América do Sul (ligas nacionais) ----
    _L('arg.1', 'Liga Argentina', 'Argentina', '🇦🇷', reg='sul'),
    _L('col.1', 'Liga Colombiana', 'Colômbia', '🇨🇴', reg='sul'),
    _L('uru.1', 'Liga Uruguaia', 'Uruguai', '🇺🇾', reg='sul'),
    _L('chi.1', 'Liga Chilena', 'Chile', '🇨🇱', reg='sul'),
    _L('par.1', 'Liga Paraguaia', 'Paraguai', '🇵🇾', reg='sul'),
    _L('ecu.1', 'Liga Equatoriana', 'Equador', '🇪🇨', reg='sul'),
    _L('per.1', 'Liga Peruana', 'Peru', '🇵🇪', reg='sul'),
    # ---- Resto do mundo ----
    _L('usa.1', 'MLS', 'Estados Unidos', '🇺🇸'),
    _L('mex.1', 'Liga MX', 'México', '🇲🇽'),
    _L('ksa.1', 'Liga Saudita', 'Arábia Saudita', '🇸🇦'),
    _L('jpn.1', 'J1 League', 'Japão', '🇯🇵'),
    _L('aus.1', 'A-League', 'Austrália', '🇦🇺'),
]

# Conferido na web em 09/10/2026 (temporada 2026/27). Direitos mudam: edite no config.
TRANSMISSAO_PADRAO = {
    'bra.1': 'Globo, Record e CazéTV (grátis) · SporTV, Premiere e Prime Video',
    'bra.copa_do_brazil': 'Globo, SporTV e Prime Video',
    'bra.copa_do_nordeste': 'SBT/TV regional e SportyNet',
    'conmebol.libertadores': 'Globo e ge tv (grátis) · ESPN/Disney+ e Paramount+',
    'conmebol.sudamericana': 'SBT (1 jogo/rodada, grátis) · ESPN/Disney+ e Paramount+',
    'uefa.champions': 'HBO Max (todos os jogos) · TNT Sports (31 jogos grátis no YouTube)',
    'uefa.europa': 'CazéTV (YouTube)',
    'eng.1': 'ESPN e Disney+ (todos os jogos) · CazéTV (1 por rodada, grátis)',
    'esp.1': 'CazéTV (YouTube) · SportyNet (2 por rodada)',
    'ita.1': 'ESPN e Disney+ · CazéTV e SportyNet (jogos selecionados)',
    'ger.1': 'SporTV, Xsports, CazéTV, GOAT e Jovem Pan (varia por jogo)',
    'fra.1': 'CazéTV e Xsports (3 jogos/rodada na TV aberta)',
    'por.1': 'ESPN e Disney+',
    'usa.1': 'Apple TV',
    'ksa.1': 'Canal GOAT (jogos selecionados)',
}

APPS_PADRAO = [
    {'k': 'globo', 'nome': 'TV Globo / Globoplay', 'emoji': '📺', 'tipo': 'TV aberta · grátis',
     'texto': 'Brasileirão (jogos por praça), Copa do Brasil e Libertadores. O Globoplay mostra a Globo ao vivo no celular/TV.'},
    {'k': 'ge', 'nome': 'ge tv', 'emoji': '🟢', 'tipo': 'YouTube · grátis',
     'texto': 'Canal esportivo da Globo no YouTube/ge.globo: jogos selecionados (ex.: Libertadores) e programas.'},
    {'k': 'sportv', 'nome': 'SporTV', 'emoji': '📡', 'tipo': 'TV por assinatura',
     'texto': 'Brasileirão, Copa do Brasil e Bundesliga. Também aparece no Globoplay conforme o pacote.'},
    {'k': 'premiere', 'nome': 'Premiere', 'emoji': '🎟️', 'tipo': 'Assinatura / pay-per-view',
     'texto': 'A maior parte dos jogos de cada rodada do Brasileirão (quase todos, menos o exclusivo de outros players).'},
    {'k': 'record', 'nome': 'Record / Record+', 'emoji': '📺', 'tipo': 'TV aberta · grátis',
     'texto': '1 jogo por rodada do Brasileirão, junto com a CazéTV.'},
    {'k': 'caze', 'nome': 'CazéTV', 'emoji': '▶️', 'tipo': 'YouTube · grátis',
     'texto': '1 jogo/rodada do Brasileirão, La Liga, Premier League (1/rodada), Europa League, Ligue 1, Bundesliga e jogos de Serie A.'},
    {'k': 'prime', 'nome': 'Prime Video', 'emoji': '🅿️', 'tipo': 'Assinatura Prime',
     'texto': '1 jogo exclusivo por rodada do Brasileirão e jogos da Copa do Brasil.'},
    {'k': 'espn', 'nome': 'ESPN + Disney+', 'emoji': '🔴', 'tipo': 'TV paga / streaming',
     'texto': 'Premier League (todos os 380 jogos no Disney+), Serie A, Liga Portugal, Libertadores e Sul-Americana. Precisa de plano com ESPN no Disney+.'},
    {'k': 'paramount', 'nome': 'Paramount+', 'emoji': '🔵', 'tipo': 'Streaming',
     'texto': 'Metade dos jogos da Libertadores e da Sul-Americana (contrato vai até 2026).'},
    {'k': 'hbo', 'nome': 'HBO Max', 'emoji': '🟣', 'tipo': 'Streaming',
     'texto': 'Champions League: todos os jogos da temporada.'},
    {'k': 'tnt', 'nome': 'TNT Sports (YouTube)', 'emoji': '🟠', 'tipo': 'TV paga + YouTube grátis',
     'texto': 'Champions League: 31 jogos abertos no YouTube em 2026/27 (um por terça e um por quarta na fase de liga).'},
    {'k': 'sbt', 'nome': 'SBT', 'emoji': '📺', 'tipo': 'TV aberta · grátis',
     'texto': '1 jogo da Sul-Americana por rodada (2026 é o último ano do contrato).'},
    {'k': 'alt', 'nome': 'Canais alternativos', 'emoji': '🛰️', 'tipo': 'Xsports · SportyNet · GOAT · N Sports',
     'texto': 'Ligue 1 e Bundesliga (Xsports), jogos de La Liga/Serie A (SportyNet), Liga Saudita (GOAT) e ligas menores.'},
    {'k': 'apple', 'nome': 'Apple TV', 'emoji': '🍎', 'tipo': 'Assinatura',
     'texto': 'MLS (futebol dos EUA, onde joga o Messi).'},
]

CONFIG_JOGOS = {
    'jogos_ligas': LIGAS_PADRAO,
    'jogos_canais': TRANSMISSAO_PADRAO,          # slug -> "onde passa" (edite à mão)
    'jogos_apps': APPS_PADRAO,
    'jogos_canais_nota': 'Informações conferidas em 09/10/2026. Os direitos mudam: confirme na programação.',
    'jogos_aviso_min': 15,
}

# ----------------------------- ESTADO ----------------------------------------
_lock = threading.RLock()
_ulock = threading.RLock()
_mem = {}           # chave -> {"ts", "data"}
_idx = {}           # (slug, id) -> {"ts", "jogo"}
_falhas = {}        # chave -> epoch da última falha
_locks_chave = {}   # chave -> Lock (uma busca por vez)
_inexistente = set()
_range_ok = None    # None = ainda não sabemos | True | False (ESPN recusou intervalo de datas)
_ent = None
_bot = None
_ultimo_erro = ''
_iniciou_thread = False


# ----------------------------- UTIL ------------------------------------------
def _agora():
    return datetime.now(TZ)


def _esc(v):
    return html.escape(str(v if v is not None else ''), quote=False)


def _dt_sp(iso):
    try:
        return datetime.fromisoformat(str(iso).replace('Z', '+00:00')).astimezone(TZ)
    except Exception:
        return None


def _fmt_dia(d):
    return f"{DIAS_SEMANA[d.weekday()]} {d.strftime('%d/%m')}"


def _rotulo_off(off):
    return {0: 'HOJE', 1: 'AMANHÃ', -1: 'ONTEM'}.get(off, '')


def _ligas():
    try:
        ligas = _ent._config().get('jogos_ligas') or LIGAS_PADRAO
        if not all(isinstance(l, dict) and 'slug' in l and 'pais' in l for l in ligas):
            return LIGAS_PADRAO               # lista do formato antigo salva no config: usa a nova
        return ligas
    except Exception:
        return LIGAS_PADRAO


def _paises():
    """[(nome, bandeira)] na ordem em que aparecem no config."""
    vistos, out = set(), []
    for l in _ligas():
        p = l.get('pais') or 'Outros'
        if p not in vistos:
            vistos.add(p)
            out.append((p, l.get('bandeira') or '🏆'))
    return out


def _tv(slug):
    try:
        return (_ent._config().get('jogos_canais', {}) or {}).get(slug, '').strip()
    except Exception:
        return ''


def _toast(call, texto=''):
    try:
        _bot.answer_callback_query(call.id, texto)
    except Exception:
        pass


def _tela_erro(call, mensagem, tentar_cb, voltar_cb='ent_jogos'):
    texto = f'😕 <b>{mensagem}</b>\n\n<i>Toque em tentar de novo daqui a instantes.</i>'
    try:
        if _ent._is_admin(call.from_user.id):
            texto += f'\n\n🛠️ <b>Só o admin vê:</b>\n<code>{_esc(_ultimo_erro or "sem detalhe")[:300]}</code>'
    except Exception:
        pass
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔄 TENTAR DE NOVO', callback_data=tentar_cb))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data=voltar_cb))
    _ent._mostrar(call, texto, m)


# ----------------------------- CACHE -----------------------------------------
def _cache(chave, ttl, buscar):
    """Dado em cache se válido; se a busca falhar devolve o antigo (melhor velho do que nada).
    Depois de uma falha, espera 90 s antes de tentar de novo (não martela a ESPN)."""
    global _ultimo_erro
    agora = time.time()
    with _lock:
        item = _mem.get(chave)
    if item and agora - item['ts'] < ttl:
        return item['data']
    if not item and agora - _falhas.get(chave, 0) < 90:
        return None
    with _locks_chave.setdefault(chave, threading.Lock()):
        with _lock:                                   # outro pedido pode ter acabado de buscar
            novo = _mem.get(chave)
        if novo and time.time() - novo['ts'] < ttl:
            return novo['data']
        try:
            dados = buscar()
        except Exception as e:
            _ultimo_erro = f'{type(e).__name__}: {e}'
            print(f'[entretenimento_jogos] falha em {chave}: {_ultimo_erro}')
            _falhas[chave] = time.time()
            return item['data'] if item else None
        _falhas.pop(chave, None)
        with _lock:
            _mem[chave] = {'ts': time.time(), 'data': dados}
        return dados


def _invalidar(slugs, idade_min=30):
    """🔄 ATUALIZAR: descarta o cache dos campeonatos (se tiver mais de 30 s, para ninguém martelar)."""
    agora = time.time()
    with _lock:
        for k in list(_mem):
            if k.startswith('jg:') and k.split(':')[1] in slugs and agora - _mem[k]['ts'] > idade_min:
                _mem.pop(k, None)
    for k in list(_falhas):
        _falhas.pop(k, None)


# ----------------------------- ESPN ------------------------------------------
def _get(slug, caminho, params=None, v2=False):
    base = 'https://site.api.espn.com/apis/v2' if v2 else 'https://site.api.espn.com/apis/site/v2'
    return requests.get(f'{base}/sports/soccer/{slug}/{caminho}', params=params or {},
                        timeout=7, headers={'User-Agent': 'Mozilla/5.0'})


def _estado_texto(tp, st):
    nome = (tp.get('name') or '').upper()
    estado = tp.get('state')
    if 'POSTPONED' in nome:
        return 'ADIADO'
    if 'CANCEL' in nome:
        return 'CANCELADO'
    if 'SUSPEND' in nome or 'DELAY' in nome or 'ABANDON' in nome:
        return 'PARALISADO'
    if estado == 'in':
        if 'HALFTIME' in nome:
            return 'INTERVALO'
        if 'SHOOTOUT' in nome:
            return 'PÊNALTIS'
        if 'EXTRA' in nome:
            rel = (st.get('displayClock') or '').strip()
            return (rel + ' (prorrog.)') if rel else 'PRORROGAÇÃO'
        return (st.get('displayClock') or '').strip() or 'AO VIVO'
    if estado == 'post':
        return 'FIM'
    return ''


def _placar(v):
    if isinstance(v, dict):
        v = v.get('displayValue', v.get('value'))
    if v is None or v == '':
        return ''
    try:
        return str(int(float(v)))
    except Exception:
        return str(v)


def _nome_time(c):
    t = c.get('team') or {}
    return t.get('shortDisplayName') or t.get('displayName') or t.get('name') or '?'


def _parse_detalhes(comp, casa_id, fora_id):
    out = []
    for d in comp.get('details') or []:
        tipo = ((d.get('type') or {}).get('text') or '').lower()
        if d.get('redCard') or 'red card' in tipo:
            ic = '🟥'
        elif d.get('yellowCard') or 'yellow' in tipo:
            ic = '🟨'
        elif d.get('scoringPlay') or 'goal' in tipo:
            ic = '⚽'
        else:
            continue
        nomes = [a.get('displayName') or a.get('shortName') or '' for a in (d.get('athletesInvolved') or [])[:1]]
        tid = str((d.get('team') or {}).get('id') or '')
        extra = ' (contra)' if 'own' in tipo else (' (pên.)' if 'penalty' in tipo and ic == '⚽' else '')
        out.append({'ic': ic, 'min': (d.get('clock') or {}).get('displayValue') or '',
                    'nome': (nomes[0] if nomes else '') + extra,
                    'lado': 'c' if tid and tid == casa_id else ('f' if tid and tid == fora_id else '')})
    return out


def _parse_eventos(j, slug):
    jogos = []
    for ev in j.get('events') or []:
        comp = (ev.get('competitions') or [{}])[0]
        st = ev.get('status') or comp.get('status') or {}
        tp = st.get('type') or {}
        times = comp.get('competitors') or []
        casa = next((c for c in times if c.get('homeAway') == 'home'), None)
        fora = next((c for c in times if c.get('homeAway') == 'away'), None)
        if not casa or not fora:
            continue
        casa_id = str((casa.get('team') or {}).get('id') or '')
        fora_id = str((fora.get('team') or {}).get('id') or '')
        venue = comp.get('venue') or {}
        notas = comp.get('notes') or []
        fase = (notas[0].get('headline') if notas and isinstance(notas[0], dict) else '') or ''
        pen = ''
        if casa.get('shootoutScore') is not None and fora.get('shootoutScore') is not None:
            pen = f"{_placar(casa.get('shootoutScore'))} x {_placar(fora.get('shootoutScore'))}"
        jogos.append({
            'id': str(ev.get('id')), 'slug': slug, 'inicio': ev.get('date'),
            'estado': tp.get('state') or 'pre', 'rotulo': _estado_texto(tp, st),
            'casa': _nome_time(casa), 'fora': _nome_time(fora),
            'casa_full': (casa.get('team') or {}).get('displayName') or '',
            'fora_full': (fora.get('team') or {}).get('displayName') or '',
            'casa_id': casa_id, 'fora_id': fora_id,
            'pc': _placar(casa.get('score')), 'pf': _placar(fora.get('score')), 'pen': pen,
            'estadio': venue.get('fullName') or '',
            'cidade': ((venue.get('address') or {}).get('city')) or '',
            'fase': fase,
            'detalhes': _parse_detalhes(comp, casa_id, fora_id),
        })
    return jogos


def _buscar_intervalo(slug, d1, d2):
    """Jogos entre d1 e d2. Tenta intervalo de datas; se a ESPN recusar (400) vai dia a dia."""
    global _range_ok
    if slug in _inexistente:
        return []
    vistos, jogos = set(), []

    def juntar(j):
        for x in _parse_eventos(j, slug):
            if x['id'] not in vistos:
                vistos.add(x['id'])
                jogos.append(x)

    recusou_intervalo = False
    if _range_ok is not False:
        r = _get(slug, 'scoreboard', {'dates': f"{d1:%Y%m%d}-{d2:%Y%m%d}", 'limit': 400})
        if r.status_code == 404:
            _inexistente.add(slug)
            return []
        if r.status_code == 200:
            _range_ok = True
            juntar(r.json())
            return jogos
        if r.status_code != 400:
            raise RuntimeError(f'ESPN HTTP {r.status_code} ({slug})')
        recusou_intervalo = True
    d = d1
    while d <= d2:
        r = _get(slug, 'scoreboard', {'dates': f'{d:%Y%m%d}', 'limit': 400})
        if r.status_code == 404:
            _inexistente.add(slug)
            return []
        if r.status_code != 200:
            raise RuntimeError(f'ESPN HTTP {r.status_code} ({slug} {d:%Y%m%d}) {r.text[:100]!r}')
        juntar(r.json())
        d += timedelta(days=1)
    if recusou_intervalo:
        _range_ok = False
    return jogos


def _jogos_janela(slug, d1, d2):
    chave = f'jg:{slug}:{d1:%Y%m%d}:{d2:%Y%m%d}'
    with _lock:
        item = _mem.get(chave)
    ao_vivo = bool(item and any(j['estado'] == 'in' for j in item['data']))
    dados = _cache(chave, 60 if ao_vivo else 300, lambda: _buscar_intervalo(slug, d1, d2))
    if dados:
        agora = time.time()
        with _lock:
            if len(_idx) > 4000:
                for k in [k for k, v in _idx.items() if agora - v['ts'] > 7200]:
                    _idx.pop(k, None)
            for j in dados:
                _idx[(slug, j['id'])] = {'ts': agora, 'jogo': j}
    return dados


def _jogos_do_dia(slug, off, vivo=False):
    alvo = _agora().date() + timedelta(days=off)
    dados = _jogos_janela(slug, alvo - timedelta(days=1), alvo + timedelta(days=1))
    if dados is None:
        return None
    if vivo:
        return [j for j in dados if j['estado'] == 'in']
    out = []
    for j in dados:
        ini = _dt_sp(j['inicio'])
        if ini and ini.date() == alvo:
            out.append(j)
    return out


def _achar_jogo(slug, eid, off_hint=None, forcar=False):
    """Procura o jogo no índice; se não achar (ou for forçado), refaz a busca nos dias prováveis."""
    chave = (slug, str(eid))
    with _lock:
        item = _idx.get(chave)
    if item and not forcar:
        return item['jogo']
    ofs = []
    if item:
        ini = _dt_sp(item['jogo']['inicio'])
        if ini:
            ofs.append((ini.date() - _agora().date()).days)
    if off_hint is not None:
        ofs.append(off_hint)
    ofs += [0, 1, -1, 2, 3, 4, 5, 6, 7]
    if forcar:
        _invalidar({slug}, idade_min=0)
    for off in dict.fromkeys(ofs):
        if not OFF_MIN <= off <= OFF_MAX:
            continue
        _jogos_do_dia(slug, off)
        with _lock:
            item = _idx.get(chave)
        if item:
            return item['jogo']
    return None


# ----------------------------- LINHAS ----------------------------------------
def _linha_jogo(n, j):
    casa, fora = _esc(j['casa']), _esc(j['fora'])
    placar = f"<b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b>"
    ini = _dt_sp(j['inicio'])
    hora = ini.strftime('%H:%M') if ini else '--:--'
    rot = j['rotulo']
    pref = f'{n}. '
    if j['estado'] == 'in':
        return f"{pref}🔴 <b>{_esc(rot)}</b> {casa} {placar} {fora}"
    if j['estado'] == 'post':
        if rot in ('ADIADO', 'CANCELADO'):
            return f"{pref}⚠️ <b>{rot}</b> {casa} x {fora}"
        return f"{pref}✅ {rot} {casa} {placar} {fora}"
    if rot in ('ADIADO', 'CANCELADO', 'PARALISADO'):
        return f"{pref}⚠️ <b>{rot}</b> {casa} x {fora}"
    return f"{pref}⏰ <b>{hora}</b> {casa} x {fora}"


def _lidxs_modo(modo):
    ligas = _ligas()
    if modo == 'top':
        return [i for i, l in enumerate(ligas) if l.get('destaque')]
    if modo in ('br', 'mundo'):
        return [i for i, l in enumerate(ligas) if l.get('grupo') == modo]
    return list(range(len(ligas)))        # vivo | todos


def _coletar(lidxs, off, vivo):
    ligas = _ligas()
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(lambda i: _jogos_do_dia(ligas[i]['slug'], off, vivo), lidxs))
    ok = any(r is not None for r in res)
    entradas = []
    for i, r in zip(lidxs, res):
        for j in sorted(r or [], key=lambda x: (0 if x['estado'] == 'in' else 1, x['inicio'] or '')):
            entradas.append((i, j))
    return entradas, ok


def _linhas_nav_dia(m, cb_base, off):
    hoje = _agora().date()
    ant, prox = off - 1, off + 1
    b = []
    if ant >= OFF_MIN:
        b.append(InlineKeyboardButton(f"◀️ {(hoje + timedelta(days=ant)).strftime('%d/%m')}",
                                      callback_data=f'{cb_base}_{ant}_0'))
    b.append(InlineKeyboardButton(('• ' if off == 0 else '') + '📅 HOJE', callback_data=f'{cb_base}_0_0'))
    if prox <= OFF_MAX:
        b.append(InlineKeyboardButton(f"{(hoje + timedelta(days=prox)).strftime('%d/%m')} ▶️",
                                      callback_data=f'{cb_base}_{prox}_0'))
    m.row(*b)


def _tela_lista(call, titulo, lidxs, off, pg, cb_base, vivo=False, extras=None, voltar='ent_jogos', atualizar=False):
    ligas = _ligas()
    if atualizar:
        _invalidar({ligas[i]['slug'] for i in lidxs})
    entradas, ok = _coletar(lidxs, off, vivo)
    if not ok:
        return _tela_erro(call, 'Não consegui buscar os jogos agora.', f'{cb_base}_{off}_{pg}', voltar)

    total = len(entradas)
    paginas = max(1, -(-total // POR_PAGINA))
    pg = min(max(pg, 0), paginas - 1)
    pagina = entradas[pg * POR_PAGINA:(pg + 1) * POR_PAGINA]

    agora = _agora()
    if vivo:
        cab = f'{titulo}\n<i>{total} jogo(s) rolando agora</i>'
    else:
        d = agora.date() + timedelta(days=off)
        rot = _rotulo_off(off)
        cab = f"{titulo}\n📅 <b>{_fmt_dia(d).upper()}</b>" + (f' · {rot}' if rot else '')

    partes, botoes, tem_tv = [], [], False
    atual, linhas = None, []

    def fecha():
        nonlocal tem_tv
        if atual is None:
            return
        liga = ligas[atual]
        tv = _tv(liga['slug'])
        tem_tv = tem_tv or bool(tv)
        tv_txt = f'\n📺 <i>Passa em: {_esc(tv)}</i>' if tv else ''
        partes.append(f"\n🏆 <b>{_esc(liga.get('bandeira', ''))} {_esc(liga['nome'])}</b>{tv_txt}\n"
                      f"<blockquote>{chr(10).join(linhas)}</blockquote>")

    for k, (i, j) in enumerate(pagina):
        n = pg * POR_PAGINA + k + 1
        if i != atual:
            fecha()
            atual, linhas = i, []
        linhas.append(_linha_jogo(n, j))
        botoes.append(InlineKeyboardButton(str(n), callback_data=f"ent_jg_D_{i}_{j['id']}"))
    fecha()

    if not partes:
        corpo = ('\n<i>Nenhum jogo ao vivo no momento.</i>' if vivo
                 else '\n<i>Nenhum jogo encontrado para este dia.</i>')
    else:
        corpo = ''.join(partes)
    rodape = ''
    if partes:
        rodape += '\n\n👇 <i>Toque no número do jogo para ver detalhes, avisos e onde assistir.</i>'
    if tem_tv:
        rodape += '\nℹ️ <i>A transmissão varia de jogo para jogo; confira na programação.</i>'
    if paginas > 1:
        rodape += f'\n📄 <i>Página {pg + 1} de {paginas} · {total} jogos</i>'
    rodape += f"\n🕒 <i>Atualizado às {agora.strftime('%H:%M:%S')} (Brasília)</i>"
    texto = f'{cab}\n{corpo}{rodape}'

    m = InlineKeyboardMarkup()
    for r in range(0, len(botoes), 6):
        m.row(*botoes[r:r + 6])
    if paginas > 1:
        nav = []
        if pg > 0:
            nav.append(InlineKeyboardButton('⬅️ ANTERIOR', callback_data=f'{cb_base}_{off}_{pg - 1}'))
        if pg < paginas - 1:
            nav.append(InlineKeyboardButton('PRÓXIMA ➡️', callback_data=f'{cb_base}_{off}_{pg + 1}'))
        m.row(*nav)
    m.row(InlineKeyboardButton('🔄 ATUALIZAR', callback_data=f'{cb_base}_{off}_{pg}_r'))
    if not vivo:
        _linhas_nav_dia(m, cb_base, off)
    for linha in (extras or []):
        m.row(*linha)
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data=voltar))
    _ent._mostrar(call, texto, m)


# ----------------------------- MENUS -----------------------------------------
def _tela_menu(call):
    texto = (
        '⚽ <b>JOGOS DO BRASIL E DO MUNDO</b>\n'
        '<i>Placar ao vivo, agenda, tabela e onde assistir — horário de Brasília.</i>\n'
        '\n'
        '<blockquote>'
        '├─ 🔍 <b>Pesquisar time</b> — digite o nome e veja os jogos e onde passa\n'
        '├─ 🔴 <b>Ao vivo</b> — o que está rolando agora\n'
        '├─ ⭐ <b>Principais</b> — Brasileirão, Champions, Premier, La Liga...\n'
        '├─ 🗺️ <b>Por país</b> — Brasil, Inglaterra, Espanha, Itália e mais\n'
        '├─ 📊 <b>Classificação</b> de cada campeonato\n'
        '├─ 📅 <b>Agenda</b> — de 3 dias atrás até 7 dias à frente\n'
        '├─ 🔔 <b>Avisos</b> — te chamo 15 min antes do jogo\n'
        '└─ 📺 <b>Onde assistir</b> — apps e canais de cada campeonato'
        '</blockquote>'
    )
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔍 PESQUISAR TIME', callback_data='ent_jg_Q'))
    m.row(InlineKeyboardButton('🔴 AO VIVO AGORA', callback_data='ent_jg_L_vivo_0_0'),
          InlineKeyboardButton('⭐ MEUS TIMES', callback_data='ent_jg_F'))
    m.row(InlineKeyboardButton('⭐ PRINCIPAIS HOJE', callback_data='ent_jg_L_top_0_0'))
    m.row(InlineKeyboardButton('🇧🇷 BRASIL', callback_data='ent_jg_L_br_0_0'),
          InlineKeyboardButton('🌍 MUNDO', callback_data='ent_jg_L_mundo_0_0'))
    m.row(InlineKeyboardButton('🗺️ POR PAÍS / CAMPEONATO', callback_data='ent_jg_P'))
    wd = _agora().weekday()                       # seg=0 ... dom=6
    off_sab = -1 if wd == 6 else (5 - wd) % 7
    off_dom = (6 - wd) % 7
    m.row(InlineKeyboardButton('🏖️ SÁBADO', callback_data=f'ent_jg_L_todos_{off_sab}_0'),
          InlineKeyboardButton('🏖️ DOMINGO', callback_data=f'ent_jg_L_todos_{off_dom}_0'))
    m.row(InlineKeyboardButton('🌐 TODOS OS JOGOS DE HOJE', callback_data='ent_jg_L_todos_0_0'))
    m.row(InlineKeyboardButton('📺 ONDE ASSISTIR', callback_data='ent_jg_A'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_menu'))
    _ent._mostrar(call, texto, m)


def _tela_paises(call):
    m = InlineKeyboardMarkup()
    botoes = [InlineKeyboardButton(f'{fl} {nome}', callback_data=f'ent_jg_C_{i}_0_0')
              for i, (nome, fl) in enumerate(_paises())]
    for i in range(0, len(botoes), 2):
        m.row(*botoes[i:i + 2])
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    _ent._mostrar(call, '🗺️ <b>POR PAÍS / CAMPEONATO</b>\n<i>Escolha o país para ver os jogos, a tabela e onde passa.</i>', m)


def _tela_pais(call, pidx, off, pg, atualizar=False):
    paises = _paises()
    if not 0 <= pidx < len(paises):
        return
    nome, fl = paises[pidx]
    ligas = _ligas()
    lidxs = [i for i, l in enumerate(ligas) if (l.get('pais') or 'Outros') == nome]
    extras, linha = [], []
    for i in lidxs:
        linha.append(InlineKeyboardButton(f"📊 {ligas[i]['nome'][:22]}", callback_data=f'ent_jg_S_{i}'))
        if len(linha) == 2:
            extras.append(linha)
            linha = []
    if linha:
        extras.append(linha)
    _tela_lista(call, f'⚽ <b>{fl} {_esc(nome).upper()}</b>', lidxs, off, pg, f'ent_jg_C_{pidx}',
                extras=extras, voltar='ent_jg_P', atualizar=atualizar)


# ----------------------------- DETALHE DO JOGO -------------------------------
def _usr_ler():
    return _ent._ler(ARQ_USUARIOS, {})


def _usr_mut(uid, fn):
    with _ulock:
        dados = _ent._ler(ARQ_USUARIOS, {})
        u = dados.setdefault(str(uid), {'times': [], 'avisos': []})
        u.setdefault('times', [])
        u.setdefault('avisos', [])
        r = fn(u)
        _ent._gravar(ARQ_USUARIOS, dados)
        return r


def _em_texto(ini):
    seg = (ini - _agora()).total_seconds()
    if seg <= 0:
        return ''
    if seg < 3600:
        return f'em {int(seg // 60)} min'
    if seg < 86400:
        h, mi = int(seg // 3600), int((seg % 3600) // 60)
        return f'em {h}h{mi:02d}'
    return f'em {int(seg // 86400)} dia(s)'


def _tela_detalhe(call, lidx, eid, forcar=False):
    ligas = _ligas()
    if not 0 <= lidx < len(ligas):
        return
    liga = ligas[lidx]
    j = _achar_jogo(liga['slug'], eid, forcar=forcar)
    if not j:
        return _tela_erro(call, 'Jogo indisponível. Abra a lista novamente.', f'ent_jg_T_{lidx}_0_0', f'ent_jg_T_{lidx}_0_0')
    ini = _dt_sp(j['inicio'])
    off = (ini.date() - _agora().date()).days if ini else 0
    casa, fora = _esc(j['casa']), _esc(j['fora'])

    if j['estado'] == 'pre':
        em = _em_texto(ini) if ini else ''
        placar_linha = f'{casa}  x  {fora}'
        status = f'🕒 Começa {em}' if em else '🕒 Ainda não começou'
        if j['rotulo'] in ('ADIADO', 'CANCELADO', 'PARALISADO'):
            status = f"⚠️ <b>{j['rotulo']}</b>"
    elif j['estado'] == 'in':
        placar_linha = f"{casa}  <b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b>  {fora}"
        status = f"🔴 <b>AO VIVO — {_esc(j['rotulo'])}</b>"
    else:
        placar_linha = f"{casa}  <b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b>  {fora}"
        status = f"✅ Encerrado ({_esc(j['rotulo'])})"
        if j['rotulo'] in ('ADIADO', 'CANCELADO'):
            status = f"⚠️ <b>{j['rotulo']}</b>"
    if j.get('pen'):
        status += f"  ·  pênaltis {_esc(j['pen'])}"

    info = [status]
    if ini:
        info.append(f"📅 {_fmt_dia(ini.date()).capitalize()} às {ini.strftime('%H:%M')} (Brasília)")
    local = ', '.join(x for x in (j['estadio'], j['cidade']) if x)
    if local:
        info.append(f'🏟️ {_esc(local)}')
    if j['fase']:
        info.append(f"🔖 {_esc(j['fase'])}")

    texto = (f"🏆 <b>{_esc(liga.get('bandeira', ''))} {_esc(liga['nome'])}</b>\n\n"
             f"<b>{placar_linha}</b>\n\n<blockquote>{chr(10).join(info)}</blockquote>")

    if j['detalhes']:
        lances = []
        for d in j['detalhes'][:16]:
            time_ = j['casa'] if d['lado'] == 'c' else (j['fora'] if d['lado'] == 'f' else '')
            lances.append(f"{d['ic']} {_esc(d['min'])} {_esc(d['nome'])}" + (f' <i>({_esc(time_)})</i>' if time_ else ''))
        texto += '\n\n<b>Lances</b>\n<blockquote>' + '\n'.join(lances) + '</blockquote>'

    tv = _tv(liga['slug'])
    if tv:
        texto += (f'\n\n📺 <b>Onde assistir:</b> {_esc(tv)}\n'
                  '<i>A transmissão varia de jogo para jogo; confira na programação.</i>')
    else:
        texto += '\n\n📺 <i>Sem informação de transmissão para este campeonato — veja o guia em ONDE ASSISTIR.</i>'
    texto += f"\n🕒 <i>Atualizado às {_agora().strftime('%H:%M:%S')}</i>"

    uid = call.from_user.id
    u = _usr_ler().get(str(uid), {})
    seguindo = {t['id'] for t in u.get('times', [])}
    avisando = any(a['id'] == j['id'] and a['slug'] == liga['slug'] for a in u.get('avisos', []))

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔄 ATUALIZAR', callback_data=f"ent_jg_D_{lidx}_{j['id']}_r"))
    if j['estado'] != 'post':
        m.row(InlineKeyboardButton('🔕 NÃO AVISAR' if avisando else '🔔 ME AVISAR DESTE JOGO',
                                   callback_data=f"ent_jg_N_{lidx}_{j['id']}"))
    def rot_time(_lado, nome, tid):
        return ('✅ SEGUINDO ' if tid in seguindo else '⭐ SEGUIR ') + nome[:14]
    m.row(InlineKeyboardButton(rot_time('c', j['casa'], j['casa_id']), callback_data=f"ent_jg_F+_{lidx}_{j['id']}_c"),
          InlineKeyboardButton(rot_time('f', j['fora'], j['fora_id']), callback_data=f"ent_jg_F+_{lidx}_{j['id']}_f"))
    m.row(InlineKeyboardButton('📊 CLASSIFICAÇÃO', callback_data=f'ent_jg_S_{lidx}'),
          InlineKeyboardButton('📺 ONDE ASSISTIR', callback_data=f"ent_jg_W_{lidx}_{j['id']}"))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data=f'ent_jg_T_{lidx}_{off}_0'))
    _ent._mostrar(call, texto, m)


def _alternar_aviso(call, lidx, eid):
    ligas = _ligas()
    liga = ligas[lidx]
    j = _achar_jogo(liga['slug'], eid)
    if not j:
        return _toast(call, 'Jogo indisponível. Abra a lista novamente.')

    def fn(u):
        for a in u['avisos']:
            if a['id'] == j['id'] and a['slug'] == liga['slug']:
                u['avisos'].remove(a)
                return 'off'
        if len(u['avisos']) >= MAX_AVISOS:
            return 'cheio'
        u['avisos'].append({'slug': liga['slug'], 'id': j['id'], 'casa': j['casa'], 'fora': j['fora'],
                            'inicio': j['inicio'], 'liga': liga['nome']})
        return 'on'

    r = _usr_mut(call.from_user.id, fn)
    _toast(call, {'on': '🔔 Combinado! Te aviso 15 min antes e quando acabar.',
                  'off': '🔕 Aviso removido.',
                  'cheio': 'Você já tem 20 avisos ativos. Remova algum antes.'}[r])
    _tela_detalhe(call, lidx, eid)


def _alternar_time(call, lidx, eid, lado):
    ligas = _ligas()
    liga = ligas[lidx]
    j = _achar_jogo(liga['slug'], eid)
    if not j:
        return _toast(call, 'Jogo indisponível. Abra a lista novamente.')
    tid = j['casa_id'] if lado == 'c' else j['fora_id']
    nome = j['casa'] if lado == 'c' else j['fora']
    if not tid:
        return _toast(call, 'Não consegui identificar este time.')

    def fn(u):
        for t in u['times']:
            if t['id'] == tid:
                u['times'].remove(t)
                return 'off'
        if len(u['times']) >= MAX_TIMES:
            return 'cheio'
        u['times'].append({'id': tid, 'nome': nome, 'slug': liga['slug']})
        return 'on'

    r = _usr_mut(call.from_user.id, fn)
    _toast(call, {'on': f'⭐ Agora você segue o {nome}.', 'off': f'Deixou de seguir o {nome}.',
                  'cheio': 'Você já segue 10 times. Remova algum antes.'}[r])
    _tela_detalhe(call, lidx, eid)


# ----------------------------- MEUS TIMES ------------------------------------
def _slugs_do_time(slug_origem):
    """Campeonatos onde procurar os jogos do time: os do país + os continentais da região."""
    ligas = _ligas()
    o = next((l for l in ligas if l['slug'] == slug_origem), None)
    if not o:
        return [slug_origem]
    out = [l['slug'] for l in ligas if (l.get('pais') or 'Outros') == (o.get('pais') or 'Outros')]
    reg = o.get('reg') or ''
    if reg:
        out += [l['slug'] for l in ligas if l.get('cont') and l.get('reg') == reg]
    return list(dict.fromkeys(out))


def _tela_favoritos(call, atualizar=False):
    uid = call.from_user.id
    times = _usr_ler().get(str(uid), {}).get('times', [])
    m = InlineKeyboardMarkup()
    if not times:
        texto = ('⭐ <b>MEUS TIMES</b>\n\n'
                 'Você ainda não segue nenhum time.\n\n'
                 '👉 Abra qualquer jogo e toque em <b>⭐ SEGUIR</b> ao lado do nome do time. '
                 'Aqui aparecem os próximos jogos dos seus times.')
        m.row(InlineKeyboardButton('⭐ VER JOGOS PRINCIPAIS', callback_data='ent_jg_L_top_0_0'))
        m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
        return _ent._mostrar(call, texto, m)

    ligas = _ligas()
    indice = {l['slug']: i for i, l in enumerate(ligas)}
    hoje = _agora().date()
    slugs = list(dict.fromkeys(s for t in times for s in _slugs_do_time(t['slug'])))
    if atualizar:
        _invalidar(set(slugs))
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(lambda s: _jogos_janela(s, hoje - timedelta(days=1), hoje + timedelta(days=7)), slugs))
    ids = {t['id'] for t in times}
    achados = []
    for s, jogos in zip(slugs, res):
        for j in jogos or []:
            if j['casa_id'] in ids or j['fora_id'] in ids:
                ini = _dt_sp(j['inicio'])
                if not ini:
                    continue
                if j['estado'] == 'post' and ini.date() < hoje:
                    continue
                achados.append((ini, s, j))
    achados.sort(key=lambda x: x[0])
    achados = achados[:12]

    linhas, botoes = [], []
    for n, (ini, s, j) in enumerate(achados, 1):
        nome_liga = ligas[indice[s]]['nome'] if s in indice else s
        if j['estado'] == 'in':
            quando = f"🔴 {_esc(j['rotulo'])}"
            meio = f"{_esc(j['casa'])} <b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b> {_esc(j['fora'])}"
        elif j['estado'] == 'post':
            quando = '✅ FIM'
            meio = f"{_esc(j['casa'])} <b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b> {_esc(j['fora'])}"
        else:
            quando = f"{_fmt_dia(ini.date())} ⏰ {ini.strftime('%H:%M')}"
            meio = f"{_esc(j['casa'])} x {_esc(j['fora'])}"
        linhas.append(f"{n}. {quando}\n    {meio} <i>· {_esc(nome_liga)}</i>")
        if s in indice:
            botoes.append(InlineKeyboardButton(str(n), callback_data=f"ent_jg_D_{indice[s]}_{j['id']}"))

    seguindo = ', '.join(_esc(t['nome']) for t in times)
    texto = f'⭐ <b>MEUS TIMES</b>\n<i>Seguindo: {seguindo}</i>\n\n'
    texto += ('<blockquote>' + '\n'.join(linhas) + '</blockquote>\n\n👇 <i>Toque no número para ver detalhes.</i>'
              if linhas else '<i>Nenhum jogo agendado para os próximos 7 dias.</i>')
    texto += f"\n🕒 <i>Atualizado às {_agora().strftime('%H:%M:%S')} (Brasília)</i>"
    for r in range(0, len(botoes), 6):
        m.row(*botoes[r:r + 6])
    m.row(InlineKeyboardButton('🔄 ATUALIZAR', callback_data='ent_jg_F_r'))
    for t in times:
        m.row(InlineKeyboardButton(f"❌ Deixar de seguir {t['nome'][:20]}", callback_data=f"ent_jg_F-_{t['id']}"))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    _ent._mostrar(call, texto, m)


def _remover_time(call, tid):
    def fn(u):
        u['times'] = [t for t in u['times'] if t['id'] != tid]
    _usr_mut(call.from_user.id, fn)
    _toast(call, 'Time removido.')
    _tela_favoritos(call)


# ----------------------------- CLASSIFICAÇÃO --------------------------------
def _stat(e, nome):
    for s in e.get('stats') or []:
        if s.get('name') == nome or s.get('type') == nome or s.get('abbreviation') == nome:
            v = s.get('value')
            if v is None:
                v = s.get('displayValue')
            try:
                return int(float(v))
            except Exception:
                return 0
    return 0


def _marca_zona(desc):
    d = (desc or '').lower()
    if any(x in d for x in ('relega', 'rebaix')):
        return '🟥'
    if any(x in d for x in ('champions', 'libertadores', 'promotion', 'promoção', 'acesso', 'qualification', 'classifica')):
        return '🟩'
    if any(x in d for x in ('europa', 'sudamericana', 'sul-americana', 'conference', 'playoff')):
        return '🟦'
    return '⬜'


def _buscar_tabela(slug):
    r = _get(slug, 'standings', v2=True)
    if r.status_code == 404:
        return []
    if r.status_code != 200:
        raise RuntimeError(f'ESPN HTTP {r.status_code} (standings {slug})')
    j = r.json()
    grupos = []
    filhos = j.get('children') or [j]
    for ch in filhos:
        entradas = ((ch.get('standings') or {}).get('entries')) or []
        if not entradas:
            continue
        linhas = []
        for e in entradas:
            t = e.get('team') or {}
            nota = e.get('note') or {}
            linhas.append({
                'pos': _stat(e, 'rank'), 'nome': t.get('shortDisplayName') or t.get('displayName') or '?',
                'pts': _stat(e, 'points'), 'j': _stat(e, 'gamesPlayed'), 'v': _stat(e, 'wins'),
                'e': _stat(e, 'ties'), 'd': _stat(e, 'losses'), 'sg': _stat(e, 'pointDifferential'),
                'zona': nota.get('description') or '',
            })
        if all(l['pos'] == 0 for l in linhas):
            linhas.sort(key=lambda l: (-l['pts'], -l['sg']))
            for k, l in enumerate(linhas, 1):
                l['pos'] = k
        else:
            linhas.sort(key=lambda l: l['pos'] or 99)
        grupos.append({'nome': ch.get('name') or '', 'linhas': linhas})
    return grupos


def _tela_classificacao(call, lidx):
    ligas = _ligas()
    if not 0 <= lidx < len(ligas):
        return
    liga = ligas[lidx]
    grupos = _cache(f'tb:{liga["slug"]}', 600, lambda: _buscar_tabela(liga['slug']))
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('📅 JOGOS DO CAMPEONATO', callback_data=f'ent_jg_T_{lidx}_0_0'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    cab = f"📊 <b>{_esc(liga.get('bandeira', ''))} {_esc(liga['nome']).upper()}</b>\n<i>Classificação</i>\n\n"
    if grupos is None:
        return _tela_erro(call, 'Não consegui buscar a classificação agora.', f'ent_jg_S_{lidx}', 'ent_jogos')
    if not grupos:
        return _ent._mostrar(call, cab + '<i>Este campeonato não tem tabela de pontos corridos '
                                         '(é mata-mata) ou ainda não começou.</i>', m)
    blocos, tamanho, legenda = [], 0, {}
    for g in grupos[:10]:
        linhas = g['linhas'][:24]
        if len(grupos) > 3:
            linhas = linhas[:6]
        corpo = ['  # Time          P  J  V  E  D  SG']
        for l in linhas:
            mk = _marca_zona(l['zona'])
            if l['zona']:
                legenda.setdefault(mk, l['zona'])
            nome12 = l['nome'][:12]
            corpo.append(f"{mk}{l['pos']:>2} {_esc(nome12)}{' ' * (12 - len(nome12))} {l['pts']:>2} {l['j']:>2} "
                         f"{l['v']:>2} {l['e']:>2} {l['d']:>2} {l['sg']:>+3}")
        bloco = (f"<b>{_esc(g['nome'])}</b>\n" if g['nome'] and len(grupos) > 1 else '') + \
                '<pre>' + '\n'.join(corpo) + '</pre>'
        if tamanho + len(bloco) > 3300:
            break
        blocos.append(bloco)
        tamanho += len(bloco)
    texto = cab + '\n'.join(blocos)
    if legenda:
        texto += '\n' + '\n'.join(f'{mk} <i>{_esc(d)}</i>' for mk, d in list(legenda.items())[:4])
    texto += '\n<i>P = pontos · J = jogos · V/E/D = vitórias/empates/derrotas · SG = saldo de gols</i>'
    _ent._mostrar(call, texto, m)


# ----------------------------- 🔍 PESQUISAR TIME ------------------------------
# O cliente digita o nome do time e o bot mostra os jogos dele (3 dias atrás até
# 7 dias à frente, em todos os campeonatos cadastrados) e onde cada um passa.
ALIAS_TIMES = {
    'bayern de munique': 'bayern munich', 'bayern': 'bayern munich', 'inter de milao': 'inter milan',
    'inter': 'inter milan', 'atletico de madrid': 'atletico madrid', 'atletico madrid': 'atletico madrid',
    'napoles': 'napoli', 'psg': 'paris saint germain', 'paris': 'paris saint germain',
    'man city': 'manchester city', 'city': 'manchester city', 'man utd': 'manchester united',
    'united': 'manchester united', 'real': 'real madrid', 'barca': 'barcelona',
    'selecao brasileira': 'brazil', 'selecao': 'brazil', 'brasil': 'brazil', 'alemanha': 'germany',
    'franca': 'france', 'espanha': 'spain', 'inglaterra': 'england', 'italia': 'italy',
    'holanda': 'netherlands', 'uruguai': 'uruguay', 'japao': 'japan', 'estados unidos': 'united states',
    'eua': 'united states', 'belgica': 'belgium', 'croacia': 'croatia', 'suica': 'switzerland',
    'marrocos': 'morocco', 'coreia do sul': 'south korea', 'equador': 'ecuador', 'peru': 'peru',
    'paraguai': 'paraguay', 'bolivia': 'bolivia', 'chile': 'chile', 'colombia': 'colombia',
    'mexico': 'mexico', 'argentina': 'argentina', 'portugal': 'portugal',
}
MAX_BUSCA_AO_VIVO, MAX_BUSCA_PROX, MAX_BUSCA_REC = 6, 8, 3
PRAZO_BUSCA = 20            # segundos esperando a ESPN antes de mostrar o que já chegou
_prefetch_ts = 0
_ultima_q = {}      # uid -> último texto pesquisado


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in s.lower()).split())


def _variantes_consulta(q):
    n = _norm(q)
    vs = [n]
    if n in ALIAS_TIMES:
        vs.append(ALIAS_TIMES[n])
    return [v for v in dict.fromkeys(vs) if v]


def _txt_bate(txt, variantes):
    palavras = set(txt.split())
    for v in variantes:
        toks = v.split()
        if all(any(w.startswith(t) for w in palavras) or (len(t) >= 4 and t in txt) for t in toks):
            return True
    return False


def _lado_bate(j, lado, variantes):
    return _txt_bate(f"{_norm(j.get(lado))} {_norm(j.get(lado + '_full'))}", variantes)


# ---- índice de times (nome -> campeonatos), para só consultar os campeonatos do time ----
ARQ_INDICE = os.path.join('database', 'entretenimento_times_idx.json')
VALIDADE_INDICE = 7 * 86400
_indice = None            # {slug: [texto_normalizado_do_time, ...]}
_indice_ts = 0
_indice_construindo = False


def _carregar_indice_disco():
    global _indice, _indice_ts
    try:
        with open(ARQ_INDICE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d.get('ligas'), dict) and time.time() - d.get('ts', 0) < VALIDADE_INDICE:
            _indice, _indice_ts = d['ligas'], d['ts']
    except Exception:
        pass


def _construir_indice():
    global _indice, _indice_ts, _indice_construindo
    try:
        ligas = _ligas()

        def um(l):
            try:
                r = _get(l['slug'], 'teams', {'limit': 500})
                if r.status_code == 404:
                    return l['slug'], []
                if r.status_code != 200:
                    return l['slug'], None
                out = []
                for sp in r.json().get('sports') or []:
                    for lg in sp.get('leagues') or []:
                        for t in lg.get('teams') or []:
                            tm = t.get('team') or {}
                            nomes = {_norm(x) for x in (tm.get('displayName'), tm.get('shortDisplayName'), tm.get('name')) if x}
                            if nomes:
                                out.append(' '.join(sorted(nomes)))
                return l['slug'], out
            except Exception:
                return l['slug'], None

        with ThreadPoolExecutor(max_workers=6) as ex:
            res = dict(ex.map(um, ligas))
        ok = {k: v for k, v in res.items() if v is not None}
        if len(ok) >= max(1, len(ligas) // 2):
            _indice, _indice_ts = ok, time.time()
            try:
                os.makedirs('database', exist_ok=True)
                with open(ARQ_INDICE, 'w', encoding='utf-8') as f:
                    json.dump({'ts': _indice_ts, 'ligas': ok}, f, ensure_ascii=False)
            except Exception as e:
                print(f'[entretenimento_jogos] índice de times não salvo: {e}')
            print(f'[entretenimento_jogos] índice de times pronto ({len(ok)}/{len(ligas)} campeonatos).')
    finally:
        _indice_construindo = False


def _garantir_indice_bg():
    """Monta o índice em segundo plano (1x por semana). Enquanto não existe, a busca varre tudo."""
    global _indice_construindo
    if _indice_construindo or (_indice and time.time() - _indice_ts < VALIDADE_INDICE):
        return
    _indice_construindo = True
    threading.Thread(target=_construir_indice, daemon=True).start()


def _buscar_jogos_time(q):
    """[(lidx, jogo, nome_do_time_encontrado)] — ou None se a ESPN não respondeu em nenhum campeonato."""
    variantes = _variantes_consulta(q)
    hoje = _agora().date()
    d1, d2 = hoje + timedelta(days=OFF_MIN), hoje + timedelta(days=OFF_MAX)
    ligas = _ligas()
    idx = _indice
    if idx:
        # só os campeonatos em que o time aparece (+ os que o índice não conseguiu carregar)
        cand = [i for i, l in enumerate(ligas)
                if l['slug'] not in idx or any(_txt_bate(t, variantes) for t in idx[l['slug']])]
        if not cand:
            return []
    else:
        _garantir_indice_bg()
        cand = list(range(len(ligas)))

    def pega(i):
        try:
            return _jogos_janela(ligas[i]['slug'], d1, d2)
        except Exception:
            return None

    # em paralelo, com prazo: o que não chegar a tempo segue carregando e entra no cache
    ex = ThreadPoolExecutor(max_workers=10)
    futs = {i: ex.submit(pega, i) for i in cand}
    wait(list(futs.values()), timeout=PRAZO_BUSCA)
    ex.shutdown(wait=False)
    res = [futs[i].result() if i in futs and futs[i].done() else None for i in range(len(ligas))]
    if cand and not any(res[i] is not None for i in cand):
        return None
    achados, vistos = [], set()
    for i, r in enumerate(res):
        for j in r or []:
            chave = (j['casa_id'], j['fora_id'], j['inicio'])
            if chave in vistos:
                continue
            for lado in ('casa', 'fora'):
                if _lado_bate(j, lado, variantes):
                    vistos.add(chave)
                    achados.append((i, j, j.get(lado + '_full') or j[lado]))
                    break
    return achados


def _linha_busca(n, j):
    ini = _dt_sp(j['inicio'])
    casa, fora = _esc(j['casa']), _esc(j['fora'])
    placar = f"<b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b>"
    dia = _fmt_dia(ini.date()) if ini else ''
    hora = ini.strftime('%H:%M') if ini else '--:--'
    rot_dia = _rotulo_off((ini.date() - _agora().date()).days) if ini else ''
    if j['estado'] == 'in':
        return f"{n}. 🔴 <b>{_esc(j['rotulo'])}</b> {casa} {placar} {fora}"
    if j['estado'] == 'post':
        if j['rotulo'] in ('ADIADO', 'CANCELADO'):
            return f"{n}. ⚠️ <b>{j['rotulo']}</b> {dia} · {casa} x {fora}"
        return f"{n}. ✅ {dia} · {casa} {placar} {fora}"
    if j['rotulo'] in ('ADIADO', 'CANCELADO', 'PARALISADO'):
        return f"{n}. ⚠️ <b>{j['rotulo']}</b> {casa} x {fora}"
    return f"{n}. ⏰ <b>{dia} {hora}</b>" + (f' ({rot_dia.lower()})' if rot_dia else '') + f"\n    {casa} x {fora}"


def _montar_busca(q):
    """(texto, markup) com os jogos do time pesquisado. Levanta RuntimeError se a ESPN falhar."""
    achados = _buscar_jogos_time(q)
    if achados is None:
        raise RuntimeError('ESPN indisponível')
    ligas = _ligas()
    ao_vivo = [a for a in achados if a[1]['estado'] == 'in']
    proximos = sorted((a for a in achados if a[1]['estado'] == 'pre'), key=lambda a: a[1]['inicio'] or '')
    recentes = sorted((a for a in achados if a[1]['estado'] == 'post'), key=lambda a: a[1]['inicio'] or '', reverse=True)
    sel = ao_vivo[:MAX_BUSCA_AO_VIVO] + proximos[:MAX_BUSCA_PROX] + recentes[:MAX_BUSCA_REC]

    m = InlineKeyboardMarkup()
    cab = f'🔍 <b>JOGOS DE “{_esc(q.upper())}”</b>'
    if not sel:
        texto = (f'{cab}\n\n😕 <b>Não encontrei jogos desse time</b> de 3 dias atrás até 7 dias à frente '
                 'nos campeonatos que acompanho.\n\n<i>Confira o nome (ex.: Flamengo, Real Madrid, Brasil) '
                 'ou tente só uma parte dele.</i>')
    else:
        times = list(dict.fromkeys(a[2] for a in sel))[:4]
        partes = [cab, f"<i>Time(s): {_esc(', '.join(times))}</i>"]
        n, botoes = 0, []

        def grupo(titulo, itens):
            nonlocal n
            if not itens:
                return
            blocos = []
            for lidx, j, _ in itens:
                n += 1
                liga = ligas[lidx]
                tv = _tv(liga['slug'])
                linha = _linha_busca(n, j)
                linha += f"\n    🏆 {_esc(liga.get('bandeira', ''))} {_esc(liga['nome'])}"
                if j['estado'] != 'post':
                    linha += f"\n    📺 {_esc(tv)}" if tv else '\n    📺 <i>veja em ONDE ASSISTIR</i>'
                blocos.append(linha)
                botoes.append(InlineKeyboardButton(str(n), callback_data=f"ent_jg_D_{lidx}_{j['id']}"))
            partes.append(f'\n{titulo}\n<blockquote>' + '\n\n'.join(blocos) + '</blockquote>')

        grupo('🔴 <b>AO VIVO</b>', ao_vivo[:MAX_BUSCA_AO_VIVO])
        grupo('📅 <b>PRÓXIMOS JOGOS</b>', proximos[:MAX_BUSCA_PROX])
        grupo('✅ <b>JOGOS RECENTES</b>', recentes[:MAX_BUSCA_REC])
        partes.append('\n👇 <i>Toque no número para ver estádio, fase, avisos e onde assistir.</i>')
        partes.append('ℹ️ <i>A transmissão varia de jogo para jogo; confira na programação.</i>')
        partes.append(f"🕒 <i>Atualizado às {_agora().strftime('%H:%M:%S')} (Brasília)</i>")
        texto = '\n'.join(partes)
        if len(texto) > 4000:
            texto = texto[:3990].rsplit('\n', 1)[0] + '\n…'
        for r in range(0, len(botoes), 6):
            m.row(*botoes[r:r + 6])
        m.row(InlineKeyboardButton('🔄 ATUALIZAR', callback_data='ent_jg_Q2_r'))
    m.row(InlineKeyboardButton('🔍 NOVA PESQUISA', callback_data='ent_jg_Q'),
          InlineKeyboardButton('📺 ONDE ASSISTIR', callback_data='ent_jg_A'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    return texto, m


def _tela_erro_busca_msg(chat_id, msg_id, q=None):
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔄 TENTAR DE NOVO', callback_data='ent_jg_Q2' if q else 'ent_jg_Q'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    _bot.edit_message_text('😕 <b>Não consegui buscar os jogos agora.</b>\n\n<i>Tente de novo daqui a instantes.</i>',
                           chat_id, msg_id, parse_mode='HTML', reply_markup=m)


def _prefetch_busca():
    _garantir_indice_bg()


def _safe_janela(slug, d1, d2):
    try:
        return _jogos_janela(slug, d1, d2)
    except Exception:
        return None


def _pedir_time(call):
    chat = call.message.chat.id
    _prefetch_busca()
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('↩️ CANCELAR', callback_data='ent_jogos'))
    texto = ('🔍 <b>PESQUISAR TIME</b>\n\n'
             '✍️ <b>Digite o nome do time</b> (ou da seleção) e envie.\n\n'
             '<blockquote>Ex.: Flamengo · Real Madrid · Palmeiras · Brasil · Manchester City</blockquote>\n'
             '<i>Mostro os jogos dele (de 3 dias atrás até 7 à frente) e onde cada um passa.</i>')
    _ent._mostrar(call, texto, m)
    _aguardar_nome(chat)


def _aguardar_nome(chat):
    try:
        _bot.clear_step_handler_by_chat_id(chat)
    except Exception:
        pass
    _bot.register_next_step_handler_by_chat_id(chat, _receber_time, time.time())


def _receber_time(message, t0):
    chat = message.chat.id
    if time.time() - t0 > 300:                      # esperou demais: trata como mensagem comum
        _bot.process_new_messages([message])
        return
    txt = getattr(message, 'text', None)
    if txt and txt.startswith('/'):                 # comando: deixa o bot executar normalmente
        _bot.process_new_messages([message])
        return
    if not txt:
        _bot.send_message(chat, '✍️ Envie o nome do time em <b>texto</b>.', parse_mode='HTML')
        return _aguardar_nome(chat)
    q = ' '.join(txt.split())[:50]
    if len(_norm(q)) < 3:
        _bot.send_message(chat, '✍️ Digite pelo menos <b>3 letras</b> do nome do time.', parse_mode='HTML')
        return _aguardar_nome(chat)
    espera = _bot.send_message(chat, f'🔎 Procurando jogos de <b>{_esc(q)}</b>…', parse_mode='HTML')
    try:
        _bot.delete_message(chat, message.message_id)
    except Exception:
        pass
    _ultima_q[message.from_user.id] = q
    try:
        texto, m = _montar_busca(q)
        _bot.edit_message_text(texto, chat, espera.message_id, parse_mode='HTML', reply_markup=m)
    except Exception as e:
        print(f'[entretenimento_jogos] busca "{q}": {type(e).__name__}: {e}')
        try:
            _tela_erro_busca_msg(chat, espera.message_id, q)
        except Exception:
            pass


def _tela_busca_salva(call, atualizar=False):
    q = _ultima_q.get(call.from_user.id)
    if not q:
        return _pedir_time(call)
    if atualizar:
        _invalidar({l['slug'] for l in _ligas()})
    _ent._mostrar(call, f'🔎 Procurando jogos de <b>{_esc(q)}</b>…', InlineKeyboardMarkup())
    try:
        texto, m = _montar_busca(q)
        _ent._mostrar(call, texto, m)
    except Exception as e:
        print(f'[entretenimento_jogos] busca "{q}": {type(e).__name__}: {e}')
        _tela_erro_busca_msg(call.message.chat.id, call.message.message_id, q)


# ----------------------------- 📺 ONDE VAI PASSAR (por jogo) -------------------
_TOKENS_APP = {
    'globo': ['globo'], 'ge': ['ge tv'], 'sportv': ['sportv'], 'premiere': ['premiere'], 'record': ['record'],
    'caze': ['cazetv', 'caze'], 'prime': ['prime'], 'espn': ['espn', 'disney'], 'paramount': ['paramount'],
    'hbo': ['hbo'], 'tnt': ['tnt'], 'sbt': ['sbt'], 'alt': ['xsports', 'sportynet', 'goat', 'n sports', 'jovem pan'],
    'apple': ['apple'],
}


def _eh_gratis(grupo):
    g = _norm(grupo)
    return any(k in g for k in ('gratis', 'youtube', 'tv aberta', 'aberta'))


def _apps_do_texto(tv):
    n = f' {_norm(tv)} '
    achados = []
    for a in (_ent._config().get('jogos_apps') or []):
        toks = _TOKENS_APP.get(a.get('k')) or [t for t in _norm(a.get('nome')).split() if len(t) >= 4]
        if any(f' {t} ' in n or t in n for t in toks):
            achados.append(a)
    return achados


def _tela_onde_jogo(call, lidx, eid):
    ligas = _ligas()
    if not 0 <= lidx < len(ligas):
        return
    liga = ligas[lidx]
    j = _achar_jogo(liga['slug'], eid)
    tv = _tv(liga['slug'])
    cab = '📺 <b>ONDE VAI PASSAR</b>'
    if j:
        ini = _dt_sp(j['inicio'])
        quando = f" · 📅 {_fmt_dia(ini.date())} às {ini.strftime('%H:%M')}" if ini else ''
        cab += f"\n⚽ <b>{_esc(j['casa'])} x {_esc(j['fora'])}</b>\n🏆 {_esc(liga.get('bandeira', ''))} {_esc(liga['nome'])}{quando}"
    else:
        cab += f"\n🏆 {_esc(liga.get('bandeira', ''))} {_esc(liga['nome'])}"
    nota = _ent._config().get('jogos_canais_nota', '')
    if not tv:
        texto = (cab + '\n\n<i>Ainda não tenho a transmissão deste campeonato cadastrada.</i>')
    else:
        gratis, pagos = [], []
        for g in [x.strip() for x in tv.split('·') if x.strip()]:
            limpo = re.sub(r',\s*grátis', '', g)
            limpo = re.sub(r'\(\s*grátis\s*\)|grátis', '', limpo)
            limpo = re.sub(r'\(\s*[,·]?\s*\)', '', limpo).replace(' ,', ',').strip(' ,')
            (gratis if _eh_gratis(g) else pagos).append(limpo or g)
        linhas = []
        if gratis:
            linhas.append('🆓 <b>Grátis:</b> ' + _esc(' · '.join(gratis)))
        if pagos:
            linhas.append('💳 <b>Assinatura / pago:</b> ' + _esc(' · '.join(pagos)))
        texto = cab + '\n\n<blockquote>' + '\n'.join(linhas) + '</blockquote>'
        apps = _apps_do_texto(tv)
        if apps:
            det = [f"{_esc(a.get('emoji', '📺'))} <b>{_esc(a['nome'])}</b> <i>({_esc(a.get('tipo', ''))})</i>\n{_esc(a.get('texto', ''))}"
                   for a in apps]
            texto += '\n\n📱 <b>Sobre cada um</b>\n<blockquote>' + '\n\n'.join(det) + '</blockquote>'
        texto += '\n\n<i>A emissora que passa cada jogo é definida perto da data; confira na programação.</i>'
    if nota:
        texto += f'\nℹ️ <i>{_esc(nota)}</i>'
    if len(texto) > 4000:
        texto = texto[:3990].rsplit('\n', 1)[0] + '\n…'
    m = InlineKeyboardMarkup()
    if j:
        m.row(InlineKeyboardButton('↩️ VOLTAR AO JOGO', callback_data=f"ent_jg_D_{lidx}_{j['id']}"))
    m.row(InlineKeyboardButton('📱 TODOS OS APPS E CANAIS', callback_data='ent_jg_A1'),
          InlineKeyboardButton('🔍 PESQUISAR TIME', callback_data='ent_jg_Q'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    _ent._mostrar(call, texto, m)


# ----------------------------- ONDE ASSISTIR ---------------------------------
def _tela_guia(call):
    nota = _ent._config().get('jogos_canais_nota', '')
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('📱 APPS E CANAIS', callback_data='ent_jg_A1'))
    m.row(InlineKeyboardButton('🏆 POR CAMPEONATO', callback_data='ent_jg_A2'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jogos'))
    texto = ('📺 <b>ONDE ASSISTIR</b>\n'
             '<i>Os jogos passam em vários lugares — uns grátis, outros por assinatura.</i>\n\n'
             '<blockquote>'
             '├─ 📱 <b>Apps e canais</b> — o que cada um transmite\n'
             '└─ 🏆 <b>Por campeonato</b> — onde passa cada competição'
             '</blockquote>')
    if nota:
        texto += f'\n\nℹ️ <i>{_esc(nota)}</i>'
    _ent._mostrar(call, texto, m)


def _tela_apps(call):
    apps = _ent._config().get('jogos_apps', []) or []
    m = InlineKeyboardMarkup()
    botoes = [InlineKeyboardButton(f"{a.get('emoji', '📺')} {a['nome'][:22]}", callback_data=f'ent_jg_A1_{i}')
              for i, a in enumerate(apps)]
    for i in range(0, len(botoes), 2):
        m.row(*botoes[i:i + 2])
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jg_A'))
    gratis = [a['nome'] for a in apps if 'grátis' in (a.get('tipo') or '').lower()]
    texto = '📱 <b>APPS E CANAIS</b>\n<i>Toque para ver o que cada um transmite.</i>'
    if gratis:
        texto += '\n\n🆓 <b>Grátis:</b> ' + _esc(' · '.join(gratis))
    _ent._mostrar(call, texto, m)


def _tela_app(call, i):
    apps = _ent._config().get('jogos_apps', []) or []
    if not 0 <= i < len(apps):
        return
    a = apps[i]
    texto = (f"{a.get('emoji', '📺')} <b>{_esc(a['nome'])}</b>\n"
             f"<i>{_esc(a.get('tipo', ''))}</i>\n\n{_esc(a.get('texto', ''))}\n\n"
             f"ℹ️ <i>{_esc(_ent._config().get('jogos_canais_nota', ''))}</i>")
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jg_A1'))
    _ent._mostrar(call, texto, m)


def _tela_por_campeonato(call):
    ligas = _ligas()
    blocos = []
    for l in ligas:
        tv = _tv(l['slug'])
        if tv:
            blocos.append(f"{_esc(l.get('bandeira', ''))} <b>{_esc(l['nome'])}</b>\n   📺 {_esc(tv)}")
    texto = '🏆 <b>ONDE PASSA CADA CAMPEONATO</b>\n\n' + ('\n\n'.join(blocos) if blocos else '<i>Nada cadastrado.</i>')
    nota = _ent._config().get('jogos_canais_nota', '')
    if nota:
        texto += f'\n\nℹ️ <i>{_esc(nota)}</i>'
    if len(texto) > 4000:
        texto = texto[:3990].rsplit('\n', 1)[0] + '\n…'
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_jg_A'))
    _ent._mostrar(call, texto, m)


# ----------------------------- AVISOS (thread) -------------------------------
def _processar_avisos():
    if not _ent.ativo('jogos'):
        return
    pre = _ent._ler(ARQ_USUARIOS, {})
    slugs = {a['slug'] for u in pre.values() for a in u.get('avisos', [])}
    if not slugs:
        return
    hoje = _agora().date()
    jogos = {}
    for s in slugs:                                   # rede FORA do lock (não trava os cliques)
        lista = _jogos_janela(s, hoje - timedelta(days=1), hoje + timedelta(days=1))
        jogos[s] = {j['id']: j for j in (lista or [])}
    envios = []
    with _ulock:
        dados = _ent._ler(ARQ_USUARIOS, {})
        agora = _agora()
        min_aviso = float(_ent._config().get('jogos_aviso_min', 15))
        mudou = False
        for uid, u in dados.items():
            novos = []
            for a in u.get('avisos', []):
                j = jogos.get(a['slug'], {}).get(a['id'])
                ini = _dt_sp(a['inicio'])
                if not j:
                    if ini and agora - ini > timedelta(hours=8):
                        mudou = True            # sumiu da ESPN e já passou: descarta
                        continue
                    novos.append(a)
                    continue
                nova_ini = _dt_sp(j['inicio'])
                if nova_ini and ini and abs((nova_ini - ini).total_seconds()) > 60:
                    a['inicio'], a['pre'] = j['inicio'], False   # horário mudou: avisa de novo
                    ini = nova_ini
                    mudou = True
                casa, fora = _esc(j['casa']), _esc(j['fora'])
                tv = _tv(a['slug'])
                tv_txt = f'\n📺 {_esc(tv)}' if tv else ''
                if j['estado'] == 'post' and j['rotulo'] not in ('ADIADO', 'CANCELADO'):
                    envios.append((uid, f"✅ <b>FIM DE JOGO</b>\n🏆 {_esc(a['liga'])}\n"
                                        f"{casa} <b>{_esc(j['pc'] or 0)} x {_esc(j['pf'] or 0)}</b> {fora}"))
                    mudou = True
                    continue                         # jogo acabou: remove o aviso
                if j['estado'] == 'in' and not a.get('pre'):
                    envios.append((uid, f"🔴 <b>A BOLA ROLOU!</b>\n🏆 {_esc(a['liga'])}\n{casa} x {fora}{tv_txt}"))
                    a['pre'] = True
                    mudou = True
                elif (j['estado'] == 'pre' and not a.get('pre') and ini
                      and 0 <= (ini - agora).total_seconds() <= min_aviso * 60 + 30):
                    mins = max(1, int((ini - agora).total_seconds() // 60))
                    envios.append((uid, f"⏰ <b>Começa em {mins} min</b>\n🏆 {_esc(a['liga'])}\n"
                                        f"{casa} x {fora} — {ini.strftime('%H:%M')} (Brasília){tv_txt}"))
                    a['pre'] = True
                    mudou = True
                novos.append(a)
            u['avisos'] = novos
        if mudou:
            _ent._gravar(ARQ_USUARIOS, dados)
    bloqueados = set()
    for uid, txt in envios:
        try:
            _bot.send_message(int(uid), txt, parse_mode='HTML')
        except Exception as e:
            if any(x in str(e) for x in ('403', 'blocked', 'deactivated', 'chat not found')):
                bloqueados.add(uid)
    if bloqueados:
        with _ulock:
            dados = _ent._ler(ARQ_USUARIOS, {})
            for uid in bloqueados:
                if uid in dados:
                    dados[uid]['avisos'] = []
            _ent._gravar(ARQ_USUARIOS, dados)


def _loop_avisos():
    while True:
        time.sleep(60)
        try:
            _processar_avisos()
        except Exception as e:
            print(f'[entretenimento_jogos] avisos: {type(e).__name__}: {e}')


# ----------------------------- REGISTRO --------------------------------------
def registrar(bot, ent):
    global _ent, _bot, _iniciou_thread
    _ent, _bot = ent, bot
    _carregar_indice_disco()
    threading.Timer(25, _garantir_indice_bg).start()   # monta o índice de times sem atrasar o boot

    def guarda(call):
        if not ent.ativo('jogos'):
            ent._alerta(call, 'Este recurso está indisponível no momento.')
            return False
        return True

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_jogos')
    def _cb_jogos(call):
        if guarda(call):
            ent._ok(call)
            _tela_menu(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_jg_'))
    def _cb_jg(call):
        global _ultimo_erro
        if not guarda(call):
            return
        p = call.data.split('_')               # ['ent','jg',cmd,...]
        cmd, a = (p[2] if len(p) > 2 else ''), p[3:]
        atualizar = bool(a) and a[-1] == 'r'
        if atualizar:
            a = a[:-1]
        try:
            # toques que respondem com "toast" (não chamam ent._ok antes)
            if cmd == 'N':
                return _alternar_aviso(call, int(a[0]), a[1])
            if cmd == 'F+':
                return _alternar_time(call, int(a[0]), a[1], a[2])
            if cmd == 'F-':
                return _remover_time(call, a[0])
            ent._ok(call)

            def num(i, padrao=0):
                try:
                    return int(a[i])
                except Exception:
                    return padrao

            if cmd in ('vivo', 'br', 'mundo', 'todos'):      # botões antigos (versão anterior)
                off = {'ontem': -1, 'hoje': 0, 'amanha': 1}.get(a[0] if a else 'hoje', 0)
                cmd, a = 'L', [cmd, str(off), '0']
            if cmd == 'L':
                modo = a[0] if a else 'top'
                if modo not in ('vivo', 'top', 'br', 'mundo', 'todos'):
                    return
                off = 0 if modo == 'vivo' else min(max(num(1), OFF_MIN), OFF_MAX)
                titulos = {'vivo': '🔴 <b>AO VIVO AGORA</b>', 'top': '⭐ <b>JOGOS — PRINCIPAIS</b>',
                           'br': '⚽ <b>JOGOS — 🇧🇷 BRASIL</b>', 'mundo': '⚽ <b>JOGOS — 🌍 MUNDO</b>',
                           'todos': '⚽ <b>JOGOS — 🌐 TODOS</b>'}
                extras = [[InlineKeyboardButton('🇧🇷 BRASIL', callback_data='ent_jg_L_br_0_0'),
                           InlineKeyboardButton('🌍 MUNDO', callback_data='ent_jg_L_mundo_0_0')],
                          [InlineKeyboardButton('⭐ PRINCIPAIS', callback_data='ent_jg_L_top_0_0'),
                           InlineKeyboardButton('🔴 AO VIVO', callback_data='ent_jg_L_vivo_0_0')],
                          [InlineKeyboardButton('🗺️ POR PAÍS', callback_data='ent_jg_P')]]
                return _tela_lista(call, titulos[modo], _lidxs_modo(modo), off, num(2), f'ent_jg_L_{modo}',
                                   vivo=(modo == 'vivo'), extras=extras, atualizar=atualizar)
            if cmd == 'P':
                return _tela_paises(call)
            if cmd == 'C':
                return _tela_pais(call, num(0), min(max(num(1), OFF_MIN), OFF_MAX), num(2), atualizar)
            if cmd == 'T':
                lidx = num(0)
                ligas = _ligas()
                if not 0 <= lidx < len(ligas):
                    return
                l = ligas[lidx]
                extras = [[InlineKeyboardButton('📊 CLASSIFICAÇÃO', callback_data=f'ent_jg_S_{lidx}'),
                           InlineKeyboardButton('📺 ONDE ASSISTIR', callback_data='ent_jg_A')]]
                return _tela_lista(call, f"⚽ <b>{_esc(l.get('bandeira', ''))} {_esc(l['nome']).upper()}</b>", [lidx],
                                   min(max(num(1), OFF_MIN), OFF_MAX), num(2), f'ent_jg_T_{lidx}',
                                   extras=extras, voltar='ent_jg_P', atualizar=atualizar)
            if cmd == 'D':
                return _tela_detalhe(call, num(0), a[1], forcar=atualizar)
            if cmd == 'S':
                return _tela_classificacao(call, num(0))
            if cmd == 'F':
                return _tela_favoritos(call, atualizar=atualizar)
            if cmd == 'W':
                return _tela_onde_jogo(call, num(0), a[1])
            if cmd == 'Q':
                return _pedir_time(call)
            if cmd == 'Q2':
                return _tela_busca_salva(call, atualizar)
            if cmd == 'A':
                return _tela_guia(call)
            if cmd == 'A1':
                return _tela_app(call, num(0)) if a else _tela_apps(call)
            if cmd == 'A2':
                return _tela_por_campeonato(call)
        except Exception as e:
            _ultimo_erro = f'{type(e).__name__}: {e}'
            print(f'[entretenimento_jogos] {call.data}: {_ultimo_erro}')
            try:
                _tela_erro(call, 'Algo deu errado ao abrir esta tela.', call.data, 'ent_jogos')
            except Exception:
                pass

    # ---------- admin: testar os campeonatos configurados ----------
    @bot.message_handler(commands=['testarligas'])
    def _cmd_testar(message):
        if not ent._is_admin(message.from_user.id):
            return bot.reply_to(message, '🚫 Acesso Negado!')
        bot.reply_to(message, '🔎 Testando os campeonatos na ESPN... (uns 20 segundos)')

        def trabalho():
            hoje = _agora().date()
            ligas = _ligas()

            def testa(l):
                try:
                    r = _get(l['slug'], 'scoreboard', {'dates': f'{hoje:%Y%m%d}'})
                    if r.status_code == 200:
                        n = len(r.json().get('events') or [])
                        return f"✅ {l['slug']} — {n} jogo(s) hoje"
                    return f"❌ {l['slug']} — HTTP {r.status_code}"
                except Exception as e:
                    return f"❌ {l['slug']} — {type(e).__name__}"
            with ThreadPoolExecutor(max_workers=10) as ex:
                linhas = list(ex.map(testa, ligas))
            try:
                r = _get('bra.1', 'scoreboard', {'dates': f'{hoje:%Y%m%d}-{hoje + timedelta(days=1):%Y%m%d}'})
                linhas.append(f'\n📅 Intervalo de datas: {"OK" if r.status_code == 200 else "recusado (HTTP " + str(r.status_code) + ") — uso dia a dia"}')
            except Exception as e:
                linhas.append(f'\n📅 Intervalo de datas: erro {type(e).__name__}')
            ruins = sum(1 for x in linhas if x.startswith('❌'))
            cab = f'🔎 <b>Teste dos campeonatos</b>: {len(ligas) - ruins}/{len(ligas)} responderam.\n' \
                  '<i>❌ = slug errado ou ESPN sem esse campeonato (o bot simplesmente ignora).</i>\n\n'
            texto = cab + '\n'.join(linhas)
            for i in range(0, len(texto), 3800):
                try:
                    bot.send_message(message.chat.id, texto[i:i + 3800], parse_mode='HTML')
                except Exception:
                    pass
        threading.Thread(target=trabalho, daemon=True).start()

    if not _iniciou_thread:
        _iniciou_thread = True
        threading.Thread(target=_loop_avisos, daemon=True).start()

    print('[entretenimento_jogos] Jogos completo iniciado (ao vivo, países, tabela, onde assistir, times, avisos).')
