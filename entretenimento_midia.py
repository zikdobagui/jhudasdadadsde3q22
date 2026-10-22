# =============================================================================
# entretenimento_midia.py — 🎬 FILMES (plataformas/lançamentos) e ⚽ JOGOS
# -----------------------------------------------------------------------------
# Extensão do entretenimento.py (registrada por ele; nada a configurar em bot.py).
#
# 📺 SÉRIES POR PLATAFORMA: mesmas plataformas dos filmes (populares + estreias).
#
# 🎬 FILMES  (dentro de "O QUE ASSISTIR HOJE?")
#     🔥 Em cartaz · 🗓️ Em breve · 📺 Por plataforma (Netflix, Prime, Disney+...)
#     Fonte: TMDB (gratuito, precisa de uma chave). Lista cacheada por 6 h e
#     renovada sozinha — novos lançamentos entram automaticamente.
#     Chave: /tmdbkey SUA_CHAVE  (admin)  ou variável de ambiente TMDB_API_KEY.
#
# ⚽ JOGOS  → agora no módulo próprio entretenimento_jogos.py
#     (ao vivo, países, tabela, onde assistir, meus times, avisos).
#
# Plataformas de filmes: database/entretenimento_config.json ("filmes_plataformas").
# =============================================================================
import os
import json
import html
import time
import threading
import unicodedata
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pytz
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import entretenimento_jogos as jogos

TZ = pytz.timezone('America/Sao_Paulo')
ARQ_CACHE = os.path.join('database', 'entretenimento_cache.json')

# ----------------------------- PADRÕES ---------------------------------------
CONFIG_MIDIA = {
    "jogos": True,
    "tmdb_api_key": "",
    "tmdb_regiao": "BR",
    "filmes_cache_horas": 6,
    "filmes_plataformas": [
        {"nome": "Netflix", "id": 8},
        {"nome": "Prime Video", "id": 119},
        {"nome": "Disney+", "id": 337},
        {"nome": "Max", "id": 1899},
        {"nome": "Globoplay", "id": 307},
        {"nome": "Apple TV+", "id": 350},
        {"nome": "Paramount+", "id": 531},
        {"nome": "Crunchyroll", "id": 283},
    ],
}

CONFIG_MIDIA.update(jogos.CONFIG_JOGOS)   # ligas, canais, apps e avisos de jogos

GENEROS = {
    28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime",
    99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História",
    27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance",
    878: "Ficção científica", 10770: "Cinema TV", 53: "Suspense", 10752: "Guerra",
    37: "Faroeste",
}
GENEROS_TV = {
    10759: "Ação e Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário",
    18: "Drama", 10751: "Família", 10762: "Infantil", 9648: "Mistério", 10763: "Notícias",
    10764: "Reality", 10765: "Ficção e Fantasia", 10766: "Novela", 10767: "Talk show",
    10768: "Guerra e Política", 37: "Faroeste",
}
DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']

_lock = threading.RLock()
_mem = {}          # chave -> {"ts": epoch, "data": ...}
_ent = None        # módulo entretenimento (injetado em registrar)
_ultimo_erro = {}  # 'filmes'|'jogos' -> texto do último erro (aparece só para o admin)


# ----------------------------- CACHE -----------------------------------------
def _carregar_cache_disco():
    try:
        with open(ARQ_CACHE, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        if isinstance(dados, dict):
            # descarta listas antigas (sem pôster); as novas usam o prefixo tm:v2:
            _mem.update({k: v for k, v in dados.items() if k.startswith('tm:v2:')})
    except Exception:
        pass


def _salvar_cache_disco():
    """Só guarda as listas de filmes (leves). Jogos mudam rápido: ficam só em memória."""
    try:
        with _lock:
            filmes = {k: v for k, v in _mem.items() if k.startswith('tm:')}
        os.makedirs('database', exist_ok=True)
        tmp = ARQ_CACHE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(filmes, f, ensure_ascii=False)
        os.replace(tmp, ARQ_CACHE)
    except Exception as e:
        print(f'[entretenimento_midia] cache em disco falhou: {e}')


def _cache(chave, ttl, buscar):
    """Devolve o dado em cache se ainda válido; senão busca. Se a busca falhar,
    devolve o dado antigo (melhor mostrar algo levemente velho do que nada)."""
    agora = time.time()
    with _lock:
        item = _mem.get(chave)
    if item and agora - item['ts'] < ttl:
        return item['data']
    try:
        dados = buscar()
    except Exception as e:
        print(f'[entretenimento_midia] falha ao buscar {chave}: {type(e).__name__}: {e}')
        _ultimo_erro['filmes' if chave.startswith(('tm:', 'bs:')) else 'jogos'] = f'{type(e).__name__}: {e}'
        return item['data'] if item else None
    with _lock:
        _mem[chave] = {'ts': agora, 'data': dados}
    if chave.startswith('tm:'):
        _salvar_cache_disco()
    return dados


# ----------------------------- util ------------------------------------------
def _agora_sp():
    return datetime.now(TZ)


def _esc(v):
    return html.escape(str(v if v is not None else ''), quote=False)   # Telegram só aceita &lt; &gt; &amp;


def _fmt_dia(d):
    return f"{DIAS_SEMANA[d.weekday()]}, {d.strftime('%d/%m')}"


def _dt_sp(iso):
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ)
    except Exception:
        return None


# ----------------------------- PÔSTERES --------------------------------------
POSTER_BASE = 'https://image.tmdb.org/t/p/w500'
LIMITE_LEGENDA = 1000  # limite do Telegram é 1024; folga p/ os emojis premium (que aumentam o texto)


def _len_legenda(t):
    """Tamanho do texto DEPOIS da troca por emojis premium (é o que o Telegram conta)."""
    try:
        import premium_emojis
        return len(premium_emojis.replace_emojis(t, context="message"))
    except Exception:
        return len(t)


def _url_poster(f):
    p = (f.get('poster') or '').strip()
    return f'{POSTER_BASE}{p}' if p.startswith('/') else ''


def _texto_detalhe(emoji, f, linhas, sinopse, com_foto):
    """Monta o texto do detalhe. Com foto, o texto vira legenda (máx. 1024):
    a sinopse é encurtada para caber sem quebrar as tags HTML."""
    ano = f['data'][:4]

    def montar(sin):
        return (f"{emoji} <b>{_esc(f['titulo'])}</b>" + (f' ({ano})' if ano else '') + '\n\n<blockquote>' +
                '\n'.join(linhas) + f'</blockquote>\n\n📖 <i>{_esc(sin)}</i>')

    texto = montar(sinopse)
    while com_foto and _len_legenda(texto) > LIMITE_LEGENDA and len(sinopse) > 40:
        corte = max(40, len(sinopse) - max(30, _len_legenda(texto) - LIMITE_LEGENDA))
        sinopse = sinopse[:corte].rsplit(' ', 1)[0].rstrip(' ,.;:') + '…'
        texto = montar(sinopse)
    return texto


def _mostrar_detalhe(call, f, texto, markup):
    """Mostra o detalhe com o pôster (foto + legenda). Sem pôster, ou se o
    Telegram não conseguir baixar a imagem, cai para a tela só de texto."""
    url = _url_poster(f)
    if url:
        try:
            import fotos_menus
            r = fotos_menus.exibir_com_foto(_ent._bot, call.message.chat.id, call.message.message_id,
                                            url, texto, reply_markup=markup)
            if r is not None:
                return
        except Exception as e:
            print(f'[entretenimento_midia] pôster falhou ({f.get("titulo")}): {e}')
    _ent._mostrar(call, texto, markup)


def _tela_erro(call, mensagem, tentar_cb, voltar_cb, tipo):
    """Tela de erro SEMPRE visível (alerta pop-up some se o toque já foi respondido)."""
    texto = f'😕 <b>{mensagem}</b>\n\n<i>Toque em tentar de novo daqui a instantes.</i>'
    try:
        if _ent._is_admin(call.from_user.id):
            motivo = _ultimo_erro.get(tipo) or 'sem detalhe'
            texto += f'\n\n🛠️ <b>Só o admin vê:</b>\n<code>{_esc(motivo)[:300]}</code>'
    except Exception:
        pass
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔄 TENTAR DE NOVO', callback_data=tentar_cb))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data=voltar_cb))
    _ent._mostrar(call, texto, m)


# =============================================================================
# 🎬 FILMES (TMDB)
# =============================================================================
class SemChave(Exception):
    pass


def _tmdb(path, **params):
    cfg = _ent._config()
    chave = (cfg.get('tmdb_api_key') or os.environ.get('TMDB_API_KEY') or '').strip()
    if not chave:
        raise SemChave('chave do TMDB não configurada - use /tmdbkey SUA_CHAVE')
    headers = {}
    params.setdefault('language', 'pt-BR')
    if chave.startswith('eyJ'):                       # token v4 (Bearer)
        headers['Authorization'] = f'Bearer {chave}'
    else:                                             # chave v3
        params['api_key'] = chave
    r = requests.get(f'https://api.themoviedb.org/3{path}', params=params,
                     headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _enxugar(r):
    return {
        'id': r.get('id'),
        'titulo': r.get('title') or r.get('original_title') or '?',
        'data': r.get('release_date') or '',
        'nota': round(float(r.get('vote_average') or 0), 1),
        'votos': int(r.get('vote_count') or 0),
        'sinopse': (r.get('overview') or '').strip(),
        'generos': [GENEROS[g] for g in (r.get('genre_ids') or []) if g in GENEROS][:3],
        'poster': r.get('poster_path') or '',
    }


def _buscar_filmes(origem):
    """origem: 'c' (em cartaz) | 'b' (em breve) | 'p<i>' (populares na plataforma i)
    | 'n<i>' (lançamentos recentes na plataforma i)."""
    cfg = _ent._config()
    regiao = cfg.get('tmdb_regiao', 'BR')
    hoje = _agora_sp().date()
    if origem == 'c':
        j = _tmdb('/movie/now_playing', region=regiao, page=1)
        itens = j.get('results', [])
    elif origem == 'b':
        j = _tmdb('/movie/upcoming', region=regiao, page=1)
        itens = [r for r in j.get('results', []) if (r.get('release_date') or '') >= hoje.isoformat()]
        itens.sort(key=lambda r: r.get('release_date') or '9999')
    else:
        tipo, idx = origem[0], int(origem[1:])
        plat = cfg.get('filmes_plataformas', [])[idx]
        params = dict(watch_region=regiao, with_watch_providers=plat['id'],
                      with_watch_monetization_types='flatrate', include_adult='false', page=1)
        if tipo == 'p':
            params['sort_by'] = 'popularity.desc'
        else:
            params['sort_by'] = 'primary_release_date.desc'
            params['primary_release_date.lte'] = hoje.isoformat()
            params['primary_release_date.gte'] = (hoje - timedelta(days=150)).isoformat()
        itens = _tmdb('/discover/movie', **params).get('results', [])
    return [_enxugar(r) for r in itens[:10]]


def _filmes(origem):
    horas = float(_ent._config().get('filmes_cache_horas', 6))
    return _cache(f'tm:v2:{origem}', horas * 3600, lambda: _buscar_filmes(origem))


def _contexto_filmes(origem):
    cfg = _ent._config()
    if origem == 'c':
        return '🔥 <b>EM CARTAZ</b>', 'Filmes que estão nos cinemas agora.', 'ent_fm_c'
    if origem == 'b':
        return '🗓️ <b>EM BREVE</b>', 'Próximos lançamentos nos cinemas.', 'ent_fm_b'
    tipo, idx = origem[0], int(origem[1:])
    nome = cfg['filmes_plataformas'][idx]['nome']
    if tipo == 'p':
        return f'🔥 <b>{_esc(nome).upper()} — MAIS POPULARES</b>', f'Os filmes mais vistos agora no {_esc(nome)}.', f'ent_fm_p_{idx}'
    return f'🆕 <b>{_esc(nome).upper()} — LANÇAMENTOS</b>', f'Filmes novos que chegaram ao {_esc(nome)}.', f'ent_fm_n_{idx}'


def _data_br(iso):
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return ''


def _tela_lista_filmes(call, origem):
    itens = _filmes(origem)
    titulo, sub, voltar_cb = _contexto_filmes(origem)
    if not itens:
        return _tela_erro(call, 'Lista de filmes indisponível no momento.' if itens is None
                          else 'Nenhum filme encontrado agora.', voltar_cb, 'ent_assistir', 'filmes')

    linhas = []
    for n, f in enumerate(itens, 1):
        ano = f['data'][:4]
        if origem == 'b' and f['data']:
            extra = f"estreia {_data_br(f['data'])[:5]}"
        else:
            extra = f"⭐ {f['nota']}" if f['votos'] >= 5 else 'novo'
        linhas.append(f"{n}. <b>{_esc(f['titulo'])}</b>" + (f' ({ano})' if ano else '') + f' — {extra}')
    texto = (f'{titulo}\n<i>{sub}</i>\n\n<blockquote>' + '\n'.join(linhas) +
             '</blockquote>\n\n👇 <i>Toque no número para ver a sinopse.</i>')

    m = InlineKeyboardMarkup()
    nums = [InlineKeyboardButton(str(n), callback_data=f"ent_fm_d_{origem}_{f['id']}")
            for n, f in enumerate(itens, 1)]
    for i in range(0, len(nums), 5):
        m.row(*nums[i:i + 5])
    if origem[0] in 'pn' and origem not in ('c', 'b'):
        idx = int(origem[1:])
        m.row(InlineKeyboardButton('🔥 POPULARES', callback_data=f'ent_fm_p_{idx}'),
              InlineKeyboardButton('🆕 LANÇAMENTOS', callback_data=f'ent_fm_n_{idx}'))
        m.row(InlineKeyboardButton('📺 OUTRA PLATAFORMA', callback_data='ent_fm_plat'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    _ent._mostrar(call, texto, m)


def _tela_detalhe_filme(call, origem, fid):
    itens = _filmes(origem) or []
    f = next((x for x in itens if str(x['id']) == str(fid)), None)
    _, _, voltar_cb = _contexto_filmes(origem)
    if not f:
        return _tela_erro(call, 'Filme indisponível. Abra a lista novamente.', voltar_cb, 'ent_assistir', 'filmes')
    ano = f['data'][:4]
    sinopse = f['sinopse'] or 'Sinopse ainda não disponível em português.'
    if len(sinopse) > 650:
        sinopse = sinopse[:650].rsplit(' ', 1)[0] + '…'
    onde = ''
    if origem == 'c':
        onde = '🎟️ <b>Onde:</b> nos cinemas'
    elif origem == 'b':
        onde = f"🎟️ <b>Estreia:</b> {_data_br(f['data'])}"
    else:
        nome = _ent._config()['filmes_plataformas'][int(origem[1:])]['nome']
        onde = f'📺 <b>Onde assistir:</b> {_esc(nome)}'
    linhas = [onde]
    if f['generos']:
        linhas.append('🎭 <b>Gênero:</b> ' + _esc(', '.join(f['generos'])))
    if f['votos'] >= 5:
        linhas.append(f"⭐ <b>Nota:</b> {f['nota']}/10")
    texto = _texto_detalhe('🎬', f, linhas, sinopse, bool(_url_poster(f)))
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🛒 VER STREAMINGS NA LOJA', callback_data='servicos'))
    m.row(InlineKeyboardButton('↩️ VOLTAR À LISTA', callback_data=voltar_cb))
    _mostrar_detalhe(call, f, texto, m)


def _tela_plataformas(call):
    plats = _ent._config().get('filmes_plataformas', [])
    m = InlineKeyboardMarkup()
    botoes = [InlineKeyboardButton(p['nome'], callback_data=f'ent_fm_p_{i}') for i, p in enumerate(plats)]
    for i in range(0, len(botoes), 2):
        m.row(*botoes[i:i + 2])
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    texto = ('📺 <b>FILMES POR PLATAFORMA</b>\n'
             '<i>Escolha o streaming e veja o que está bombando e o que acabou de chegar.</i>')
    _ent._mostrar(call, texto, m)


# =============================================================================
# 📺 SÉRIES POR PLATAFORMA (TMDB) — mesmas plataformas dos filmes
# =============================================================================
def _enxugar_serie(r):
    return {
        'id': r.get('id'),
        'titulo': r.get('name') or r.get('original_name') or '?',
        'data': r.get('first_air_date') or '',
        'nota': round(float(r.get('vote_average') or 0), 1),
        'votos': int(r.get('vote_count') or 0),
        'sinopse': (r.get('overview') or '').strip(),
        'generos': [GENEROS_TV[g] for g in (r.get('genre_ids') or []) if g in GENEROS_TV][:3],
        'poster': r.get('poster_path') or '',
    }


def _buscar_series(origem):
    """origem: 'p<i>' (populares na plataforma i) | 'n<i>' (estreias recentes na plataforma i)."""
    cfg = _ent._config()
    regiao = cfg.get('tmdb_regiao', 'BR')
    hoje = _agora_sp().date()
    tipo, idx = origem[0], int(origem[1:])
    plat = cfg.get('filmes_plataformas', [])[idx]
    params = dict(watch_region=regiao, with_watch_providers=plat['id'],
                  with_watch_monetization_types='flatrate', include_adult='false', page=1)
    if tipo == 'p':
        params['sort_by'] = 'popularity.desc'
    else:
        params['sort_by'] = 'first_air_date.desc'
        params['first_air_date.lte'] = hoje.isoformat()
        params['first_air_date.gte'] = (hoje - timedelta(days=150)).isoformat()
    itens = _tmdb('/discover/tv', **params).get('results', [])
    return [_enxugar_serie(r) for r in itens[:10]]


def _series(origem):
    horas = float(_ent._config().get('filmes_cache_horas', 6))
    return _cache(f'tm:v2:tv:{origem}', horas * 3600, lambda: _buscar_series(origem))


def _contexto_series(origem):
    nome = _ent._config()['filmes_plataformas'][int(origem[1:])]['nome']
    if origem[0] == 'p':
        return (f'🔥 <b>{_esc(nome).upper()} — SÉRIES MAIS POPULARES</b>',
                f'As séries mais vistas agora no {_esc(nome)}.', f'ent_sr_p_{origem[1:]}')
    return (f'🆕 <b>{_esc(nome).upper()} — SÉRIES NOVAS</b>',
            f'Séries que estrearam há pouco no {_esc(nome)}.', f'ent_sr_n_{origem[1:]}')


def _tela_lista_series(call, origem):
    itens = _series(origem)
    titulo, sub, voltar_cb = _contexto_series(origem)
    if not itens:
        return _tela_erro(call, 'Lista de séries indisponível no momento.' if itens is None
                          else 'Nenhuma série encontrada agora.', voltar_cb, 'ent_sr_plat', 'filmes')
    linhas = []
    for n, f in enumerate(itens, 1):
        ano = f['data'][:4]
        extra = f"⭐ {f['nota']}" if f['votos'] >= 5 else 'novo'
        linhas.append(f"{n}. <b>{_esc(f['titulo'])}</b>" + (f' ({ano})' if ano else '') + f' — {extra}')
    texto = (f'{titulo}\n<i>{sub}</i>\n\n<blockquote>' + '\n'.join(linhas) +
             '</blockquote>\n\n👇 <i>Toque no número para ver a sinopse.</i>')
    m = InlineKeyboardMarkup()
    nums = [InlineKeyboardButton(str(n), callback_data=f"ent_sr_d_{origem}_{f['id']}")
            for n, f in enumerate(itens, 1)]
    for i in range(0, len(nums), 5):
        m.row(*nums[i:i + 5])
    idx = origem[1:]
    m.row(InlineKeyboardButton('🔥 POPULARES', callback_data=f'ent_sr_p_{idx}'),
          InlineKeyboardButton('🆕 ESTREIAS', callback_data=f'ent_sr_n_{idx}'))
    m.row(InlineKeyboardButton('📺 OUTRA PLATAFORMA', callback_data='ent_sr_plat'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    _ent._mostrar(call, texto, m)


def _tela_detalhe_serie(call, origem, sid):
    itens = _series(origem) or []
    f = next((x for x in itens if str(x['id']) == str(sid)), None)
    _, _, voltar_cb = _contexto_series(origem)
    if not f:
        return _tela_erro(call, 'Série indisponível. Abra a lista novamente.', voltar_cb, 'ent_sr_plat', 'filmes')
    ano = f['data'][:4]
    sinopse = f['sinopse'] or 'Sinopse ainda não disponível em português.'
    if len(sinopse) > 650:
        sinopse = sinopse[:650].rsplit(' ', 1)[0] + '…'
    nome = _ent._config()['filmes_plataformas'][int(origem[1:])]['nome']
    linhas = [f'📺 <b>Onde assistir:</b> {_esc(nome)}']
    if f['data']:
        linhas.append(f"🗓️ <b>Estreia:</b> {_data_br(f['data'])}")
    if f['generos']:
        linhas.append('🎭 <b>Gênero:</b> ' + _esc(', '.join(f['generos'])))
    if f['votos'] >= 5:
        linhas.append(f"⭐ <b>Nota:</b> {f['nota']}/10")
    texto = _texto_detalhe('📺', f, linhas, sinopse, bool(_url_poster(f)))
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🛒 VER STREAMINGS NA LOJA', callback_data='servicos'))
    m.row(InlineKeyboardButton('↩️ VOLTAR À LISTA', callback_data=voltar_cb))
    _mostrar_detalhe(call, f, texto, m)


def _tela_plataformas_series(call):
    plats = _ent._config().get('filmes_plataformas', [])
    m = InlineKeyboardMarkup()
    botoes = [InlineKeyboardButton(p['nome'], callback_data=f'ent_sr_p_{i}') for i, p in enumerate(plats)]
    for i in range(0, len(botoes), 2):
        m.row(*botoes[i:i + 2])
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    texto = ('📺 <b>SÉRIES POR PLATAFORMA</b>\n'
             '<i>Escolha o streaming e veja as séries que estão bombando e as estreias recentes.</i>')
    _ent._mostrar(call, texto, m)


# =============================================================================
# 🔍 PESQUISAR FILME / SÉRIE  (lupa)  — o cliente digita o nome e vê, em detalhe,
# onde passa (assinatura, grátis, alugar, comprar), nota, elenco, sinopse e pôster.
# Fonte: TMDB (+ dados de streaming do JustWatch, que o TMDB repassa).
# =============================================================================
_bot = None
_ultima_busca = {}      # uid -> {'q': texto, 'itens': [...]}

STATUS_TV = {'Returning Series': 'Em exibição', 'Ended': 'Finalizada', 'Canceled': 'Cancelada',
             'In Production': 'Em produção', 'Planned': 'Planejada', 'Pilot': 'Piloto'}
STATUS_FILME = {'Released': 'Lançado', 'Post Production': 'Em pós-produção', 'In Production': 'Em produção',
                'Planned': 'Planejado', 'Rumored': 'Rumor', 'Canceled': 'Cancelado'}


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in s.lower()).split())


def _buscar_titulos(q):
    j = _tmdb('/search/multi', query=q, include_adult='false', page=1)
    out = []
    for r in j.get('results', []):
        mt = r.get('media_type')
        if mt not in ('movie', 'tv'):
            continue
        out.append({
            'tipo': 'm' if mt == 'movie' else 't', 'id': r.get('id'),
            'titulo': r.get('title') or r.get('name') or r.get('original_title') or r.get('original_name') or '?',
            'data': r.get('release_date') or r.get('first_air_date') or '',
            'nota': round(float(r.get('vote_average') or 0), 1), 'votos': int(r.get('vote_count') or 0),
            'poster': r.get('poster_path') or '',
        })
        if len(out) >= 8:
            break
    regiao = _ent._config().get('tmdb_regiao', 'BR')

    def plataformas(it):
        try:
            pj = _tmdb(f"/{'movie' if it['tipo'] == 'm' else 'tv'}/{it['id']}/watch/providers")
            pv = (pj.get('results') or {}).get(regiao) or {}
            it['prov'] = {k: list(dict.fromkeys(x['provider_name'] for x in pv.get(k, []) if x.get('provider_name')))[:6]
                          for k in ('flatrate', 'free', 'ads', 'rent', 'buy')}
        except Exception:
            it['prov'] = None

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(plataformas, out))
    return out


def _resumo_plataformas(prov):
    """Uma linha curta: onde o título passa (para a lista de resultados)."""
    if prov is None:
        return 'toque para ver onde assistir'
    for chave, rotulo in (('flatrate', ''), ('free', 'Grátis: '), ('ads', 'Grátis: '),
                          ('rent', 'Alugar: '), ('buy', 'Comprar: ')):
        nomes = prov.get(chave) or []
        if nomes:
            extra = f' +{len(nomes) - 3}' if len(nomes) > 3 else ''
            return rotulo + ', '.join(nomes[:3]) + extra
    return 'sem streaming no Brasil agora'


def _titulos(q):
    return _cache('bs:q2:' + _norm(q), 3600, lambda: _buscar_titulos(q))


def _buscar_detalhe(tipo, tid):
    caminho = f"/{'movie' if tipo == 'm' else 'tv'}/{int(tid)}"
    r = _tmdb(caminho, append_to_response='credits,watch/providers')
    regiao = _ent._config().get('tmdb_regiao', 'BR')
    prov = ((r.get('watch/providers') or {}).get('results') or {}).get(regiao) or {}

    def nomes(chave):
        return list(dict.fromkeys(p['provider_name'] for p in prov.get(chave, []) if p.get('provider_name')))[:8]

    cred = r.get('credits') or {}
    prox = r.get('next_episode_to_air') or {}
    return {
        'tipo': tipo, 'id': r.get('id'),
        'titulo': r.get('title') or r.get('name') or '?',
        'original': r.get('original_title') or r.get('original_name') or '',
        'data': r.get('release_date') or r.get('first_air_date') or '',
        'ultima': r.get('last_air_date') or '',
        'generos': [g.get('name') for g in r.get('genres', []) if g.get('name')][:4],
        'nota': round(float(r.get('vote_average') or 0), 1), 'votos': int(r.get('vote_count') or 0),
        'sinopse': (r.get('overview') or '').strip(),
        'duracao': r.get('runtime') or ((r.get('episode_run_time') or [0])[0] if r.get('episode_run_time') else 0),
        'temporadas': r.get('number_of_seasons') or 0, 'episodios': r.get('number_of_episodes') or 0,
        'status': (STATUS_TV if tipo == 't' else STATUS_FILME).get(r.get('status'), r.get('status') or ''),
        'diretores': [c['name'] for c in cred.get('crew', []) if c.get('job') == 'Director' and c.get('name')][:2],
        'criadores': [c['name'] for c in r.get('created_by', []) if c.get('name')][:3],
        'elenco': [c['name'] for c in cred.get('cast', []) if c.get('name')][:5],
        'redes': [n['name'] for n in r.get('networks', []) if n.get('name')][:3],
        'proximo': {'data': prox.get('air_date') or '', 's': prox.get('season_number'), 'e': prox.get('episode_number')} if prox else None,
        'poster': r.get('poster_path') or '',
        'prov': {k: nomes(k) for k in ('flatrate', 'free', 'ads', 'rent', 'buy')},
    }


def _detalhe_titulo(tipo, tid):
    return _cache(f'bs:d:{tipo}:{tid}', 6 * 3600, lambda: _buscar_detalhe(tipo, tid))


def _linhas_onde_assistir(d):
    pv = d['prov']
    linhas = ['📺 <b>Onde assistir no Brasil:</b>']
    achou = False
    for chave, rotulo in (('flatrate', '✅ Na assinatura'), ('free', '🆓 Grátis'), ('ads', '🆓 Grátis (com anúncios)'),
                          ('rent', '🎟️ Alugar'), ('buy', '🛒 Comprar')):
        if pv.get(chave):
            achou = True
            linhas.append(f"{rotulo}: <b>{_esc(', '.join(pv[chave]))}</b>")
    if not achou:
        linhas.append('❌ Não encontrei em nenhum streaming no Brasil agora.')
        hoje = _agora_sp().date().isoformat()
        if d['tipo'] == 'm' and d['data']:
            if d['data'] > hoje:
                linhas.append(f"🎟️ Estreia prevista: {_data_br(d['data'])}")
            elif d['data'] >= (_agora_sp().date() - timedelta(days=100)).isoformat():
                linhas.append('🎟️ Lançamento recente: pode estar em cartaz nos cinemas.')
    return linhas


def _texto_busca(d):
    """Texto do detalhe. Com pôster vira legenda (máx. 1024): corta primeiro a sinopse e depois
    os itens de menor prioridade, mas NUNCA o 'onde assistir'."""
    ico = '🎬' if d['tipo'] == 'm' else '📺'
    ano = d['data'][:4]
    cabeca = f"{ico} <b>{_esc(d['titulo'])}</b>" + (f' ({ano})' if ano else '')
    principais = _linhas_onde_assistir(d)
    info = []
    if d['generos']:
        info.append('🎭 <b>Gênero:</b> ' + _esc(', '.join(d['generos'])))
    if d['votos'] >= 5:
        info.append(f"⭐ <b>Nota:</b> {d['nota']}/10")
    if d['tipo'] == 'm':
        if d['data']:
            info.append(f"🗓️ <b>Lançamento:</b> {_data_br(d['data'])}")
        if d['duracao']:
            h, mi = divmod(int(d['duracao']), 60)
            info.append(f"⏱️ <b>Duração:</b> {h}h{mi:02d}" if h else f'⏱️ <b>Duração:</b> {mi} min')
    else:
        if d['data']:
            info.append(f"🗓️ <b>Estreia:</b> {_data_br(d['data'])}")
        if d['temporadas']:
            info.append(f"📚 <b>{d['temporadas']} temporada(s)</b> · {d['episodios']} episódios")
        if d['status']:
            info.append(f"📡 <b>Situação:</b> {_esc(d['status'])}")
        px = d.get('proximo')
        if px and px.get('data'):
            info.append(f"🔜 <b>Próximo episódio:</b> {_data_br(px['data'])}"
                        + (f" (T{px['s']}E{px['e']})" if px.get('s') and px.get('e') else ''))
    extras = []
    if d['diretores']:
        extras.append('🎬 <b>Direção:</b> ' + _esc(', '.join(d['diretores'])))
    if d['criadores']:
        extras.append('✍️ <b>Criação:</b> ' + _esc(', '.join(d['criadores'])))
    if d['elenco']:
        extras.append('👥 <b>Elenco:</b> ' + _esc(', '.join(d['elenco'])))
    if d['redes']:
        extras.append('📡 <b>Canal/Rede:</b> ' + _esc(', '.join(d['redes'])))
    if d['original'] and _norm(d['original']) != _norm(d['titulo']):
        extras.append('🏷️ <b>Título original:</b> ' + _esc(d['original']))
    sinopse = d['sinopse'] or 'Sinopse ainda não disponível em português.'
    if len(sinopse) > 700:
        sinopse = sinopse[:700].rsplit(' ', 1)[0] + '…'
    rodape = '\n\n📡 <i>Streaming: JustWatch</i>'
    limite = LIMITE_LEGENDA if d.get('poster') else 4000

    def montar(sin):
        corpo = '\n'.join(principais + [''] + info + extras).rstrip()
        return f"{cabeca}\n\n<blockquote>{corpo}</blockquote>\n\n📖 <i>{_esc(sin)}</i>{rodape}"

    texto = montar(sinopse)
    while _len_legenda(texto) > limite:
        if len(sinopse) > 160:
            sinopse = sinopse[:max(160, len(sinopse) - max(40, _len_legenda(texto) - limite))].rsplit(' ', 1)[0].rstrip(' ,.;:') + '…'
        elif extras:
            extras.pop()
        elif len(sinopse) > 40:
            sinopse = sinopse[:max(40, len(sinopse) - max(30, _len_legenda(texto) - limite))].rsplit(' ', 1)[0].rstrip(' ,.;:') + '…'
        elif info:
            info.pop()
        else:
            break
        texto = montar(sinopse)
    return texto


def _montar_resultados(q, itens):
    m = InlineKeyboardMarkup()
    if not itens:
        texto = (f'🔍 <b>RESULTADOS PARA “{_esc(q)}”</b>\n\n😕 <b>Não encontrei nenhum filme ou série</b> com esse nome.\n\n'
                 '<i>Confira a escrita ou tente só uma parte do nome.</i>')
    else:
        linhas = []
        for n, it in enumerate(itens, 1):
            ano = it['data'][:4]
            ico, tipo = ('🎬', 'Filme') if it['tipo'] == 'm' else ('📺', 'Série')
            nota = f" · ⭐ {it['nota']}" if it['votos'] >= 5 else ''
            linhas.append(f"{n}. {ico} <b>{_esc(it['titulo'])}</b>" + (f' ({ano})' if ano else '') + f' — {tipo}{nota}'
                          + f"\n    📺 {_esc(_resumo_plataformas(it.get('prov')))}")
        texto = (f'🔍 <b>RESULTADOS PARA “{_esc(q)}”</b>\n\n<blockquote>' + '\n'.join(linhas) +
                 '</blockquote>\n\n👇 <i>Toque no número para ver <b>onde assistir</b>, sinopse e detalhes.</i>')
        nums = [InlineKeyboardButton(str(n), callback_data=f"ent_bs_d_{it['tipo']}_{it['id']}")
                for n, it in enumerate(itens, 1)]
        for i in range(0, len(nums), 4):
            m.row(*nums[i:i + 4])
    m.row(InlineKeyboardButton('🔍 NOVA PESQUISA', callback_data='ent_bs_q'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    return texto, m


def _pedir_busca(call):
    chat = call.message.chat.id
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('↩️ CANCELAR', callback_data='ent_assistir'))
    texto = ('🔍 <b>PESQUISAR FILME OU SÉRIE</b>\n\n'
             '✍️ <b>Digite o nome</b> do filme ou da série e envie.\n\n'
             '<blockquote>Ex.: Interestelar · La Casa de Papel · Breaking Bad · Homem-Aranha</blockquote>\n'
             '<i>Mostro em qual plataforma passa, nota, elenco, sinopse e o pôster.</i>')
    _ent._mostrar(call, texto, m)
    _aguardar_busca(chat)


def _aguardar_busca(chat):
    try:
        _bot.clear_step_handler_by_chat_id(chat)
    except Exception:
        pass
    _bot.register_next_step_handler_by_chat_id(chat, _receber_busca, time.time())


def _botoes_erro_busca():
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔍 TENTAR OUTRA PESQUISA', callback_data='ent_bs_q'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    return m


def _receber_busca(message, t0):
    chat = message.chat.id
    if time.time() - t0 > 300:                      # esperou demais: trata como mensagem comum
        _bot.process_new_messages([message])
        return
    txt = getattr(message, 'text', None)
    if txt and txt.startswith('/'):                 # comando: deixa o bot executar normalmente
        _bot.process_new_messages([message])
        return
    if not txt:
        _bot.send_message(chat, '✍️ Envie o nome do filme ou série em <b>texto</b>.', parse_mode='HTML')
        return _aguardar_busca(chat)
    q = ' '.join(txt.split())[:60]
    if len(_norm(q)) < 2:
        _bot.send_message(chat, '✍️ Digite pelo menos <b>2 letras</b> do nome.', parse_mode='HTML')
        return _aguardar_busca(chat)
    espera = _bot.send_message(chat, f'🔎 Procurando <b>{_esc(q)}</b>…', parse_mode='HTML')
    try:
        _bot.delete_message(chat, message.message_id)
    except Exception:
        pass
    itens = None
    try:
        itens = _titulos(q)
    except Exception as e:
        print(f'[entretenimento_midia] busca "{q}": {type(e).__name__}: {e}')
    if itens is None:
        _bot.edit_message_text('😕 <b>Não consegui pesquisar agora.</b>\n\n<i>Tente de novo daqui a instantes.</i>',
                               chat, espera.message_id, parse_mode='HTML', reply_markup=_botoes_erro_busca())
        return
    _ultima_busca[message.from_user.id] = {'q': q, 'itens': itens}
    texto, m = _montar_resultados(q, itens)
    _bot.edit_message_text(texto, chat, espera.message_id, parse_mode='HTML', reply_markup=m)


def _tela_resultados_salvos(call):
    b = _ultima_busca.get(call.from_user.id)
    if not b:
        return _pedir_busca(call)
    texto, m = _montar_resultados(b['q'], b['itens'])
    _ent._mostrar(call, texto, m)


def _tela_detalhe_busca(call, tipo, tid):
    try:
        d = _detalhe_titulo(tipo, tid)
    except Exception:
        d = None
    if not d:
        m = InlineKeyboardMarkup()
        m.row(InlineKeyboardButton('🔄 TENTAR DE NOVO', callback_data=call.data))
        m.row(InlineKeyboardButton('↩️ VOLTAR AOS RESULTADOS', callback_data='ent_bs_r'))
        return _ent._mostrar(call, '😕 <b>Não consegui abrir este título agora.</b>\n\n<i>Tente de novo daqui a instantes.</i>', m)
    texto = _texto_busca(d)
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🛒 VER STREAMINGS NA LOJA', callback_data='servicos'))
    m.row(InlineKeyboardButton('↩️ VOLTAR AOS RESULTADOS', callback_data='ent_bs_r'),
          InlineKeyboardButton('🔍 NOVA PESQUISA', callback_data='ent_bs_q'))
    _mostrar_detalhe(call, d, texto, m)


# =============================================================================
# REGISTRO
# =============================================================================
def registrar(bot, ent):
    global _ent, _bot
    _ent, _bot = ent, bot
    _carregar_cache_disco()

    def guarda(call, chave):
        if not ent.ativo(chave):
            ent._alerta(call, 'Este recurso está indisponível no momento.')
            return False
        return True

    # ---------- filmes ----------
    @bot.callback_query_handler(func=lambda c: c.data in ('ent_fm_c', 'ent_fm_b', 'ent_fm_plat'))
    def _cb_filmes(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        if call.data == 'ent_fm_plat':
            return _tela_plataformas(call)
        _tela_lista_filmes(call, call.data.replace('ent_fm_', '', 1))

    @bot.callback_query_handler(func=lambda c: c.data.startswith(('ent_fm_p_', 'ent_fm_n_')))
    def _cb_filmes_plataforma(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        try:
            _, _, tipo, idx = call.data.split('_')
            idx = int(idx)
            if not 0 <= idx < len(ent._config().get('filmes_plataformas', [])):
                return
        except Exception:
            return
        _tela_lista_filmes(call, f'{tipo}{idx}')

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_fm_d_'))
    def _cb_filme_detalhe(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        try:
            _, _, _, origem, fid = call.data.split('_')
        except Exception:
            return
        _tela_detalhe_filme(call, origem, fid)

    # ---------- séries ----------
    @bot.callback_query_handler(func=lambda c: c.data == 'ent_sr_plat')
    def _cb_series_plat(call):
        if guarda(call, 'assistir'):
            ent._ok(call)
            _tela_plataformas_series(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith(('ent_sr_p_', 'ent_sr_n_')))
    def _cb_series_lista(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        try:
            _, _, tipo, idx = call.data.split('_')
            idx = int(idx)
            if not 0 <= idx < len(ent._config().get('filmes_plataformas', [])):
                return
        except Exception:
            return
        _tela_lista_series(call, f'{tipo}{idx}')

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_sr_d_'))
    def _cb_serie_detalhe(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        try:
            _, _, _, origem, sid = call.data.split('_')
        except Exception:
            return
        _tela_detalhe_serie(call, origem, sid)

    # ---------- 🔍 pesquisa de filme/série ----------
    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_bs_'))
    def _cb_busca(call):
        if not guarda(call, 'assistir'):
            return
        ent._ok(call)
        if call.data == 'ent_bs_q':
            return _pedir_busca(call)
        if call.data == 'ent_bs_r':
            return _tela_resultados_salvos(call)
        if call.data.startswith('ent_bs_d_'):
            try:
                _, _, _, tipo, tid = call.data.split('_')
                int(tid)
            except Exception:
                return
            if tipo in ('m', 't'):
                _tela_detalhe_busca(call, tipo, tid)

    # ---------- jogos (módulo próprio) ----------
    jogos.registrar(bot, ent)

    # ---------- admin: chave do TMDB ----------
    @bot.message_handler(commands=['tmdbkey'])
    def _cmd_tmdbkey(message):
        if not ent._is_admin(message.from_user.id):
            return bot.reply_to(message, '🚫 Acesso Negado!')
        partes = (message.text or '').split(maxsplit=1)
        if len(partes) < 2 or not partes[1].strip():
            return bot.reply_to(
                message,
                '🎬 <b>Chave do TMDB</b>\n\nUse: <code>/tmdbkey SUA_CHAVE</code>\n'
                'Crie grátis em themoviedb.org → Configurações → API.',
                parse_mode='HTML')
        with ent._lock:
            cfg = ent._ler(ent.ARQ_CONFIG, dict(ent.CONFIG_PADRAO))
            cfg['tmdb_api_key'] = partes[1].strip()
            ent._gravar(ent.ARQ_CONFIG, cfg)
        with _lock:                                  # força renovar as listas na próxima abertura
            for k in [k for k in _mem if k.startswith('tm:')]:
                _mem.pop(k, None)
        try:
            bot.delete_message(message.chat.id, message.message_id)   # não deixa a chave no chat
        except Exception:
            pass
        bot.send_message(message.chat.id, '✅ Chave do TMDB salva. As listas de filmes já vão carregar.')

    print('[Entretenimento] Extensão iniciada (filmes por plataforma/lançamentos + jogos).')
