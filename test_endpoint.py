import json
import imagehash
from PIL import Image

def test():
    # Mocking what comes from backend
    asset_str = '[{"id": 1, "hash_signature": "{\\"phash\\":\\"3a3a\\"}", "image_url": "http://example.com"}]'
    registered_assets = json.loads(asset_str)
    
    candidates = []
    for asset in registered_assets:
        hs = asset.get("hash_signature") or {}
        if isinstance(hs, str):
            try:
                hs = json.loads(hs)
            except Exception:
                hs = {}

        stored_phash = hs.get("phash", "")
        if not stored_phash:
            print("No stored phash")
            continue

        try:
            print(f"Stored phash: {stored_phash}")
            # we need 16 hex chars for imagehash, 3a3a is 4 chars
            # let's try actual phash logic
        except Exception as e:
            print(e)
            continue

test()
