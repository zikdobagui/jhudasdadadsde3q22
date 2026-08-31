import json
import os
import signal
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timedelta


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

active_trials = {}


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def serialize_trial(trial):
    data = dict(trial)
    for key in ("created_at", "expires_at"):
        if isinstance(data.get(key), datetime):
            data[key] = data[key].isoformat()
    return data


def _ignore_runtime_files(directory, names):
    ignored = {
        ".git",
        "__pycache__",
        "bot_pai",
        "sync_log.txt",
        "sync_log.txt.1",
        "sync_log.txt.2",
        "sync_log.txt.3",
        "casino.log",
    }
    return {name for name in names if name in ignored or name.endswith(".zip")}


def _load_json(path):
    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _pid_file(runtime_path):
    return os.path.join(runtime_path, ".trial.pid")


def _read_pid(runtime_path):
    try:
        with open(_pid_file(runtime_path), "r", encoding="utf-8") as file:
            return int(file.read().strip())
    except (OSError, TypeError, ValueError):
        return None


def _write_pid(runtime_path, pid):
    with open(_pid_file(runtime_path), "w", encoding="utf-8") as file:
        file.write(str(pid))


def _terminate_pid(pid):
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _prepare_child_credentials(runtime_path, trial):
    source = os.path.join(PROJECT_DIR, "settings", "credenciais.example.json")
    credentials = _load_json(source)
    credentials["id_dono"] = int(trial["admin_id"])
    credentials["api-bot"] = trial["token"]
    credentials["user_bot"] = trial.get("username", "")
    support_url = trial.get("support_url") or "https://t.me/RamonSuporteV"
    credentials["link_suporte"] = support_url
    credentials["central_stock_api_url"] = trial["central_stock_api_url"]
    credentials["central_stock_api_key"] = trial["central_stock_api_key"]
    credentials["child_bot_id"] = f"trial-{trial['id']}"
    credentials["reseller_admin_id"] = str(trial["admin_id"])
    # O prazo real do teste e controlado pelo timer do bot pai.
    # O vencimento interno do bot filho fica distante para nao bloquear o teste.
    credentials["vencimento_bot"] = "01/01/2099"
    credentials["maintance"] = "off"
    _save_json(os.path.join(runtime_path, "settings", "credenciais.json"), credentials)


def start_trial_bot(trial, on_expire=None, rebuild_runtime=True):
    trial = dict(trial)
    trial["expires_at"] = parse_datetime(trial["expires_at"])
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    runtime_path = os.path.join(RUNTIME_DIR, f"trial-{trial['id']}")
    _terminate_pid(_read_pid(runtime_path))

    if rebuild_runtime:
        if os.path.exists(runtime_path):
            shutil.rmtree(runtime_path)
        shutil.copytree(PROJECT_DIR, runtime_path, ignore=_ignore_runtime_files)
    elif not os.path.exists(runtime_path):
        shutil.copytree(PROJECT_DIR, runtime_path, ignore=_ignore_runtime_files)

    _prepare_child_credentials(runtime_path, trial)

    process = subprocess.Popen(
        [sys.executable, "bot.py"],
        cwd=runtime_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _write_pid(runtime_path, process.pid)

    remaining = (trial["expires_at"] - datetime.now()).total_seconds()
    trial_seconds = max(int(remaining), 1)
    timer = threading.Timer(trial_seconds, stop_trial_bot, args=(trial["id"], "expired", on_expire))
    timer.daemon = True
    timer.start()

    active_trials[trial["id"]] = {
        "process": process,
        "timer": timer,
        "runtime_path": runtime_path,
        "expires_at": trial["expires_at"],
    }
    return active_trials[trial["id"]]


def is_trial_running(trial_id):
    runtime = active_trials.get(int(trial_id))
    if not runtime:
        return False
    process = runtime.get("process")
    return bool(process and process.poll() is None)


def stop_trial_bot(trial_id, reason="stopped", on_expire=None):
    runtime = active_trials.pop(trial_id, None)
    if not runtime:
        return False

    timer = runtime.get("timer")
    if timer:
        timer.cancel()

    process = runtime.get("process")
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    _terminate_pid(_read_pid(runtime.get("runtime_path", "")))

    if on_expire:
        on_expire(trial_id, reason, runtime)
    return True


def delete_trial_runtime(trial_id):
    stop_trial_bot(int(trial_id), "deleted", None)
    runtime_path = os.path.join(RUNTIME_DIR, f"trial-{trial_id}")
    _terminate_pid(_read_pid(runtime_path))
    if os.path.exists(runtime_path):
        shutil.rmtree(runtime_path, ignore_errors=True)


def build_trial(data, config, request_id):
    minutes = int(config.get("trial_minutes", 10))
    now = datetime.now()
    return {
        "id": request_id,
        "store_name": data["store_name"],
        "token": data["token"],
        "admin_id": int(data["admin_id"]),
        "username": data.get("username", ""),
        "trial_minutes": minutes,
        "status": "trial_running",
        "created_at": now,
        "expires_at": now + timedelta(minutes=minutes),
        "central_stock_api_url": config.get("central_stock_api_url") or "https://vendasdoramon.squareweb.app",
        "central_stock_api_key": config.get("central_stock_api_key") or config.get("stock_api_key", ""),
        "support_url": config.get("support_url") or "https://t.me/RamonSuporteV",
    }
