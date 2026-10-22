# -*- coding: utf-8 -*-
"""
Imagens dos aplicativos (Netflix, Prime, HBO...) trocadas pelo PAINEL ADM do site.

- A imagem enviada é recodificada (JPEG 512x512) e salva em database/webapp_imagens/.
- O índice fica em settings/webapp_imagens.json: {nome_normalizado: {"arq": "...", "v": timestamp}}.
- "v" muda a cada troca/remoção e vai na URL (/img?n=...&v=...), assim o navegador e o
  service worker do celular baixam a imagem nova na hora.
- Tem prioridade sobre /setfoto, assets/icones e logos da internet (ver webapp._imagem).
  Remover a imagem pelo painel volta ao comportamento antigo.
"""
import os
import re
import json
import time
import base64
import hashlib
import threading
from io import BytesIO

_BASE = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.join(_BASE, 'database', 'webapp_imagens')
_IDX = os.path.join(_BASE, 'settings', 'webapp_imagens.json')
_lock = threading.Lock()
_mem = {'mtime': None, 'dados': {}}


class ErroImagem(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.msg, self.status = msg, status


def _norm(nome):
    """Mesma regra do webapp._norm ('🌺PRIME VIDEO' -> 'prime video')."""
    limpo = re.sub(r'[^\w\s+&]', ' ', str(nome or ''), flags=re.UNICODE)
    return re.sub(r'\s+', ' ', limpo).strip().lower()


def _ler():
    try:
        mt = os.path.getmtime(_IDX)
    except OSError:
        _mem.update(mtime=None, dados={})
        return _mem['dados']
    if _mem['mtime'] != mt:
        try:
            with open(_IDX, 'r', encoding='utf-8') as f:
                d = json.load(f)
            _mem.update(mtime=mt, dados=d if isinstance(d, dict) else {})
        except Exception:
            _mem.update(mtime=mt, dados={})
    return _mem['dados']


def _gravar(dados):
    os.makedirs(os.path.dirname(_IDX), exist_ok=True)
    tmp = _IDX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _IDX)
    _mem['mtime'] = None


def versao(nome):
    """Número que muda quando a imagem do serviço é trocada/removida (0 = nunca mexeram)."""
    e = _ler().get(_norm(nome))
    return int(e.get('v') or 0) if isinstance(e, dict) else 0


def caminho(nome):
    """Caminho do arquivo enviado pelo admin para esse serviço (ou None)."""
    e = _ler().get(_norm(nome))
    if not isinstance(e, dict) or not e.get('arq'):
        return None
    arq = os.path.join(_DIR, os.path.basename(str(e['arq'])))
    return arq if os.path.isfile(arq) else None


def personalizada(nome):
    return caminho(nome) is not None


def salvar(nome, dataurl):
    chave = _norm(nome)
    if not chave or len(chave) > 120:
        raise ErroImagem('Nome do serviço inválido.')
    m = re.match(r'^data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)$', str(dataurl or ''))
    if not m:
        raise ErroImagem('Imagem inválida. Use JPG, PNG ou WEBP.')
    try:
        raw = base64.b64decode(m.group(1), validate=True)
    except Exception:
        raise ErroImagem('Imagem inválida.')
    if len(raw) > 550_000:
        raise ErroImagem('Imagem muito grande (máx. ~500 KB).', 413)
    try:
        from PIL import Image, ImageOps
        im = Image.open(BytesIO(raw))
        if im.width * im.height > 16_000_000:
            raise ErroImagem('Imagem muito grande.', 413)
        im = ImageOps.exif_transpose(im)
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            fundo = Image.new('RGBA', im.size, (255, 255, 255, 255))
            fundo.alpha_composite(im)
            im = fundo
        im = ImageOps.fit(im.convert('RGB'), (512, 512), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, 'JPEG', quality=90, optimize=True)      # recodifica: nada do original sobrevive
    except ErroImagem:
        raise
    except Exception:
        raise ErroImagem('Não consegui ler essa imagem. Tente outra (JPG ou PNG).')
    os.makedirs(_DIR, exist_ok=True)
    arq = hashlib.sha1(chave.encode('utf-8')).hexdigest()[:20] + f'_{int(time.time())}.jpg'
    with open(os.path.join(_DIR, arq), 'wb') as f:
        f.write(buf.getvalue())
    with _lock:
        dados = dict(_ler())
        antigo = (dados.get(chave) or {}).get('arq')
        dados[chave] = {'arq': arq, 'v': int(time.time())}
        _gravar(dados)
    _apagar(antigo)
    return versao(nome)


def remover(nome):
    chave = _norm(nome)
    with _lock:
        dados = dict(_ler())
        e = dados.get(chave)
        if not isinstance(e, dict) or not e.get('arq'):
            raise ErroImagem('Esse serviço não tem imagem personalizada.', 404)
        antigo = e['arq']
        dados[chave] = {'arq': '', 'v': int(time.time())}      # guarda o "v" para o celular largar o cache
        _gravar(dados)
    _apagar(antigo)
    return versao(nome)


def _apagar(arq):
    if arq:
        try:
            os.remove(os.path.join(_DIR, os.path.basename(str(arq))))
        except Exception:
            pass
