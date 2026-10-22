# =============================================================================
# entretenimento.py — 🎮 ENTRETENIMENTO (botão do menu inicial)
# -----------------------------------------------------------------------------
# Submenu pensado para o cliente VOLTAR ao bot todo dia (e comprar mais):
#
#   🎬 O QUE ASSISTIR HOJE?  -> sugere filme/série/anime aleatório + atalho
#                               "🛒 Ver streamings" (leva direto para a loja).
#   🎰 ROLETA DA SORTE       -> 1 giro grátis por dia, prêmio em saldo.
#                               Só quem já comprou gira (evita farm de contas).
#   🧠 QUIZ FILMES & SÉRIES  -> 5 perguntas por dia, ganha pontos e entra no
#                               ranking (você pode premiar o Top 1 do mês).
#
# Arquivos criados automaticamente em database/ (todos editáveis à mão):
#   entretenimento_config.json    -> liga/desliga, prêmios e pesos da roleta
#   entretenimento_catalogo.json  -> lista de filmes/séries/animes sugeridos
#   entretenimento_quiz.json      -> perguntas do quiz
#   entretenimento_usuarios.json  -> progresso de cada cliente
#
# Admin: /entretenimento  (liga/desliga cada parte pelo próprio Telegram)
# Registro: entretenimento.registrar_handlers(bot)  (feito em bot.py)
# =============================================================================
import os
import json
import html
import time
import random
import sys
import threading
from datetime import datetime

import pytz
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import central as api
import database
import entretenimento_midia as midia

DB_DIR = 'database'
ARQ_CONFIG = os.path.join(DB_DIR, 'entretenimento_config.json')
ARQ_CATALOGO = os.path.join(DB_DIR, 'entretenimento_catalogo.json')
ARQ_QUIZ = os.path.join(DB_DIR, 'entretenimento_quiz.json')
ARQ_USUARIOS = os.path.join(DB_DIR, 'entretenimento_usuarios.json')

CHAVE_FOTO = 'entretenimento'   # /setfotomenu -> foto opcional do submenu
_lock = threading.RLock()
_rng = random.SystemRandom()
_bot = None
_ultima_sugestao = {}           # user_id -> título (evita repetir seguido)

# ----------------------------- DEFAULTS --------------------------------------
CONFIG_PADRAO = {
    "geral": True,
    "assistir": True,
    "roleta": True,
    "quiz": True,
    "roleta_exige_compra": True,
    "roleta_notificar_admin_a_partir_de": 2.0,
    "roleta_premios": [
        {"valor": 0.0, "peso": 55},
        {"valor": 0.25, "peso": 25},
        {"valor": 0.5, "peso": 12},
        {"valor": 1.0, "peso": 6},
        {"valor": 2.0, "peso": 2},
    ],
    "quiz_perguntas_por_dia": 5,
    "quiz_pontos_por_acerto": 10,
}

CONFIG_PADRAO.update(midia.CONFIG_MIDIA)   # jogos, TMDB, ligas e plataformas

CATALOGO_PADRAO = [
    # ---------------- FILMES ----------------
    {"titulo": "Interestelar", "tipo": "filme", "genero": "Ficção científica", "ano": 2014,
     "sinopse": "Exploradores atravessam um buraco de minhoca em busca de um novo lar para a humanidade."},
    {"titulo": "Parasita", "tipo": "filme", "genero": "Suspense", "ano": 2019,
     "sinopse": "Uma família pobre se infiltra aos poucos na vida de uma família rica. Venceu o Oscar de Melhor Filme."},
    {"titulo": "Os Vingadores", "tipo": "filme", "genero": "Ação", "ano": 2012,
     "sinopse": "Os maiores heróis da Marvel se unem pela primeira vez para enfrentar Loki."},
    {"titulo": "Divertida Mente", "tipo": "filme", "genero": "Animação", "ano": 2015,
     "sinopse": "As emoções de uma garota de 11 anos vivem uma grande aventura dentro da cabeça dela."},
    {"titulo": "Matrix", "tipo": "filme", "genero": "Ficção científica", "ano": 1999,
     "sinopse": "Um hacker descobre que a realidade em que vive é uma simulação."},
    {"titulo": "Gladiador", "tipo": "filme", "genero": "Ação / Drama", "ano": 2000,
     "sinopse": "Um general romano traído busca vingança dentro da arena."},
    {"titulo": "A Origem", "tipo": "filme", "genero": "Ficção científica", "ano": 2010,
     "sinopse": "Ladrões invadem sonhos para plantar uma ideia na mente de um empresário."},
    {"titulo": "O Poderoso Chefão", "tipo": "filme", "genero": "Crime / Drama", "ano": 1972,
     "sinopse": "A saga de uma poderosa família mafiosa italiana nos Estados Unidos."},
    {"titulo": "Ilha do Medo", "tipo": "filme", "genero": "Suspense", "ano": 2010,
     "sinopse": "Um agente federal investiga o sumiço de uma paciente em um hospital psiquiátrico numa ilha."},
    {"titulo": "Coco", "tipo": "filme", "genero": "Animação", "ano": 2017,
     "sinopse": "Um menino viaja à Terra dos Mortos para descobrir a história da própria família."},
    {"titulo": "De Volta para o Futuro", "tipo": "filme", "genero": "Aventura", "ano": 1985,
     "sinopse": "Um adolescente viaja no tempo em um DeLorean e precisa garantir que os pais se apaixonem."},
    {"titulo": "Clube da Luta", "tipo": "filme", "genero": "Drama / Suspense", "ano": 1999,
     "sinopse": "Um homem insone e um vendedor carismático criam um clube secreto de lutas."},
    {"titulo": "O Rei Leão", "tipo": "filme", "genero": "Animação", "ano": 1994,
     "sinopse": "O jovem Simba precisa enfrentar o passado para assumir seu lugar como rei."},
    {"titulo": "Shrek", "tipo": "filme", "genero": "Animação / Comédia", "ano": 2001,
     "sinopse": "Um ogro rabugento resgata uma princesa para recuperar o seu pântano."},
    # ---------------- SÉRIES ----------------
    {"titulo": "Stranger Things", "tipo": "serie", "genero": "Ficção científica / Terror", "ano": 2016,
     "sinopse": "Em Hawkins, um grupo de amigos enfrenta forças sobrenaturais após o sumiço de um garoto."},
    {"titulo": "Breaking Bad", "tipo": "serie", "genero": "Drama / Crime", "ano": 2008,
     "sinopse": "Um professor de química com câncer se torna produtor de drogas para sustentar a família."},
    {"titulo": "La Casa de Papel", "tipo": "serie", "genero": "Ação / Crime", "ano": 2017,
     "sinopse": "Um grupo comandado pelo Professor planeja o maior assalto da história."},
    {"titulo": "Round 6", "tipo": "serie", "genero": "Suspense", "ano": 2021,
     "sinopse": "Endividados disputam jogos infantis mortais por um prêmio bilionário."},
    {"titulo": "Peaky Blinders", "tipo": "serie", "genero": "Drama / Crime", "ano": 2013,
     "sinopse": "A ascensão de uma gangue de Birmingham após a Primeira Guerra Mundial."},
    {"titulo": "Friends", "tipo": "serie", "genero": "Comédia", "ano": 1994,
     "sinopse": "Seis amigos e suas confusões em Nova York."},
    {"titulo": "The Office", "tipo": "serie", "genero": "Comédia", "ano": 2005,
     "sinopse": "O dia a dia de um escritório de papel, filmado como se fosse um documentário."},
    {"titulo": "Dark", "tipo": "serie", "genero": "Ficção científica", "ano": 2017,
     "sinopse": "Desaparecimentos numa cidade alemã revelam segredos de gerações e viagens no tempo."},
    {"titulo": "Black Mirror", "tipo": "serie", "genero": "Ficção científica", "ano": 2011,
     "sinopse": "Episódios independentes sobre o lado sombrio da tecnologia."},
    {"titulo": "Wandinha", "tipo": "serie", "genero": "Comédia / Mistério", "ano": 2022,
     "sinopse": "Wandinha Addams investiga mistérios na escola Nunca Mais."},
    {"titulo": "Game of Thrones", "tipo": "serie", "genero": "Fantasia", "ano": 2011,
     "sinopse": "Famílias nobres disputam o Trono de Ferro."},
    {"titulo": "The Boys", "tipo": "serie", "genero": "Ação / Sátira", "ano": 2019,
     "sinopse": "Vigilantes enfrentam super-heróis corruptos."},
    {"titulo": "The Last of Us", "tipo": "serie", "genero": "Drama / Ação", "ano": 2023,
     "sinopse": "Um sobrevivente escolta uma adolescente por um mundo devastado por uma infecção."},
    {"titulo": "Vikings", "tipo": "serie", "genero": "Drama histórico", "ano": 2013,
     "sinopse": "A saga do guerreiro Ragnar Lothbrok e sua busca por novas terras."},
    # ---------------- ANIMES ----------------
    {"titulo": "Naruto", "tipo": "anime", "genero": "Ação / Aventura", "ano": 2002,
     "sinopse": "Um jovem ninja sonha em se tornar o Hokage da sua vila."},
    {"titulo": "One Piece", "tipo": "anime", "genero": "Aventura", "ano": 1999,
     "sinopse": "Luffy e seu bando navegam atrás do tesouro lendário que dá o título de Rei dos Piratas."},
    {"titulo": "Death Note", "tipo": "anime", "genero": "Suspense", "ano": 2006,
     "sinopse": "Um estudante encontra um caderno capaz de matar quem tiver o nome escrito nele."},
    {"titulo": "Attack on Titan", "tipo": "anime", "genero": "Ação / Drama", "ano": 2013,
     "sinopse": "A humanidade vive atrás de muralhas para se proteger de titãs gigantes."},
    {"titulo": "Demon Slayer", "tipo": "anime", "genero": "Ação", "ano": 2019,
     "sinopse": "Tanjiro enfrenta demônios para curar a irmã que foi transformada em um deles."},
    {"titulo": "Dragon Ball Z", "tipo": "anime", "genero": "Ação", "ano": 1989,
     "sinopse": "Goku e seus amigos defendem a Terra de inimigos cada vez mais poderosos."},
    {"titulo": "Jujutsu Kaisen", "tipo": "anime", "genero": "Ação / Sobrenatural", "ano": 2020,
     "sinopse": "Um estudante entra no mundo dos feiticeiros para combater maldições."},
    {"titulo": "Fullmetal Alchemist: Brotherhood", "tipo": "anime", "genero": "Aventura / Fantasia", "ano": 2009,
     "sinopse": "Dois irmãos usam alquimia para tentar recuperar o que perderam."},
]

# Cada pergunta: id, pergunta, opcoes (4), correta (índice 0..3)
QUIZ_PADRAO = [
    {"id": 1, "pergunta": "Em qual cidade fictícia se passa a série Stranger Things?",
     "opcoes": ["Derry", "Hawkins", "Sunnydale", "Riverdale"], "correta": 1},
    {"id": 2, "pergunta": "Qual era a profissão de Walter White no início de Breaking Bad?",
     "opcoes": ["Médico", "Advogado", "Professor de química", "Policial"], "correta": 2},
    {"id": 3, "pergunta": "Quem dirigiu o filme Titanic (1997)?",
     "opcoes": ["Steven Spielberg", "James Cameron", "Christopher Nolan", "Ridley Scott"], "correta": 1},
    {"id": 4, "pergunta": "Qual filme da Pixar tem um rato que sonha em ser chef de cozinha?",
     "opcoes": ["Ratatouille", "Up", "Valente", "Carros"], "correta": 0},
    {"id": 5, "pergunta": "Como se chama a cafeteria onde os amigos de Friends se encontram?",
     "opcoes": ["Starbucks", "Central Perk", "Moe's", "Café Nervosa"], "correta": 1},
    {"id": 6, "pergunta": "Qual anime tem como protagonista Monkey D. Luffy?",
     "opcoes": ["Naruto", "Bleach", "One Piece", "Dragon Ball"], "correta": 2},
    {"id": 7, "pergunta": "De qual país é a série Round 6 (Squid Game)?",
     "opcoes": ["Japão", "China", "Tailândia", "Coreia do Sul"], "correta": 3},
    {"id": 8, "pergunta": "Que cor é o macacão usado pelos assaltantes de La Casa de Papel?",
     "opcoes": ["Vermelho", "Azul", "Preto", "Laranja"], "correta": 0},
    {"id": 9, "pergunta": "Qual filme foi o primeiro de língua não inglesa a ganhar o Oscar de Melhor Filme?",
     "opcoes": ["Roma", "Parasita", "O Labirinto do Fauno", "A Vida É Bela"], "correta": 1},
    {"id": 10, "pergunta": "Em Harry Potter, a qual casa de Hogwarts Harry pertence?",
     "opcoes": ["Sonserina", "Corvinal", "Lufa-Lufa", "Grifinória"], "correta": 3},
    {"id": 11, "pergunta": "Quantas Joias (Pedras) do Infinito existem no universo Marvel?",
     "opcoes": ["4", "5", "6", "7"], "correta": 2},
    {"id": 12, "pergunta": "Qual o nome do protagonista do anime Demon Slayer?",
     "opcoes": ["Tanjiro Kamado", "Zenitsu", "Inosuke", "Giyu"], "correta": 0},
    {"id": 13, "pergunta": "Qual o nome da peixinha esquecida de Procurando Nemo?",
     "opcoes": ["Marlin", "Dory", "Bruce", "Coral"], "correta": 1},
    {"id": 14, "pergunta": "Em Matrix, qual a cor da pílula que Neo escolhe?",
     "opcoes": ["Azul", "Verde", "Branca", "Vermelha"], "correta": 3},
    {"id": 15, "pergunta": "Qual o lema da Casa Stark em Game of Thrones?",
     "opcoes": ["Ouça-me rugir", "O Inverno está chegando", "Fogo e Sangue", "Nunca esquecemos"], "correta": 1},
    {"id": 16, "pergunta": "The Last of Us, da HBO, é baseada em qual tipo de mídia?",
     "opcoes": ["Livro", "Videogame", "Quadrinho", "Filme"], "correta": 1},
    {"id": 17, "pergunta": "Qual o nome do cowboy de brinquedo em Toy Story?",
     "opcoes": ["Buzz", "Rex", "Woody", "Slinky"], "correta": 2},
    {"id": 18, "pergunta": "Qual banda é retratada no filme Bohemian Rhapsody?",
     "opcoes": ["The Beatles", "Queen", "Led Zeppelin", "The Rolling Stones"], "correta": 1},
    {"id": 19, "pergunta": "Qual o nome do dragão de Como Treinar o Seu Dragão?",
     "opcoes": ["Banguela", "Smaug", "Drogon", "Falkor"], "correta": 0},
    {"id": 20, "pergunta": "Em qual cidade fictícia o Batman atua?",
     "opcoes": ["Metrópolis", "Gotham City", "Star City", "Central City"], "correta": 1},
    {"id": 21, "pergunta": "Qual o nome do robô apaixonado por EVA no filme da Pixar?",
     "opcoes": ["R2-D2", "Bumblebee", "WALL-E", "Baymax"], "correta": 2},
    {"id": 22, "pergunta": "Qual serviço de streaming exibe a série The Mandalorian?",
     "opcoes": ["Netflix", "Disney+", "Max", "Prime Video"], "correta": 1},
]

CATEGORIAS = {
    "filme": ("🎥", "FILME"),
    "serie": ("📺", "SÉRIE"),
    "anime": ("🍥", "ANIME"),
}


# ----------------------------- JSON helpers ----------------------------------
def _ler(caminho, padrao):
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return padrao


def _gravar(caminho, dados):
    os.makedirs(DB_DIR, exist_ok=True)
    tmp = caminho + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    os.replace(tmp, caminho)


def garantir_arquivos():
    """Cria os arquivos padrão na 1ª execução (nunca sobrescreve os existentes)."""
    with _lock:
        if not os.path.exists(ARQ_CONFIG):
            _gravar(ARQ_CONFIG, CONFIG_PADRAO)
        if not os.path.exists(ARQ_CATALOGO):
            _gravar(ARQ_CATALOGO, CATALOGO_PADRAO)
        if not os.path.exists(ARQ_QUIZ):
            _gravar(ARQ_QUIZ, QUIZ_PADRAO)
        if not os.path.exists(ARQ_USUARIOS):
            _gravar(ARQ_USUARIOS, {})


def _config():
    cfg = dict(CONFIG_PADRAO)
    cfg.update(_ler(ARQ_CONFIG, {}))
    return cfg


def ativo(chave='geral'):
    """True se o recurso está ligado. 'geral' desliga o botão do menu inteiro."""
    try:
        cfg = _config()
        if chave == 'geral':
            return bool(cfg.get('geral', True))
        return bool(cfg.get('geral', True)) and bool(cfg.get(chave, True))
    except Exception:
        return True


def _hoje():
    try:
        return datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%Y-%m-%d')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d')


def _brl(v):
    return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _carregar_usuarios():
    return _ler(ARQ_USUARIOS, {})


def _is_admin(user_id):
    try:
        return bool(api.Admin.verificar_admin(user_id)) or str(user_id) == str(api.CredentialsChange.id_dono())
    except Exception:
        return False


def _tem_compra(user_id):
    try:
        ud = database.load_user_data(user_id) or {}
        return len(ud.get('compras', [])) > 0
    except Exception:
        return False


# ----------------------------- UI helpers ------------------------------------
def _mostrar(call, texto, markup):
    """Troca a tela atual (funciona sobre a foto do menu inicial)."""
    chat_id, mid = call.message.chat.id, call.message.message_id
    try:
        import fotos_menus
        if fotos_menus.exibir_com_foto_opcional(_bot, chat_id, mid, CHAVE_FOTO, texto, reply_markup=markup):
            return
    except Exception as e:
        print(f"[entretenimento] foto opcional falhou: {e}")
    api.editar_menu_seguro(_bot, chat_id, mid, texto, reply_markup=markup)


def _editar_rapido(call, texto):
    """Edição sem teclado (usada na animação da roleta)."""
    chat_id, mid = call.message.chat.id, call.message.message_id
    try:
        if getattr(call.message, 'content_type', 'text') == 'photo':
            _bot.edit_message_caption(texto, chat_id=chat_id, message_id=mid, parse_mode='HTML')
        else:
            _bot.edit_message_text(texto, chat_id=chat_id, message_id=mid, parse_mode='HTML')
    except Exception:
        pass


def _nome(user):
    n = (user.first_name or '').strip() or 'Cliente'
    return html.escape(n)


def _alerta(call, texto):
    try:
        _bot.answer_callback_query(call.id, texto, show_alert=True)
    except Exception:
        pass


def _ok(call):
    try:
        _bot.answer_callback_query(call.id)
    except Exception:
        pass


# ----------------------------- MENU PRINCIPAL --------------------------------
def texto_menu():
    return (
        '🎮 <b>ENTRETENIMENTO</b>\n'
        '<i>Diversão, sorte e prêmios — de graça, todo dia.</i>\n'
        '\n'
        '✨ <b>O QUE TEM AQUI</b>\n'
        '<blockquote>'
        '├─ 🎬 <b>O que assistir hoje?</b> — lançamentos, filmes por streaming e dicas\n'
        '├─ ⚽ <b>Jogos</b> — placar ao vivo do Brasil e do mundo\n'
        '├─ 🎰 <b>Roleta da Sorte</b> — 1 giro grátis por dia, prêmio em saldo\n'
        '└─ 🧠 <b>Quiz</b> — acerte, some pontos e suba no ranking'
        '</blockquote>'
    )


def _abrir_menu(call):
    from menus import gerar_menu_entretenimento
    _mostrar(call, texto_menu(), gerar_menu_entretenimento())


def _voltar_markup(destino='ent_menu', rotulo='↩️ VOLTAR'):
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton(rotulo, callback_data=destino))
    return m


# ----------------------------- 🎬 ASSISTIR -----------------------------------
def _tela_assistir_inicio(call):
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🔍 PESQUISAR FILME OU SÉRIE', callback_data='ent_bs_q'))
    m.row(InlineKeyboardButton('🎥 FILME', callback_data='ent_ass_filme'),
          InlineKeyboardButton('📺 SÉRIE', callback_data='ent_ass_serie'))
    m.row(InlineKeyboardButton('🍥 ANIME', callback_data='ent_ass_anime'),
          InlineKeyboardButton('🎲 SURPREENDA-ME', callback_data='ent_ass_todos'))
    m.row(InlineKeyboardButton('🔥 EM CARTAZ', callback_data='ent_fm_c'),
          InlineKeyboardButton('🗓️ EM BREVE', callback_data='ent_fm_b'))
    m.row(InlineKeyboardButton('🎞️ FILMES POR PLATAFORMA', callback_data='ent_fm_plat'))
    m.row(InlineKeyboardButton('📺 SÉRIES POR PLATAFORMA', callback_data='ent_sr_plat'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_menu'))
    texto = (
        '🎬 <b>O QUE ASSISTIR HOJE?</b>\n'
        '<i>Lançamentos, filmes e séries de cada streaming ou uma sugestão aleatória.</i>\n'
        '\n'
        '<blockquote>├─ 🔍 <b>Pesquisar</b> o nome e ver em qual plataforma passa\n'
        '├─ 🔥 <b>Em cartaz</b> e 🗓️ <b>em breve</b> nos cinemas\n'
        '├─ 📺 <b>Filmes e séries por plataforma:</b> Netflix, Prime, Disney+, Max...\n'
        '└─ 🎲 <b>Sugestão rápida</b> de filme, série ou anime</blockquote>'
    )
    _mostrar(call, texto, m)


def _sugerir(call, tipo):
    itens = _ler(ARQ_CATALOGO, [])
    if tipo != 'todos':
        itens = [i for i in itens if i.get('tipo') == tipo]
    if not itens:
        _alerta(call, 'Nenhuma sugestão cadastrada nessa categoria ainda.')
        return
    uid = call.from_user.id
    candidatos = [i for i in itens if i.get('titulo') != _ultima_sugestao.get(uid)] or itens
    item = _rng.choice(candidatos)
    _ultima_sugestao[uid] = item.get('titulo')

    emoji, rotulo = CATEGORIAS.get(item.get('tipo'), ('🎬', 'TÍTULO'))
    ano = f" ({item['ano']})" if item.get('ano') else ''
    texto = (
        f"🎬 <b>SUGESTÃO DE HOJE</b>\n"
        f"\n"
        f"{emoji} <b>{html.escape(str(item.get('titulo', '')))}</b>{ano}\n"
        f"<blockquote>├─ <b>Tipo:</b> {rotulo}\n"
        f"└─ <b>Gênero:</b> {html.escape(str(item.get('genero', '-')))}</blockquote>\n"
        f"\n"
        f"📖 <i>{html.escape(str(item.get('sinopse', '')))}</i>\n"
        f"\n"
        f"🍿 <b>Quer assistir?</b> Veja os streamings disponíveis na nossa loja."
    )
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('🎲 OUTRA SUGESTÃO', callback_data=f'ent_ass_{tipo}'))
    m.row(InlineKeyboardButton('🛒 VER STREAMINGS', callback_data='servicos'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_assistir'))
    _mostrar(call, texto, m)


# ----------------------------- 🎰 ROLETA -------------------------------------
def _faixa_premios(cfg):
    valores = [float(p.get('valor', 0)) for p in cfg.get('roleta_premios', []) if float(p.get('valor', 0)) > 0]
    if not valores:
        return None
    return min(valores), max(valores)


def _tela_roleta(call):
    cfg = _config()
    uid = call.from_user.id
    u = _carregar_usuarios().get(str(uid), {})
    ja_girou = u.get('roleta_dia') == _hoje()
    faixa = _faixa_premios(cfg)
    faixa_txt = f"{_brl(faixa[0])} até {_brl(faixa[1])}" if faixa else 'prêmios surpresa'
    exige = bool(cfg.get('roleta_exige_compra', True))

    if ja_girou:
        status = '⏳ <b>Você já girou hoje.</b> Volte amanhã!'
    elif exige and not _tem_compra(uid):
        status = '🔒 <b>Liberada após a sua 1ª compra.</b>'
    else:
        status = '✅ <b>Seu giro de hoje está disponível!</b>'

    texto = (
        '🎰 <b>ROLETA DA SORTE</b>\n'
        '<i>Gire grátis uma vez por dia e ganhe saldo.</i>\n'
        '\n'
        '🏆 <b>PRÊMIOS</b>\n'
        f'<blockquote>├─ <b>Saldo de:</b> {faixa_txt}\n'
        '└─ <b>Giros:</b> 1 por dia (zera à meia-noite)</blockquote>\n'
        '\n'
        f'{status}'
    )
    m = InlineKeyboardMarkup()
    if not ja_girou:
        if exige and not _tem_compra(uid):
            m.row(InlineKeyboardButton('🛒 FAZER MINHA 1ª COMPRA', callback_data='servicos'))
        else:
            m.row(InlineKeyboardButton('🎰 GIRAR AGORA', callback_data='ent_girar'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_menu'))
    _mostrar(call, texto, m)


def _girar(call):
    uid = call.from_user.id
    cfg = _config()
    if not ativo('roleta'):
        return _alerta(call, 'A roleta está desligada no momento.')

    premio = None
    with _lock:
        usuarios = _carregar_usuarios()
        u = usuarios.setdefault(str(uid), {})
        hoje = _hoje()
        if u.get('roleta_dia') == hoje:
            return _alerta(call, '⏳ Você já girou hoje. Volte amanhã!')
        if cfg.get('roleta_exige_compra', True) and not _tem_compra(uid):
            return _alerta(call, '🔒 A roleta é liberada depois da sua 1ª compra.')

        premios = cfg.get('roleta_premios') or CONFIG_PADRAO['roleta_premios']
        pesos = [max(float(p.get('peso', 0)), 0) for p in premios]
        if sum(pesos) <= 0:
            return _alerta(call, 'Roleta sem prêmios configurados.')
        premio = _rng.choices(premios, weights=pesos, k=1)[0]
        valor = float(premio.get('valor', 0))

        u['roleta_dia'] = hoje          # marca ANTES de pagar (anti duplo clique)
        u['roleta_giros'] = int(u.get('roleta_giros', 0)) + 1
        u['nome'] = call.from_user.first_name or u.get('nome', '')
        _gravar(ARQ_USUARIOS, usuarios)
        if valor > 0:
            try:
                database.add_saldo(uid, valor)
                u['roleta_ganho_total'] = round(float(u.get('roleta_ganho_total', 0)) + valor, 2)
                _gravar(ARQ_USUARIOS, usuarios)
            except Exception as e:
                # falhou ao creditar -> devolve o giro para o cliente tentar de novo
                print(f"[entretenimento] erro ao creditar roleta ({uid}): {e}")
                u['roleta_dia'] = ''
                u['roleta_giros'] = max(int(u.get('roleta_giros', 1)) - 1, 0)
                _gravar(ARQ_USUARIOS, usuarios)
                return _alerta(call, '⚠️ Erro ao creditar o prêmio. Tente novamente.')

    _ok(call)
    simbolos = ['🍒', '🍋', '🔔', '⭐', '💎', '7️⃣']
    for _ in range(3):
        a, b, c = (_rng.choice(simbolos) for _ in range(3))
        _editar_rapido(call, f'🎰 <b>GIRANDO...</b>\n\n<b>[ {a} | {b} | {c} ]</b>')
        time.sleep(0.7)

    if valor > 0:
        s = _rng.choice(simbolos)
        texto = (
            f'🎰 <b>[ {s} | {s} | {s} ]</b>\n\n'
            f'🎉 <b>PARABÉNS, {_nome(call.from_user)}!</b>\n'
            f'<blockquote>├─ <b>Prêmio:</b> {_brl(valor)} de saldo\n'
            f'└─ <b>Já está na sua carteira</b> 💰</blockquote>\n\n'
            f'<i>Volte amanhã para girar de novo!</i>'
        )
        _avisar_admin_premio(call.from_user, valor, cfg)
    else:
        a, b, c = _rng.sample(simbolos, 3)
        texto = (
            f'🎰 <b>[ {a} | {b} | {c} ]</b>\n\n'
            f'😅 <b>Não foi dessa vez!</b>\n'
            f'<i>Amanhã tem mais um giro grátis. Boa sorte!</i>'
        )
    m = InlineKeyboardMarkup()
    if valor > 0:
        m.row(InlineKeyboardButton('🛒 USAR MEU SALDO', callback_data='servicos'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_menu'))
    _mostrar(call, texto, m)


def _avisar_admin_premio(user, valor, cfg):
    try:
        limite = float(cfg.get('roleta_notificar_admin_a_partir_de', 2.0))
        if valor < limite:
            return
        _bot.send_message(
            api.CredentialsChange.id_dono(),
            f"🎰 <b>Roleta: prêmio alto!</b>\n\n"
            f"👤 {_nome(user)} (<code>{user.id}</code>)\n"
            f"💰 Ganhou <b>{_brl(valor)}</b> de saldo",
            parse_mode='HTML')
    except Exception as e:
        print(f"[entretenimento] aviso ao admin falhou: {e}")


# ----------------------------- 🧠 QUIZ ---------------------------------------
def _perguntas_do_dia(u):
    if u.get('quiz_dia') != _hoje():
        return 0, []
    resp = u.get('quiz_respondidas', [])
    return len(resp), resp


def _tela_quiz(call):
    cfg = _config()
    limite = int(cfg.get('quiz_perguntas_por_dia', 5))
    pontos_acerto = int(cfg.get('quiz_pontos_por_acerto', 10))
    u = _carregar_usuarios().get(str(call.from_user.id), {})
    feitas, _ = _perguntas_do_dia(u)
    restantes = max(limite - feitas, 0)
    texto = (
        '🧠 <b>QUIZ FILMES &amp; SÉRIES</b>\n'
        '<i>Teste o que você sabe e entre para o ranking.</i>\n'
        '\n'
        '📊 <b>SEU PROGRESSO</b>\n'
        f'<blockquote>├─ <b>Pontos:</b> {int(u.get("quiz_pontos", 0))}\n'
        f'├─ <b>Acertos:</b> {int(u.get("quiz_acertos", 0))}\n'
        f'├─ <b>Perguntas hoje:</b> {feitas}/{limite}\n'
        f'└─ <b>Cada acerto vale:</b> {pontos_acerto} pontos</blockquote>'
    )
    m = InlineKeyboardMarkup()
    if restantes > 0:
        m.row(InlineKeyboardButton('▶️ JOGAR', callback_data='ent_qz_play'))
    else:
        texto += '\n\n⏳ <b>Você completou o quiz de hoje.</b> Volte amanhã!'
    m.row(InlineKeyboardButton('🏆 RANKING', callback_data='ent_qz_rank'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_menu'))
    _mostrar(call, texto, m)


def _jogar_quiz(call):
    cfg = _config()
    limite = int(cfg.get('quiz_perguntas_por_dia', 5))
    perguntas = _ler(ARQ_QUIZ, [])
    u = _carregar_usuarios().get(str(call.from_user.id), {})
    feitas, respondidas = _perguntas_do_dia(u)
    if feitas >= limite:
        _ok(call)
        return _tela_quiz(call)
    # Evita repetir perguntas já respondidas hoje; se acabou o banco, libera repetir
    pool = [q for q in perguntas if q.get('id') not in respondidas] or perguntas
    if not pool:
        return _alerta(call, 'Ainda não há perguntas cadastradas.')
    q = _rng.choice(pool)
    texto = (
        f'🧠 <b>PERGUNTA {feitas + 1}/{limite}</b>\n'
        f'\n'
        f'❓ <b>{html.escape(q["pergunta"])}</b>'
    )
    m = InlineKeyboardMarkup()
    letras = ['A', 'B', 'C', 'D']
    for i, op in enumerate(q['opcoes']):
        m.row(InlineKeyboardButton(f'{letras[i]}) {op}', callback_data=f'ent_qa_{q["id"]}_{i}'))
    _ok(call)
    _mostrar(call, texto, m)


def _responder_quiz(call):
    try:
        _, _, qid, idx = call.data.split('_')
        qid, idx = int(qid), int(idx)
    except Exception:
        return _ok(call)
    cfg = _config()
    limite = int(cfg.get('quiz_perguntas_por_dia', 5))
    pontos_acerto = int(cfg.get('quiz_pontos_por_acerto', 10))
    q = next((x for x in _ler(ARQ_QUIZ, []) if x.get('id') == qid), None)
    if not q or not (0 <= idx < len(q['opcoes'])):
        return _alerta(call, 'Pergunta indisponível.')

    uid = call.from_user.id
    with _lock:
        usuarios = _carregar_usuarios()
        u = usuarios.setdefault(str(uid), {})
        hoje = _hoje()
        if u.get('quiz_dia') != hoje:
            u['quiz_dia'] = hoje
            u['quiz_respondidas'] = []
        if len(u['quiz_respondidas']) >= limite:
            _ok(call)
            return _tela_quiz(call)
        if qid in u['quiz_respondidas']:
            return _alerta(call, 'Você já respondeu essa pergunta hoje.')
        acertou = (idx == int(q['correta']))
        u['quiz_respondidas'].append(qid)
        u['nome'] = call.from_user.first_name or u.get('nome', '')
        if acertou:
            u['quiz_pontos'] = int(u.get('quiz_pontos', 0)) + pontos_acerto
            u['quiz_acertos'] = int(u.get('quiz_acertos', 0)) + 1
        _gravar(ARQ_USUARIOS, usuarios)
        feitas = len(u['quiz_respondidas'])
        total = int(u.get('quiz_pontos', 0))

    _ok(call)
    certa = html.escape(q['opcoes'][int(q['correta'])])
    if acertou:
        texto = (f'✅ <b>ACERTOU!</b> +{pontos_acerto} pontos\n\n'
                 f'<blockquote>├─ <b>Resposta:</b> {certa}\n'
                 f'└─ <b>Seus pontos:</b> {total}</blockquote>')
    else:
        texto = (f'❌ <b>Errou!</b>\n\n'
                 f'<blockquote>├─ <b>Resposta certa:</b> {certa}\n'
                 f'└─ <b>Seus pontos:</b> {total}</blockquote>')
    m = InlineKeyboardMarkup()
    if feitas < limite:
        m.row(InlineKeyboardButton('▶️ PRÓXIMA PERGUNTA', callback_data='ent_qz_play'))
    else:
        texto += '\n\n🎉 <b>Quiz de hoje concluído!</b> Volte amanhã.'
    m.row(InlineKeyboardButton('🏆 RANKING', callback_data='ent_qz_rank'))
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_quiz'))
    _mostrar(call, texto, m)


def _ranking_quiz(call):
    usuarios = _carregar_usuarios()
    lista = [(uid, d) for uid, d in usuarios.items() if int(d.get('quiz_pontos', 0)) > 0]
    lista.sort(key=lambda x: int(x[1].get('quiz_pontos', 0)), reverse=True)
    medalhas = ['🥇', '🥈', '🥉']
    linhas = []
    for pos, (uid, d) in enumerate(lista[:10]):
        nome = html.escape((d.get('nome') or 'Cliente')[:18])
        marca = medalhas[pos] if pos < 3 else f'{pos + 1}º'
        linhas.append(f'{marca} {nome} — <b>{int(d["quiz_pontos"])}</b> pts')
    corpo = '\n'.join(linhas) if linhas else '<i>Ninguém pontuou ainda. Seja o primeiro!</i>'

    meu = ''
    uid_str = str(call.from_user.id)
    for pos, (uid, d) in enumerate(lista):
        if uid == uid_str:
            meu = f'\n\n📍 <b>Sua posição:</b> {pos + 1}º com {int(d["quiz_pontos"])} pontos'
            break
    texto = f'🏆 <b>RANKING DO QUIZ</b>\n\n{corpo}{meu}'
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton('↩️ VOLTAR', callback_data='ent_quiz'))
    _ok(call)
    _mostrar(call, texto, m)


# ----------------------------- PAINEL ADMIN ----------------------------------
def _painel_admin_markup():
    cfg = _config()
    m = InlineKeyboardMarkup()
    nomes = [('geral', '🎮 Botão no menu'), ('assistir', '🎬 O que assistir / filmes'),
             ('jogos', '⚽ Jogos'), ('roleta', '🎰 Roleta'), ('quiz', '🧠 Quiz')]
    for chave, rotulo in nomes:
        estado = '🟢 LIGADO' if cfg.get(chave, True) else '🔴 DESLIGADO'
        m.row(InlineKeyboardButton(f'{rotulo}: {estado}', callback_data=f'ent_adm_t_{chave}'))
    m.row(InlineKeyboardButton('🔒 Roleta só p/ quem já comprou: ' +
                               ('SIM' if cfg.get('roleta_exige_compra', True) else 'NÃO'),
                               callback_data='ent_adm_t_roleta_exige_compra'))
    return m


TEXTO_ADMIN = (
    '🎮 <b>PAINEL — ENTRETENIMENTO</b>\n\n'
    'Liga/desliga cada parte. Para editar prêmios, perguntas e sugestões, altere os arquivos em '
    '<code>database/entretenimento_*.json</code> e reinicie o bot.\n\n'
    '🎬 Filmes por plataforma/lançamentos precisam da chave grátis do TMDB: '
    '<code>/tmdbkey SUA_CHAVE</code>'
)


# ----------------------------- REGISTRO --------------------------------------
def registrar_handlers(bot):
    global _bot
    _bot = bot
    garantir_arquivos()

    def _guarda(call, chave):
        """Bloqueia a tela se o recurso estiver desligado."""
        if not ativo(chave):
            _alerta(call, 'Este recurso está indisponível no momento.')
            return False
        return True

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_menu')
    def _cb_menu(call):
        _ok(call)
        if not _guarda(call, 'geral'):
            return
        _abrir_menu(call)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_assistir')
    def _cb_assistir(call):
        _ok(call)
        if _guarda(call, 'assistir'):
            _tela_assistir_inicio(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_ass_'))
    def _cb_assistir_tipo(call):
        _ok(call)
        if not _guarda(call, 'assistir'):
            return
        tipo = call.data.replace('ent_ass_', '', 1)
        if tipo not in ('filme', 'serie', 'anime', 'todos'):
            return
        _sugerir(call, tipo)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_roleta')
    def _cb_roleta(call):
        _ok(call)
        if _guarda(call, 'roleta'):
            _tela_roleta(call)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_girar')
    def _cb_girar(call):
        _girar(call)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_quiz')
    def _cb_quiz(call):
        _ok(call)
        if _guarda(call, 'quiz'):
            _tela_quiz(call)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_qz_play')
    def _cb_quiz_play(call):
        if _guarda(call, 'quiz'):
            _jogar_quiz(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_qa_'))
    def _cb_quiz_resp(call):
        if _guarda(call, 'quiz'):
            _responder_quiz(call)

    @bot.callback_query_handler(func=lambda c: c.data == 'ent_qz_rank')
    def _cb_quiz_rank(call):
        if _guarda(call, 'quiz'):
            _ranking_quiz(call)

    # ---- admin ----
    @bot.message_handler(commands=['entretenimento'])
    def _cmd_admin(message):
        if not _is_admin(message.from_user.id):
            return bot.reply_to(message, '🚫 Acesso Negado!')
        bot.send_message(message.chat.id, TEXTO_ADMIN, parse_mode='HTML',
                         reply_markup=_painel_admin_markup())

    @bot.callback_query_handler(func=lambda c: c.data.startswith('ent_adm_t_'))
    def _cb_admin_toggle(call):
        if not _is_admin(call.from_user.id):
            return _alerta(call, '🚫 Acesso Negado!')
        chave = call.data.replace('ent_adm_t_', '', 1)
        if chave not in ('geral', 'assistir', 'jogos', 'roleta', 'quiz', 'roleta_exige_compra'):
            return _ok(call)
        with _lock:
            cfg = _ler(ARQ_CONFIG, dict(CONFIG_PADRAO))
            cfg[chave] = not bool(cfg.get(chave, True))
            _gravar(ARQ_CONFIG, cfg)
        _ok(call)
        try:
            bot.edit_message_text(TEXTO_ADMIN, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=_painel_admin_markup())
        except Exception:
            pass

    midia.registrar(bot, sys.modules[__name__])

    print('[Entretenimento] Módulo iniciado (roleta, o que assistir, quiz).')
