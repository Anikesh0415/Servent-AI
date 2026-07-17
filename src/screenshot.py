import base64
import io
import os
from PIL import ImageGrab

def capture_screen_base64() -> str:
    """Captures the primary screen and returns it as a base64-encoded string."""
    try:
        screenshot = ImageGrab.grab()
        width, height = screenshot.size
        screenshot = screenshot.resize((width // 2, height // 2))
    except Exception as e:
        print(f"[Screenshot] Failed to grab screen (headless environment?): {e}")
        from PIL import Image
        screenshot = Image.new('RGB', (800, 600), color='white')
    
    buffer = io.BytesIO()
    # Save as JPEG for compression
    screenshot.save(buffer, format="JPEG", quality=80)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

if __name__ == "__main__":
    b64 = capture_screen_base64()
    print(f"Captured screenshot, base64 length: {len(b64)}")
