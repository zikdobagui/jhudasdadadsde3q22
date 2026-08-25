import os
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REMOTE = os.getenv("AUTO_GIT_REMOTE", "origin")
BRANCH = os.getenv("AUTO_GIT_BRANCH", "main")
UPDATE_NOTIFY_FILE = ROOT / ".last_update_notify"
LOCAL_DATA_DIRS = ("botoes",)
LOCAL_DATA_FILES = ("settings/notify.json", "settings/roleta.json", "settings/button_overrides.json")


def run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def log(message: str) -> None:
    print(f"[auto-update] {message}", flush=True)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_short_commit(commit_hash: str) -> str:
    if not commit_hash:
        return "desconhecido"
    return commit_hash[:7]


def get_commit_subject(commit_ref: str) -> str:
    result = run_git("log", "-1", "--pretty=%s", commit_ref)
    if result.returncode != 0:
        return "Sem detalhes do commit"
    return result.stdout.strip() or "Sem detalhes do commit"


def get_admin_chat_ids() -> list[int]:
    chat_ids = set()

    credentials_path = ROOT / "settings" / "credenciais.json"
    if credentials_path.exists():
        credentials = read_json(credentials_path)
        owner_id = credentials.get("id_dono")
        if owner_id:
            chat_ids.add(int(owner_id))

    admins_path = ROOT / "database" / "admins.json"
    if admins_path.exists():
        admins = read_json(admins_path).get("admins", [])
        for admin in admins:
            admin_id = admin.get("id")
            if admin_id:
                chat_ids.add(int(admin_id))

    return sorted(chat_ids)


def get_bot_token() -> str | None:
    credentials_path = ROOT / "settings" / "credenciais.json"
    if not credentials_path.exists():
        return None
    return str(read_json(credentials_path).get("api-bot") or "").strip() or None


def send_telegram_message(token: str, chat_id: int, text: str) -> bool:
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        log(f"Falha ao notificar admin {chat_id}: {exc}")
        return False


def notify_admins_updated(old_commit: str, new_commit: str) -> None:
    token = get_bot_token()
    chat_ids = get_admin_chat_ids()
    if not token or not chat_ids:
        log("Nao encontrei token ou admin para notificar sobre a atualizacao.")
        return

    notify_key = f"{old_commit}>{new_commit}"
    if UPDATE_NOTIFY_FILE.exists() and UPDATE_NOTIFY_FILE.read_text(encoding="utf-8").strip() == notify_key:
        return

    subject = get_commit_subject(new_commit)
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    text = (
        "<b>Bot atualizado com sucesso!</b>\n\n"
        f"<b>Repositorio:</b> {REMOTE}/{BRANCH}\n"
        f"<b>Antes:</b> <code>{get_short_commit(old_commit)}</code>\n"
        f"<b>Agora:</b> <code>{get_short_commit(new_commit)}</code>\n"
        f"<b>Commit:</b> {subject}\n"
        f"<b>Horario:</b> {now}"
    )

    sent_any = False
    for chat_id in chat_ids:
        sent_any = send_telegram_message(token, chat_id, text) or sent_any

    if sent_any:
        UPDATE_NOTIFY_FILE.write_text(notify_key, encoding="utf-8")


def has_git_repo() -> bool:
    result = run_git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def local_change_paths() -> list[str] | None:
    result = run_git("status", "--porcelain")
    if result.returncode != 0:
        log(f"Nao foi possivel checar alteracoes locais:\n{result.stdout.strip()}")
        return None
    paths = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        paths.append(line[3:].strip().strip('"'))
    return paths


def is_preserved_local_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    return (
        any(normalized == item or normalized.startswith(f"{item}/") for item in LOCAL_DATA_DIRS)
        or normalized in LOCAL_DATA_FILES
    )


def has_blocking_local_changes() -> bool:
    paths = local_change_paths()
    if paths is None:
        return True
    blocking = [path for path in paths if not is_preserved_local_path(path)]
    if blocking:
        log("Existem alteracoes locais rastreadas fora de dados preservados; pulei o git pull.")
        return True
    return False


def backup_local_data():
    temp_dir = Path(tempfile.mkdtemp(prefix="auto_update_local_", dir=str(ROOT)))
    backups = []
    for dirname in LOCAL_DATA_DIRS:
        source = ROOT / dirname
        if source.exists():
            destination = temp_dir / dirname
            shutil.copytree(source, destination)
            backups.append((source, destination))
    for filename in LOCAL_DATA_FILES:
        source = ROOT / filename
        if source.exists():
            destination = temp_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            backups.append((source, destination))
    return temp_dir, backups


def restore_local_data(temp_dir: Path, backups) -> None:
    try:
        for source, backup in backups:
            if backup.is_file():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, source)
            elif source.exists():
                shutil.rmtree(source)
                shutil.copytree(backup, source)
            else:
                shutil.copytree(backup, source)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def reset_preserved_paths_for_pull() -> None:
    for dirname in LOCAL_DATA_DIRS:
        run_git("checkout", "--", dirname)
    for filename in LOCAL_DATA_FILES:
        run_git("checkout", "--", filename)


def update() -> bool:
    if os.getenv("AUTO_GIT_UPDATE", "1").lower() in {"0", "false", "no", "off"}:
        log("Atualizacao automatica desativada por AUTO_GIT_UPDATE.")
        return False

    if not has_git_repo():
        log("Este ambiente nao tem repositorio Git; iniciando sem atualizar.")
        return False

    if has_blocking_local_changes():
        return False

    log(f"Buscando atualizacoes de {REMOTE}/{BRANCH}...")
    fetch = run_git("fetch", REMOTE, BRANCH)
    if fetch.returncode != 0:
        log(f"Falha no git fetch:\n{fetch.stdout.strip()}")
        return False

    local = run_git("rev-parse", "HEAD")
    upstream = run_git("rev-parse", f"{REMOTE}/{BRANCH}")
    if local.returncode != 0 or upstream.returncode != 0:
        log("Nao foi possivel comparar a versao local com a remota.")
        return False

    if local.stdout.strip() == upstream.stdout.strip():
        log("Ja esta atualizado.")
        return False

    old_commit = local.stdout.strip()
    new_commit = upstream.stdout.strip()

    temp_dir, backups = backup_local_data()
    try:
        reset_preserved_paths_for_pull()
        pull = run_git("pull", "--ff-only", REMOTE, BRANCH)
        if pull.returncode != 0:
            log(f"Falha no git pull:\n{pull.stdout.strip()}")
            return False
    finally:
        restore_local_data(temp_dir, backups)

    log("Atualizacao aplicada com sucesso.")
    notify_admins_updated(old_commit, new_commit)
    return True


if __name__ == "__main__":
    try:
        sys.exit(0 if update() else 1)
    except Exception as exc:
        log(f"Erro inesperado: {exc}")
        sys.exit(1)
