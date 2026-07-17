import requests
import base64
import json

try:
    print("Fetching image...")
    # Generate a dummy base64 image 1x1 pixel for testing
    img_str = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    print("Calling Ollama...")
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": "moondream",
        "prompt": "Output a JSON object with: {'action': 'wait'}",
        "images": [img_str],
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }, timeout=10)
    print(response.status_code)
    print(response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
