import asyncio
import os
import tempfile
import requests
from core.ai_engine import verify_semantic_match_with_gemini
from dotenv import load_dotenv

load_dotenv()

async def run_test():
    # Public image for testing
    img_url = "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=400"
    
    # Download image to a temp file (Suspicious)
    headers = {"User-Agent": "AegisTest/1.0"}
    res = requests.get(img_url, headers=headers)
    res.raise_for_status()
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tf.write(res.content)
    tf.close()
    suspicious_path = tf.name
    
    # Mock official assets
    db_assets = [
        {
            "asset_id": "matched_asset_1",
            "image_url": img_url # Exact same image
        }
    ]
    
    print("--- Testing AI Logic (Gemini/NVIDIA) ---")
    print(f"Suspicious Path: {suspicious_path}")
    print(f"Asset URL: {img_url}")
    
    try:
        result = await verify_semantic_match_with_gemini(suspicious_path, db_assets)
        print("\nRESULT:")
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        if os.path.exists(suspicious_path):
            os.remove(suspicious_path)

if __name__ == "__main__":
    asyncio.run(run_test())
