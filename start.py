import subprocess
import sys
import time


def auto_update():
    try:
        subprocess.run([sys.executable, 'auto_update.py'], check=False)
    except Exception as exc:
        print(f"Falha ao executar auto-update: {exc}")


def start_scripts():
    try:
        auto_update()

        # Inicia a API HTTP de catálogo (porta 80 — obrigatório SquareCloud)
        api_process = subprocess.Popen([sys.executable, 'api_catalogo.py'])
        print("API de catálogo iniciada (porta 80).")

        # Inicia o bot principal
        bot_process = subprocess.Popen([sys.executable, 'bot.py'])
        print("Bot principal iniciado.")

        # Inicia atualização de usernames em background
        update_process = subprocess.Popen([sys.executable, 'update_usernames.py'])
        print("Script de atualização de usernames iniciado.")

        # Aguarda qualquer processo finalizar; se um cair, encerra todos
        processos = [api_process, bot_process, update_process]
        while True:
            for proc in processos:
                ret = proc.poll()
                if ret is not None:
                    print(f"Processo {proc.args} finalizou (código {ret}). Encerrando todos...")
                    for p in processos:
                        if p.poll() is None:
                            p.terminate()
                    return
            time.sleep(2)

    except KeyboardInterrupt:
        print("Encerrando processos...")
        for p in [api_process, bot_process, update_process]:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    start_scripts()
