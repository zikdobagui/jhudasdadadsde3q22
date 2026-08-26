#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API HTTP simples que retorna o catálogo em tempo real
consultando direto o database/acessos.json
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import time

# Adicionar diretório raiz ao path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    import central as api
except ImportError:
    print("❌ Erro: não foi possível importar 'central'")
    sys.exit(1)

MINIAPP_IMAGES_FILE = os.path.join(BASE_DIR, 'database', 'miniapp_images.json')

def _load_miniapp_images():
    """Carrega mapeamento de imagens"""
    try:
        if os.path.exists(MINIAPP_IMAGES_FILE):
            with open(MINIAPP_IMAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def gerar_catalogo_tempo_real():
    """Gera catálogo consultando direto o banco de dados"""
    try:
        image_map = _load_miniapp_images()
        agrupados = {}
        
        # Puxa logins direto do banco
        servicos = api.ControleLogins.pegar_servicos()
        
        for acesso in servicos:
            nome = acesso['nome']
            if nome not in agrupados:
                agrupados[nome] = {
                    'name': nome,
                    'price': float(acesso['valor']),
                    'stock': 0
                }
            agrupados[nome]['stock'] += 1
        
        # Ordena e adiciona imagens
        catalogo = []
        for produto in sorted(agrupados.values(), key=lambda x: x['name']):
            nome = produto['name']
            if nome in image_map:
                produto['image'] = image_map[nome]
                produto['updated_at'] = int(time.time())
            catalogo.append(produto)
        
        return catalogo
        
    except Exception as e:
        print(f"❌ Erro ao gerar catálogo: {e}")
        return []


class CatalogoHandler(BaseHTTPRequestHandler):
    """Handler HTTP que responde com o catálogo em JSON"""
    
    def do_GET(self):
        if self.path == '/catalog.json' or self.path == '/catalog':
            try:
                catalogo = gerar_catalogo_tempo_real()
                
                # Responde com JSON
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')  # CORS
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                
                response = json.dumps(catalogo, ensure_ascii=False, indent=2)
                self.wfile.write(response.encode('utf-8'))
                
                print(f"✅ Catálogo servido: {len(catalogo)} produtos")
                
            except Exception as e:
                print(f"❌ Erro: {e}")
                self.send_error(500, f"Erro interno: {e}")
        else:
            self.send_error(404, "Endpoint não encontrado")
    
    def log_message(self, format, *args):
        """Sobrescreve log para ficar mais limpo"""
        pass


def iniciar_servidor(porta=8080):
    """Inicia servidor HTTP na porta especificada"""
    server_address = ('', porta)
    httpd = HTTPServer(server_address, CatalogoHandler)
    
    print("=" * 60)
    print("🚀 API DE CATÁLOGO EM TEMPO REAL")
    print("=" * 60)
    print(f"📡 Servidor rodando em: http://localhost:{porta}")
    print(f"📍 Endpoint: http://localhost:{porta}/catalog.json")
    print(f"🔄 Consultando: database/acessos.json")
    print("=" * 60)
    print("Pressione Ctrl+C para parar\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n⏹️  Servidor parado")
        httpd.shutdown()


if __name__ == '__main__':
    PORT = int(os.getenv('CATALOG_API_PORT', 8080))
    iniciar_servidor(PORT)
