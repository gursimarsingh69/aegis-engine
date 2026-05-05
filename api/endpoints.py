"""
endpoints.py
============
Pure stateless compute endpoints for the Aegis AI Engine.

Engine is a computation-only service — NO database reads or writes.
All persistence is handled by the Backend (Node/Express + Supabase).

Routes:
  POST /hash    — compute perceptual hash signatures for an asset file
  POST /compare — compare a suspicious file against a list of registered hashes
  GET  /status  — health check
"""

import json
import os
import shutil
import uuid

import imagehash
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from config import ASSETS_DIR, SUSPICIOUS_DIR
from core.image_processing import compute_hashes, get_blur_index

router = APIRouter()


# ─── Hash ─────────────────────────────────────────────────────────────────────

@router.post("/hash")
async def compute_hash(file: UploadFile = File(...)):
    """
    Compute perceptual hash signatures for an uploaded asset.

    Stateless — no DB reads or writes. Saves a temp file, computes hashes,
    deletes the temp file, and returns the hash_signature object.
    """
    unique_id = str(uuid.uuid4())[:8]
    tmp_path = os.path.join(ASSETS_DIR, f"tmp_{unique_id}_{file.filename}")

    try:
        with open(tmp_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        phash, dhash, ahash, chash, width, height = compute_hashes(tmp_path)
        blur_idx = float(get_blur_index(tmp_path))

        return {
            "hash_signature": {
                "phash": phash,
                "dhash": dhash,
                "ahash": ahash,
                "chash": chash,
                "width": width,
                "height": height,
                "blur_index": blur_idx,
            }
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─── Compare ──────────────────────────────────────────────────────────────────

@router.post("/compare")
async def compare(
    file: UploadFile = File(...),
    assets: str = Form(...),
):
    """
    Compare a suspicious file against a caller-provided list of registered assets.

    Stateless — no DB reads or writes. The caller (Backend) fetches assets from
    Supabase and passes them here as JSON.

    assets: JSON string — list of { id, hash_signature: { phash, dhash, ... } }

    Returns: { match, confidence, matched_asset_id, reason, modifications }
    """
    unique_id = str(uuid.uuid4())[:8]
    suspicious_path = os.path.join(SUSPICIOUS_DIR, f"susp_{unique_id}_{file.filename}")

    try:
        with open(suspicious_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        if os.path.getsize(suspicious_path) == 0:
            return {
                "match": False,
                "confidence": 0,
                "matched_asset_id": None,
                "reason": "Uploaded file is empty or corrupted.",
                "modifications": [],
            }

        # Parse assets JSON
        try:
            registered_assets = json.loads(assets)
        except Exception:
            raise HTTPException(status_code=400, detail="assets must be valid JSON")

        if not registered_assets:
            return {
                "match": False,
                "confidence": 0,
                "matched_asset_id": None,
                "reason": "No registered assets to compare against.",
                "modifications": [],
            }

        # ── pHash Sieve ────────────────────────────────────────────────────────
        try:
            susp_phash = str(imagehash.phash(Image.open(suspicious_path)))
        except Exception as e:
            return {
                "match": False,
                "confidence": 0,
                "matched_asset_id": None,
                "reason": f"Error processing image: {e}",
                "modifications": [],
            }

        candidates = []
        for asset in registered_assets:
            # hash_signature may be a dict or a JSON string (from Supabase)
            hs = asset.get("hash_signature") or {}
            if isinstance(hs, str):
                try:
                    hs = json.loads(hs)
                except Exception:
                    hs = {}

            stored_phash = hs.get("phash", "")
            if not stored_phash:
                continue

            try:
                distance = (
                    imagehash.hex_to_hash(stored_phash)
                    - imagehash.hex_to_hash(susp_phash)
                )
            except Exception:
                continue

            # Build candidate in the format verify_semantic_match_with_gemini expects
            candidates.append({
                "asset": {
                    "asset_id": asset.get("id"),
                    "phash": hs.get("phash"),
                    "dhash": hs.get("dhash"),
                    "ahash": hs.get("ahash"),
                    "chash": hs.get("chash"),
                    "width": hs.get("width"),
                    "height": hs.get("height"),
                    "blur_index": hs.get("blur_index"),
                },
                "distance": distance,
            })

        if not candidates:
            return {
                "match": False,
                "confidence": 0,
                "matched_asset_id": None,
                "reason": "No valid hash signatures to compare.",
                "modifications": [],
            }

        candidates.sort(key=lambda x: x["distance"])
        top_candidates = [c["asset"] for c in candidates[:3]]

        # ── AI Verification ────────────────────────────────────────────────────
        from core.ai_engine import verify_semantic_match_with_gemini
        ai_result = await verify_semantic_match_with_gemini(suspicious_path, top_candidates)

        if ai_result:
            return {
                "match": ai_result.get("match", False),
                "confidence": ai_result.get("similarity_score", 0),
                "matched_asset_id": ai_result.get("matched_asset_id"),
                "reason": ai_result.get("reason", "Analyzed via AI."),
                "modifications": ai_result.get("modifications", []),
            }

        return {
            "match": False,
            "confidence": 0,
            "matched_asset_id": None,
            "reason": "AI Engine unavailable or failed.",
            "modifications": [],
        }

    finally:
        if os.path.exists(suspicious_path):
            os.remove(suspicious_path)


# ─── Status ───────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """Health check — confirms the Engine is online."""
    return {"engine": "online"}
