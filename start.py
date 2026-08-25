import subprocess
import sys


def auto_update():
    try:
        subprocess.run([sys.executable, 'auto_update.py'], check=False)
    except Exception as exc:
        print(f"Falha ao executar auto-update: {exc}")

def start_scripts():
 
    try:
        auto_update()
        
        bot_process = subprocess.Popen([sys.executable, 'bot.py'])
        print("Bot principal iniciado.")

        # DESABILITADO: Bot gerenciador causa conflito (Error 409) por usar o mesmo token
        # Para usar o gerenciador, execute manualmente: python gerenciador.py
        # bot_process2 = subprocess.Popen(['python', 'gerenciador.py'])
        # print("Bot gerenciador iniciado.")

        
        update_process = subprocess.Popen([sys.executable, 'update_usernames.py'])
        print("Script de atualização de usernames iniciado.")

        
        bot_process.wait()
        # bot_process2.wait()
        update_process.wait()

    except KeyboardInterrupt:
        print("Encerrando processos...")
        bot_process.terminate()
        # bot_process2.terminate()
        update_process.terminate()

if __name__ == "__main__":
    start_scripts()
