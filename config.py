import os

DB_FILE = "db.json"
ASSETS_DIR = "assets"
SUSPICIOUS_DIR = "suspicious"

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SUSPICIOUS_DIR, exist_ok=True)
