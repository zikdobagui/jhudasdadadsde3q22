#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para as funções de consulta de vendas
"""

import database
from datetime import datetime, timedelta

print("=" * 50)
print("TESTE DAS FUNÇÕES DE CONSULTA DE VENDAS")
print("=" * 50)

# Teste 1: Buscar vendas de uma data específica
print("\n1. Testando busca de vendas por data...")
data_teste = "11/02/2026"
vendas = database.get_sales_by_date(data_teste)
print(f"   Vendas encontradas para {data_teste}: {len(vendas)}")
if vendas:
    print(f"   Primeira venda: {vendas[0]['servico']} - R$ {vendas[0]['valor']}")

# Teste 2: Buscar vendas de hoje
print("\n2. Testando busca de vendas de hoje...")
hoje = datetime.now().strftime("%d/%m/%Y")
vendas_hoje = database.get_sales_by_date(hoje)
print(f"   Vendas de hoje ({hoje}): {len(vendas_hoje)}")

# Teste 3: Estatísticas do mês
print("\n3. Testando estatísticas do mês...")
agora = datetime.now()
inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
if agora.month == 12:
    fim_mes = agora.replace(year=agora.year + 1, month=1, day=1, hour=23, minute=59, second=59)
else:
    fim_mes = agora.replace(month=agora.month + 1, day=1, hour=23, minute=59, second=59)
fim_mes = fim_mes - timedelta(seconds=1)

stats = database.get_sales_stats(inicio_mes, fim_mes)
print(f"   Total de vendas no mês: {stats['total_vendas']}")
print(f"   Valor total: R$ {stats['total_valor']:.2f}")
if stats['total_vendas'] > 0:
    print(f"   Ticket médio: R$ {(stats['total_valor'] / stats['total_vendas']):.2f}")

# Teste 4: Top 5 produtos mais vendidos
print("\n4. Top 5 produtos mais vendidos do mês:")
produtos_ordenados = sorted(
    stats['produtos_vendidos'].items(),
    key=lambda x: x[1]['quantidade'],
    reverse=True
)
for i, (produto, info) in enumerate(produtos_ordenados[:5], 1):
    print(f"   {i}. {produto}")
    print(f"      Quantidade: {info['quantidade']} | Total: R$ {info['valor_total']:.2f}")

print("\n" + "=" * 50)
print("TESTES CONCLUÍDOS!")
print("=" * 50)
