import os
import requests
import glob

ENGINE_URL = "http://localhost:8000/register"
ASSETS_DIR = "./assets"

def register_all():
    print(f"🚀 Starting bulk registration for assets in {ASSETS_DIR}...")
    
    # Supported extensions
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(ASSETS_DIR, ext)))
    
    if not files:
        print("❌ No official assets found to register.")
        return

    for file_path in files:
        file_name = os.path.basename(file_path)
        print(f"📦 Registering {file_name}...")
        
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    ENGINE_URL,
                    files={'file': (file_name, f, 'image/jpeg')},
                    data={'asset_id': file_name}
                )
                
            if response.status_code == 200:
                print(f"✅ Success: {response.json().get('asset_id')}")
            else:
                print(f"⚠️ Failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"🔥 Error: {e}")

if __name__ == "__main__":
    register_all()
