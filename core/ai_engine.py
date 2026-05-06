import requests
import tempfile
import os
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

import base64

import asyncio

# Global semaphore to limit concurrent requests to Gemini (Traffic Controller)
# This prevents hitting the 429 Rate Limit when many images are scanned at once.
gemini_semaphore = asyncio.Semaphore(2)

async def verify_semantic_match_with_gemini(suspicious_path, db_assets):
    """
    Uses Gemini Multimodal API with NVIDIA fallback.
    Optimized for speed to stay under 30s.
    """
    async with gemini_semaphore:
        # 1. Fetch and process all images in parallel at the start
        susp_img = Image.open(suspicious_path)
        susp_b64 = encode_image_to_base64(suspicious_path)
        
        async def prepare_asset(asset):
            if "image_url" in asset and asset["image_url"]:
                try:
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(None, lambda: requests.get(asset["image_url"], timeout=8))
                    if res.status_code == 200:
                        img_data = res.content
                        pil_img = Image.open(io.BytesIO(img_data))
                        
                        # Prepare for NVIDIA (Resize & Encode)
                        rgb_img = pil_img.convert("RGB")
                        if max(rgb_img.size) > 512:
                            rgb_img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                        
                        buf = io.BytesIO()
                        rgb_img.save(buf, format="JPEG", quality=70)
                        b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
                        
                        return {
                            "id": asset['asset_id'],
                            "pil": pil_img,
                            "b64": f"data:image/jpeg;base64,{b64_img}"
                        }
                except Exception as e:
                    print(f"Error preparing asset {asset.get('asset_id')}: {e}")
            return None

        import io
        fetch_tasks = [prepare_asset(asset) for asset in db_assets]
        prepared_assets = [a for a in await asyncio.gather(*fetch_tasks) if a]

        # 2. Check keys and Fallback if needed
        if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
            if NVIDIA_API_KEY:
                print("Gemini API Key missing. Falling back to NVIDIA NIM...")
                return await verify_semantic_match_with_nvidia(susp_b64, prepared_assets)
            return None

        # 3. Attempt Gemini with strict timeout
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                client = genai.Client(api_key=API_KEY)
                prompt = """
                Respond strictly in JSON:
                {
                  "match": true/false,
                  "similarity_score": 0-100,
                  "matched_asset_id": "string",
                  "reason": "string",
                  "modifications": []
                }
                """
                contents = [prompt, "Suspicious Image:", susp_img, "Official Images:"]
                for pa in prepared_assets:
                    contents.append(f"Asset ID: {pa['id']}")
                    contents.append(pa['pil'])

                # 12s timeout for Gemini inference
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    ),
                    timeout=12.0
                )

                if response.candidates and response.candidates[0].content.parts:
                    text = response.candidates[0].content.parts[0].text.strip()
                    if text.startswith("```json"): text = text[7:-3].strip()
                    elif text.startswith("```"): text = text[3:-3].strip()
                    return json.loads(text)

            except Exception as e:
                print(f"Gemini Attempt {attempt+1} failed: {e}")
                if attempt == 0 and ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)):
                    await asyncio.sleep(3) # Short sleep before last attempt
                    continue
                break # Fallback on other errors or last attempt

        # 4. Final Fallback to NVIDIA
        if NVIDIA_API_KEY:
            print("Gemini failed or timed out. Falling back to NVIDIA NIM...")
            return await verify_semantic_match_with_nvidia(susp_b64, prepared_assets)
            
        return None

def encode_image_to_base64(image_path, max_size=512):
    import mimetypes
    from PIL import Image
    import io
    
    # Open and convert to RGB
    img = Image.open(image_path).convert("RGB")
    
    # Resize if too large
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    # Save to buffer
    # Save to buffer
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70) # 70% quality to save space
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

async def verify_semantic_match_with_nvidia(susp_b64, prepared_assets):
    """
    Fallback implementation using NVIDIA NIM.
    Takes pre-processed base64 images to save time.
    """
    if not NVIDIA_API_KEY: 
        return None

    async def compare_one(pa):
        try:
            prompt = """
            Expert copyright detection. Compare 'Suspicious Image' vs 'Official Image'.
            Respond strictly in JSON:
            { "match": true/false, "similarity_score": 0-100, "reason": "string", "modifications": [] }
            """
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "text", "text": "Suspicious Image:"},
                        {"type": "image_url", "image_url": {"url": susp_b64}},
                        {"type": "text", "text": f"Official Image (ID: {pa['id']}):"},
                        {"type": "image_url", "image_url": {"url": pa['b64']}}
                    ]
                }
            ]
            
            payload = {
                "model": NVIDIA_MODEL,
                "messages": messages,
                "max_tokens": 512,
                "temperature": 0.1,
                "stream": False
            }

            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: requests.post(
                    NVIDIA_URL, 
                    headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"}, 
                    json=payload,
                    timeout=10
                )),
                timeout=12.0
            )

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                if content.startswith("```json"): content = content[7:-3].strip()
                elif content.startswith("```"): content = content[3:-3].strip()
                res = json.loads(content)
                res["matched_asset_id"] = pa['id']
                return res
        except Exception as e:
            print(f"NVIDIA comparison failed for {pa['id']}: {e}")
        return None

    # Run all comparisons in parallel
    tasks = [compare_one(pa) for pa in prepared_assets]
    results = await asyncio.gather(*tasks)
    
    # Filter and find best match
    matches = [r for r in results if r and r.get("match")]
    if not matches:
        return {"match": False, "similarity_score": 0, "matched_asset_id": None, "reason": "No match found across all official assets.", "modifications": []}
    
    # Sort by similarity score descending
    matches.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
    return matches[0]
