"""
Módulo de integração com a API Player TV (PLAYER REVENDAS)
https://playertv.sbs/api/v1/docs
"""

import requests
import json
import os
import time
from typing import Optional, Dict, List, Any

PLAYER_CONFIG_FILE = 'settings/player_config.json'
PLAYER_API_BASE_URL = 'https://playertv.sbs/api/v1'
_PRODUCTS_CACHE: List[Dict[str, Any]] = []
_PRODUCTS_CACHE_AT = 0.0
_PRODUCTS_CACHE_TTL_SECONDS = 60

def load_player_config() -> Dict[str, Any]:
    """Carrega a configuração da API Player"""
    try:
        if os.path.exists(PLAYER_CONFIG_FILE):
            with open(PLAYER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[PLAYER API] Erro ao carregar config: {e}")
    
    return {
        'api_key': '',
        'enabled': False
    }

def save_player_config(api_key: str, enabled: bool = True):
    """Salva a configuração da API Player"""
    os.makedirs(os.path.dirname(PLAYER_CONFIG_FILE), exist_ok=True)
    
    config = {
        'api_key': api_key.strip(),
        'enabled': enabled,
        'markup_percentage': get_markup_percentage(),
    }
    
    with open(PLAYER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_markup_percentage() -> float:
    try:
        value = float(load_player_config().get('markup_percentage', 0) or 0)
        return max(0.0, min(value, 500.0))
    except (TypeError, ValueError):
        return 0.0

def set_markup_percentage(value: float) -> float:
    percentage = max(0.0, min(float(value), 500.0))
    config = load_player_config()
    config['markup_percentage'] = percentage
    os.makedirs(os.path.dirname(PLAYER_CONFIG_FILE), exist_ok=True)
    with open(PLAYER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    return percentage

def get_sale_price(base_price: Any) -> float:
    return round(float(base_price or 0) * (1 + get_markup_percentage() / 100), 2)

def get_api_key() -> Optional[str]:
    """Retorna a chave da API Player configurada"""
    config = load_player_config()
    return config.get('api_key', '').strip() if config.get('enabled', False) else None

def is_player_enabled() -> bool:
    """Verifica se a integração Player está habilitada"""
    config = load_player_config()
    return config.get('enabled', False) and bool(config.get('api_key', '').strip())

def toggle_player_status():
    """Alterna o status da integração Player"""
    config = load_player_config()
    config['enabled'] = not config.get('enabled', False)
    
    with open(PLAYER_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    return config['enabled']

def get_headers() -> Dict[str, str]:
    """Retorna os headers para requisições à API Player"""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("API Key do Player não configurada")
    
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

def test_api_connection() -> tuple[bool, str]:
    """Testa a conexão com a API Player"""
    try:
        api_key = get_api_key()
        if not api_key:
            return False, "API Key não configurada"
        
        # Testa chamando o endpoint de produtos
        response = requests.get(
            f'{PLAYER_API_BASE_URL}/products',
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "Conexão estabelecida com sucesso!"
        elif response.status_code == 401:
            return False, "API Key inválida"
        else:
            return False, f"Erro: {response.status_code}"
            
    except Exception as e:
        return False, f"Erro ao conectar: {str(e)}"

def get_products() -> Optional[List[Dict]]:
    """
    Obtém lista de produtos disponíveis no catálogo Player
    
    Returns:
        Lista de produtos ou None em caso de erro
    """
    global _PRODUCTS_CACHE, _PRODUCTS_CACHE_AT
    if _PRODUCTS_CACHE and (time.monotonic() - _PRODUCTS_CACHE_AT) < _PRODUCTS_CACHE_TTL_SECONDS:
        return _PRODUCTS_CACHE

    try:
        if not is_player_enabled():
            return None
        
        response = requests.get(
            f'{PLAYER_API_BASE_URL}/products',
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # A API atual do Player responde {success, count, data}; versões
            # anteriores respondiam {products}. Aceita ambos os contratos.
            if isinstance(data, list):
                _PRODUCTS_CACHE = data
                _PRODUCTS_CACHE_AT = time.monotonic()
                return _PRODUCTS_CACHE
            if isinstance(data, dict):
                products = data.get('data', data.get('products', []))
                if isinstance(products, list):
                    _PRODUCTS_CACHE = products
                    _PRODUCTS_CACHE_AT = time.monotonic()
                    return _PRODUCTS_CACHE
                return []
            return []
        
        # Mantém o catálogo disponível em caso de instabilidade temporária do
        # Player, inclusive para buscas inline e detalhes de produtos.
        return _PRODUCTS_CACHE or None
        
    except Exception as e:
        print(f"[PLAYER API] Erro ao obter produtos: {e}")
        return None

def product_description(product: Dict) -> str:
    """Texto original da descrição, aceitando os nomes usados pelo fornecedor."""
    for field in ('description', 'descricao', 'descrição', 'details', 'instructions'):
        value = product.get(field)
        if isinstance(value, str) and value.strip():
            return value.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n').strip()
    return ''


def get_product_details(product_id: str) -> Optional[Dict]:
    """
    Obtém detalhes de um produto específico
    
    Args:
        product_id: ID do produto
        
    Returns:
        Detalhes do produto ou None em caso de erro
    """
    try:
        if not is_player_enabled():
            return None
        
        response = requests.get(
            f'{PLAYER_API_BASE_URL}/products/{product_id}',
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get('data'), dict):
                details = data['data']
            else:
                details = data if isinstance(data, dict) else None
            if details is not None:
                cached = next((p for p in _PRODUCTS_CACHE if str(p.get('id')) == str(product_id)), {})
                details = {**cached, **details}
                details['description'] = product_description(details) or product_description(cached)
            return details

        # O catálogo já contém preço, descrição e estoque. A versão atual da
        # API não expõe /products/{id}; por isso reutilizamos o item listado
        # para que tocar no produto continue funcionando.
        for product in get_products() or []:
            if str(product.get('id')) == str(product_id):
                return product
        return None
        
    except Exception as e:
        print(f"[PLAYER API] Erro ao obter detalhes do produto {product_id}: {e}")
        return None

def create_order(product_id: str, quantity: int = 1, user_telegram_id: Optional[int] = None) -> Optional[Dict]:
    """
    Cria um pedido na API Player
    
    Args:
        product_id: ID do produto a ser comprado
        quantity: Quantidade (padrão: 1)
        user_telegram_id: ID do usuário no Telegram (opcional)
        
    Returns:
        Dados do pedido ou None em caso de erro
    """
    try:
        if not is_player_enabled():
            return None
        
        payload = {
            'product_id': product_id,
            'quantity': quantity
        }
        
        if user_telegram_id:
            payload['customer_id'] = str(user_telegram_id)
        
        response = requests.post(
            f'{PLAYER_API_BASE_URL}/orders',
            headers=get_headers(),
            json=payload,
            timeout=15
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        
        return None
        
    except Exception as e:
        print(f"[PLAYER API] Erro ao criar pedido: {e}")
        return None

def get_order_status(order_id: str) -> Optional[Dict]:
    """
    Verifica o status de um pedido
    
    Args:
        order_id: ID do pedido
        
    Returns:
        Status do pedido ou None em caso de erro
    """
    try:
        if not is_player_enabled():
            return None
        
        response = requests.get(
            f'{PLAYER_API_BASE_URL}/orders/{order_id}',
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        
        return None
        
    except Exception as e:
        print(f"[PLAYER API] Erro ao verificar status do pedido {order_id}: {e}")
        return None

def get_balance() -> Optional[float]:
    """
    Obtém o saldo da conta Player
    
    Returns:
        Saldo em reais ou None em caso de erro
    """
    try:
        if not is_player_enabled():
            return None
        
        response = requests.get(
            f'{PLAYER_API_BASE_URL}/balance',
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return float(data.get('balance', 0))
        
        return None
        
    except Exception as e:
        print(f"[PLAYER API] Erro ao obter saldo: {e}")
        return None

def format_product_for_display(product: Dict) -> str:
    """
    Formata um produto para exibição no bot
    
    Args:
        product: Dicionário com dados do produto
        
    Returns:
        String formatada para exibição
    """
    name = product.get('name', 'Produto')
    price = product.get('price', 0)
    description = product.get('description', '')
    stock = product.get('stock', 0)
    
    text = f"🌍 <b>{name}</b>\n"
    text += f"💰 Preço: R$ {price:.2f}\n"
    
    if description:
        text += f"📝 {description}\n"
    
    if stock > 0:
        text += f"📦 Estoque: {stock} disponível(is)\n"
    else:
        text += "⚠️ <b>Sem estoque</b>\n"
    
    return text
