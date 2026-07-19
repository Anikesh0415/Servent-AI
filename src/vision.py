import json
import requests
import time
from src.screenshot import capture_screen_base64
from src.logger import logger

OLLAMA_API_URL = "http://localhost:11434/api/generate"
VISION_MODEL   = "moondream"

# ---------------------------------------------------------------------------
# CORE VISTA CALL
# ---------------------------------------------------------------------------

def vista_analyze(prompt: str, timeout: int = 30) -> str:
    """
    Captures the screen and sends it to VISTA (Moondream) with the given prompt.
    Returns the raw text response from the vision model.
    """
    b64_image = capture_screen_base64()

    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "images": [b64_image],
        "stream": False,
        "keep_alive": -1,      # Keep Moondream pinned in RAM
        "options": {
            "temperature": 0.0
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        res_text = response.json().get("response", "").strip()
        logger.info(f"VISTA Moondream Response: '{res_text}'")
        return res_text
    except Exception as e:
        logger.error(f"VISTA Error during vision analysis: {e}")
        return ""

# ---------------------------------------------------------------------------
# PRE-ACTION PREFLIGHT & POPUP DETECTION
# ---------------------------------------------------------------------------

def preflight_check(action_target: str = "") -> dict:
    """
    Pre-Action Vision Preflight:
    Captures the screen BEFORE executing an action to verify state and detect unexpected pop-ups.
    Returns: {"clear_to_proceed": bool, "popup_detected": bool, "popup_description": str}
    """
    prompt = (
        "Analyze the current computer screen. "
        "Is there an unexpected error popup, dialog box, or warning blocking the screen? "
        "Answer with POPUP_DETECTED: <description> or CLEAR."
    )
    res = vista_analyze(prompt, timeout=15)
    
    if "POPUP_DETECTED" in res.upper():
        logger.warning(f"Preflight check detected obstacle: {res}")
        return {
            "clear_to_proceed": False,
            "popup_detected": True,
            "popup_description": res
        }
        
    return {
        "clear_to_proceed": True,
        "popup_detected": False,
        "popup_description": ""
    }

# ---------------------------------------------------------------------------
# OCR / TEXT-BASED ELEMENT LOCATING
# ---------------------------------------------------------------------------

def ocr_screen_search(target_text: str) -> dict:
    """
    Attempts fast OCR text search on the screen.
    Returns: {"found": bool, "text": str}
    """
    try:
        # Check Windows OCR or pytesseract if installed
        import pytesseract
        from PIL import Image
        import io
        import base64
        
        b64_img = capture_screen_base64()
        img = Image.open(io.BytesIO(base64.b64decode(b64_img)))
        extracted_text = pytesseract.image_to_string(img)
        
        found = target_text.lower() in extracted_text.lower()
        return {"found": found, "text": extracted_text[:200]}
    except Exception:
        # Fallback to Moondream vision question
        res = vista_analyze(f"Is the text or button '{target_text}' visible on screen? Answer YES or NO.")
        return {"found": "YES" in res.upper(), "text": res}

# ---------------------------------------------------------------------------
# POST-ACTION ANCHOR VERIFICATION
# ---------------------------------------------------------------------------

def verify_anchor(anchor_check: str) -> bool:
    """
    Post-Action Verification.
    Queries Moondream with a precise question derived from anchor_check.
    """
    prompt = (
        f"Look at the current screen carefully. "
        f"Answer with ONLY the word YES or NO. "
        f"Question: {anchor_check}?"
    )
    response = vista_analyze(prompt)

    upper = response.upper()
    if "YES" in upper:
        return True
    elif "NO" in upper:
        return False
    else:
        logger.warning(f"Ambiguous anchor response: '{response}' — defaulting to True")
        return True

# ---------------------------------------------------------------------------
# SMART WAIT
# ---------------------------------------------------------------------------

def smart_wait_for_completion(
    loading_indicator_question: str,
    max_wait_seconds: int = 60,
    poll_interval: float = 3.0
) -> bool:
    """
    Polls VISTA every `poll_interval` seconds until loading is complete.
    """
    elapsed = 0.0
    while elapsed < max_wait_seconds:
        is_met = vista_analyze(
            f"Answer ONLY YES or NO. Is this condition met: '{loading_indicator_question}'?"
        ).upper()

        if "YES" in is_met:
            logger.info(f"SmartWait condition met after {elapsed:.1f}s.")
            return True

        logger.info(f"SmartWait polling... ({elapsed:.1f}s elapsed). Moondream: '{is_met}'")
        time.sleep(poll_interval)
        elapsed += poll_interval

    logger.warning(f"SmartWait timed out after {max_wait_seconds}s.")
    return False

def verify_action_success(action_description: str) -> bool:
    """Legacy helper maintained for backward compatibility."""
    return verify_anchor(f"Did the following succeed: {action_description}")


if __name__ == "__main__":
    print("Testing Preflight Check...")
    print(preflight_check("open chrome"))
