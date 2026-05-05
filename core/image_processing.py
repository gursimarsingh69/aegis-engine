import cv2
import numpy as np
from PIL import Image
import imagehash

def compute_hashes(img_path):
    img = Image.open(img_path)
    phash = str(imagehash.phash(img))
    dhash = str(imagehash.dhash(img))
    ahash = str(imagehash.average_hash(img))
    chash = str(imagehash.colorhash(img))
    return phash, dhash, ahash, chash, img.width, img.height

def get_blur_index(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def check_screenshot_borders(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return False
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if h < 20 or w < 20: 
        return False
    
    # Heuristic: check if the first 5 rows and last 5 rows have extremely low variance
    top_var = np.var(gray[0:5, :])
    bottom_var = np.var(gray[-5:, :])
    left_var = np.var(gray[:, 0:5])
    right_var = np.var(gray[:, -5:])

    if (top_var < 10 and bottom_var < 10) or (left_var < 10 and right_var < 10):
        return True
    return False

def orb_feature_match(img1_path, img2_path):
    img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
    
    if img1 is None or img2 is None:
        return 0
        
    # Resize to speed up and normalize feature detection
    img1 = cv2.resize(img1, (640, 480))
    img2 = cv2.resize(img2, (640, 480))
        
    orb = cv2.ORB_create(nfeatures=500)
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    
    if des1 is None or des2 is None:
        return 0
        
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    
    # Count "good" matches (distance < 50 is usually a solid feature match for ORB)
    good_matches = [m for m in matches if m.distance < 50]
    
    return len(good_matches)
