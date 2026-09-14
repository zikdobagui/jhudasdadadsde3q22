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
    if os.path.normcase(os.path.abspath(directory)) == os.path.normcase(os.path.join(PROJECT_DIR, "database")):
        ignored.add("acessos.json")
    return {name for name in names if name in ignored or name.endswith(".zip")}


def _load_json(path):
    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _sanitize_child_runtime(runtime_path, reset_customer_data=False):
    """Remove dados privados copiados do projeto antes de ligar um bot filho."""
    database_dir = os.path.join(runtime_path, "database")
    os.makedirs(database_dir, exist_ok=True)
    accesses_path = os.path.join(database_dir, "acessos.json")
    if os.path.isfile(accesses_path):
        os.remove(accesses_path)
    _save_json(os.path.join(database_dir, "login_registry.json"), {"contas": {}})
    _save_json(os.path.join(database_dir, "reserve_verified.json"), {})

    if reset_customer_data:
        users_dir = os.path.join(database_dir, "users")
        if os.path.isdir(users_dir):
            shutil.rmtree(users_dir)
        os.makedirs(users_dir, exist_ok=True)

        history_dir = os.path.join(runtime_path, "historicos")
        if os.path.isdir(history_dir):
            shutil.rmtree(history_dir)
        os.makedirs(history_dir, exist_ok=True)


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
        return False
    try:
        if os.name == "nt":
            # O Python da Microsoft Store usa um processo intermediario. Mesmo
            # depois que ele encerra, os filhos preservam ParentProcessId.
            root_pid = int(pid)
            script = (
                f"$rootPid={root_pid};"
                "$all=@(Get-CimInstance Win32_Process);"
                "$targets=New-Object System.Collections.Generic.List[int];"
                "$queue=New-Object System.Collections.Generic.Queue[int];"
                "$queue.Enqueue($rootPid);"
                "while($queue.Count -gt 0){$parent=$queue.Dequeue();"
                "foreach($child in $all|Where-Object{$_.ParentProcessId -eq $parent}){"
                "$childPid=[int]$child.ProcessId;"
                "if(-not $targets.Contains($childPid)){$targets.Add($childPid);$queue.Enqueue($childPid)}}};"
                "$targets.Reverse();"
                "foreach($targetPid in $targets){Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue};"
                "Stop-Process -Id $rootPid -Force -ErrorAction SilentlyContinue"
            )
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def _prepare_child_credentials(runtime_path, trial, preserve_existing=False):
    destination = os.path.join(runtime_path, "settings", "credenciais.json")
    source = destination if preserve_existing and os.path.isfile(destination) else os.path.join(PROJECT_DIR, "settings", "credenciais.example.json")
    credentials = _load_json(source)
    credentials["id_dono"] = int(trial["admin_id"])
    credentials["api-bot"] = trial["token"]
    credentials["user_bot"] = trial.get("username", "")
    support_url = trial.get("support_url") or "https://t.me/RamonSuporteV"
    credentials["link_suporte"] = support_url
    if not preserve_existing:
        credentials["central_stock_api_url"] = ""
        credentials["central_stock_api_key"] = ""
    credentials["child_api_only"] = True
    credentials["child_bot_id"] = f"trial-{trial['id']}"
    credentials["reseller_admin_id"] = str(trial["admin_id"])
    # O prazo real do teste e controlado pelo timer do bot pai.
    # O vencimento interno do bot filho fica distante para nao bloquear o teste.
    credentials["vencimento_bot"] = "01/01/2099"
    credentials["maintance"] = "off"
    _save_json(destination, credentials)


def start_trial_bot(trial, on_expire=None, rebuild_runtime=True):
    trial = dict(trial)
    trial["expires_at"] = parse_datetime(trial["expires_at"])
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    runtime_path = os.path.join(RUNTIME_DIR, f"trial-{trial['id']}")
    _terminate_pid(_read_pid(runtime_path))

    runtime_created = rebuild_runtime or not os.path.exists(runtime_path)
    if rebuild_runtime:
        if os.path.exists(runtime_path):
            shutil.rmtree(runtime_path)
        shutil.copytree(PROJECT_DIR, runtime_path, ignore=_ignore_runtime_files)
    elif not os.path.exists(runtime_path):
        shutil.copytree(PROJECT_DIR, runtime_path, ignore=_ignore_runtime_files)

    _sanitize_child_runtime(runtime_path, reset_customer_data=runtime_created)
    _prepare_child_credentials(runtime_path, trial, preserve_existing=not runtime_created)

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
    recorded_pid = _read_pid(runtime.get("runtime_path", ""))
    if os.name == "nt":
        _terminate_pid(recorded_pid or getattr(process, "pid", None))
    elif process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=10)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    else:
        _terminate_pid(recorded_pid)

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
        "central_stock_api_url": "",
        "central_stock_api_key": "",
        "support_url": config.get("support_url") or "https://t.me/RamonSuporteV",
    }
