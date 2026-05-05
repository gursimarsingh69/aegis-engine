import os
import io
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

# Import app to use TestClient
import main
import config

client = TestClient(main.app)

def create_sample_image(filename, text, bg_color, size=(800, 600)):
    # Create simple solid color with text for "Mock" images
    img = Image.new('RGB', size, color=bg_color)
    d = ImageDraw.Draw(img)
    # Just draw some shapes, maybe a circle and some text to make it different
    d.ellipse([(100, 100), (400, 400)], fill=(200, 200, 200), outline=(0,0,0))
    d.text((size[0]//3, size[1]//2), text, fill=(0,0,0))
    img.save(filename)
    return filename

def main_seed():
    print("Clearing out existing db...")
    if os.path.exists(config.DB_FILE):
         os.remove(config.DB_FILE)
    
    # 1. Create a logo
    create_sample_image("logo.jpg", "SPORTS LOGO", bg_color=(255, 0, 0), size=(300, 300))
    # 2. Create a match poster
    create_sample_image("poster.jpg", "MATCH POSTER TEAM A vs TEAM B", bg_color=(0, 0, 255), size=(1080, 1920))
    # 3. Create a celebration photo
    create_sample_image("celebration.jpg", "CELEBRATION GOAL!", bg_color=(0, 255, 0), size=(1280, 720))

    assets = [
        {"file": "logo.jpg", "id": "asset001_logo"},
        {"file": "poster.jpg", "id": "asset002_poster"},
        {"file": "celebration.jpg", "id": "asset003_celeb"}
    ]

    print("Registering samples...")
    for ast in assets:
        with open(ast["file"], "rb") as f:
            resp = client.post("/register", files={"file": (ast["file"], f, "image/jpeg")}, data={"asset_id": ast["id"]})
            print(f"Registered {ast['id']}: {resp.json()}")

    print("\n--- Generating Suspicious Images ---\n")
    # Simulate a crop of the celebration.jpg
    celeb_img = Image.open("celebration.jpg")
    celeb_cropped = celeb_img.crop((100, 100, 800, 800)) # Change aspect ratio
    celeb_cropped.save("suspicious_crop.jpg")

    # Simulate a resize of the logo.jpg
    logo_img = Image.open("logo.jpg")
    # Make it incredibly small
    logo_resized = logo_img.resize((100, 100))
    logo_resized.save("suspicious_resize.jpg")

    # Simulate screenshot borders on poster.jpg (pillar boxing)
    poster_img = cv2.imread("poster.jpg")
    borders = cv2.copyMakeBorder(poster_img, 0, 0, 100, 100, cv2.BORDER_CONSTANT, value=[0,0,0])
    cv2.imwrite("suspicious_screenshot.jpg", borders)
    
    # Compress the celebration heavily to simulate low quality
    celeb_img.save("suspicious_compressed.jpg", "JPEG", quality=5)

    print("Scanning suspicious images...")
    sus = ["suspicious_crop.jpg", "suspicious_resize.jpg", "suspicious_screenshot.jpg", "suspicious_compressed.jpg"]
    for s in sus:
        with open(s, "rb") as f:
            resp = client.post("/scan", files={"file": (s, f, "image/jpeg")})
            print(f"Scan result for {s}: {resp.json()}")

if __name__ == "__main__":
    main_seed()
