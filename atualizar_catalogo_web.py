#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para atualizar o catálogo do miniapp (catalog.json) 
com base no estoque real do bot (database/acessos.json)

Este script pode ser executado manualmente ou agendado para rodar periodicamente.
"""

import json
import os
import time
import sys

# Adicionar o diretório raiz ao path para importar módulos do bot
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    import central as api
except ImportError:
    print("❌ Erro: Não foi possível importar o módulo 'central'")
    sys.exit(1)

# Configurações de caminhos
MINIAPP_CATALOG_FILE = os.path.join(BASE_DIR, 'miniapp', 'catalog.json')
MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')
MINIAPP_SERVICE_IMAGES_DIR = os.path.join(BASE_DIR, 'miniapp', 'assets', 'service-images')
MINIAPP_AUTO_ICONS_DIR = os.path.join(MINIAPP_SERVICE_IMAGES_DIR, 'auto-icons')
ICONS_DIR = os.path.join(BASE_DIR, 'icons')

def _normalize_key(text):
    """Normaliza texto para comparação"""
    import re
    normalized = text.lower()
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def _load_miniapp_images():
    """Carrega o mapeamento de imagens personalizadas"""
    try:
        if not os.path.exists(MINIAPP_IMAGES_FILE):
            return {}
        with open(MINIAPP_IMAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"⚠️  Aviso: Erro ao carregar imagens: {e}")
    return {}

def _miniapp_image_for_service(nome, image_map=None):
    """Busca imagem personalizada para um serviço"""
    image_map = image_map if image_map is not None else _load_miniapp_images()
    exact = image_map.get(nome)
    if exact:
        return exact
    nome_key = _normalize_key(nome)
    for key, value in image_map.items():
        key_norm = _normalize_key(key)
        if key_norm and (key_norm in nome_key or nome_key in key_norm):
            return value
    return ''

def _miniapp_auto_icon_for_service(nome):
    """Busca ícone automático para um serviço"""
    import re
    if not os.path.isdir(ICONS_DIR):
        return ''
    nome_key = _normalize_key(nome)
    if not nome_key:
        return ''
    
    stopwords = {
        'conta', 'tela', 'premium', 'padrao', 'standard', 'anuncio', 'anuncios',
        'acesso', 'acessos', 'convite', 'seu', 'email', 'gmail', 'link', 'meses',
        'mes', 'com', 'sem', 'familia', 'family', 'adicional', 'adicionais'
    }
    
    nome_tokens = {
        token for token in re.findall(r'[a-z0-9]{3,}', re.sub(r'[^a-zA-Z0-9]+', ' ', nome.lower()))
        if token not in stopwords
    }
    
    if not nome_tokens:
        return ''
    
    # Procurar ícones que correspondam
    candidates = []
    for icon_filename in os.listdir(ICONS_DIR):
        if not icon_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
            continue
        icon_name_key = _normalize_key(os.path.splitext(icon_filename)[0])
        icon_tokens = set(re.findall(r'[a-z0-9]{3,}', icon_name_key))
        
        intersection = nome_tokens & icon_tokens
        if intersection:
            score = len(intersection)
            candidates.append((score, icon_filename))
    
    if candidates:
        candidates.sort(reverse=True)
        best = candidates[0][1]
        dest_filename = _normalize_key(nome) + os.path.splitext(best)[1]
        dest_path = os.path.join(MINIAPP_AUTO_ICONS_DIR, dest_filename)
        
        # Copiar ícone se não existir
        if not os.path.exists(dest_path):
            os.makedirs(MINIAPP_AUTO_ICONS_DIR, exist_ok=True)
            import shutil
            try:
                shutil.copy2(os.path.join(ICONS_DIR, best), dest_path)
            except Exception:
                pass
        
        return f'assets/service-images/auto-icons/{dest_filename}'
    
    return ''

def atualizar_catalogo():
    """Atualiza o catalog.json com base no estoque real"""
    print("🔄 Atualizando catálogo do miniapp...")
    
    try:
        # Carregar serviços do banco de dados real
        image_map = _load_miniapp_images()
        agrupados = {}
        
        servicos = api.ControleLogins.pegar_servicos()
        print(f"📦 Encontrados {len(servicos)} logins no estoque")
        
        for acesso in servicos:
            nome = acesso['nome']
            if nome not in agrupados:
                agrupados[nome] = {
                    'name': nome,
                    'price': float(acesso['valor']),
                    'stock': 0
                }
            agrupados[nome]['stock'] += 1

        # Criar catálogo ordenado
        catalogo = []
        for produto in sorted(agrupados.values(), key=lambda item: _normalize_key(item['name'])):
            image = _miniapp_image_for_service(produto['name'], image_map) or _miniapp_auto_icon_for_service(produto['name'])
            if image:
                produto['image'] = image
                produto['updated_at'] = int(time.time())
            catalogo.append(produto)

        # Salvar catalog.json
        os.makedirs(os.path.dirname(MINIAPP_CATALOG_FILE), exist_ok=True)
        with open(MINIAPP_CATALOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(catalogo, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Catálogo atualizado com sucesso!")
        print(f"📊 Total de produtos únicos: {len(catalogo)}")
        
        # Mostrar resumo dos 5 produtos com mais estoque
        top5 = sorted(catalogo, key=lambda x: x['stock'], reverse=True)[:5]
        if top5:
            print("\n🔝 Top 5 produtos com mais estoque:")
            for p in top5:
                print(f"   • {p['name']}: {p['stock']} unidades - R$ {p['price']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar catálogo: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("ATUALIZADOR DE CATÁLOGO WEB")
    print("=" * 60)
    
    sucesso = atualizar_catalogo()
    
    print("=" * 60)
    if sucesso:
        print("✅ Processo concluído com sucesso!")
        sys.exit(0)
    else:
        print("❌ Processo concluído com erros!")
        sys.exit(1)
