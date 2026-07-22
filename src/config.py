import os
import json

# Fallback configurations if not defined in environment
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

LM_STUDIO_API_URL = os.environ.get(
    "LM_STUDIO_API_URL", "http://127.0.0.1:1234/v1/chat/completions"
)
LM_STUDIO_MODELS_URL = os.environ.get(
    "LM_STUDIO_MODELS_URL", "http://127.0.0.1:1234/v1/models"
)
DEFAULT_LM_STUDIO_MODEL = os.environ.get(
    "DEFAULT_LM_STUDIO_MODEL", "hermes-2-pro-llama-3-8b"
)

VISION_MODEL = os.environ.get("VISION_MODEL", "moondream")

# Phase 3: Cognitive Model Swapping
IDE_MODEL_OLLAMA = os.environ.get("IDE_MODEL_OLLAMA", "qwen2.5-coder:1.5b")
IDE_MODEL_LMSTUDIO = os.environ.get("IDE_MODEL_LMSTUDIO", "qwen2.5-coder")
IDE_APP_NAMES = [
    "Code",
    "Visual Studio Code",
    "Cursor",
    "PyCharm",
    "IntelliJ",
    "devenv",
]

# Comprehensive Universal Service Map
_default_browser_map = {
    # AI Portals
    "antigravity": "https://antigravity.google.com",
    "gemini": "https://gemini.google.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "perplexity": "https://perplexity.ai",
    "copilot": "https://copilot.microsoft.com",
    "deepseek": "https://chat.deepseek.com",
    "mistral": "https://chat.mistral.ai",
    "huggingface": "https://huggingface.co",

    # Search & Media
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "yt": "https://youtube.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://netflix.com",
    "twitch": "https://twitch.tv",

    # Social & Community
    "whatsapp": "WhatsApp",
    "telegram": "https://web.telegram.org",
    "discord": "https://discord.com/app",
    "reddit": "https://reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "instagram": "https://instagram.com",
    "linkedin": "https://linkedin.com",

    # Developer & Productivity
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "notion": "https://notion.so",
    "figma": "https://figma.com",
    "gmail": "https://mail.google.com",
}
try:
    BROWSER_APP_MAP = json.loads(os.environ.get("BROWSER_APP_MAP", "{}"))
    if not BROWSER_APP_MAP:
        BROWSER_APP_MAP = _default_browser_map
except Exception:
    BROWSER_APP_MAP = _default_browser_map

# Phase 7 & 8: Acoustic Neutrality
try:
    WAKE_WORDS = json.loads(
        os.environ.get("WAKE_WORDS", '["servent", "servant", "forge"]')
    )
except Exception:
    WAKE_WORDS = ["servent", "servant", "forge"]

NOISE_GATE_THRESHOLD = float(os.environ.get("NOISE_GATE_THRESHOLD", "0.05"))
