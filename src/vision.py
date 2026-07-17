import json
import requests
from src.screenshot import capture_screen_base64

# URL to Ollama's generate API
OLLAMA_API_URL = "http://localhost:11434/api/generate"
VISION_MODEL = "moondream"

def vista_analyze(prompt: str) -> str:
    """
    Captures the screen and sends it to the VISTA model (moondream) 
    along with the prompt to analyze the screen state.
    """
    # 1. Capture the screen
    b64_image = capture_screen_base64()
    
    # 2. Prepare request to Ollama
    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "images": [b64_image],
        "stream": False,
        "options": {
            "temperature": 0.0 # Deterministic analysis
        }
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "").strip()
    except Exception as e:
        print(f"[VISTA Error] Failed to analyze screen: {e}")
        return "Error: Could not analyze screen."

def verify_action_success(action_description: str) -> bool:
    """
    Asks the vision model to verify if a specific action was successful based on the current screen.
    """
    prompt = f"I just tried to perform this action: '{action_description}'. Based on the current screen, did this action succeed? Answer with exactly YES or NO."
    response = vista_analyze(prompt)
    
    # Fallback to YES if model is confused, to prevent infinite loops, but log it
    if "YES" in response.upper():
        return True
    elif "NO" in response.upper():
        return False
    else:
        print(f"[VISTA Warning] Ambiguous verification response: {response}")
        return True # Default to true to continue execution

if __name__ == "__main__":
    # Test VISTA
    print("Testing VISTA (Moondream)...")
    res = vista_analyze("Describe what you see on the screen briefly.")
    print(f"VISTA Analysis: {res}")
