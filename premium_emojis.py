"""Suporte centralizado a emojis premium/custom emoji do Telegram.

Edite somente o arquivo ``premium_emojis.json`` para trocar os IDs dos emojis
premium. Exemplo de entrada:

    "🛒": {
      "fallback": "🛒",
      "custom_emoji_id": "5312361253610475399"
    }

O módulo aplica duas estratégias diferentes, conforme o local:

* Mensagens HTML: troca o emoji por ``<tg-emoji emoji-id="...">fallback</tg-emoji>``.
* Botões: usa o campo oficial ``icon_custom_emoji_id`` em ``InlineKeyboardButton``
  e ``KeyboardButton``. Esse campo foi adicionado no Bot API 9.4. Como o projeto
  usa pyTelegramBotAPI 4.12.0, que ainda não serializa esse campo, este módulo
  adiciona compatibilidade por monkey patch em ``to_dict()``.
* Cores dos botões: campo oficial ``style`` (``primary`` azul, ``success`` verde,
  ``danger`` vermelho), também do Bot API 9.4. As cores são aplicadas
  automaticamente em TODOS os botões conforme ``botoes_cores.json`` (editável, sem
  reiniciar o bot). Para forçar a cor de um botão específico no código:
  ``InlineKeyboardButton("X", callback_data="x", style="danger")``; para deixar um
  botão sem cor: ``style="none"``.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import os
import re
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "premium_emojis.json")

_CONFIG_CACHE: Dict[str, Any] | None = None
_CONFIG_MTIME: float | None = None
_EMOJI_PATTERN: re.Pattern[str] | None = None
_INSTALLED = False

CORES_PATH = os.path.join(BASE_DIR, "botoes_cores.json")
_CORES_CACHE: Dict[str, Any] | None = None
_CORES_MTIME: float | None = None
_ESTILOS_VALIDOS = ("primary", "success", "danger")
_CORES_PADRAO: Dict[str, Any] = {
    "ativo": True,
    "padrao": "primary",
    "botoes": {},
    "servicos": {},
    "marcadores_botoes": {},
    "marcadores_servicos": {},
    "regras": [
        {"estilo": "danger", "contem": ["SUPORTE", "CANCELAR", "EXCLUIR", "REMOVER", "RECUSAR"]},
        {"estilo": "success", "contem": ["CONFIRMAR", "FINALIZAR", "PAGAR", "JÁ PAGUEI"]},
    ],
}

_TG_EMOJI_TAG_RE = re.compile(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", flags=re.IGNORECASE | re.DOTALL)


def _load_config() -> Dict[str, Any]:
    """Carrega o JSON e atualiza cache se o arquivo foi alterado."""
    global _CONFIG_CACHE, _CONFIG_MTIME, _EMOJI_PATTERN
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        return {"enabled": False, "emojis": {}}

    if _CONFIG_CACHE is not None and _CONFIG_MTIME == mtime:
        return _CONFIG_CACHE

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as exc:
        print(f"[premium_emojis] Erro ao ler {CONFIG_PATH}: {exc}")
        cfg = {"enabled": False, "emojis": {}}

    emojis = cfg.get("emojis", {}) if isinstance(cfg.get("emojis", {}), dict) else {}
    keys = [k for k, v in emojis.items() if isinstance(k, str) and k and isinstance(v, dict)]
    keys.sort(key=len, reverse=True)
    _EMOJI_PATTERN = re.compile("|".join(re.escape(k) for k in keys)) if keys else None
    _CONFIG_CACHE = cfg
    _CONFIG_MTIME = mtime
    return cfg


def _valid_custom_id(value: Any) -> str:
    value = str(value or "").strip()
    return value if value.isdigit() else ""


def _emoji_data(emoji: str) -> Dict[str, Any]:
    cfg = _load_config()
    data = cfg.get("emojis", {}).get(emoji, {})
    return data if isinstance(data, dict) else {}


def custom_emoji_id(emoji: str) -> str:
    """Retorna o custom_emoji_id configurado para um emoji, ou string vazia."""
    return _valid_custom_id(_emoji_data(emoji).get("custom_emoji_id"))


def _emoji_html(emoji: str) -> str:
    data = _emoji_data(emoji)
    fallback = str(data.get("fallback") or emoji)
    cid = _valid_custom_id(data.get("custom_emoji_id"))
    if cid:
        return f'<tg-emoji emoji-id="{cid}">{_html.escape(fallback)}</tg-emoji>'
    return fallback


def _emoji_fallback(emoji: str) -> str:
    data = _emoji_data(emoji)
    return str(data.get("fallback") or emoji)


def _replace_outside_existing_tags(text: str, replace_segment: Callable[[str], str]) -> str:
    """Evita processar novamente emojis já convertidos em tags <tg-emoji>."""
    if "<tg-emoji" not in text.lower():
        return replace_segment(text)
    parts = []
    pos = 0
    for match in _TG_EMOJI_TAG_RE.finditer(text):
        parts.append(replace_segment(text[pos:match.start()]))
        parts.append(match.group(0))
        pos = match.end()
    parts.append(replace_segment(text[pos:]))
    return "".join(parts)


def replace_emojis(text: Any, context: str = "message") -> Any:
    """Substitui emojis configurados por HTML premium em mensagens ou fallback em botões."""
    if not isinstance(text, str) or not text:
        return text
    cfg = _load_config()
    if not cfg.get("enabled", True):
        return text
    if context == "button" and not cfg.get("apply_to_buttons", True):
        return text
    if context == "message" and not cfg.get("apply_to_html_messages", True):
        return text
    pattern = _EMOJI_PATTERN
    if not pattern:
        return text

    if context == "button":
        return pattern.sub(lambda m: _emoji_fallback(m.group(0)), text)

    def repl(segment: str) -> str:
        return pattern.sub(lambda m: _emoji_html(m.group(0)), segment)

    return _replace_outside_existing_tags(text, repl)


def html_emoji(emoji: str) -> str:
    """Retorna manualmente o HTML premium de um emoji configurado."""
    return _emoji_html(emoji)


def button_emoji(emoji: str) -> str:
    """Retorna o fallback textual seguro para botões."""
    return _emoji_fallback(emoji)


def _find_button_icon(text: Any) -> Tuple[str, str]:
    """Localiza o primeiro emoji do texto que tem custom_emoji_id configurado.

    Retorna ``(emoji_unicode, custom_emoji_id)``. O Bot API aceita apenas um ícone
    premium por botão via ``icon_custom_emoji_id``; por isso usamos o primeiro
    emoji configurado encontrado no texto do botão.
    """
    if not isinstance(text, str) or not text:
        return "", ""
    cfg = _load_config()
    if not cfg.get("enabled", True) or not cfg.get("apply_to_buttons", True):
        return "", ""
    if not cfg.get("button_icon_custom_emoji", True):
        return "", ""
    pattern = _EMOJI_PATTERN
    if not pattern:
        return "", ""
    for match in pattern.finditer(text):
        emoji = match.group(0)
        cid = custom_emoji_id(emoji)
        if cid:
            return emoji, cid
    return "", ""


def _normalize_button_text(text: Any, icon_emoji: str = "") -> Any:
    """Normaliza o texto do botão e remove o emoji que virou ícone premium.

    Quando ``remove_icon_emoji_from_button_text`` está ativo, o emoji usado como
    ``icon_custom_emoji_id`` sai do texto para evitar duplicação visual. Se outros
    emojis sem ID existirem no botão, continuam como fallback Unicode.
    """
    if not isinstance(text, str) or not text:
        return text
    cfg = _load_config()
    result = replace_emojis(text, context="button")
    if icon_emoji and cfg.get("remove_icon_emoji_from_button_text", True):
        fallback = _emoji_fallback(icon_emoji)
        result = result.replace(fallback, "", 1)
        result = " ".join(result.split())
        if not result.strip():
            # Botão só com emoji: mantém o texto original (o Telegram rejeita texto vazio)
            return text
    return result


def _get_arg(args: Tuple[Any, ...], kwargs: Dict[str, Any], index: int, name: str) -> Any:
    if name in kwargs:
        return kwargs[name]
    if index >= 0 and len(args) > index:
        return args[index]
    return None


def _set_arg(args: Tuple[Any, ...], kwargs: Dict[str, Any], index: int, name: str, value: Any) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    if name in kwargs:
        kwargs[name] = value
        return args, kwargs
    if index >= 0 and len(args) > index:
        args_list = list(args)
        args_list[index] = value
        return tuple(args_list), kwargs
    kwargs[name] = value
    return args, kwargs


def _is_html_parse_mode(parse_mode: Any) -> bool:
    return isinstance(parse_mode, str) and parse_mode.lower() == "html"


def _can_auto_html(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    # Evita quebrar mensagens que já contenham markup ou caracteres que exigem escape em HTML.
    return "<" not in text and ">" not in text and "&" not in text


def _wrap_text_method(original: Callable[..., Any], text_index: int, text_name: str, parse_index: int = -1) -> Callable[..., Any]:
    @wraps(original)
    def wrapper(self, *args, **kwargs):
        text = _get_arg(args, kwargs, text_index, text_name)
        cfg = _load_config()
        parse_mode = _get_arg(args, kwargs, parse_index, "parse_mode") if parse_index >= 0 else kwargs.get("parse_mode")
        effective_parse_mode = parse_mode or getattr(self, "parse_mode", None)

        should_replace = _is_html_parse_mode(effective_parse_mode)
        if not should_replace and cfg.get("auto_html_parse_mode", False) and _can_auto_html(text):
            should_replace = True
            if parse_index >= 0:
                args, kwargs = _set_arg(args, kwargs, parse_index, "parse_mode", "HTML")
            else:
                kwargs.setdefault("parse_mode", "HTML")

        if should_replace:
            args, kwargs = _set_arg(args, kwargs, text_index, text_name, replace_emojis(text, context="message"))
        return original(self, *args, **kwargs)
    return wrapper


_CORES_LOCK = threading.RLock()
_VISTOS: Dict[str, Dict[str, str]] = {}
_VISTOS_PATH = os.path.join(BASE_DIR, "botoes_vistos.json")
_VISTOS_CARREGADO = False
_VISTOS_SUJO = False
_VISTOS_ULTIMO_SAVE = 0.0
_VISTOS_MAX = 600
_ID_DINAMICO_RE = re.compile(r"\d{4,}")


def _limpar(txt: Any) -> str:
    """Só letras/números/espaços em maiúsculo (tira emojis, R$, colchetes...)."""
    return " ".join(re.sub(r"[^\w\s]", " ", str(txt or ""), flags=re.UNICODE).upper().split())


def hash_chave(chave: str) -> str:
    return hashlib.sha1(str(chave).encode("utf-8")).hexdigest()[:8]


def _load_cores() -> Dict[str, Any]:
    """Lê botoes_cores.json (recarrega sozinho quando o arquivo muda)."""
    global _CORES_CACHE, _CORES_MTIME
    try:
        mtime = os.path.getmtime(CORES_PATH)
    except OSError:
        return _CORES_PADRAO
    if _CORES_CACHE is not None and _CORES_MTIME == mtime:
        return _CORES_CACHE
    try:
        with open(CORES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        _CORES_CACHE = data if isinstance(data, dict) else _CORES_PADRAO
    except Exception as exc:
        print(f"[premium_emojis] botoes_cores.json inválido, usando padrão: {exc}")
        _CORES_CACHE = _CORES_PADRAO
    _CORES_MTIME = mtime
    return _CORES_CACHE


def _salvar_cores(cfg: Dict[str, Any]) -> None:
    global _CORES_CACHE, _CORES_MTIME
    with _CORES_LOCK:
        tmp = CORES_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, CORES_PATH)
        _CORES_CACHE = cfg
        try:
            _CORES_MTIME = os.path.getmtime(CORES_PATH)
        except OSError:
            _CORES_MTIME = None


def _cfg_editavel() -> Dict[str, Any]:
    cfg = json.loads(json.dumps(_load_cores()))  # cópia profunda
    cfg.setdefault("ativo", True)
    cfg.setdefault("padrao", "primary")
    cfg.setdefault("regras", [])
    cfg.setdefault("botoes", {})
    cfg.setdefault("servicos", {})
    cfg.setdefault("marcadores_botoes", {})
    cfg.setdefault("marcadores_servicos", {})
    return cfg


def _norm_estilo(valor: Any) -> Optional[str]:
    """'primary'/'success'/'danger' -> itself; 'none' -> 'none'; resto -> None."""
    v = str(valor or "").strip().lower()
    if v in _ESTILOS_VALIDOS or v == "none":
        return v
    return None


def cfg_set_botao(chave: str, estilo: Optional[str]) -> None:
    """Define a cor de UM botão (chave = callback_data). estilo None = automático."""
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        e = _norm_estilo(estilo)
        if e:
            cfg["botoes"][chave] = e
        else:
            cfg["botoes"].pop(chave, None)
        _salvar_cores(cfg)


def cfg_set_servico(nome: str, estilo: Optional[str]) -> None:
    """Define a cor de um SERVIÇO (vale para todo botão que citar o nome)."""
    chave = _limpar(nome)
    if not chave:
        return
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        e = _norm_estilo(estilo)
        if e:
            cfg["servicos"][chave] = e
        else:
            cfg["servicos"].pop(chave, None)
        _salvar_cores(cfg)


def cfg_set_marcador_botao(chave: str, emoji: Optional[str]) -> None:
    """Marcador colorido (🟦🟩🟥🟧🟨🟪🟫⬛⬜) na frente do texto de UM botão."""
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        if emoji:
            cfg["marcadores_botoes"][chave] = emoji
        else:
            cfg["marcadores_botoes"].pop(chave, None)
        _salvar_cores(cfg)


def cfg_set_marcador_servico(nome: str, emoji: Optional[str]) -> None:
    chave = _limpar(nome)
    if not chave:
        return
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        if emoji:
            cfg["marcadores_servicos"][chave] = emoji
        else:
            cfg["marcadores_servicos"].pop(chave, None)
        _salvar_cores(cfg)


def cfg_aplicar_lote(botoes: Dict[str, str], servicos: Dict[str, str],
                     marc_servicos: Dict[str, str]) -> None:
    """Grava várias cores de uma vez (usado pelo botão de cores automáticas)."""
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        cfg["botoes"] = dict(botoes)
        cfg["servicos"] = {_limpar(k): v for k, v in servicos.items() if _limpar(k)}
        cfg["marcadores_servicos"] = {_limpar(k): v for k, v in marc_servicos.items() if _limpar(k)}
        cfg["marcadores_botoes"] = {}
        cfg["ativo"] = True
        _salvar_cores(cfg)


def _marcador_botao(text: Any, chave: str) -> str:
    # Quadrados coloridos na frente dos botões DESATIVADOS (as cores do botão continuam).
    return ""
    cfg = _load_cores()
    if not cfg.get("ativo", True) or chave.startswith("cores_") or chave == "noop":
        return ""
    m = (cfg.get("marcadores_botoes") or {}).get(chave)
    if m:
        return str(m)
    ms = cfg.get("marcadores_servicos") or {}
    if ms:
        alvo = _limpar(str(text or "") + " " + chave)
        melhor = ""
        for nome in ms:
            if len(nome) >= 2 and nome in alvo and len(nome) > len(melhor):
                melhor = nome
        if melhor:
            return str(ms[melhor])
    return ""


def cfg_set_campo(campo: str, valor: Any) -> None:
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        cfg[campo] = valor
        _salvar_cores(cfg)


def cfg_limpar_personalizacoes() -> None:
    with _CORES_LOCK:
        cfg = _cfg_editavel()
        cfg["botoes"], cfg["servicos"] = {}, {}
        cfg["marcadores_botoes"], cfg["marcadores_servicos"] = {}, {}
        _salvar_cores(cfg)


def cfg_get() -> Dict[str, Any]:
    return _cfg_editavel()


def _chave_do_botao(data: Dict[str, Any]) -> str:
    cb = data.get("callback_data")
    if cb:
        return str(cb)
    if data.get("url"):
        return "url:" + _limpar(data.get("text", ""))
    return "txt:" + _limpar(data.get("text", ""))


def _estilo_botao(text: Any, explicit: Any = None, chave: str = "") -> str:
    """Prioridade: botão específico > serviço > código (style=) > regras > padrão."""
    cfg = _load_cores()
    interno = chave.startswith("cores_") or chave == "noop"
    if explicit is not None and interno:
        e = str(explicit).strip().lower()
        return e if e in _ESTILOS_VALIDOS else ""
    if not cfg.get("ativo", True):
        return ""
    if not interno:
        ov = _norm_estilo((cfg.get("botoes") or {}).get(chave))
        if ov:
            return "" if ov == "none" else ov
        servicos = cfg.get("servicos") or {}
        if servicos:
            alvo = _limpar(str(text or "") + " " + chave)
            melhor = ""
            for nome in servicos:
                if len(nome) >= 2 and nome in alvo and len(nome) > len(melhor):
                    melhor = nome
            if melhor:
                ov = _norm_estilo(servicos[melhor])
                if ov:
                    return "" if ov == "none" else ov
    if explicit is not None:
        e = str(explicit).strip().lower()
        return e if e in _ESTILOS_VALIDOS else ""
    texto = str(text or "").upper()
    for regra in cfg.get("regras", []) or []:
        estilo = str(regra.get("estilo", "")).strip().lower()
        if estilo not in _ESTILOS_VALIDOS:
            continue
        if any(str(t).upper() in texto for t in regra.get("contem", []) or []):
            return estilo
    padrao = str(cfg.get("padrao", "")).strip().lower()
    return padrao if padrao in _ESTILOS_VALIDOS else ""


def estilo_efetivo(texto: str, chave: str) -> str:
    return _estilo_botao(texto, None, chave)


def _carregar_vistos() -> None:
    global _VISTOS_CARREGADO
    if _VISTOS_CARREGADO:
        return
    _VISTOS_CARREGADO = True
    try:
        with open(_VISTOS_PATH, "r", encoding="utf-8") as fh:
            dados = json.load(fh)
        if isinstance(dados, dict):
            _VISTOS.update({k: v for k, v in dados.items() if isinstance(v, dict)})
    except Exception:
        pass


def _registrar_visto(chave: str, texto: str) -> None:
    """Guarda os botões que o bot já exibiu, para listar no painel de cores."""
    global _VISTOS_SUJO, _VISTOS_ULTIMO_SAVE
    if not chave or chave.startswith("cores_") or chave in ("noop",) or _ID_DINAMICO_RE.search(chave):
        return
    if chave.startswith("txt:") and not chave[4:]:
        return
    with _CORES_LOCK:
        _carregar_vistos()
        atual = _VISTOS.get(chave)
        if atual and atual.get("t") == texto:
            pass
        else:
            _VISTOS[chave] = {"t": texto, "ts": str(int(time.time()))}
            _VISTOS_SUJO = True
            if len(_VISTOS) > _VISTOS_MAX:
                velhos = sorted(_VISTOS.items(), key=lambda kv: int(kv[1].get("ts", "0")))
                for k, _ in velhos[: len(_VISTOS) - _VISTOS_MAX]:
                    _VISTOS.pop(k, None)
        if _VISTOS_SUJO and time.time() - _VISTOS_ULTIMO_SAVE > 20:
            _VISTOS_ULTIMO_SAVE = time.time()
            _VISTOS_SUJO = False
            try:
                tmp = _VISTOS_PATH + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(_VISTOS, fh, ensure_ascii=False)
                os.replace(tmp, _VISTOS_PATH)
            except Exception:
                pass


def listar_vistos() -> list:
    """[(chave, texto)] ordenado pelo texto."""
    with _CORES_LOCK:
        _carregar_vistos()
        itens = [(k, v.get("t", k)) for k, v in _VISTOS.items()]
    return sorted(itens, key=lambda kv: _limpar(kv[1]) or kv[0])


def _wrap_button_init(original: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(original)
    def wrapper(self, *args, **kwargs):
        explicit_icon = _valid_custom_id(kwargs.pop("icon_custom_emoji_id", ""))
        explicit_style = kwargs.pop("style", None)
        text = _get_arg(args, kwargs, 0, "text")
        if explicit_icon:
            # Ícone definido explicitamente: não detecta nem remove emojis do texto
            # (assim um ⚡ no texto continua aparecendo como emoji comum).
            icon_emoji, detected_icon = "", ""
        else:
            icon_emoji, detected_icon = _find_button_icon(text)
        icon_id = explicit_icon or detected_icon
        normalized_text = _normalize_button_text(text, icon_emoji if detected_icon else "")
        args, kwargs = _set_arg(args, kwargs, 0, "text", normalized_text)
        original(self, *args, **kwargs)
        if icon_id:
            setattr(self, "icon_custom_emoji_id", icon_id)
        # Cor do botão: guarda a escolha explícita (ou None) e resolve no to_dict,
        # assim a edição do botoes_cores.json vale sem reiniciar o bot.
        setattr(self, "_estilo_explicito", explicit_style)
        setattr(self, "_texto_original", text)
        return None
    return wrapper


def _wrap_button_to_dict(original: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
    @wraps(original)
    def wrapper(self, *args, **kwargs):
        data = original(self, *args, **kwargs)
        icon_id = _valid_custom_id(getattr(self, "icon_custom_emoji_id", ""))
        if icon_id:
            data["icon_custom_emoji_id"] = icon_id
        chave = _chave_do_botao(data)
        texto_orig = getattr(self, "_texto_original", data.get("text", ""))
        try:
            _registrar_visto(chave, str(texto_orig))
        except Exception:
            pass
        estilo = _estilo_botao(texto_orig, getattr(self, "_estilo_explicito", None), chave)
        if estilo:
            data["style"] = estilo
        try:
            marc = _marcador_botao(texto_orig, chave)
            if marc and data.get("text") and not str(data["text"]).startswith(marc):
                data["text"] = f"{marc} {data['text']}"[:64]
        except Exception:
            pass
        return data
    return wrapper


def install() -> None:
    """Instala patches globais no pyTelegramBotAPI."""
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        import telebot
        from telebot import types
    except Exception as exc:
        print(f"[premium_emojis] pyTelegramBotAPI não disponível: {exc}")
        return

    # Métodos com texto principal.
    telebot.TeleBot.send_message = _wrap_text_method(telebot.TeleBot.send_message, 1, "text", 2)
    telebot.TeleBot.edit_message_text = _wrap_text_method(telebot.TeleBot.edit_message_text, 0, "text", 4)

    # Métodos comuns com caption. Os índices seguem as assinaturas do pyTelegramBotAPI 4.x.
    for method_name, caption_index, parse_index in (
        ("send_photo", 2, 5),
        ("send_document", 2, 5),
        ("send_video", 2, 5),
        ("send_animation", 2, 5),
        ("edit_message_caption", 0, 4),
    ):
        original = getattr(telebot.TeleBot, method_name, None)
        if original is not None and not getattr(original, "_premium_emoji_text_wrapped", False):
            wrapped = _wrap_text_method(original, caption_index, "caption", parse_index)
            setattr(wrapped, "_premium_emoji_text_wrapped", True)
            setattr(telebot.TeleBot, method_name, wrapped)

    # InlineKeyboardButton e KeyboardButton: suporte ao campo icon_custom_emoji_id.
    for class_name in ("InlineKeyboardButton", "KeyboardButton"):
        cls = getattr(types, class_name, None)
        if cls is None:
            continue
        if hasattr(cls, "__init__") and not getattr(cls.__init__, "_premium_emoji_button_wrapped", False):
            wrapped_init = _wrap_button_init(cls.__init__)
            setattr(wrapped_init, "_premium_emoji_button_wrapped", True)
            cls.__init__ = wrapped_init
        if hasattr(cls, "to_dict") and not getattr(cls.to_dict, "_premium_emoji_to_dict_wrapped", False):
            wrapped_to_dict = _wrap_button_to_dict(cls.to_dict)
            setattr(wrapped_to_dict, "_premium_emoji_to_dict_wrapped", True)
            cls.to_dict = wrapped_to_dict

    _INSTALLED = True
    print("[premium_emojis] Sistema de emojis premium carregado com suporte a icon_custom_emoji_id nos botões.")
