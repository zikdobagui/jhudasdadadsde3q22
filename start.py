import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'settings', 'credenciais.json')


def auto_update():
    try:
        subprocess.run([sys.executable, 'auto_update.py'], cwd=BASE_DIR, check=False)
    except Exception as exc:
        print(f"[AUTO-UPDATE] Falha ao executar: {exc}")


def iniciar_api():
    return subprocess.Popen(
        [sys.executable, 'api_catalogo.py'],
        cwd=BASE_DIR
    )


def iniciar_bot():
    return subprocess.Popen(
        [sys.executable, 'bot.py'],
        cwd=BASE_DIR
    )


def iniciar_atualizador_usernames():
    return subprocess.Popen(
        [sys.executable, 'update_usernames.py'],
        cwd=BASE_DIR
    )


def credenciais_disponiveis():
    return os.path.isfile(CREDENTIALS_FILE)


def encerrar(processos):
    for processo in processos:
        if processo and processo.poll() is None:
            try:
                processo.terminate()
            except Exception:
                pass


def start_scripts():
    processos = []
    try:
        auto_update()

        # O site permanece disponível mesmo se faltar o arquivo privado do bot.
        api_process = iniciar_api()
        processos.append(api_process)
        print('[MINIAPP] API/site iniciado na porta 80.')

        if not credenciais_disponiveis():
            print('ERRO DE CONFIGURAÇÃO: settings/credenciais.json não foi encontrado.')
            print('Envie esse arquivo privado para a pasta settings/ da aplicação SquareCloud.')
            print('Use settings/credenciais.example.json apenas como modelo; nunca o use com os placeholders.')
            print('O site ficará online, mas o bot não será iniciado até as credenciais serem enviadas.')
            while api_process.poll() is None:
                time.sleep(5)
            return

        bot_process = iniciar_bot()
        processos.append(bot_process)
        print('[BOT] Bot principal iniciado.')

        usernames_process = iniciar_atualizador_usernames()
        processos.append(usernames_process)
        print('[USERS] Atualizador de usernames iniciado.')

        while True:
            for processo in processos:
                retorno = processo.poll()
                if retorno is not None:
                    print(f'[START] Processo finalizou com código {retorno}. Encerrando os demais.')
                    encerrar(processos)
                    return
            time.sleep(2)

    except KeyboardInterrupt:
        print('[START] Encerrando processos...')
    finally:
        encerrar(processos)


if __name__ == '__main__':
    start_scripts()
