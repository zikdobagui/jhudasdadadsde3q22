# -*- coding: utf-8 -*-
"""
WEBAPP_ENTRETENIMENTO.PY — 🎮 ENTRETENIMENTO do site (igual ao botão do bot).

Reaproveita os MESMOS módulos do bot (entretenimento.py, entretenimento_midia.py,
entretenimento_jogos.py): mesma chave do TMDB, mesmas plataformas/ligas do
database/entretenimento_config.json, mesmo cache e mesmos textos de "onde passa".
O que o admin ligar/desligar em /entretenimento no bot vale para o site.

Rotas (todas POST, exigem login como o resto do site):
  /api/ent/inicio    plataformas, campeonatos, países e flags
  /api/ent/lista     filmes/séries (em cartaz, em breve, por plataforma)
  /api/ent/detalhe   detalhe de um filme/série + onde assistir
  /api/ent/buscar    pesquisar filme/série por nome
  /api/ent/jogos     jogos por modo (ao vivo, principais, Brasil, mundo, todos, país) e dia
  /api/ent/jogo      detalhe de um jogo (placar, gols, cartões, onde passa)
  /api/ent/tabela    classificação de um campeonato
  /api/ent/time      jogos de um time (pesquisa e "meus times")
  /api/ent/guia      guia de apps/canais para assistir futebol

Botões de compra: cada plataforma/app tem a lista de produtos da loja que combinam
com ele (campo "loja"), e o site abre a compra direto.
"""
import re
import time
import unicodedata
from datetime import timedelta


class ErroEnt(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


# ------------------------------------------------------------- módulos do bot
def _mods():
    try:
        import entretenimento as ent
        import entretenimento_midia as mid
        import entretenimento_jogos as jg
    except Exception as e:
        raise ErroEnt('Entretenimento indisponível no momento.', 503) from e
    if getattr(mid, '_ent', None) is None or getattr(jg, '_ent', None) is None:
        raise ErroEnt('Entretenimento ainda está iniciando. Tente de novo em instantes.', 503)
    return ent, mid, jg


def _ligado(ent, chave):
    try:
        return bool(ent.ativo(chave))
    except Exception:
        return True


def _exigir(ent, chave):
    if not _ligado(ent, chave):
        raise ErroEnt('Este recurso está indisponível no momento.', 403)


# ------------------------------------------------- apps <-> produtos da loja
# provedor/app -> chave. A mesma chave no nome do produto da loja = botão de comprar.
_REGRAS = [
    ('netflix', ('netflix',)),
    ('prime', ('prime video', 'amazon prime', 'prime')),
    ('disney', ('disney', 'star+', 'starplus')),
    ('max', ('hbo', 'max')),
    ('globoplay', ('globoplay', 'globo play')),
    ('apple', ('apple tv', 'appletv')),
    ('paramount', ('paramount',)),
    ('crunchyroll', ('crunchyroll', 'crunchy')),
    ('youtube', ('youtube',)),
    ('spotify', ('spotify',)),
    ('deezer', ('deezer',)),
    ('telecine', ('telecine',)),
    ('mubi', ('mubi',)),
    ('looke', ('looke',)),
    ('premiere', ('premiere',)),
    ('sportv', ('sportv',)),
    ('dazn', ('dazn',)),
    ('espn', ('espn',)),
    ('canva', ('canva',)),
    ('vix', ('vix',)),
    ('claro', ('claro tv', 'clarotv', 'claro video')),
    ('directv', ('directv', 'direct tv', 'dgo')),
]
# "apps de futebol" do guia (campo k de jogos_apps) -> chave
_APP_CHAVE = {'globo': 'globoplay', 'prime': 'prime', 'espn': 'disney', 'paramount': 'paramount',
              'hbo': 'max', 'apple': 'apple', 'premiere': 'premiere', 'sportv': 'sportv', 'tnt': 'max'}


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ' '.join(''.join(c if c.isalnum() or c == '+' else ' ' for c in s.lower()).split())


def _chave(nome):
    n = f' {_norm(nome)} '
    for k, toks in _REGRAS:
        for t in toks:
            if f' {t} ' in n or (len(t) >= 5 and t in n):
                return k
    return None


class _Loja:
    """Casa um app/provedor com os produtos da loja (nome do estoque)."""

    def __init__(self, catalogo):
        try:
            prods = catalogo() or []
        except Exception:
            prods = []
        self.itens = []
        for p in prods:
            nome = p.get('nome') or ''
            if nome and int(p.get('estoque') or 0) > 0:
                self.itens.append((nome, _norm(nome), _chave(nome)))

    def achar(self, nome=None, chave=None):
        chave = chave or _chave(nome)
        pn = _norm(nome)
        out = []
        for nm, n, k in self.itens:
            if (chave and k == chave) or (not chave and len(pn) >= 4 and pn in n):
                out.append(nm)
        return out[:6]


# ------------------------------------------------------------------- filmes
def _plats(ent):
    return ent._config().get('filmes_plataformas', []) or []


def _poster(mid, p, larg='w342'):
    p = (p or '').strip()
    return mid.POSTER_BASE.replace('w500', larg) + p if p.startswith('/') else ''


def _item_titulo(mid, r, tipo):
    return {
        'id': r.get('id'), 'tipo': tipo, 'titulo': r.get('titulo') or '?',
        'ano': (r.get('data') or '')[:4], 'data': mid._data_br(r.get('data') or ''),
        'nota': r.get('nota') or 0, 'generos': r.get('generos') or [],
        'sinopse': (r.get('sinopse') or '')[:420], 'poster': _poster(mid, r.get('poster')),
    }


def _erro_catalogo(mid):
    motivo = (getattr(mid, '_ultimo_erro', {}) or {}).get('filmes') or ''
    if 'chave' in motivo.lower():
        return ErroEnt('O catálogo de filmes ainda não foi configurado pelo administrador.', 503)
    return ErroEnt('Não consegui buscar a lista agora. Toque em tentar de novo daqui a instantes.', 503)


def _inicio(catalogo):
    ent, mid, jg = _mods()
    loja = _Loja(catalogo)
    plats = [{'i': i, 'nome': p.get('nome') or '?', 'loja': loja.achar(p.get('nome'))}
             for i, p in enumerate(_plats(ent))]
    ligas = [{'i': i, 'slug': l['slug'], 'nome': l['nome'], 'pais': l.get('pais') or 'Outros',
              'bandeira': l.get('bandeira') or '🏆', 'grupo': l.get('grupo') or 'mundo',
              'destaque': bool(l.get('destaque'))} for i, l in enumerate(jg._ligas())]
    return {
        'geral': _ligado(ent, 'geral'),
        'filmes': _ligado(ent, 'assistir'),
        'jogos': _ligado(ent, 'jogos'),
        'plataformas': plats,
        'ligas': ligas,
        'paises': [{'nome': n, 'bandeira': b} for n, b in jg._paises()],
        'dias': {'min': jg.OFF_MIN, 'max': jg.OFF_MAX},
    }


def _lista(d, catalogo):
    ent, mid, jg = _mods()
    _exigir(ent, 'assistir')
    tipo = 's' if d.get('tipo') == 's' else 'f'
    origem = str(d.get('origem') or '')[:6]
    plats = _plats(ent)
    plat = None
    if origem in ('c', 'b'):
        if tipo == 's':
            raise ErroEnt('Origem inválida.')
    else:
        if origem[:1] not in ('p', 'n') or not origem[1:].isdigit() or int(origem[1:]) >= len(plats):
            raise ErroEnt('Origem inválida.')
        pl = plats[int(origem[1:])]
        plat = {'i': int(origem[1:]), 'nome': pl.get('nome') or '?',
                'loja': _Loja(catalogo).achar(pl.get('nome'))}
    dados = mid._series(origem) if tipo == 's' else mid._filmes(origem)
    if dados is None:
        raise _erro_catalogo(mid)
    nome = plat['nome'] if plat else ''
    if origem == 'c':
        titulo, sub = '🔥 Em cartaz', 'Filmes que estão nos cinemas agora.'
    elif origem == 'b':
        titulo, sub = '🗓️ Em breve', 'Próximos lançamentos nos cinemas.'
    elif origem[0] == 'p':
        titulo = f'🔥 {nome} — mais populares'
        sub = f"{'As séries' if tipo == 's' else 'Os filmes'} mais vistos agora no {nome}."
    else:
        titulo = f"🆕 {nome} — {'séries novas' if tipo == 's' else 'lançamentos'}"
        sub = f"{'Séries que estrearam' if tipo == 's' else 'Filmes novos que chegaram'} há pouco no {nome}."
    t = 't' if tipo == 's' else 'm'
    return {'titulo': titulo, 'sub': sub, 'plat': plat,
            'itens': [_item_titulo(mid, r, t) for r in dados]}


def _grupos_onde(mid, pv, loja):
    rot = (('flatrate', '✅ Na assinatura'), ('free', '🆓 Grátis'), ('ads', '🆓 Grátis (com anúncios)'),
           ('rent', '🎟️ Alugar'), ('buy', '🛒 Comprar'))
    out = []
    for chave, r in rot:
        nomes = (pv or {}).get(chave) or []
        if nomes:
            out.append({'k': chave, 'rotulo': r,
                        'apps': [{'nome': n, 'loja': loja.achar(n)} for n in nomes]})
    return out


def _detalhe(d, catalogo):
    ent, mid, jg = _mods()
    _exigir(ent, 'assistir')
    tipo = 't' if d.get('tipo') == 't' else 'm'
    try:
        tid = int(d.get('id'))
    except Exception:
        raise ErroEnt('Título inválido.')
    r = mid._detalhe_titulo(tipo, tid)
    if not r:
        raise _erro_catalogo(mid)
    loja = _Loja(catalogo)
    hoje = mid._agora_sp().date()
    aviso = ''
    onde = _grupos_onde(mid, r.get('prov'), loja)
    if not onde:
        aviso = 'Não encontrei em nenhum streaming no Brasil agora.'
        if tipo == 'm' and r.get('data'):
            if r['data'] > hoje.isoformat():
                aviso += f" Estreia prevista: {mid._data_br(r['data'])}."
            elif r['data'] >= (hoje - timedelta(days=100)).isoformat():
                aviso += ' Lançamento recente: pode estar em cartaz nos cinemas.'
    prox = r.get('proximo') or None
    if prox and prox.get('data'):
        prox = {'data': mid._data_br(prox['data']), 's': prox.get('s'), 'e': prox.get('e')}
    else:
        prox = None
    return {
        'tipo': tipo, 'id': r.get('id'), 'titulo': r.get('titulo'), 'original': r.get('original'),
        'ano': (r.get('data') or '')[:4], 'data': mid._data_br(r.get('data') or ''),
        'generos': r.get('generos') or [], 'nota': r.get('nota') or 0, 'votos': r.get('votos') or 0,
        'sinopse': r.get('sinopse') or 'Sem sinopse disponível.', 'duracao': r.get('duracao') or 0,
        'temporadas': r.get('temporadas') or 0, 'episodios': r.get('episodios') or 0,
        'status': r.get('status') or '', 'diretores': r.get('diretores') or [],
        'criadores': r.get('criadores') or [], 'elenco': r.get('elenco') or [],
        'redes': r.get('redes') or [], 'proximo': prox,
        'poster': _poster(mid, r.get('poster'), 'w500'), 'onde': onde, 'aviso': aviso,
    }


def _buscar(d, catalogo):
    ent, mid, jg = _mods()
    _exigir(ent, 'assistir')
    q = ' '.join(str(d.get('q') or '').split())[:80]
    if len(q) < 2:
        raise ErroEnt('Digite pelo menos 2 letras.')
    r = mid._titulos(q)
    if r is None:
        raise _erro_catalogo(mid)
    out = []
    for x in r:
        out.append({
            'id': x.get('id'), 'tipo': x.get('tipo'), 'titulo': x.get('titulo'),
            'ano': (x.get('data') or '')[:4], 'nota': x.get('nota') or 0,
            'poster': _poster(mid, x.get('poster')), 'onde': mid._resumo_plataformas(x.get('prov')),
        })
    return {'q': q, 'itens': out}


# -------------------------------------------------------------------- jogos
def _hora(jg, iso):
    ini = jg._dt_sp(iso)
    return (ini.strftime('%H:%M'), jg._fmt_dia(ini.date())) if ini else ('--:--', '')


def _jogo_resumo(jg, lidx, j):
    hora, dia = _hora(jg, j.get('inicio'))
    return {'id': j['id'], 'lidx': lidx, 'estado': j['estado'], 'rotulo': j['rotulo'],
            'casa': j['casa'], 'fora': j['fora'], 'pc': j['pc'], 'pf': j['pf'],
            'pen': j.get('pen') or '', 'hora': hora, 'dia': dia}


def _jogos(d):
    ent, mid, jg = _mods()
    _exigir(ent, 'jogos')
    modo = d.get('modo') if d.get('modo') in ('vivo', 'top', 'br', 'mundo', 'todos', 'pais') else 'top'
    try:
        off = int(d.get('off') or 0)
    except Exception:
        off = 0
    off = max(jg.OFF_MIN, min(jg.OFF_MAX, off))
    if d.get('atualizar'):
        jg._invalidar({l['slug'] for l in jg._ligas()})
    ligas = jg._ligas()
    if modo == 'pais':
        pais = str(d.get('pais') or '')[:60]
        lidxs = [i for i, l in enumerate(ligas) if (l.get('pais') or 'Outros') == pais]
        if not lidxs:
            raise ErroEnt('País não encontrado.')
    else:
        lidxs = jg._lidxs_modo('top' if modo == 'top' else modo)
    vivo = modo == 'vivo'
    if vivo:
        off = 0
    entradas, ok = jg._coletar(lidxs, off, vivo)
    if not ok:
        raise ErroEnt('Não consegui buscar os jogos agora. Toque em tentar de novo.', 503)
    grupos, ordem = {}, []
    for i, j in entradas:
        if i not in grupos:
            grupos[i] = []
            ordem.append(i)
        grupos[i].append(_jogo_resumo(jg, i, j))
    hoje = jg._agora().date()
    alvo = hoje + timedelta(days=off)
    return {
        'modo': modo, 'off': off, 'dia': jg._fmt_dia(alvo), 'rotulo': jg._rotulo_off(off),
        'dd': alvo.strftime('%d/%m'),
        'ant': (hoje + timedelta(days=off - 1)).strftime('%d/%m') if off - 1 >= jg.OFF_MIN else '',
        'prox': (hoje + timedelta(days=off + 1)).strftime('%d/%m') if off + 1 <= jg.OFF_MAX else '',
        'total': len(entradas), 'agora': jg._agora().strftime('%H:%M:%S'),
        'ligas': [{'lidx': i, 'nome': ligas[i]['nome'], 'bandeira': ligas[i].get('bandeira') or '🏆',
                   'jogos': grupos[i]} for i in ordem],
    }


def _separar_canais(tv):
    gratis, pagos = [], []
    for g in [x.strip() for x in str(tv or '').split('·') if x.strip()]:
        limpo = re.sub(r',\s*grátis', '', g)
        limpo = re.sub(r'\(\s*grátis\s*\)|grátis', '', limpo)
        limpo = re.sub(r'\(\s*[,·]?\s*\)', '', limpo).replace(' ,', ',').strip(' ,')
        grupo = g
        n = _norm(grupo)
        eh_gratis = any(k in n for k in ('gratis', 'youtube', 'tv aberta', 'aberta'))
        (gratis if eh_gratis else pagos).append(limpo or g)
    return gratis, pagos


def _apps_da_transmissao(jg, tv, loja):
    out = []
    for a in jg._apps_do_texto(tv):
        ch = _APP_CHAVE.get(a.get('k'))
        out.append({'k': a.get('k'), 'nome': a.get('nome'), 'emoji': a.get('emoji') or '📺',
                    'tipo': a.get('tipo') or '', 'texto': a.get('texto') or '',
                    'loja': loja.achar(chave=ch) if ch else []})
    return out


def _jogo(d, catalogo):
    ent, mid, jg = _mods()
    _exigir(ent, 'jogos')
    ligas = jg._ligas()
    try:
        lidx = int(d.get('lidx'))
    except Exception:
        raise ErroEnt('Jogo inválido.')
    if not 0 <= lidx < len(ligas):
        raise ErroEnt('Campeonato inválido.')
    liga = ligas[lidx]
    eid = str(d.get('id') or '')[:30]
    if not re.match(r'^[A-Za-z0-9_-]+$', eid):
        raise ErroEnt('Jogo inválido.')
    j = jg._achar_jogo(liga['slug'], eid, forcar=bool(d.get('atualizar')))
    if not j:
        raise ErroEnt('Não encontrei esse jogo agora. Ele pode ter saído da lista do dia.', 404)
    hora, dia = _hora(jg, j.get('inicio'))
    tv = jg._tv(liga['slug'])
    gratis, pagos = _separar_canais(tv)
    loja = _Loja(catalogo)
    return {
        'lidx': lidx, 'liga': liga['nome'], 'bandeira': liga.get('bandeira') or '🏆',
        'id': j['id'], 'estado': j['estado'], 'rotulo': j['rotulo'], 'hora': hora, 'dia': dia,
        'casa': j['casa'], 'fora': j['fora'], 'casa_full': j.get('casa_full') or j['casa'],
        'fora_full': j.get('fora_full') or j['fora'], 'pc': j['pc'], 'pf': j['pf'], 'pen': j.get('pen') or '',
        'estadio': j.get('estadio') or '', 'cidade': j.get('cidade') or '', 'fase': j.get('fase') or '',
        'detalhes': j.get('detalhes') or [],
        'tv': {'texto': tv, 'gratis': gratis, 'pagos': pagos},
        'apps': _apps_da_transmissao(jg, tv, loja),
        'nota': ent._config().get('jogos_canais_nota', ''),
    }


def _tabela(d):
    ent, mid, jg = _mods()
    _exigir(ent, 'jogos')
    ligas = jg._ligas()
    try:
        lidx = int(d.get('lidx'))
    except Exception:
        raise ErroEnt('Campeonato inválido.')
    if not 0 <= lidx < len(ligas):
        raise ErroEnt('Campeonato inválido.')
    liga = ligas[lidx]
    grupos = jg._cache(f'tb:{liga["slug"]}', 600, lambda: jg._buscar_tabela(liga['slug']))
    if grupos is None:
        raise ErroEnt('Não consegui buscar a classificação agora.', 503)
    out = []
    for g in grupos[:12]:
        linhas = []
        for l in g['linhas'][:30]:
            mk = jg._marca_zona(l.get('zona'))
            linhas.append({'pos': l['pos'], 'nome': l['nome'], 'pts': l['pts'], 'j': l['j'], 'v': l['v'],
                           'e': l['e'], 'd': l['d'], 'sg': l['sg'], 'zona': l.get('zona') or '',
                           'cor': {'🟩': 'v', '🟥': 'r', '🟦': 'a'}.get(mk, '')})
        out.append({'nome': g.get('nome') or '', 'linhas': linhas})
    return {'lidx': lidx, 'liga': liga['nome'], 'bandeira': liga.get('bandeira') or '🏆', 'grupos': out}


def _time(d):
    ent, mid, jg = _mods()
    _exigir(ent, 'jogos')
    q = ' '.join(str(d.get('q') or '').split())[:50]
    if len(q) < 2:
        raise ErroEnt('Digite pelo menos 2 letras do nome do time.')
    achados = jg._buscar_jogos_time(q)
    if achados is None:
        raise ErroEnt('Não consegui buscar agora. Tente de novo em instantes.', 503)
    ligas = jg._ligas()
    itens = []
    for i, j, nome in achados:
        r = _jogo_resumo(jg, i, j)
        r['liga'] = ligas[i]['nome']
        r['bandeira'] = ligas[i].get('bandeira') or '🏆'
        r['inicio'] = j.get('inicio') or ''
        r['time'] = nome
        itens.append(r)
    itens.sort(key=lambda x: x['inicio'])
    nomes = list(dict.fromkeys(x['time'] for x in itens))
    return {'q': q, 'times': nomes[:5], 'itens': itens[:60]}


def _guia(catalogo):
    ent, mid, jg = _mods()
    _exigir(ent, 'jogos')
    loja = _Loja(catalogo)
    cfg = ent._config()
    apps = []
    for a in cfg.get('jogos_apps') or []:
        ch = _APP_CHAVE.get(a.get('k'))
        apps.append({'k': a.get('k'), 'nome': a.get('nome'), 'emoji': a.get('emoji') or '📺',
                     'tipo': a.get('tipo') or '', 'texto': a.get('texto') or '',
                     'loja': loja.achar(chave=ch) if ch else []})
    camps = []
    for i, l in enumerate(jg._ligas()):
        tv = jg._tv(l['slug'])
        if tv:
            camps.append({'lidx': i, 'nome': l['nome'], 'bandeira': l.get('bandeira') or '🏆', 'tv': tv})
    return {'apps': apps, 'campeonatos': camps, 'nota': cfg.get('jogos_canais_nota', '')}


# ---------------------------------------------------------------- despacho
_ROTAS_PESADAS = {'/api/ent/buscar': 1.2, '/api/ent/time': 1.2}


def intervalo(rota):
    """Intervalo mínimo (s) entre pedidos do mesmo cliente nessa rota (anti-abuso)."""
    return _ROTAS_PESADAS.get(rota, 0.0)


def tratar(rota, d, catalogo):
    if rota == '/api/ent/inicio':
        return _inicio(catalogo)
    if rota == '/api/ent/lista':
        return _lista(d, catalogo)
    if rota == '/api/ent/detalhe':
        return _detalhe(d, catalogo)
    if rota == '/api/ent/buscar':
        return _buscar(d, catalogo)
    if rota == '/api/ent/jogos':
        return _jogos(d)
    if rota == '/api/ent/jogo':
        return _jogo(d, catalogo)
    if rota == '/api/ent/tabela':
        return _tabela(d)
    if rota == '/api/ent/time':
        return _time(d)
    if rota == '/api/ent/guia':
        return _guia(catalogo)
    raise ErroEnt('Rota inexistente.', 404)
