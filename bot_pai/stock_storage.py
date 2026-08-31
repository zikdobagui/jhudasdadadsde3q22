import json
import os
import tempfile
import threading
from collections import OrderedDict


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STOCK_FILE = os.path.join(DATA_DIR, "acessos.json")

stock_lock = threading.Lock()


def ensure_stock():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(STOCK_FILE):
        save_stock({"acessos": []})


def load_stock():
    ensure_stock()
    with open(STOCK_FILE, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if isinstance(data, list):
        return {"acessos": data}
    if not isinstance(data, dict):
        return {"acessos": []}
    data.setdefault("acessos", [])
    return data


def save_stock(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="acessos-", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, STOCK_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def stock_summary():
    with stock_lock:
        data = load_stock()
        grouped = OrderedDict()
        for acesso in data.get("acessos", []):
            name = str(acesso.get("nome", "")).strip()
            if not name:
                continue
            key = name.casefold()
            if key not in grouped:
                grouped[key] = {
                    "nome": name,
                    "valor": acesso.get("valor", 0),
                    "quantidade": 0,
                }
            grouped[key]["quantidade"] += 1
        return list(grouped.values())


def reserve_first(service_name, child_bot_id="", buyer_id="", sale_id=""):
    service_key = str(service_name or "").strip().casefold()
    if not service_key:
        return None

    with stock_lock:
        data = load_stock()
        acessos = data.get("acessos", [])
        for index, acesso in enumerate(acessos):
            if str(acesso.get("nome", "")).strip().casefold() == service_key:
                reserved = acessos.pop(index)
                save_stock(data)
                return {
                    "nome": reserved.get("nome", ""),
                    "valor": reserved.get("valor", 0),
                    "email": reserved.get("email", ""),
                    "senha": reserved.get("senha", ""),
                    "descricao": reserved.get("descricao", ""),
                    "duracao": reserved.get("duracao", ""),
                    "reserved_by": {
                        "child_bot_id": child_bot_id,
                        "buyer_id": buyer_id,
                        "sale_id": sale_id,
                    },
                }
    return None


def add_access(access):
    required = ("nome", "valor", "email", "senha")
    missing = [field for field in required if not str(access.get(field, "")).strip()]
    if missing:
        return False, f"Campos obrigatorios faltando: {', '.join(missing)}"

    item = {
        "nome": access.get("nome", ""),
        "valor": access.get("valor", 0),
        "descricao": access.get("descricao", ""),
        "email": access.get("email", ""),
        "senha": access.get("senha", ""),
        "duracao": access.get("duracao", ""),
    }

    with stock_lock:
        data = load_stock()
        data.setdefault("acessos", []).append(item)
        save_stock(data)
    return True, item
