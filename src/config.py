import os
import json

# Fallback configurations if not defined in environment
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

LM_STUDIO_API_URL = os.environ.get("LM_STUDIO_API_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODELS_URL = os.environ.get("LM_STUDIO_MODELS_URL", "http://localhost:1234/v1/models")
DEFAULT_LM_STUDIO_MODEL = os.environ.get("DEFAULT_LM_STUDIO_MODEL", "lmstudio-community/gemma-4-E4B-it-GGUF")

VISION_MODEL = os.environ.get("VISION_MODEL", "moondream")

# Use a JSON string from environment or fallback to default
_default_browser_map = {
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com"
}
try:
    BROWSER_APP_MAP = json.loads(os.environ.get("BROWSER_APP_MAP", "{}"))
    if not BROWSER_APP_MAP:
        BROWSER_APP_MAP = _default_browser_map
except Exception:
    BROWSER_APP_MAP = _default_browser_map
