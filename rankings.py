# rankings.py

import os
import json
import logging
from datetime import datetime, timedelta
import pytz

 
USER_DATA_DIR = 'database/users'

def load_all_users():
 
    users = []
    if os.path.exists(USER_DATA_DIR):
        for filename in os.listdir(USER_DATA_DIR):
            if filename.endswith('.json'):
                user_file = os.path.join(USER_DATA_DIR, filename)
                try:
                    with open(user_file, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                        users.append(user_data)
                except json.JSONDecodeError:
                    print(f"Erro ao decodificar o arquivo JSON: {user_file}")
    return users

def parse_date(date_str):
 
    date_formats = [
        "%d/%m/%Y as %H:%M:%S",  # Com 'as'
        "%d/%m/%Y às %H:%M:%S",  # Com 'às' (acento)
        "%d/%m/%Y %H:%M:%S"      # Sem 'as'
    ]
    for fmt in date_formats:
        try:
            
            return pytz.timezone('America/Sao_Paulo').localize(datetime.strptime(date_str, fmt))
        except ValueError:
            continue
    
    print(f"Formato de data inválido para: {date_str}")
    return None

def get_top_users_by_balance(top_n=20):
 
    users = load_all_users()
    sorted_users = sorted(users, key=lambda x: float(x.get('saldo', 0.0)), reverse=True)
    return sorted_users[:top_n]

def get_top_depositors(top_n=10):
 
    users = load_all_users()
    sorted_users = sorted(users, key=lambda x: float(x.get('total_pagos', 0.0)), reverse=True)
    return sorted_users[:top_n]

def get_top_recent_depositors(top_n=10, days=30):
 
    cutoff_date = datetime.now(pytz.timezone('America/Sao_Paulo')) - timedelta(days=days)
    users = load_all_users()
    recent_depositors = []

    for user in users:
        total_recent = 0.0
        for pagamento in user.get('pagamentos', []):
            pagamento_data_str = pagamento.get('data')
            if pagamento_data_str:
                pagamento_date = parse_date(pagamento_data_str)
                if pagamento_date and pagamento_date >= cutoff_date:
                    total_recent += float(pagamento.get('valor', 0.0))
        user['total_recent_pagos'] = total_recent
        recent_depositors.append(user)

    sorted_recent = sorted(recent_depositors, key=lambda x: float(x.get('total_recent_pagos', 0.0)), reverse=True)
    return sorted_recent[:top_n]

def get_top_products_last_30_days(top_n=10, days=30):
 
    cutoff_date = datetime.now(pytz.timezone('America/Sao_Paulo')) - timedelta(days=days)
    product_sales = {}
    users = load_all_users()

    for user in users:
        for compra in user.get('compras', []):
            servico = compra.get('servico') 
            compra_data_str = compra.get('data')
            if servico and compra_data_str:
                compra_date = parse_date(compra_data_str)
                if compra_date and compra_date >= cutoff_date:
                    servico_lower = servico.lower()
                    product_sales[servico_lower] = product_sales.get(servico_lower, 0) + 1

 
    product_sales_corrected = {servico.title(): vendas for servico, vendas in product_sales.items()}
    sorted_products = sorted(product_sales_corrected.items(), key=lambda x: x[1], reverse=True)
    return sorted_products[:top_n]
