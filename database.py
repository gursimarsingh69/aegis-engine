import os
import json
from config import DB_FILE

def load_db():
    if not os.path.exists(DB_FILE):
        return {"assets": [], "history": []}
    try:
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            if "history" not in data:
                data["history"] = []
            return data
    except json.JSONDecodeError:
        return {"assets": [], "history": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)
