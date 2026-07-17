import json
import requests
from src.screenshot import capture_screen_base64

OLLAMA_API_URL = "http://localhost:11434/api/generate"
VISION_MODEL   = "moondream"

# ---------------------------------------------------------------------------
# CORE VISTA CALL (Phase 1: keep_alive=-1 pins Moondream in RAM)
# ---------------------------------------------------------------------------

def vista_analyze(prompt: str, timeout: int = 30) -> str:
    """
    Captures the screen and sends it to VISTA (moondream) with the given prompt.
    Returns the raw text response from the vision model.
    """
    b64_image = capture_screen_base64()

    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "images": [b64_image],
        "stream": False,
        "keep_alive": -1,      # Phase 1: keep Moondream pinned in RAM
        "options": {
            "temperature": 0.0
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        print(f"[VISTA Error] {e}")
        return ""


# ---------------------------------------------------------------------------
# ANCHOR VERIFICATION (Phase 4)
# ---------------------------------------------------------------------------

def verify_anchor(anchor_check: str) -> bool:
    """
    Phase 4 — Anchor Verification.
    Instead of asking a vague "did it work?", we ask VISTA a precise, 
    specific question derived from the anchor_check field ARIA produced.
    
    VISTA is asked to respond with exactly YES or NO.
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
        # Ambiguous: default to True to avoid blocking execution
        print(f"[VISTA Warning] Ambiguous anchor response: '{response}' — defaulting to True")
        return True


# ---------------------------------------------------------------------------
# SMART WAIT — polls until loading indicator disappears (Phase 4)
# ---------------------------------------------------------------------------

def smart_wait_for_completion(
    loading_indicator_question: str,
    max_wait_seconds: int = 60,
    poll_interval: float = 3.0
) -> bool:
    """
    Phase 4 — Smart Wait.
    Polls VISTA every `poll_interval` seconds, asking whether a loading
    indicator is STILL VISIBLE. Returns True once loading is gone, or
    False if max_wait_seconds is exceeded.

    Example loading_indicator_question:
        "Are the animated loading stars or spinner still visible near the text input?"
    """
    import time
    elapsed = 0.0

    while elapsed < max_wait_seconds:
        still_loading = vista_analyze(
            f"Answer ONLY YES or NO. {loading_indicator_question}"
        ).upper()

        if "NO" in still_loading:
            print(f"[VISTA SmartWait] Loading complete after {elapsed:.1f}s.")
            return True

        print(f"[VISTA SmartWait] Still loading... ({elapsed:.1f}s elapsed)")
        time.sleep(poll_interval)
        elapsed += poll_interval

    print(f"[VISTA SmartWait] Timed out after {max_wait_seconds}s.")
    return False


# ---------------------------------------------------------------------------
# LEGACY HELPER (kept for backward compat, calls anchor verify internally)
# ---------------------------------------------------------------------------

def verify_action_success(action_description: str) -> bool:
    """
    Legacy helper: passes the action description as the anchor question.
    New code should use verify_anchor(anchor_check) directly.
    """
    return verify_anchor(f"Did the following succeed: {action_description}")


if __name__ == "__main__":
    print("Testing VISTA (Moondream)...")
    res = vista_analyze("Describe briefly what you see on the screen.")
    print(f"VISTA: {res}")
