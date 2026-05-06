import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("NVIDIA_API_KEY")
model = os.environ.get("NVIDIA_MODEL", "mistralai/mistral-large-3-675b-instruct-2512")
url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Hello! Reply with 'Aegis Engine' if you can hear me."}],
    "max_tokens": 16,
    "stream": False
}

print(f"Testing NVIDIA API Key with model: {model}...")
try:
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        print("SUCCESS!")
        print(f"Response: {result['choices'][0]['message']['content']}")
    else:
        print(f"FAILED! Status Code: {response.status_code}")
        print(f"Error: {response.text}")
except Exception as e:
    print(f"ERROR: {e}")
