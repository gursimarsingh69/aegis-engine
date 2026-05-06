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
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "mistralai/pixtral-12b")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

import base64

import asyncio

# Global semaphore to limit concurrent requests to Gemini (Traffic Controller)
# This prevents hitting the 429 Rate Limit when many images are scanned at once.
gemini_semaphore = asyncio.Semaphore(2)

async def verify_semantic_match_with_gemini(suspicious_path, db_assets):
    """
    Uses Gemini Multimodal API to compare the suspicious image against a batch of official assets.
    db_assets: List of dicts representing registered assets.
    """
    async with gemini_semaphore:
        if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
            return None  # Skip if API key not set

        max_retries = 3
        base_delay = 10  # 10 seconds fixed gap
        
        for attempt in range(max_retries):
            try:
                # Initialize client using the new google.genai SDK
                client = genai.Client(api_key=API_KEY)
                
                prompt = """
                You are an expert copyright and media infringement detection AI.
                I will provide you with a Suspicious Image, followed by a list of Official Images.
                
                Your task is to determine if the Suspicious Image is derived from, is a cropped version of, or depicts the EXACT SAME source material as any of the Official Images. 
                
                CRITICAL RULES:
                1. If the Suspicious Image is simply a heavily cropped, resized, or zoomed-in section of an Official Image, IT IS A MATCH.
                2. Missing features (e.g., horns, text, or background elements) that are cut off due to cropping DO NOT mean it is a different image. It is still a MATCH.
                3. Color grading, filters, watermarks, or minor edits do not change the underlying match.
                
                If you find a match, identify the most similar Official Image.
                
                Respond strictly in the following JSON format without any markdown wrappers or extra text:
                {
                  "match": true,
                  "similarity_score": <integer 0-100 representing confidence that it is the same source material>,
                  "matched_asset_id": "<asset_id of the matched official image, MUST NOT BE NULL if match is true>",
                  "reason": "<brief explanation focusing on why it is a match despite any cropping or edits>",
                  "modifications": ["<list of visual differences, e.g. 'heavily cropped', 'color shifted', 'watermarked', or 'none'>"]
                }
                """
                
                contents = [prompt]
                
                # Load suspicious image
                susp_img = Image.open(suspicious_path)
                contents.append("Suspicious Image:")
                contents.append(susp_img)
                
                contents.append("Official Images:")
                for asset in db_assets:
                    try:
                        if "image_url" in asset and asset["image_url"]:
                            res = requests.get(asset["image_url"])
                            if res.status_code == 200:
                                tf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                                tf.write(res.content)
                                tf.close()
                                img = Image.open(tf.name)
                                contents.append(f"Asset ID: {asset['asset_id']}")
                                contents.append(img)
                            else:
                                print(f"Warning: Failed to fetch image for asset {asset.get('asset_id')}. HTTP {res.status_code} - {res.text}")
                    except Exception as ex:
                        print(f"Error loading image from URL: {ex}")
                        pass
                
                # Using the client to generate content asynchronously
                response = await client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                
                if not response.candidates or not response.candidates[0].content.parts:
                    print(f"Gemini API Error: Empty response. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                    return None
                    
                text = response.candidates[0].content.parts[0].text.strip()
                
                if text.startswith("```json"):
                    text = text[7:-3].strip()
                elif text.startswith("```"):
                    text = text[3:-3].strip()
                    
                result = json.loads(text)
                return result

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    delay = base_delay
                    print(f"Gemini API Rate Limit hit (429). Retrying in {delay}s... (Attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                else:
                    print("Gemini API Error:", e)
                    if NVIDIA_API_KEY:
                        print("Attempting NVIDIA NIM fallback due to Gemini error...")
                        return await verify_semantic_match_with_nvidia(suspicious_path, db_assets)
                    return None
        
        print("Gemini API Error: Max retries exceeded for 429 error.")
        
        # ── NVIDIA Fallback ──────────────────────────────────────────────────
        if NVIDIA_API_KEY:
            print("Attempting NVIDIA NIM fallback...")
            return await verify_semantic_match_with_nvidia(suspicious_path, db_assets)
            
        return None

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

async def verify_semantic_match_with_nvidia(suspicious_path, db_assets):
    """
    Fallback implementation using NVIDIA NIM (Mistral/Pixtral).
    """
    if not NVIDIA_API_KEY:
        print("NVIDIA API Key not set. Skipping fallback.")
        return None

    try:
        prompt = """
        You are an expert copyright and media infringement detection AI.
        I will provide you with a Suspicious Image, followed by a list of Official Images.
        
        Your task is to determine if the Suspicious Image is derived from, is a cropped version of, or depicts the EXACT SAME source material as any of the Official Images. 
        
        CRITICAL RULES:
        1. If the Suspicious Image is simply a heavily cropped, resized, or zoomed-in section of an Official Image, IT IS A MATCH.
        2. Missing features (e.g., horns, text, or background elements) that are cut off due to cropping DO NOT mean it is a different image. It is still a MATCH.
        3. Color grading, filters, watermarks, or minor edits do not change the underlying match.
        
        Respond strictly in the following JSON format without any markdown wrappers or extra text:
        {
          "match": true,
          "similarity_score": <integer 0-100>,
          "matched_asset_id": "<asset_id>",
          "reason": "<explanation>",
          "modifications": ["<differences>"]
        }
        """

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encode_image_to_base64(suspicious_path)}"}
                    }
                ]
            }
        ]

        # Add official images to the message
        for asset in db_assets:
            if "image_url" in asset and asset["image_url"]:
                try:
                    res = requests.get(asset["image_url"])
                    if res.status_code == 200:
                        b64_img = base64.b64encode(res.content).decode("utf-8")
                        messages[0]["content"].append({
                            "type": "text", 
                            "text": f"Official Asset ID: {asset['asset_id']}"
                        })
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                        })
                except Exception as e:
                    print(f"Error encoding asset for NVIDIA: {e}")

        payload = {
            "model": NVIDIA_MODEL,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.15,
            "top_p": 1.0,
            "stream": False
        }

        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json"
        }

        # Run the request in a thread to keep it non-blocking for the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(NVIDIA_URL, headers=headers, json=payload))

        if response.status_code == 200:
            result_data = response.json()
            content = result_data["choices"][0]["message"]["content"].strip()
            
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
                
            return json.loads(content)
        else:
            print(f"NVIDIA API Error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"NVIDIA Fallback failed: {e}")
        return None
