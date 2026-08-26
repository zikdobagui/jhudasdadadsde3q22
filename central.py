import mercadopago
import json
import time
import telebot
import uuid
import datetime
import random
import html
import pytz
import os
import threading
from datetime import timezone
from database import load_user_data, save_user_data
from pytz import timezone
from utils import hc, virtualPayToken, datauser

DEFAULT_DATABASE_FILES = {
    'database/admins.json': {"admins": []},
    'database/acessos.json': {"acessos": []},
    'database/gift_card.json': {"gift": []},
    'database/info_transmitir.json': {"texto": None, "photo": None, "markup": None},
    'database/custom_descriptions.json': {"descriptions": {}},
    'database/reserve_verified.json': {},
    'database/users.json': {"users": []},
}
DEFAULT_TEXT_FILES = {
    'log/registro.txt': (
        "👤 <b>NOVO USUÁRIO REGISTRADO</b>\n\n"
        "• <b>ID:</b> <code>{id}</code>\n"
        "• <b>Nome:</b> {name}\n"
        "• <b>Username:</b> {username}\n"
        "• <b>Perfil:</b> {link}"
    ),
    'log/compra.txt': (
        "🛒 <b>NOVA COMPRA</b>\n\n"
        "• <b>Cliente:</b> {name}\n"
        "• <b>ID:</b> <code>{id}</code>\n"
        "• <b>Username:</b> {username}\n"
        "• <b>Serviço:</b> {servico}\n"
        "• <b>Valor:</b> R${valor}\n"
        "• <b>Saldo após compra:</b> R${saldo}\n"
        "• <b>Data:</b> {data} às {hora}\n\n"
        "• <b>Email/Login:</b> <code>{email}</code>\n"
        "• <b>Senha:</b> <code>{senha}</code>\n"
        "• <b>Descrição:</b> {descricao}"
    ),
    'log/recarga.txt': (
        "💰 <b>NOVA RECARGA</b>\n\n"
        "• <b>Cliente:</b> {name}\n"
        "• <b>ID:</b> <code>{id}</code>\n"
        "• <b>Username:</b> {username}\n"
        "• <b>Pagamento:</b> <code>{id_pagamento}</code>\n"
        "• <b>Valor:</b> R${valor}\n"
        "• <b>Saldo atual:</b> R${saldo}\n"
        "• <b>Data:</b> {data} às {hora}"
    ),
}

os.makedirs('database/users', exist_ok=True)

def ensure_default_database_file(filepath):
    normalized = filepath.replace('\\', '/')
    default = DEFAULT_DATABASE_FILES.get(normalized)
    if default is None or os.path.exists(filepath):
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(default, f, indent=4, ensure_ascii=False)

def ensure_default_text_file(filepath):
    normalized = filepath.replace('\\', '/')
    default = DEFAULT_TEXT_FILES.get(normalized)
    if default is None or os.path.exists(filepath):
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(default)

def open_utf8(filepath, mode='r'):
    if 'r' in mode and '+' not in mode:
        ensure_default_database_file(filepath)
        ensure_default_text_file(filepath)
    return open(filepath, mode, encoding='utf-8')

class ViewTime():
    def data_atual():
        data_e_hora_atuais = datetime.datetime.now()
        data_e_hora_em_texto = data_e_hora_atuais.strftime('%d/%m/%Y')
        return data_e_hora_em_texto
    def hora_atual():
        data_e_hora_atuais = datetime.datetime.now()
        fuso_horario = timezone('America/Sao_Paulo')
        data_e_hora_sao_paulo = data_e_hora_atuais.astimezone(fuso_horario)
        hora_sao_paulo_em_texto = data_e_hora_sao_paulo.strftime('%H:%M:%S')
        hora_sao_paulo = datetime.datetime.strptime(hora_sao_paulo_em_texto, '%H:%M:%S').time()
        return hora_sao_paulo
class CredentialsChange():
    def user_bot():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return str(data["user_bot"])
    def mudar_user_bot(user):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["user_bot"] = str(user)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def token_bot():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return str(data["api-bot"])
    def mudar_token_bot(token):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["api-bot"] = str(token)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def versao_bot():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return str(data["version"])
    def mudar_versao_bot(version):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["version"] = version
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def verificar_premium():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        if int(data["premium"]) == 0:
            return False
        elif int(data["premium"]) == 1:
            return True
    def separador():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return str(data["separador"])
    def mudar_separador(separador):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["separador"] = separador
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def status_manutencao():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        if data["maintance"] == 'on':
            return True
        else:
            return False
    def mudar_status_manutencao():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        if data["maintance"] == "on":
            data["maintance"] = "off"
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return
        else:
            data["maintance"] = "on"
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return
    def id_dono():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        dono_id = data["id_dono"]
        return int(dono_id)
    def mudar_dono(id):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["id_dono"] = int(id)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    
    def modo_exibicao():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return data.get("modo_exibicao", "lista_direta")
    
    def mudar_modo_exibicao(modo):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["modo_exibicao"] = modo
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    
    class SuporteInfo():
        def link_suporte():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return str(data["link_suporte"])
        def mudar_link_suporte(link):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["link_suporte"] = str(link)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
    class StatusPix():
        def pix_manual():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            if str(data["status_pix_manu"]) == 'on':
                return True
            else:
                return False
        def pix_auto():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            if str(data["status_pix_auto"]) == 'on':
                return True
            else:
                return False
    class ChangeStatusPix():
        def change_pix_manual():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            if str(data["status_pix_manu"]) == 'on':
                data["status_pix_manu"] = 'off'
                with open_utf8('settings/credenciais.json', 'w') as f:
                    json.dump(data, f, indent=4)
                return
            else:
                data["status_pix_manu"] = 'on'
                with open_utf8('settings/credenciais.json', 'w') as f:
                    json.dump(data, f, indent=4)
                return False
        def change_pix_auto():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            if str(data["status_pix_auto"]) == 'on':
                data["status_pix_auto"] = 'off'
                with open_utf8('settings/credenciais.json', 'w') as f:
                    json.dump(data, f, indent=4)
                return
            else:
                data["status_pix_auto"] = 'on'
                with open_utf8('settings/credenciais.json', 'w') as f:
                    json.dump(data, f, indent=4)
                return False
    class BonusPix():
        def quantidade_bonus():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return int(data["bonus_pix"])
        def mudar_quantidade_bonus(porcentagem):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["bonus_pix"] = int(porcentagem)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return
        def valor_minimo_para_bonus():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return int(data["bonus_pix_min"])
        def mudar_valor_minimo_para_bonus(valor_min):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["bonus_pix_min"] = int(valor_min)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
    class BonusRegistro():
        def bonus():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return float(data["bonus_registro"])
        def mudar_bonus(novo_bonus):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["bonus_registro"] = float(novo_bonus)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
    class InfoPix():
        def token_mp():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            token = data["token_mp"]
            return str(token)
        def mudar_tokenmp(token):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["token_mp"] = str(token)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
            return
        def deposito_minimo_pix():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return float(data["min_pix"])
        def trocar_deposito_minimo_pix(min):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["min_pix"] = float(min)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return
        def deposito_maximo_pix():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return float(data["max_pix"])
        def trocar_deposito_maximo_pix(max):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["max_pix"] = float(max)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return
        def expiracao():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            expiracao_time = data["expiracao_pix"]
            return int(expiracao_time)
        def mudar_expiracao(minutes):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            data["expiracao_pix"] = int(minutes)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
                return True
        def misticpay_client_id():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return str(data.get('gateway_pagamento', {}).get('misticpay', {}).get('client_id', ''))
        def misticpay_client_secret():
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            return str(data.get('gateway_pagamento', {}).get('misticpay', {}).get('client_secret', ''))
        def salvar_misticpay(client_id=None, client_secret=None):
            with open_utf8('settings/credenciais.json', 'r') as f:
                data = json.load(f)
            if 'gateway_pagamento' not in data:
                data['gateway_pagamento'] = {}
            if 'misticpay' not in data['gateway_pagamento']:
                data['gateway_pagamento']['misticpay'] = {}
            if client_id is not None:
                data['gateway_pagamento']['misticpay']['client_id'] = str(client_id)
            if client_secret is not None:
                data['gateway_pagamento']['misticpay']['client_secret'] = str(client_secret)
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
class AfiliadosInfo():
    def status_afiliado():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        if data["afiliados"] == 'on':
            return True
        else:
            return False
    def mudar_status_afiliado():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        if data["afiliados"] == 'on':
            data["afiliados"] = "off"
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
            return
        else:
            data["afiliados"] = "on"
            with open_utf8('settings/credenciais.json', 'w') as f:
                json.dump(data, f, indent=4)
            return
    def pontos_por_recarga():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return float(data["pontos_by_indicate_buy"])
    def mudar_pontos_por_recarga(pontos):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["pontos_by_indicate_buy"] = float(pontos)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
        return
    def minimo_pontos_pra_saldo():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return data["min_points_saldo"]
    def trocar_minimo_pontos_pra_saldo(min):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["min_points_saldo"] = int(min)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def multiplicador_pontos():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return float(data["multiplicador_pontos"])
    def trocar_multiplicador_pontos(multiplicador):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["multiplicador_pontos"] = float(multiplicador)
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
class Notificacoes():
    def modo_servico():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["tipo_texto"])
    def mudar_modo_servico():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        if data["tipo_texto"] == 0:
            data["tipo_texto"] = 1
        else:
            data["tipo_texto"] = 0
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def status_notificacoes():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        if data["status_notify"] == 'on':
            return True
        else:
            return False
    def mudar_status_notificacoes():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        if data["status_notify"] == 'on':
            data["status_notify"] = 'off'
            with open_utf8('settings/notify.json', 'w') as f:
                json.dump(data, f, indent=4)
            return
        else:
            data["status_notify"] = 'on'
            with open_utf8('settings/notify.json', 'w') as f:
                json.dump(data, f, indent=4)
            return
    def id_grupo():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["id_grupo"])
    def trocar_id_grupo(id_grupo):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["id_grupo"] = int(id_grupo)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
        return
    def min_max_ids():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data.get("id_min", 898012903)), int(data.get("id_max", 4290812093))
    def trocar_min_max_ids(id_min, id_max):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["id_min"] = int(id_min)
        data["id_max"] = int(id_max)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
        return
    def tempo_minimo_compras():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["time_min_compras"])
    def quantidade_de_servicos_pra_sortear():
        with open_utf8('settings/notificacao/servicos.txt', 'r') as f:
            file = f.read()
        quantidade = 0
        servicos = file.strip().split('\n')
        for servico in servicos:
            if len(servico) > 0:
                quantidade += 1
            pass
        return quantidade


    def pegar_servico_random():
        with open('settings/notificacao/servicos.txt', 'r', encoding='utf-8') as f:
            file = f.read()

        # Remove linhas em branco e espaços desnecessários
        file = [line.strip() for line in file.splitlines() if line.strip()]

        # Filtra as linhas que possuem 'R$' e exclui as que não seguem o formato
        valid_lines = [line for line in file if 'R$' in line]

        if not valid_lines:
            raise ValueError("Nenhuma linha válida com 'R$' foi encontrada no arquivo.")
        
        while True:
            servico = random.choice(valid_lines)
            try:
                # Divide o serviço pelo 'R$' para pegar nome e valor
                separar = servico.split('R$')
                servico_nome = separar[0].strip()
                valor = separar[1].strip()
                return servico_nome, f'R${valor}'
            except IndexError:
                print(f"Linha '{servico}' não contém o formato esperado 'R$'. Pulando...")

    # Teste
    nome_servico, valor_servico = pegar_servico_random()
    print(f"Serviço: {nome_servico}, Valor: {valor_servico}")

    def pegar_servicos_disponiveis():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        nomes = []
        for acesso in data["acessos"]:
            if acesso["nome"] in nomes:
                pass
            nomes.append({"nome": acesso["nome"], "valor": acesso["valor"]})
        sort = random.choice(nomes)
        return sort["nome"], f'R${sort["valor"]:.2f}'
    def mudar_servicos_random(lista):
        with open_utf8('settings/notificacao/servicos.txt', 'w') as f:
            f.write(lista)
    def trocar_tempo_minimo_compras(min):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["time_min_compras"] = int(min)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def tempo_maximo_compras():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["time_max_compras"])
    def trocar_tempo_maximo_compras(max):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["time_max_compras"] = int(max)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def tempo_minimo_saldo():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["time_min_saldo"])
    def trocar_tempo_minimo_saldo(min):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["time_min_saldo"] = int(min)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def tempo_maximo_saldo():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return int(data["time_max_saldo"])
    def trocar_tempo_maximo_saldo(max):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["time_max_saldo"] = int(max)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def min_max_saldo():
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        return float(data["saldo_min"]), float(data["saldo_max"])
    def trocar_min_max_saldo(min, max):
        with open_utf8('settings/notify.json', 'r') as f:
            data = json.load(f)
        data["saldo_min"] = int(min)
        data["saldo_max"] = int(max)
        with open_utf8('settings/notify.json', 'w') as f:
            json.dump(data, f, indent=4)
    def pegar_texto_saldo():
        with open_utf8('settings/notificacao/saldo.txt', 'r') as f:
            return f.read()
    def mudar_texto_saldo(texto):
        with open_utf8('settings/notificacao/saldo.txt', 'w') as f:
            f.write(texto)
    def pegar_texto_compra():
        with open_utf8('settings/notificacao/compra.txt', 'r') as f:
            return f.read()
    def mudar_texto_compra(texto):
        with open_utf8('settings/notificacao/compra.txt', 'w') as f:
            f.write(texto)
    def texto_notificacao_saldo():
        texto = Notificacoes.pegar_texto_saldo()
        id_min, id_max = Notificacoes.min_max_ids()
        id = random.randint(min(id_min, id_max), max(id_min, id_max))
        saldo_min, saldo_max = Notificacoes.min_max_saldo()
        saldo =  random.randint(int(saldo_min), int(saldo_max))
        texto = texto.replace('{id}', f'{id}').replace('{saldo}', f'{saldo}')
        return texto
    def texto_notificacao_compra():
        texto = Notificacoes.pegar_texto_compra()
        id_min, id_max = Notificacoes.min_max_ids()
        id = random.randint(min(id_min, id_max), max(id_min, id_max))
        if Notificacoes.modo_servico() == 0:
            servico, valor = Notificacoes.pegar_servico_random()
        else:
            servico, valor = Notificacoes.pegar_servicos_disponiveis()
        texto = texto.replace('{id}', f'{id}').replace('{servico}', f'{servico}').replace('{valor}', f'{valor}')
        return texto
class InfoUser():
    def verificar_usuario(id):
        user_data = load_user_data(id)
        return user_data is not None

    def novo_afiliado(usuario, indicador):
        user_data_usuario = load_user_data(usuario)
        user_data_indicador = load_user_data(indicador)
        
        if user_data_usuario and user_data_indicador:
            if user_data_usuario["afiliado_por"] != 0:
                return
            user_data_usuario["afiliado_por"] = int(indicador)
            user_data_indicador["afiliacoes"] += 1
            user_data_indicador["afiliados"].append({"id_afiliado": int(usuario)})
            
            save_user_data(usuario, user_data_usuario)
            save_user_data(indicador, user_data_indicador)

    def novo_usuario(id):
        user_data = {
            "id": int(id),
            "banned": "False",
            "afiliado_por": 0,
            "saldo": 0,
            "gift_redeemed": 0,
            "total_compras": 0,
            "compras": [],
            "total_pagos": 0,
            "pagamentos": [],
            "pontos_indicado": 0,
            "afiliacoes": 0,
            "afiliados": []
        }
        save_user_data(id, user_data)


    def verificar_ban(id):
        user_data = load_user_data(id)
        if user_data and user_data.get("banned") == "True":
            return True
            return False

            pass
        
    def dar_ban(id):
        user_data = load_user_data(id)
        if user_data:
            user_data["banned"] = "True"
            save_user_data(id, user_data)

    def tirar_ban(id):
        user_data = load_user_data(id)
        if user_data:
            user_data["banned"] = "False"
            save_user_data(id, user_data)

    def quantidade_afiliados(id):
        user_data = load_user_data(id)
        if user_data:
            return len(user_data.get("afiliados", []))
            return 0

    def saldo(id):
        user_data = load_user_data(id)
        if user_data:
            return float(user_data.get("saldo", 0))
        return 0

    def add_saldo(id, novo_saldo):
        user_data = load_user_data(id)
        if user_data:
            user_data["saldo"] += float(novo_saldo)
            save_user_data(id, user_data)


    def tirar_saldo(id, novo_saldo):
        user_data = load_user_data(id)
        if user_data:
            saldo = user_data["saldo"]
            user_data["saldo"] = float(saldo) - float(novo_saldo)
            save_user_data(id, user_data)

    def mudar_saldo(id, novo_saldo):
        user_data = load_user_data(id)
        if user_data:
            user_data["saldo"] = float(novo_saldo)
            save_user_data(id, user_data)

    def gifts_resgatados(id):
        user_data = load_user_data(id)
        if user_data:
            return float(user_data["gift_redeemed"])
        return 0

    def total_compras(id):
        user_data = load_user_data(id)
        if user_data:
            return user_data.get("total_compras", 0)
        return 0

    def total_pagos(id):
        user_data = load_user_data(id)
        if user_data:
            return user_data.get("total_pagos", 0)
        return 0

    def pix_inseridos(id):
        user_data = load_user_data(id)
        if user_data:
            total_pix = sum([float(pagamento["valor"]) for pagamento in user_data.get("pagamentos", [])])
            return total_pix
        return 0

    def pontos_indicacao(id):
        user_data = load_user_data(id)
        if user_data:
            return user_data.get("pontos_indicado", 0)
        return 0

    def trocar_pontos(id):
        user_data = load_user_data(id)
        if user_data:
            pontos = user_data.get("pontos_indicado", 0)
            if pontos >= AfiliadosInfo.minimo_pontos_pra_saldo():
                saldo_novo = pontos * AfiliadosInfo.multiplicador_pontos()
                user_data["pontos_indicado"] = 0
                user_data["saldo"] += saldo_novo
                save_user_data(id, user_data)
                return True
        return False

    def fazer_txt_do_historico(id):
        user_data = load_user_data(id)
        if user_data:
            historico = f'HISTÓRICO DETALHADO @{CredentialsChange.user_bot()}\n_______________________\n\nCOMPRAS:\n'
            for compra in user_data.get("compras", []):
                historico += f'Serviço: {compra["servico"]}\nValor: {compra["valor"]}\nEmail: {compra["email"]}\nSenha: {compra["senha"]}\nData: {compra["data"]}\n\n'

            historico += '_______________________\n\nPAGAMENTOS:\n'
            for pagamento in user_data.get("pagamentos", []):
                historico += f'Id pagamento: {pagamento["id_pagamento"]}\nValor: {pagamento["valor"]}\nData: {pagamento["data"]}\n\n'

            with open_utf8(f'historicos/{id}.txt', 'w') as f:
                f.write(historico)
            return True
        return False

class MudancaHistorico():
    def mudar_gift_resgatado(id, valor):
        with open_utf8('database/users.json') as f:
            data = json.load(f)
        for user in data["users"]:
            if int(user["id"]) == int(id):
                user["gift_redeemed"] += float(valor)
                with open_utf8('database/users.json', 'w') as f:
                    json.dump(data, f, indent=4)
                break
            pass
    def add_compra(id, servico, valor, email, senha):
        user_data = load_user_data(id)
        if user_data:
            user_data["total_compras"] += 1
            user_data["compras"].append({
                "servico": servico,
                "valor": valor,
                "email": email,
                "senha": senha,
                "data": f"{ViewTime.data_atual()} às {ViewTime.hora_atual()}"
            })
            save_user_data(id, user_data)

    def add_pagamentos(id, valor, id_pag):
        user_data = load_user_data(id)
        if user_data:
            user_data["total_pagos"] += 1
            user_data["pagamentos"].append({"id_pagamento": id_pag, "valor": valor, "data": f"{ViewTime.data_atual()} as {ViewTime.hora_atual()}"})
            InfoUser.add_saldo(id, valor)  # Adicionar saldo aqui
            save_user_data(id, user_data)

            afiliado_por = user_data["afiliado_por"]
            if AfiliadosInfo.status_afiliado() == True and afiliado_por != 0:
                indicador_data = load_user_data(afiliado_por)
                if indicador_data:
                    comissao = round(float(valor) * float(AfiliadosInfo.pontos_por_recarga()) / 100, 2)
                    indicador_data["saldo"] = float(indicador_data.get("saldo", 0)) + comissao
                    indicador_data["pontos_indicado"] = float(indicador_data.get("pontos_indicado", 0)) + comissao
                    save_user_data(afiliado_por, indicador_data)

    def zerar_pontos(id):
        user_data = load_user_data(id)
        if user_data:
            user_data["pontos_indicado"] = 0
            save_user_data(id, user_data)

class GiftCard():
    def validar_gift(codigo):
        with open_utf8("database/gift_card.json", 'r') as f:
            data = json.load(f)
        for gift in data['gift']:
            if gift["codigo"] == codigo:
                valor = float(gift["valor"])
                return True, valor
        return False, 0
    def listar_gift():
        with open_utf8('database/gift_card.json', 'r') as f:
            data = json.load(f)
        msg = ''
        for gift in data["gift"]:
            msg += f'<code>{gift["codigo"]}</code> R${float(gift["valor"]):.2f}\n'
        return msg
    def create_gift(codigo, valor):
        with open_utf8("database/gift_card.json", 'r') as f:
            data = json.load(f)
        data["gift"].append({"codigo": codigo, "valor": float(valor)})
        with open_utf8("database/gift_card.json", 'w') as j:
            json.dump(data, j, indent=4)
        return True
    def del_gift(codigo):
        with open_utf8("database/gift_card.json", 'r') as f:
            data = json.load(f)
        for gift in data["gift"]:
            if gift["codigo"] == codigo:
                data["gift"].remove(gift)
                with open_utf8("database/gift_card.json", 'w') as f:
                    json.dump(data, f, indent=4)
                return True
            pass
        return False

class FuncaoTransmitir():
    def formatar_html(texto, entities):
        padrao_tags_html = r"<\/?[a-zA-Z]+[^>]*>"
        tags_encontradas = re.findall(padrao_tags_html, texto)
        if tags_encontradas:
            return texto
        tags_html = {
            'bold': ('<b>', '</b>'),
            'italic': ('<i>', '</i>'),
            'code': ('<code>', '</code>')
        }
        formatted_text = texto
        offset_adjustment = 0
        entities = sorted(entities, key=lambda e: e["offset"], reverse=True)
        for entity in entities:
            entity_type = entity["type"]
            start_offset = entity["offset"] + offset_adjustment
            end_offset = start_offset + entity["length"]
            if entity_type in tags_html:
                tag_abertura, tag_fechamento = tags_html[entity_type]
                formatted_text = formatted_text[:start_offset] + tag_abertura + formatted_text[start_offset:end_offset] + tag_fechamento + formatted_text[end_offset:]
                offset_adjustment += len(tag_abertura) + len(tag_fechamento)
        return formatted_text
    def pegar_foto():
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
            return data["photo"]
    def pegar_texto():
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
            return data["texto"]
    def pegar_markup():
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
            return data["markup"]
    def adicionar_foto(photo):
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
        data["photo"] = photo
        with open_utf8('database/info_transmitir.json', 'w') as f:
            data = json.dump(data, f, indent=4)
    def adicionar_texto(txt):
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
        data["texto"] = txt
        with open_utf8('database/info_transmitir.json', 'w') as f:
            json.dump(data, f, indent=4)
    def adicionar_entitie(ent):
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
        entities = []
        if ent == None:
            return
        for entity in ent:
            entities.append(entity.to_dict())
        txt = FuncaoTransmitir.formatar_html(data["texto"], entities)
        data["texto"] = txt
        with open_utf8('database/info_transmitir.json', 'w') as f:
            json.dump(data, f, indent=4)
    def adicionar_markup(markup):
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
        if markup is not None:
            inline_keyboard = []
            for row in markup.keyboard:
                row_buttons = []
                for but in row:
                    button_dict = {
                        'text': but.text,
                        'url': but.url
                    }
                    row_buttons.append(button_dict)
                inline_keyboard.append(row_buttons)
            data["markup"] = inline_keyboard
        else:
            data["markup"] = None
        with open_utf8('database/info_transmitir.json', 'w') as f:
            json.dump(data, f, indent=4)
    def zerar_infos():
        with open_utf8('database/info_transmitir.json', 'r') as f:
            data = json.load(f)
        data["texto"] = None
        data["photo"] = None
        data["markup"] = None
        with open_utf8('database/info_transmitir.json', 'w') as f:
            json.dump(data, f, indent=4)

# Outras importações e código acima...

class FuncaoTransmitir:
    _foto = None
    _texto = None
    _markup = None
    _video = None  # Variável para armazenar o vídeo

    @staticmethod
    def adicionar_foto(foto):
        FuncaoTransmitir._foto = foto

    @staticmethod
    def pegar_foto():
        return FuncaoTransmitir._foto

    @staticmethod
    def adicionar_video(video):
        FuncaoTransmitir._video = video  # Armazena o caminho do vídeo

    @staticmethod
    def pegar_video():
        return FuncaoTransmitir._video  # Retorna o caminho do vídeo

    @staticmethod
    def adicionar_texto(texto):
        FuncaoTransmitir._texto = texto

    @staticmethod
    def pegar_texto():
        return FuncaoTransmitir._texto

    @staticmethod
    def adicionar_markup(markup):
        FuncaoTransmitir._markup = markup

    @staticmethod
    def pegar_markup():
        return FuncaoTransmitir._markup

    @staticmethod
    def zerar_infos():
        FuncaoTransmitir._foto = None
        FuncaoTransmitir._video = None  # Reseta o vídeo também
        FuncaoTransmitir._texto = None
        FuncaoTransmitir._markup = None

# Outras classes ou funções podem continuar aqui...

class ControleLogins():
    _registry_lock = threading.RLock()
    _registry_path = 'database/login_registry.json'

    @staticmethod
    def _normalizar_conta(nome, email):
        return f'{str(nome).strip().casefold()}|{str(email).strip().casefold()}'

    @classmethod
    def _carregar_registro(cls):
        if os.path.exists(cls._registry_path):
            try:
                with open_utf8(cls._registry_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get('contas'), dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass

        contas = {}
        try:
            with open_utf8('database/acessos.json', 'r') as f:
                acessos = json.load(f).get('acessos', [])
            for acesso in acessos:
                nome, email = acesso.get('nome'), acesso.get('email')
                if nome and email:
                    contas[cls._normalizar_conta(nome, email)] = {
                        'servico': str(nome).strip(),
                        'login': str(email).strip(),
                        'origem': 'estoque_existente'
                    }
        except (OSError, json.JSONDecodeError):
            pass

        users_dir = 'database/users'
        if os.path.isdir(users_dir):
            for filename in os.listdir(users_dir):
                if not filename.endswith('.json'):
                    continue
                try:
                    with open_utf8(os.path.join(users_dir, filename), 'r') as f:
                        compras = json.load(f).get('compras', [])
                    for compra in compras:
                        nome, email = compra.get('servico'), compra.get('email')
                        if nome and email:
                            contas[cls._normalizar_conta(nome, email)] = {
                                'servico': str(nome).strip(),
                                'login': str(email).strip(),
                                'origem': 'historico_de_compra'
                            }
                except (OSError, json.JSONDecodeError, AttributeError):
                    continue

        data = {'contas': contas}
        os.makedirs(os.path.dirname(cls._registry_path), exist_ok=True)
        with open_utf8(cls._registry_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    @classmethod
    def inicializar_registro(cls):
        with cls._registry_lock:
            return len(cls._carregar_registro().get('contas', {}))
  
    @classmethod
    def peek_primeiro_disponivel(cls, servico: str):
 
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        
        for acesso in data["acessos"]:
            if acesso["nome"].lower() == servico.lower():
                return (
                    acesso["nome"],
                    acesso["valor"],
                    acesso["email"],
                    acesso["senha"],
                    acesso["descricao"],
                    acesso["duracao"]
                )
        return None

  
    def add_login(nome, valor, descricao, email, senha, duracao):
        with ControleLogins._registry_lock:
            registro = ControleLogins._carregar_registro()
            chave = ControleLogins._normalizar_conta(nome, email)
            if chave in registro['contas']:
                return False

            with open_utf8('database/acessos.json', 'r') as f:
                data = json.load(f)
            data["acessos"].append({"nome": nome, "valor": valor, "descricao": descricao, "email": email, "senha": senha, "duracao": duracao})
            with open_utf8('database/acessos.json', 'w') as f:
                json.dump(data, f, indent=4)

            registro['contas'][chave] = {
                'servico': str(nome).strip(),
                'login': str(email).strip(),
                'origem': 'cadastro'
            }
            with open_utf8(ControleLogins._registry_path, 'w') as f:
                json.dump(registro, f, indent=2, ensure_ascii=False)
            return True
    # remover login
    def remover_login(nome, email):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if acesso["nome"] == nome and acesso["email"] == email:
                data["acessos"].remove(acesso)
                with open_utf8('database/acessos.json', 'w') as f:
                    json.dump(data, f, indent=4)
                    return True
            pass
        return False
    # listar servicos
    def pegar_servicos():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        lista = []
        for acesso in data["acessos"]:
            lista.append({"nome": acesso["nome"], "valor": acesso["valor"]})
            pass
        return lista
    def estoque_total():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        quantity = 0
        for acesso in data["acessos"]:
            quantity +=1
        return quantity
    # pegar estoque por nome
    def pegar_estoque(nome):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        quantidade = 0
        for acesso in data["acessos"]:
            if acesso["nome"] == nome:
                quantidade +=1
            pass
        return quantidade
    def pegar_estoque_detalhado():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        ja_foram = []
        lista = []
        for acesso in data["acessos"]:
            if acesso["nome"] not in ja_foram:
                quant = ControleLogins.pegar_estoque(acesso["nome"])
                lista.append({"nome": acesso["nome"], "quantidade": quant})
                ja_foram.append(acesso["nome"])
                continue
            else:
                pass
        montagem = "<b>ACESSOS EM ESTOQUE:</b>\n"
        logins = ''
        for login in lista:
            nome = login["nome"]
            quantidade = login["quantidade"]
            logins += f'\n{nome}: {quantidade}'
        montagem += f"\n<code>{logins}</code>"
        return montagem
    def criar_estoque_detalhado():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        mensagem = "ACESSOS EM ESTOQUE:\n"
        for acesso in data["acessos"]:
            mensagem += f'\n\nNome: {acesso["nome"]}\nValor: {acesso["valor"]}\nDescricao: {acesso["descricao"]}\nEmail: {acesso["email"]}\nSenha: {acesso["senha"]}\nDuracao: {acesso["duracao"]}'
        with open_utf8('historicos/estoque_detalhado.txt', 'w') as f:
            f.write(mensagem)
        return True
    def arquivo_estoque_detalhado():
        with open_utf8('historicos/estoque_detalhado.txt', 'rb') as file:
            return file
    def remover_por_nome(nome):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if str(acesso["nome"]) == str(nome):
                data["acessos"].remove(acesso)
            else:
                pass
        with open_utf8('database/acessos.json', 'w') as f:
            json.dump(data, f, indent=4)
        return True
    def zerar_estoque():
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        data["acessos"] = []
        with open_utf8('database/acessos.json', 'w') as f:
            json.dump(data, f, indent=4)
        return True

    def mudar_valor_por_nome(nome, novo_valor):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if acesso["nome"] == nome:
                acesso["valor"] = float(novo_valor)
                continue
            pass
        with open_utf8('database/acessos.json', 'w') as f:
            json.dump(data, f, indent=4)
    def mudar_valor_de_todos(valor):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            acesso["valor"] = float(valor)
            continue
        with open_utf8('database/acessos.json', 'w') as f:
            json.dump(data, f, indent=4)
    def pegar_info(nome):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if acesso["nome"] == nome:
                return acesso["nome"], acesso["valor"], acesso["descricao"],  acesso["duracao"], acesso["email"]
        # Se não encontrou o produto, retorna valores padrão
        return nome, "0.00", "Produto não encontrado", "30", "nao@encontrado.com"
    def entregar_acesso(nome, email):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if acesso["nome"] == nome:
                if acesso["email"] == email:
                    return acesso["nome"], acesso["valor"], acesso["email"], acesso["senha"], acesso["descricao"],  acesso["duracao"]
                else:
                    pass
            else:
                pass
    def pegar_info_entrega(nome, email):
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        for acesso in data["acessos"]:
            if acesso["nome"] == nome:
                if acesso["email"] == email:
                    return acesso
                else:
                    pass
            else:
                pass
    @staticmethod
    def pegar_primeiro_disponivel(servico: str):
        """
        Retorna o primeiro login do tipo `servico`.
        Remove do estoque para não vender duplicado.

        Se não achar nenhum, retorna None.
        Se achar, retorna (nome, valor, email, senha, descricao, duracao).
        """
        with open_utf8('database/acessos.json', 'r') as f:
            data = json.load(f)
        
        for acesso in data["acessos"]:
            if acesso["nome"].lower() == servico.lower():
                # Remove imediatamente do estoque para não duplicar venda
                data["acessos"].remove(acesso)
                with open_utf8('database/acessos.json', 'w') as fw:
                    json.dump(data, fw, indent=4)
                
                # Retorna o “pacote” de informações
                return (
                    acesso["nome"],
                    acesso["valor"],
                    acesso["email"],
                    acesso["senha"],
                    acesso["descricao"],
                    acesso["duracao"]
                )

        # Se não achar nada:
        return None
             



class Admin():
    def total_users():
        user_files = os.listdir('database/users')
        return len(user_files)

    def verificar_vencimento():
        time = Admin.tempo_ate_o_vencimento()
        if int(time) <= 0:
            return True
    def data_vencimento():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return str(data["vencimento_bot"])
    def tempo_ate_o_vencimento():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data_vencimento_str = data['vencimento_bot']
        data_vencimento = datetime.datetime.strptime(data_vencimento_str, '%d/%m/%Y').date()
        data_atual = datetime.datetime.now().date()
        diferenca = data_vencimento - data_atual
        return diferenca.days
    def aumentar_vencimento(dias):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        vencimento = int(dias)
        vencimento_bot_str = data['vencimento_bot']
        vencimento_bot = datetime.datetime.strptime(vencimento_bot_str, '%d/%m/%Y')
        nova_data = vencimento_bot + datetime.timedelta(days=vencimento)
        data["vencimento_bot"] = nova_data.strftime('%d/%m/%Y')
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
            return True
    def diminuir_vencimento(days):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        vencimento = int(days)
        vencimento_str = data["vencimento_bot"]
        vencimento_bot = datetime.datetime.strptime(vencimento_str, '%d/%m/%Y')
        nova_data = vencimento_bot - datetime.timedelta(days=vencimento)
        data["vencimento_bot"] = nova_data.strftime('%d/%m/%Y')
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def zerar_vencimento():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["vencimento_bot"] = '01/01/2023'
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def receita_total():
        receita = 0.0
        user_files = os.listdir('database/users')  # Lista todos os arquivos de usuário
        for user_file in user_files:
            user_data = load_user_data(user_file.split('.')[0])  # Carrega os dados do usuário
            if user_data and user_data["total_pagos"] > 0:
                for pagamento in user_data["pagamentos"]:
                    receita += float(pagamento["valor"])
        return receita

    def receita_hoje():
        receita_dia = 0.0
        tz = pytz.timezone('America/Sao_Paulo')
        today = datetime.datetime.now(tz).strftime('%d/%m/%Y')

        user_files = os.listdir('database/users')  # Lista todos os arquivos de usuário
        for user_file in user_files:
            user_data = load_user_data(user_file.split('.')[0])  # Carrega os dados do usuário
            if user_data and user_data["total_pagos"] > 0:
                for pagamento in user_data["pagamentos"]:
                    if str(pagamento['data'].split(' ')[0]) == str(today):
                        receita_dia += float(pagamento['valor'])
        return receita_dia

    def acessos_vendidos():
        user_files = os.listdir('database/users')
        quantidade = 0
        for user_file in user_files:
            user_data = load_user_data(user_file.split('.')[0])
            if user_data and user_data["total_compras"] > 0:
                quantidade += user_data["total_compras"]
        return quantidade

    def acessos_vendidos_hoje():
        tz = pytz.timezone('America/Sao_Paulo')
        today = datetime.datetime.now(tz).strftime('%d/%m/%Y')
        quantidade = 0
        
        user_files = os.listdir('database/users')
        for user_file in user_files:
            user_data = load_user_data(user_file.split('.')[0])
            if user_data and user_data["total_compras"] > 0:
                for compra in user_data["compras"]:
                    if compra["data"].split(' ')[0] == today:
                        quantidade += 1
        return quantidade

    def verificar_admin(id):
        with open_utf8('database/admins.json', 'r') as f:
            data = json.load(f)
        for admin in data["admins"]:
            if int(admin["id"]) == int(id):
                return True
            pass
        return False
    def add_admin(id):
        with open_utf8('database/admins.json', 'r') as f:
            data = json.load(f)
        data["admins"].append({"id": int(id)})
        with open_utf8('database/admins.json', 'w') as f:
            json.dump(data, f, indent=4)
        return True
    def quantidade_admin():
        with open_utf8('database/admins.json', 'r') as f:
            data = json.load(f)
        quantity = 0
        for admin in data["admins"]:
            quantity +=1
        return quantity
    def listar_admins():
        with open_utf8('database/admins.json', 'r') as f:
            data = json.load(f)
        adm_list = '<b>👮 LISTA DE ADMINS:</b> 🚨\n\n'
        for admin in data["admins"]:
            adm_list += f'\n<b>ADMIN ID</b>: <code>{admin["id"]}</code>'
        return adm_list
    def remover_admin(id):
        with open_utf8('database/admins.json', 'r') as f:
            data = json.load(f)
        for admin in data["admins"]:
            if int(admin["id"]) == int(id):
                data["admins"].remove(admin)
                with open_utf8('database/admins.json', 'w') as f:
                    json.dump(data, f, indent=4)
                return True
            pass
class Textos():
    def start(message):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        if str(message.chat.id).startswith('-'):
            id = message.from_user.id
            first_name = message.from_user.first_name
            username = message.from_user.username
        link_afiliado = f'https://t.me/{CredentialsChange.user_bot()}?start={message.chat.id}'
        saldo = InfoUser.saldo(id)
        pontos_indicacao = InfoUser.pontos_indicacao(id)
        quantidade_afiliados = InfoUser.quantidade_afiliados(id)
        quantidade_compras = InfoUser.total_compras(id)
        pix_inseridos = f'{InfoUser.pix_inseridos(id):.2f}'
        gifts_resgatados = f'{InfoUser.gifts_resgatados(id):.2f}'

        # Garantindo que o arquivo seja lido com a codificação UTF-8
        with open_utf8('textos/start.txt', 'r') as f:
            texto = f.read()

        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}') \
                    .replace('{id}', f'{id}').replace('{link_afiliado}', f'{link_afiliado}') \
                    .replace('{saldo}', f'{saldo:.2f}').replace('{pontos_indicacao}', f'{pontos_indicacao}') \
                    .replace('{quantidade_afiliados}', f'{quantidade_afiliados}') \
                    .replace('{quantidade_compras}', f'{quantidade_compras}') \
                    .replace('{pix_inseridos}', f'{pix_inseridos}') \
                    .replace('{gifts_resgatados}', f'{gifts_resgatados}')
        
        return texto

    def perfil(message):
        first_name = message.first_name or ''
        last_name = message.last_name or ''
        full_name = ' '.join(part for part in (first_name, last_name) if part).strip()
        username = f'@{message.username}' if message.username else 'Não informado'
        id = message.id
        saldo = InfoUser.saldo(id)
        quantidade_compras = InfoUser.total_compras(id)
        pix_inseridos = f'{InfoUser.pix_inseridos(id):.2f}'
        gifts_resgatados = f'{InfoUser.gifts_resgatados(id):.2f}'
        with open_utf8('textos/perfil.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', html.escape(first_name)) \
                    .replace('{full_name}', html.escape(full_name or 'Não informado')) \
                    .replace('{username}', html.escape(username)) \
                    .replace('{id}', f'{id}') \
                    .replace('{saldo}', f'{saldo:.2f}') \
                    .replace('{quantidade_compras}', f'{quantidade_compras}') \
                    .replace('{pix_inseridos}', f'{pix_inseridos}') \
                    .replace('{gifts_resgatados}', f'{gifts_resgatados}')
        return texto
    def adicionar_saldo(message):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        link_afiliado = f'https://t.me/{CredentialsChange.user_bot()}?start={message.chat.id}'
        saldo = InfoUser.saldo(id)
        pontos_indicacao = InfoUser.pontos_indicacao(id)
        quantidade_afiliados = InfoUser.quantidade_afiliados(id)
        quantidade_compras = InfoUser.total_compras(id)
        pix_inseridos = f'{InfoUser.pix_inseridos(id):.2f}'
        gifts_resgatados = f'{InfoUser.gifts_resgatados(id):.2f}'
        with open_utf8('textos/adicionar_saldo.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{link_afiliado}', f'{link_afiliado}').replace('{saldo}', f'{saldo:.2f}').replace('{pontos_indicacao}', f'{pontos_indicacao}').replace('{quantidade_afiliados}', f'{quantidade_afiliados}').replace('{quantidade_compras}', f'{quantidade_compras}').replace('{pix_inseridos}', f'{pix_inseridos}').replace('{gifts_resgatados}', f'{gifts_resgatados}')
        return texto
    def pix_manual(message):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        saldo = InfoUser.saldo(id)
        deposito_minimo = f'{CredentialsChange.InfoPix.deposito_minimo_pix():.2f}'
        with open_utf8('textos/pix_manual.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{saldo}', f'{saldo:.2f}').replace('{deposito_minimo}', f'{deposito_minimo}')
        return texto
    def pix_automatico(message, pix_copia_cola, expiracao, id_pagamento, valor):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        saldo = InfoUser.saldo(id)
        deposito_minimo = f'{CredentialsChange.InfoPix.deposito_minimo_pix():.2f}'
        pix_inseridos = f'{InfoUser.pix_inseridos(id):.2f}'
        with open_utf8('textos/pix_automatico.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{saldo}', f'{saldo:.2f}').replace('{pix_inseridos}', f'{pix_inseridos}').replace('{pix_copia_cola}', f'{pix_copia_cola}').replace('{expiracao}', f'{expiracao}').replace('{id_pagamento}', f'{id_pagamento}').replace('{valor}', f'{valor}').replace('{deposito_minimo}', f'{deposito_minimo}')
        return texto
    def pagamento_expirado(message, id_pagamento, valor):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        link_afiliado = f'https://t.me/{CredentialsChange.user_bot()}?start={message.chat.id}'
        saldo = InfoUser.saldo(id)
        with open_utf8('textos/pagamento_expirado.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{link_afiliado}', f'{link_afiliado}').replace('{saldo}', f'{saldo:.2f}').replace('{id_pagamento}', f'{id_pagamento}').replace('{valor}', f'{valor}')
        return texto
    def pagamento_aprovado(message, id_pagamento, valor):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        link_afiliado = f'https://t.me/{CredentialsChange.user_bot()}?start={message.chat.id}'
        saldo = InfoUser.saldo(id)
        with open_utf8('textos/pagamento_aprovado.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{link_afiliado}', f'{link_afiliado}').replace('{saldo}', f'{saldo:.2f}').replace('{id_pagamento}', f'{id_pagamento}').replace('{valor}', f'{valor}')
        return texto
    def menu_comprar(message):
        first_name = message.chat.first_name
        username = message.chat.username
        id = message.chat.id
        link_afiliado = f'https://t.me/{CredentialsChange.user_bot()}?start={message.chat.id}'
        saldo = InfoUser.saldo(id)
        pontos_indicacao = InfoUser.pontos_indicacao(id)
        quantidade_afiliados = InfoUser.quantidade_afiliados(id)
        quantidade_compras = InfoUser.total_compras(id)
        pix_inseridos = InfoUser.pix_inseridos(id)
        gifts_resgatados = InfoUser.gifts_resgatados(id)
        with open_utf8('textos/menu_comprar.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{first_name}', f'{first_name}').replace('{username}', f'@{username}').replace('{id}', f'{id}').replace('{link_afiliado}', f'{link_afiliado}').replace('{saldo}', f'{saldo:.2f}').replace('{pontos_indicacao}', f'{pontos_indicacao}').replace('{quantidade_afiliados}', f'{quantidade_afiliados}').replace('{quantidade_compras}', f'{quantidade_compras}').replace('{pix_inseridos}', f'{pix_inseridos}').replace('{gifts_resgatados}', f'{gifts_resgatados}')
        return texto
    def exibir_servico(message, nome):
        saldo = InfoUser.saldo(message.chat.id)
        nome_servico, valor, descricao, duracao, email = ControleLogins.pegar_info(nome)
        estoque = ControleLogins.pegar_estoque(nome)
        with open_utf8('textos/exibir_servico.txt', 'r') as f:
            texto = f.read()
        
        # Verificar se existe descrição personalizada (por nome exato do produto)
        try:
            import json
            with open_utf8('database/custom_descriptions.json', 'r') as f:
                custom_data = json.load(f)
            custom_desc = custom_data.get('descriptions', {}).get(nome_servico)
            if custom_desc:
                descricao = custom_desc
        except Exception:
            # Se não conseguir carregar, usa a descrição padrão
            pass
        
        texto = texto.replace('{nome_servico}', f'{nome_servico}').replace('{valor}', f'{float(valor):.2f}').replace('{descricao}', f'{descricao}').replace('{saldo}', f'{float(saldo):.2f}').replace('{estoque}', f'{estoque}').replace('{duracao}', f'{duracao}')
        return texto, email
    def mensagem_comprou(message, nome, valor, email, senha, descricao, duracao):
        saldo = InfoUser.saldo(message.chat.id)
        with open_utf8('textos/mensagem_comprou.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{nome}', f'{nome}').replace('{valor}', f'{valor}').replace('{saldo}', f'{saldo:.2f}').replace('{email}', f'{email}').replace('{senha}', f'{senha}').replace('{duracao}', f'{duracao}').replace('{descricao}', f'{descricao}')
        return texto
    @staticmethod
    def mensagem_comprou_inline(user_id, nome, valor, email, senha, descricao, duracao):
        """
        Retorna exatamente o mesmo texto do 'mensagem_comprou',
        porém usando 'user_id' em vez de 'message', para não ter problema de inline.
        """
        saldo = InfoUser.saldo(user_id)  # Pega saldo pelo ID
        with open_utf8('textos/mensagem_comprou.txt', 'r') as f:
            texto = f.read()
        texto = (texto
            .replace('{nome}', f'{nome}')
            .replace('{valor}', f'{valor}')
            .replace('{saldo}', f'{float(saldo):.2f}')
            .replace('{email}', f'{email}')
            .replace('{senha}', f'{senha}')
            .replace('{duracao}', f'{duracao}')
            .replace('{descricao}', f'{descricao}')
        )
        return texto
    

class MudarTexto():
    def alugar_bot(texto):
        with open_utf8('botoes/alugar_bot.txt', 'w') as f:
            f.write(texto)
    def start(texto):
        with open_utf8('textos/start.txt', 'r') as f:
            f.write(texto)
    def perfil(texto):
        with open_utf8('textos/perfil.txt', 'w') as f:
            f.write(texto)
    def adicionar_saldo(texto):
        with open_utf8('textos/adicionar_saldo.txt', 'w') as f:
            f.write(texto)
    def pix_manual(texto):
        with open_utf8('textos/pix_manual.txt', 'w') as f:
            f.write(texto)
    def pix_automatico(texto):
        with open_utf8('textos/pix_automatico.txt', 'w') as f:
            f.write(texto)
    def pagamento_expirado(texto):
        with open_utf8('textos/pagamento_expirado.txt', 'w') as f:
            f.write(texto)
    def pagamento_aprovado(texto):
        with open_utf8('textos/pagamento_aprovado.txt', 'w') as f:
            f.write(texto)
    def menu_comprar(texto):
        with open_utf8('textos/menu_comprar.txt', 'w') as f:
            f.write(texto)
    def exibir_servico(texto):
        with open_utf8('textos/exibir_servico.txt', 'w') as f:
            f.write(texto)
    def mensagem_comprou(texto):
        with open_utf8('textos/mensagem_comprou.txt', 'w') as f:
            f.write(texto)
class Botoes():
    def alugar_bot():
        with open_utf8('botoes/alugar_bot.txt', 'r') as f:
            return f.read()
    def comprar():
        with open_utf8('botoes/comprar.txt', 'r') as f:
            return f.read()
    def perfil():
        with open_utf8('botoes/perfil.txt', 'r') as f:
            return f.read()
    def addsaldo():
        with open_utf8('botoes/addsaldo.txt', 'r') as f:
            return f.read()
    def suporte():
        with open_utf8('botoes/suporte.txt', 'r') as f:
            return f.read()
    def voltar():
        with open_utf8('botoes/voltar.txt', 'r') as f:
            return f.read()
    def comprar_login():
        with open_utf8('botoes/comprar_loguin.txt', 'r') as f:
            return f.read()
    def pix_manual():
        with open_utf8('botoes/pix_manual.txt', 'r') as f:
            return f.read()
    def pix_automatico():
        with open_utf8('botoes/pix_automatico.txt', 'r') as f:
            return f.read()
    def download_historico():
        with open_utf8('botoes/download_historico.txt', 'r') as f:
            return f.read()
    def trocar_pontos_por_saldo():
        with open_utf8('botoes/trocar_pontos_por_saldo.txt', 'r') as f:
            return f.read()
    def aguardando_pagamento():
        try:
            with open_utf8('botoes/aguardando_pagamento.txt', 'r') as f:
                return f.read()
        except:
            with open_utf8('botoes/aguardando_pagamnto.txt', 'w') as f:
                f.write('⏰ AGUARDANDO PAGAMENTO')
                return '⏰ AGUARDANDO PAGAMENTO'
class MudarBotao():
    def alugar_bot(texto):
        with open_utf8('botoes/alugar_bot.txt', 'w') as f:
            f.write(texto)
    def comprar(texto):
        with open_utf8('botoes/comprar.txt', 'w') as f:
            f.write(texto)
    def perfil(texto):
        with open_utf8('botoes/perfil.txt', 'w') as f:
            f.write(texto)
    def addsaldo(texto):
        with open_utf8('botoes/addsaldo.txt', 'w') as f:
            f.write(texto)
    def suporte(texto):
        with open_utf8('botoes/suporte.txt', 'w') as f:
            f.write(texto)
    def voltar(texto):
        with open_utf8('botoes/voltar.txt', 'w') as f:
            f.write(texto)
    def comprar_login(texto):
        with open_utf8('botoes/comprar_login.txt', 'w') as f:
            f.write(texto)
    def pix_manual(texto):
        with open_utf8('botoes/pix_manual.txt', 'w') as f:
            f.write(texto)
    def pix_automatico(texto):
        with open_utf8('botoes/pix_automatico.txt', 'w') as f:
            f.write(texto)
    def download_historico(texto):
        with open_utf8('botoes/download_historico.txt', 'w') as f:
            f.write(texto)
    def trocar_pontos_por_saldo(texto):
        with open_utf8('botoes/trocar_pontos_por_saldo.txt', 'w') as f:
            f.write(texto)
    def aguardando_pagamento(texto):
        with open_utf8('botoes/aguardando_pagamento.txt', 'w') as f:
            f.write(texto)
class Log():
    def id_log_destino():
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        return data["destino_log"]
    def mudar_destino_logs(id):
        with open_utf8('settings/credenciais.json', 'r') as f:
            data = json.load(f)
        data["destino_log"] = id
        with open_utf8('settings/credenciais.json', 'w') as f:
            json.dump(data, f, indent=4)
    def log_registro(message):
        with open_utf8('log/registro.txt', 'r') as f:
            txt = f.read()
        if message == None:
            return txt
        id = message.chat.id
        name = message.chat.first_name
        username = message.chat.username
        link = f'https://t.me/{username}'
        texto = txt.replace('{id}', f'{id}').replace('{name}', f'{name}').replace('{username}', f'@{username}').replace('{link}', f'{link}').replace('\\n', '\n')
        return texto
    def log_compra(message, servico, email, senha, valor, descricao):
        with open_utf8('log/compra.txt', 'r') as f:
            txt = f.read()
        if message == None:
            return txt
        id = message.chat.id
        name = message.chat.first_name
        username = message.chat.username
        link = f'https://t.me/{username}'
        data = ViewTime.data_atual()
        hora = ViewTime.hora_atual()
        saldo = InfoUser.saldo(message.chat.id)
        texto = txt.replace('{id}', f'{id}').replace('{name}', f'{name}').replace('{username}', f'@{username}').replace('{link}', f'{link}').replace('{data}', f'{data}').replace('{hora}', f'{hora}').replace('{email}', f'{email}').replace('{senha}', f'{senha}').replace('{valor}', f'{float(valor):.2f}').replace('{servico}', f'{servico}').replace('\\n', '\n').replace('{saldo}', f'{float(saldo):.2f}').replace('{descricao}', f'{descricao}')
        return texto
    def log_recarga(message, id_pagamento, valor):
        with open_utf8('log/recarga.txt', 'r') as f:
            txt = f.read()
        if message == None:
            return txt
        id = message.chat.id
        name = message.chat.first_name
        username = message.chat.username
        link = f'https://t.me/{username}'
        data = ViewTime.data_atual()
        hora = ViewTime.hora_atual()
        saldo = InfoUser.saldo(message.chat.id)
        texto = txt.replace('{id}', f'{id}').replace('{name}', f'{name}').replace('{username}', f'@{username}').replace('{link}', f'{link}').replace('{data}', f'{data}').replace('{hora}', f'{hora}').replace('{id_pagamento}', f'{id_pagamento}').replace('{valor}', f'{float(valor):.2f}').replace('{saldo}', f'{float(saldo):.2f}').replace('\\n', '\n')
        return texto
    @staticmethod
    def log_compra_inline(user_id, nome, email, senha, valor, descricao):
        """
        Versão do log para compra inline, sem precisar do objeto 'message'.
        Copia o corpo do log_compra, mas pega o 'nome' e 'username' do user_data.
        """
        # 1) Carrega user_data para pegar o first_name e username
        user_data = InfoUser.verificar_usuario(user_id)
        if not user_data:
            # Se não achar, define um fallback
            first_name = "UserSemNome"
            username = f"{user_id}"
        else:
            # Se user_data for “True”, significa que load_user_data existe
            # Mas você precisará pegar o user_data inteiro, por ex.:
            real_data = load_user_data(user_id)
            first_name = real_data.get('first_name', 'UserSemNome')
            username   = real_data.get('username', f"{user_id}")

        link = f"https://t.me/{username}"
        
        data = ViewTime.data_atual()
        hora = ViewTime.hora_atual()
        saldo = InfoUser.saldo(user_id)

        # 2) Ler o template original (compra.txt)
        with open_utf8('log/compra.txt', 'r') as f:
            txt = f.read()

        # 3) Substituir as tags
        texto = (
            txt
            .replace('{id}', f'{user_id}')
            .replace('{name}', f'{first_name}')
            .replace('{username}', f'@{username}')
            .replace('{link}', f'{link}')
            .replace('{data}', f'{data}')
            .replace('{hora}', f'{hora}')
            .replace('{email}', f'{email}')
            .replace('{senha}', f'{senha}')
            .replace('{valor}', f'{float(valor):.2f}')
            .replace('{servico}', f'{nome}')
            .replace('{saldo}', f'{float(saldo):.2f}')
            .replace('{descricao}', f'{descricao}')
            .replace('\\n', '\n')
        )
        return texto

class MudarLog():
    def log_registro(txt):
        with open_utf8('log/registro.txt', 'w') as f:
            f.write(txt)
    def log_compra(txt):
        with open_utf8('log/compra.txt', 'w') as f:
            f.write(txt)
    def log_recarga(txt):
        with open_utf8('log/recarga.txt', 'w') as f:
            f.write(txt)
class TextoInline():
    def giftcard(message, codigo, quantidade, valor):
        with open_utf8('textos/giftcard.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{codigo}', f'{codigo}').replace('{quantidade}', f'{quantidade}').replace('{valor}', f'{valor}')
        return texto
    def pix_gerado_inline(valor, pix_copia_cola, id_pagamento):
        with open_utf8('textos/pix_gerado_inline.txt', 'r') as f:
            texto = f.read()
        expiracao = CredentialsChange.InfoPix.expiracao()
        texto = texto.replace('{valor}', f'{valor}').replace('{id_pagamento}', f'{id_pagamento}').replace('{pix_copia_cola}', f'{pix_copia_cola}').replace('{expiracao}', f'{expiracao}')
        return texto
    def pagamento_aprovado(message, valor, id_pagamento):
        with open_utf8('textos/aprovado_inline.txt', 'r') as f:
            texto = f.read()
        texto = texto.replace('{valor}', f'{valor}').replace('{id_pagamento}', f'{id_pagamento}')
        return texto
class MudarTextoInline():
    def mudar_giftcar(txt):
        with open_utf8('textos/giftcard.txt', 'w') as f:
            f.write(txt)
    def mudar_pix_gerado(txt):
        with open_utf8('textos/pix_gerado_inline.txt', 'w') as f:
            f.write(txt)
    def mudar_pagamento_aprovado(txt):
        with open_utf8('textos/aprovado_inline.txt', 'w') as f:
            f.write(txt)

class CriarPixMisticPay():
    BASE_URL = 'https://api.misticpay.com'

    def gerar(valor, user_id):
        import requests
        import uuid
        client_id = CredentialsChange.InfoPix.misticpay_client_id()
        client_secret = CredentialsChange.InfoPix.misticpay_client_secret()
        headers = {
            'ci': client_id,
            'cs': client_secret,
            'Content-Type': 'application/json',
        }
        dataus = datauser()
        cpf, nome, email = next(dataus)
        payload = {
            'amount': float(valor),
            'payerName': nome,
            'payerDocument': cpf,
            'transactionId': str(uuid.uuid4()),
            'description': f'Recarga de {valor} para {user_id}',
        }
        resp = requests.post(f'{CriarPixMisticPay.BASE_URL}/api/transactions/create', headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def consultar_saldo():
        import requests
        client_id = CredentialsChange.InfoPix.misticpay_client_id()
        client_secret = CredentialsChange.InfoPix.misticpay_client_secret()
        headers = {'ci': client_id, 'cs': client_secret}
        resp = requests.get(f'{CriarPixMisticPay.BASE_URL}/api/balance', headers=headers)
        resp.raise_for_status()
        return resp.json()

    def verificar_transacao(transaction_id):
        import requests
        client_id = CredentialsChange.InfoPix.misticpay_client_id()
        client_secret = CredentialsChange.InfoPix.misticpay_client_secret()
        headers = {
            'ci': client_id, 
            'cs': client_secret,
            'Content-Type': 'application/json'
        }
        payload = {'transactionId': transaction_id}
        resp = requests.post(f'{CriarPixMisticPay.BASE_URL}/api/transactions/check', headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


class CriarPix():    
      
     def gerar(valor, id):
         sdk = mercadopago.SDK(str(CredentialsChange.InfoPix.token_mp()))
         expiracao_time = CredentialsChange.InfoPix.expiracao()
         expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=int(expiracao_time))
         expire = expire.strftime("%Y-%m-%dT%H:%M:%S.000Z")
         payment_data = {
             "transaction_amount": float(valor),
             "description":f'Recarga de {valor} para {id}',
             "payment_method_id": 'pix',
             "date_of_expiration": f'{expire}',
             "payer": {
                 "email": 'Stalkerzinho@outlook.com'
             }
         }
         result = sdk.payment().create(payment_data)
         return result
    

# estrutura da virtualpay caso algum momento queirar usar XD #Tv Player 14/03/2025
#   
#class CriarPix():
#    def gerar(valor, id):
#        dataus = datauser()
#        cpf, full_name, email = next(dataus)
#    
#        payment = hc.post(
#            "https://virtualpay.online/api/v1/transactions/deposit",
#            headers={
#                "Content-Type": "application/json",
#                "Accept": "application/json",
#                "Authorization": f"Bearer {virtualPayToken}",
#            },
#            json={
#                "amount": float(valor),
#                "document": cpf,
#                "name": full_name,
#                "description": f"Recarga de {valor} para {id}",
#            }
#        )
#
#        transaction: dict = payment.json()
#
#        return {
#            "payment_id": transaction.get('id'),
#            "copy_paste": transaction.get('qr_code'),
#            "status": transaction.get('status')
#        }

        
