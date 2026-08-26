import json
import os
import logging
from datetime import datetime, timedelta

# Diretório onde os dados dos usuários serão armazenados
USER_DATA_DIR = 'database/users'
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Função para salvar os dados do usuário em arquivos separados
def save_user_data(user_id, user_data):
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
    
    user_file = os.path.join(USER_DATA_DIR, f'{user_id}.json')
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=4)

# Função para carregar os dados do usuário
def load_user_data(user_id):
    user_file = os.path.join(USER_DATA_DIR, f'{user_id}.json')
    if os.path.exists(user_file):
        with open(user_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# Função para inicializar os dados de um novo usuário
def initialize_user(user_id, username=None):
    user_data = {
        "id": user_id,
        "username": username if username else f"User{user_id}",
        "banned": "False",
        "afiliado_por": 0,
        "saldo": 0.0,
        "gift_redeemed": 0.0,
        "total_compras": 0,
        "compras": [],
        "total_pagos": 0.0,
        "pagamentos": [],
        "pontos_indicado": 0,
        "afiliacoes": 0,
        "afiliados": []
    }
    save_user_data(user_id, user_data)
    return user_data

# Função para atualizar o saldo de um usuário
def update_user_balance(user_id, value):
    user_data = load_user_data(user_id)
    if user_data:
        user_data['saldo'] = float(user_data.get('saldo', 0.0)) + float(value)
        save_user_data(user_id, user_data)
        return True
    return False

# Função para verificar se o usuário está banido
def is_user_banned(user_id):
    user_data = load_user_data(user_id)
    if user_data:
        return user_data.get('banned', 'False') == 'True'
    return False

# Função para adicionar compra
def add_purchase(user_id, purchase):
    user_data = load_user_data(user_id)
    if user_data:
        user_data['compras'].append(purchase)
        user_data['total_compras'] += 1
        save_user_data(user_id, user_data)

# Função para adicionar pagamento
def add_payment(user_id, payment):
    user_data = load_user_data(user_id)
    if user_data:
        user_data['pagamentos'].append(payment)
        user_data['total_pagos'] += payment['valor']
        save_user_data(user_id, user_data)

# Função para adicionar saldo
def add_saldo(user_id, saldo):
    user_data = load_user_data(user_id)
    if user_data:
        user_data['saldo'] += float(saldo)
        save_user_data(user_id, user_data)

# Função para registrar pagamento
def add_pagamento(user_id, valor, id_pagamento):
    user_data = load_user_data(user_id)
    if user_data:
        user_data['total_pagos'] += float(valor)
        user_data['pagamentos'].append({
            'valor': valor,
            'id_pagamento': id_pagamento,
            'data': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        })
        save_user_data(user_id, user_data)

# Função para obter o saldo do usuário
def get_user_balance(user_id):
    user_data = load_user_data(user_id)
    if user_data:
        return user_data.get('saldo', 0.0)
    return 0.0

# Função para obter os top 20 usuários com maior saldo
def get_top_users(top_n=20):
    user_balances = []
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    user_id = user_data.get('id')
                    username = user_data.get('username', f'User{user_id}')
                    saldo = float(user_data.get('saldo', 0.0))
                    user_balances.append({
                        'username': username,
                        'id': user_id,
                        'saldo': saldo
                    })
    # Ordenar os usuários pelo saldo em ordem decrescente
    top_users = sorted(user_balances, key=lambda x: x['saldo'], reverse=True)
    # Selecionar os top N
    top_n_users = top_users[:top_n]
    return top_n_users

# Função para atualizar usernames
def update_usernames():
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                
                # Atualizar apenas se o username não estiver presente ou estiver no formato "User<ID>"
                if 'username' not in user_data or user_data['username'].startswith("User"):
                    user_id = user_data['id']
                    # Simula a busca do username (pode ser substituído por uma chamada à API do Telegram)
                    username = f"User{user_id}"  # Troque isso pela busca real se necessário
                    user_data['username'] = username
                    with open(user_file, "w", encoding="utf-8") as f:
                        json.dump(user_data, f, indent=4)

# Funções de Ranking Adicionais

# Função para obter o top 10 usuários com mais depósitos
def get_top_depositors(top_n=10):
    user_deposits = []
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    user_id = user_data.get('id')
                    username = user_data.get('username', f'User{user_id}')
                    total_pagos = float(user_data.get('total_pagos', 0.0))
                    user_deposits.append({
                        'username': username,
                        'id': user_id,
                        'total_pagos': total_pagos
                    })
    # Ordenar os usuários pelo total de depósitos em ordem decrescente
    top_depositors = sorted(user_deposits, key=lambda x: x['total_pagos'], reverse=True)[:top_n]
    return top_depositors

# Função para obter o top 10 usuários com mais depósitos nos últimos 30 dias
def get_top_recent_depositors(top_n=10, days=30):
    cutoff_date = datetime.now() - timedelta(days=days)
    user_recent_deposits = []
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    user_id = user_data.get('id')
                    username = user_data.get('username', f'User{user_id}')
                    total_recent_pagos = 0.0
                    for pagamento in user_data.get('pagamentos', []):
                        pagamento_date = datetime.strptime(pagamento.get('data'), "%d/%m/%Y %H:%M:%S")
                        if pagamento_date >= cutoff_date:
                            total_recent_pagos += float(pagamento.get('valor', 0.0))
                    user_recent_deposits.append({
                        'username': username,
                        'id': user_id,
                        'total_recent_pagos': total_recent_pagos
                    })
    # Ordenar os usuários pelo total de depósitos recentes em ordem decrescente
    top_recent_depositors = sorted(user_recent_deposits, key=lambda x: x['total_recent_pagos'], reverse=True)[:top_n]
    return top_recent_depositors

# Função para obter o top 10 produtos mais vendidos nos últimos 30 dias
def get_top_products_last_30_days(top_n=10, days=30):
    cutoff_date = datetime.now() - timedelta(days=days)
    product_sales = {}
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                with open(user_file, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    for compra in user_data.get('compras', []):
                        compra_date = datetime.strptime(compra.get('data'), "%d/%m/%Y %H:%M:%S")
                        if compra_date >= cutoff_date:
                            produto = compra.get('produto')
                            if produto:
                                product_sales[produto] = product_sales.get(produto, 0) + 1
    # Converter para lista de dicionários e ordenar
    product_sales_list = [{'produto': k, 'vendas': v} for k, v in product_sales.items()]
    top_products = sorted(product_sales_list, key=lambda x: x['vendas'], reverse=True)[:top_n]
    return top_products

# Função para obter todas as vendas de um dia específico
def get_sales_by_date(target_date):
    """
    Retorna todas as vendas realizadas em uma data específica.
    
    Args:
        target_date (str): Data no formato "DD/MM/YYYY"
    
    Returns:
        list: Lista de dicionários contendo informações das vendas
    """
    sales = []
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                try:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                        user_id = user_data.get('id')
                        username = user_data.get('username', f'User{user_id}')
                        
                        # Verificar cada compra do usuário
                        for compra in user_data.get('compras', []):
                            compra_data = compra.get('data', '')
                            # Extrair apenas a data (DD/MM/YYYY) da string completa
                            if 'às' in compra_data:
                                data_parte = compra_data.split('às')[0].strip()
                            else:
                                data_parte = compra_data.split()[0] if compra_data else ''
                            
                            # Comparar com a data alvo
                            if data_parte == target_date:
                                sales.append({
                                    'user_id': user_id,
                                    'username': username,
                                    'servico': compra.get('servico', 'N/A'),
                                    'valor': compra.get('valor', '0'),
                                    'email': compra.get('email', 'N/A'),
                                    'senha': compra.get('senha', 'N/A'),
                                    'data_completa': compra_data
                                })
                except Exception as e:
                    logging.error(f"Erro ao processar arquivo {filename}: {e}")
                    continue
    
    # Ordenar por horário
    sales.sort(key=lambda x: x['data_completa'])
    return sales

# Função para obter estatísticas de vendas por período
def get_sales_stats(start_date=None, end_date=None):
    """
    Retorna estatísticas de vendas em um período.
    
    Args:
        start_date (datetime): Data inicial (opcional)
        end_date (datetime): Data final (opcional)
    
    Returns:
        dict: Dicionário com estatísticas
    """
    total_vendas = 0
    total_valor = 0.0
    produtos_vendidos = {}
    
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                try:
                    with open(user_file, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                        
                        for compra in user_data.get('compras', []):
                            compra_data_str = compra.get('data', '')
                            try:
                                # Tentar extrair a data
                                if 'às' in compra_data_str:
                                    data_str = compra_data_str.replace('às', '').strip()
                                    compra_date = datetime.strptime(data_str, "%d/%m/%Y %H:%M:%S")
                                else:
                                    continue
                                
                                # Verificar se está no período
                                if start_date and compra_date < start_date:
                                    continue
                                if end_date and compra_date > end_date:
                                    continue
                                
                                # Contabilizar
                                total_vendas += 1
                                valor = float(compra.get('valor', 0))
                                total_valor += valor
                                
                                servico = compra.get('servico', 'N/A')
                                if servico in produtos_vendidos:
                                    produtos_vendidos[servico]['quantidade'] += 1
                                    produtos_vendidos[servico]['valor_total'] += valor
                                else:
                                    produtos_vendidos[servico] = {
                                        'quantidade': 1,
                                        'valor_total': valor
                                    }
                            except Exception:
                                continue
                except Exception as e:
                    logging.error(f"Erro ao processar arquivo {filename}: {e}")
                    continue
    
    return {
        'total_vendas': total_vendas,
        'total_valor': total_valor,
        'produtos_vendidos': produtos_vendidos
    }

# =====================
# Sistema de Carrinho de Compras
# =====================

# Dicionário temporário para armazenar carrinhos (em memória)
# Formato: {user_id: [{'servico': 'nome', 'valor': 10.0, 'quantidade': 1}, ...]}
carrinhos = {}

def get_carrinho(user_id):
    """Retorna o carrinho do usuário"""
    return carrinhos.get(user_id, [])

def add_to_carrinho(user_id, servico, valor):
    """Adiciona um item ao carrinho"""
    if user_id not in carrinhos:
        carrinhos[user_id] = []
    
    # Verificar se o produto já está no carrinho
    for item in carrinhos[user_id]:
        if item['servico'] == servico:
            item['quantidade'] += 1
            return True
    
    # Se não está, adicionar novo item
    carrinhos[user_id].append({
        'servico': servico,
        'valor': float(valor),
        'quantidade': 1
    })
    return True

def remove_from_carrinho(user_id, servico):
    """Remove um item do carrinho"""
    if user_id not in carrinhos:
        return False
    
    carrinhos[user_id] = [item for item in carrinhos[user_id] if item['servico'] != servico]
    return True

def update_quantidade_carrinho(user_id, servico, quantidade):
    """Atualiza a quantidade de um item no carrinho"""
    if user_id not in carrinhos:
        return False
    
    for item in carrinhos[user_id]:
        if item['servico'] == servico:
            if quantidade <= 0:
                remove_from_carrinho(user_id, servico)
            else:
                item['quantidade'] = quantidade
            return True
    return False

def clear_carrinho(user_id):
    """Limpa o carrinho do usuário"""
    if user_id in carrinhos:
        carrinhos[user_id] = []
    return True

def get_carrinho_total(user_id):
    """Retorna o valor total do carrinho"""
    if user_id not in carrinhos:
        return 0.0
    
    total = sum(item['valor'] * item['quantidade'] for item in carrinhos[user_id])
    return total

def get_carrinho_quantidade_total(user_id):
    """Retorna a quantidade total de itens no carrinho"""
    if user_id not in carrinhos:
        return 0
    
    return sum(item['quantidade'] for item in carrinhos[user_id])

# =====================
# Sistema de Notificação de Reabastecimento
# =====================

# Dicionário para armazenar notificações de reabastecimento
# Formato: {user_id: [{'produto': 'netflix', 'produto_normalizado': 'netflix'}, ...]}
notificacoes_reabastecimento = {}

def normalizar_produto(produto):
    """Normaliza o nome do produto para comparação"""
    import re
    # Converter para minúsculas e remover caracteres especiais
    normalizado = produto.lower()
    normalizado = re.sub(r'[^a-z0-9\s]', '', normalizado)
    normalizado = re.sub(r'\s+', ' ', normalizado).strip()
    return normalizado

def adicionar_notificacao_reabastecimento(user_id, produto):
    """Adiciona uma notificação de reabastecimento para o usuário"""
    if user_id not in notificacoes_reabastecimento:
        notificacoes_reabastecimento[user_id] = []
    
    produto_normalizado = normalizar_produto(produto)
    
    # Verificar se já existe
    for item in notificacoes_reabastecimento[user_id]:
        if item['produto_normalizado'] == produto_normalizado:
            return False  # Já existe
    
    notificacoes_reabastecimento[user_id].append({
        'produto': produto,
        'produto_normalizado': produto_normalizado
    })
    return True

def remover_notificacao_reabastecimento(user_id, produto):
    """Remove uma notificação de reabastecimento"""
    if user_id not in notificacoes_reabastecimento:
        return False
    
    produto_normalizado = normalizar_produto(produto)
    
    notificacoes_reabastecimento[user_id] = [
        item for item in notificacoes_reabastecimento[user_id]
        if item['produto_normalizado'] != produto_normalizado
    ]
    return True

def get_notificacoes_reabastecimento(user_id):
    """Retorna todas as notificações de reabastecimento do usuário"""
    return notificacoes_reabastecimento.get(user_id, [])

def get_usuarios_aguardando_produto(produto):
    """Retorna lista de user_ids que estão aguardando um produto"""
    produto_normalizado = normalizar_produto(produto)
    usuarios = []
    
    for user_id, notificacoes in notificacoes_reabastecimento.items():
        for item in notificacoes:
            if item['produto_normalizado'] == produto_normalizado:
                usuarios.append(user_id)
                break
    
    return usuarios

def limpar_notificacoes_reabastecimento(user_id):
    """Limpa todas as notificações de um usuário"""
    if user_id in notificacoes_reabastecimento:
        notificacoes_reabastecimento[user_id] = []
    return True

def total_notificacoes_reabastecimento(user_id):
    """Retorna o total de notificações ativas do usuário"""
    return len(notificacoes_reabastecimento.get(user_id, []))
