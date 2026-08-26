#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script que mapeia explicitamente cada produto do catálogo
para o ícone correto da pasta icons/, copia os arquivos para
miniapp/assets/service-images/auto-icons/ e regenera o catalog.json.
"""

import json
import os
import shutil
import time
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR          = os.path.join(BASE_DIR, 'icons')
AUTO_ICONS_DIR     = os.path.join(BASE_DIR, 'miniapp', 'assets', 'service-images', 'auto-icons')
CATALOG_FILE       = os.path.join(BASE_DIR, 'miniapp', 'catalog.json')
ACESSOS_FILE       = os.path.join(BASE_DIR, 'database', 'acessos.json')
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')

# ─── MAPEAMENTO EXPLÍCITO: nome do produto → arquivo em icons/ ───────────────
# Produtos sem imagem equivalente ficam com None (aparece banner padrão)
MAPA = {
    # CANVA
    "🎨CANVA PRO":                             "canvaproanualseuemail.jpg",
    "🎨CONVITE CANVA PRO(SEU E-MAIL)":         "canvaproanualseuemail.jpg",

    # CAPCUT  (sem ícone na pasta – None)
    "🎥CAPCUT PRO 1 ACESSO":                   None,
    "🎥CONTA CAPCUT PRO":                      None,

    # CRUNCHYROLL
    "🟠CONTA CRUNCHYROLL PREMIUM":             "contacrunchyrollmegafan.jpg",
    "🟠TELA CRUNCHYROLL PREMIUM":              "crunchyrollmegafantela.jpg",

    # DEEZER
    "🎧CONTA DEEZER FAMILY":                   "deezerpremiumlink.jpg",

    # DISNEY
    "🔵CONTA DISNEY COM ANUNCIO":              "contadisneypadro.jpg",
    "🔵DISNEY PADRÃO COM ANÚNCIO TELA":        "teladisneypadrosemanuncio.jpg",
    "🔵DISNEY PREMIUM TELA":                   "contadisneypremium.jpg",

    # GLOBO
    "🔴CONTA GLOBO BÁSICA":                    "contagloboplay.jpg",
    "🔴CONTA GLOBO PREMIUM":                   "contagloboplaypremium.jpg",
    "🔴TELA GLOBO PLAY COM ANÚNCIO":           "10contagloboplayseuemail.jpg",
    "🔴TELA GLOBO PREMIUM":                    "contagloboplaypremium.jpg",
    "🔴GLOBO PREMIUM COM TELECINE TELA":       "telaglobocnspremieretelecine.jpg",

    # HBO MAX
    "🔵CONTA HBOMAX COM ANUNCIO":              "contahbomaxplatinum.jpg",
    "🔵CONTA HBOMAX SEM ANUNCIO":              "contahbomaxplatinum.jpg",
    "🔵HBO MAX  STANDARD TELA":                "telahbomaxstandard.jpg",
    "🔵TELA HBO MAX":                          "telahbomaxplatinum.jpg",

    # NETFLIX
    "🔴CONTA NETFLIX PADRÃO COM ANUN":         "contanetflixpcomanncio.jpg",
    "🔴CONTA NETFLIX PREMIUM":                 "contanetflixpcomanncio.jpg",
    "🛒NETFLIX PREMIUM TELA":                  "telanetflixpremium.jpg",

    # PRIME VIDEO
    "🅿️CONTA PRIME VIDEO":                    "10contaprimevideoseuemail.jpg",
    "🅿️PRIME VIDEO 6 MESES CONTA":            "contaprime6meses.jpg",
    "🅿️PRIME VIDEO COM PARAMOUNT CONTA":      "primevideocomparamountconta.jpg",
    "🅿️PRIME VIDEO COM PREMIERE CONTA":       "primevideocompremieretela.jpg",
    "🅿️PRIME VIDEO SEM ANUNCIO CONTA":        "10contaprimevideoseuemail.jpg",
    "🅿️TELA PRIME VIDEO":                     "telaprimevideo2adicionais.jpg",

    # RECORDPLUS
    "🟣RECORDPLUS TELA":                       "telarecordplus.jpg",

    # SPOTIFY
    "🎧CONTA SPOTIFY 3 MESES":                 "spotify3meses.jpg",

    # TIDAL
    "⚫️CONTA TIDAL FAMILIA":                  "contatidal.jpg",

    # UNITV
    "🟡UNITV CODIGO DE ATIVAÇÃO":              "contaunitv.jpg",
    "🟡20 CODIGO UNITV":                       "contaunitv.jpg",
    "🟡45 CODIGO UNITV":                       "contaunitv.jpg",

    # WAREZ PLAY  (sem ícone – None)
    "🟢WAREZ PLAY 2 APARELHOS":               None,

    # KRATOR+  (sem ícone – None)
    "🟣KRATOR+":                               None,

    # YOUTUBE
    "🔴YOUTUBE PREMIUM CONVITE(SEU E-MAIL)":   "contayoutubefamiliaseugmailnovo.jpg",
}


def copiar_icones():
    """Copia cada ícone mapeado para a pasta auto-icons do miniapp."""
    os.makedirs(AUTO_ICONS_DIR, exist_ok=True)
    copiados = 0
    for produto, arquivo in MAPA.items():
        if not arquivo:
            continue
        src = os.path.join(ICONS_DIR, arquivo)
        dst = os.path.join(AUTO_ICONS_DIR, arquivo)
        if not os.path.exists(src):
            print(f"  ⚠️  Arquivo não encontrado em icons/: {arquivo}")
            continue
        shutil.copy2(src, dst)
        copiados += 1
    print(f"✅ {copiados} ícones copiados para auto-icons/")


def salvar_miniapp_images():
    """Persiste o mapeamento em database/miniapp_images.json para o bot usar."""
    data = {}
    for produto, arquivo in MAPA.items():
        if arquivo:
            data[produto] = f"assets/service-images/auto-icons/{arquivo}"
    os.makedirs(os.path.dirname(MINIAPP_IMAGES_FILE), exist_ok=True)
    with open(MINIAPP_IMAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ miniapp_images.json atualizado com {len(data)} mapeamentos")


def gerar_catalogo():
    """Lê acessos.json, agrupa por produto, aplica ícones e salva catalog.json."""
    with open(ACESSOS_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    acessos = raw.get('acessos', raw) if isinstance(raw, dict) else raw

    agrupados = {}
    for acesso in acessos:
        nome  = acesso['nome']
        valor = float(acesso['valor'])
        if nome not in agrupados:
            agrupados[nome] = {'name': nome, 'price': valor, 'stock': 0}
        agrupados[nome]['stock'] += 1

    catalogo = []
    sem_imagem = []
    for produto in sorted(agrupados.values(), key=lambda x: x['name']):
        nome   = produto['name']
        arquivo = MAPA.get(nome)
        if arquivo:
            produto['image']      = f"assets/service-images/auto-icons/{arquivo}"
            produto['updated_at'] = int(time.time())
        else:
            sem_imagem.append(nome)
        catalogo.append(produto)

    os.makedirs(os.path.dirname(CATALOG_FILE), exist_ok=True)
    with open(CATALOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalogo, f, indent=2, ensure_ascii=False)

    print(f"✅ catalog.json gerado: {len(catalogo)} produtos")
    if sem_imagem:
        print(f"ℹ️  Sem imagem ({len(sem_imagem)}): {', '.join(sem_imagem)}")
    return catalogo


if __name__ == '__main__':
    print("=" * 60)
    print("MAPEADOR DE ÍCONES DO CATÁLOGO WEB")
    print("=" * 60)
    copiar_icones()
    salvar_miniapp_images()
    gerar_catalogo()
    print("=" * 60)
    print("✅ Pronto!")
