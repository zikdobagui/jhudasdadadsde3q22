import json
import os
import tempfile
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BOTS_FILE = os.path.join(DATA_DIR, "bots.json")


def ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(BOTS_FILE):
        save_bots([])


def load_bots():
    ensure_storage()
    with open(BOTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_bots(bots):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="bots-", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(bots, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, BOTS_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def next_bot_id(bots):
    if not bots:
        return 1
    return max(int(bot["id"]) for bot in bots) + 1


def create_child_bot(name, owner_id, token, username="", expires_at=""):
    bots = load_bots()
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    child = {
        "id": next_bot_id(bots),
        "name": name,
        "owner_id": int(owner_id),
        "token": token,
        "username": username,
        "status": "active",
        "expires_at": expires_at,
        "squarecloud_app_id": "",
        "created_at": now,
        "updated_at": now
    }
    bots.append(child)
    save_bots(bots)
    return child


def find_bot(bot_id):
    bot_id = int(bot_id)
    for child in load_bots():
        if int(child["id"]) == bot_id:
            return child
    return None


def update_status(bot_id, status):
    bots = load_bots()
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    for child in bots:
        if int(child["id"]) == int(bot_id):
            child["status"] = status
            child["updated_at"] = now
            save_bots(bots)
            return child
    return None
