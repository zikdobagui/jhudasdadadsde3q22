import httpx
import json
import random

timeout = httpx.Timeout(40, pool=None)

hc = httpx.Client(http2=True, timeout=timeout)

virtualPayToken = "token virtualpay caso queira integrar futuramente"


def datauser():
    with open('pessoas.json', 'r', encoding='utf-8') as arquivo:
        data = json.load(arquivo)   
    if "pessoa" in data:
        pessoas = data["pessoa"]
        random.shuffle(pessoas)
        for pessoa in pessoas:
            cpf, nome = pessoa["cpf"], pessoa["nome"]
            sobrenome = nome.split()[-1] if nome.split() else nome
            nome_usuario = ''.join(c for c in nome if c.isalnum()).lower()
            email = f"{nome_usuario}@gmail.com"
            yield cpf, nome, email
