import os
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

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

    max_retries = 5
    base_delay = 10  # Start with 10 seconds
    
    for attempt in range(max_retries):
        try:
            # Initialize client using the new google.genai SDK
            client = genai.Client(api_key=API_KEY)
            
            prompt = """
            You are an expert copyright and media alteration detection AI.
            I will provide you with a Suspicious Image, followed by a list of Official Registered Images.
            Does the Suspicious Image depict the EXACT SAME real-world event, scene, or person at the exact same moment in time as any of the Official Images? It might be taken from a different angle, have different lighting, or be heavily cropped.
            
            Respond strictly in the following JSON format without any markdown wrappers or extra text:
            {
              "match": true,
              "similarity_score": <integer 0-100 representing how semantically similar the most similar official image is>,
              "matched_asset_id": "<asset_id of the most similar official image, MUST NOT BE NULL>",
              "reason": "<brief explanation>",
              "modifications": ["<list of visual differences, e.g. 'cropped', 'different lighting', or 'none'>"]
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
                    img = Image.open(asset["file_path"])
                    contents.append(f"Asset ID: {asset['asset_id']}")
                    contents.append(img)
                except Exception:
                    pass
            
            # Using the client to generate content
            # The google-genai SDK's generate_content is synchronous by default in current versions, 
            # but we run it in a way that allows us to retry asynchronously.
            response = client.models.generate_content(
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
                delay = base_delay * (2 ** attempt)
                print(f"Gemini API Rate Limit hit (429). Retrying in {delay}s... (Attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)
            else:
                print("Gemini API Error:", e)
                return None
    
    print("Gemini API Error: Max retries exceeded for 429 error.")
    return None
