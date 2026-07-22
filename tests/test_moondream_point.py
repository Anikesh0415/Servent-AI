import requests
import base64
import io
from PIL import ImageGrab

def capture_screen_base64():
    img = ImageGrab.grab()
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=80)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

b64_image = capture_screen_base64()

payload = {
    "model": "moondream",
    "prompt": "Point at the Gemini copy button.",
    "images": [b64_image],
    "stream": False
}

try:
    response = requests.post("http://127.0.0.1:11434/api/generate", json=payload)
    print("Moondream response:")
    print(response.json().get("response"))
except Exception as e:
    print(e)
