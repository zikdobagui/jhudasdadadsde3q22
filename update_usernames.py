import os
import json
import time
import threading
from telebot import TeleBot



time.sleep(100000)
# Substitua pelo token do seu bot
BOT_TOKEN = "7440448387:AAHBRSuGpSTkotResBumqPCLWXnIwUux4s4"

# Diretório onde os arquivos JSON estão localizados
USER_DATA_DIR = 'database/users'  # Diretório correto

# Inicializar o bot
bot = TeleBot(BOT_TOKEN, parse_mode=None)

def get_username_by_id(user_id):
    """
    Obtém o username (@) ou o nome do Telegram a partir do ID do usuário.
    """
    try:
        user = bot.get_chat(user_id)
        if user.username:
            return f"{user.username}"  # Retorna o @username se disponível
        elif user.first_name:
            return user.first_name  # Retorna o nome se o @username não estiver disponível
        else:
            return f"Usuario sem @"  # Caso nenhuma informação esteja disponível
    except Exception as e:
        print(f"Erro ao obter informações para ID {user_id}: {e}")
        return f"Usuario sem @"

def process_user_file(user_file):
    """
    Processa um arquivo JSON individual para atualizar o username ou nome.
    """
    try:
        with open(user_file, 'r') as f:
            user_data = json.load(f)
    except Exception as e:
        print(f"Erro ao abrir o arquivo {user_file}: {e}")
        return

    user_id = user_data.get('id')
    if not user_id:
        print(f"Arquivo {user_file} não contém um ID válido.")
        return

    print(f"Processando usuário ID: {user_id}")
    novo_username = get_username_by_id(user_id)

    if novo_username != user_data.get('username'):
        user_data['username'] = novo_username
        try:
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=4)
            print(f"Username atualizado para {novo_username} no arquivo {user_file}.")
        except Exception as e:
            print(f"Erro ao salvar o arquivo {user_file}: {e}")
    else:
        print(f"Username já está atualizado para {novo_username} no arquivo {user_file}.")

def update_usernames():
    """
    Atualiza os usernames ou nomes nos arquivos JSON com base no ID do usuário.
    """
    if not os.path.exists(USER_DATA_DIR):
        print("Diretório de usuários não encontrado.")
        return

    files = [os.path.join(USER_DATA_DIR, f) for f in os.listdir(USER_DATA_DIR) if f.endswith('.json')]
    threads = []

    for user_file in files:
        # Criar uma thread para cada arquivo JSON
        thread = threading.Thread(target=process_user_file, args=(user_file,))
        threads.append(thread)
        thread.start()

        # Limitar o número de threads simultâneas para evitar sobrecarga
        while len(threads) >= 10:  # Ajuste o limite de threads conforme necessário
            threads = [t for t in threads if t.is_alive()]
            time.sleep(0.1)

    # Garantir que todas as threads tenham terminado
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    while True:
        print("Iniciando atualização dos usernames...")
        update_usernames()
        print("Atualização concluída. Aguardando 24 horas para a próxima execução...")
        time.sleep(86400)  # 24 horas em segundos
