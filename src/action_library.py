import pyautogui
import time
import pyperclip
import webbrowser

pyautogui.FAILSAFE = False

def click_action(x: int, y: int) -> str:
    """Moves the mouse to (x,y) and clicks."""
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()
    return f"Clicked at ({x}, {y})"

def type_action(text: str) -> str:
    """Types the given text using clipboard paste for reliability."""
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'v')
    return f"Typed: '{text}'"

def key_action(key: str) -> str:
    """Presses a specific key (e.g., 'enter', 'tab', 'esc')."""
    pyautogui.press(key)
    return f"Pressed key: '{key}'"

def open_app_action(app_name: str) -> str:
    """Opens a system app or website."""
    # Handle known websites
    url_map = {
        "youtube": "https://youtube.com",
        "gemini": "https://gemini.google.com",
        "chatgpt": "https://chatgpt.com",
        "google": "https://google.com"
    }
    
    app_name_lower = app_name.lower().strip()
    
    if app_name_lower in url_map:
        webbrowser.open(url_map[app_name_lower])
        return f"Opened website: {url_map[app_name_lower]}"
    
    # Try to open via start menu
    pyautogui.press('win')
    time.sleep(0.5)
    type_action(app_name)
    time.sleep(1.0)
    pyautogui.press('enter')
    return f"Attempted to open app: {app_name}"

def scroll_action(amount: int) -> str:
    """Scrolls the screen by the given amount."""
    pyautogui.scroll(amount)
    return f"Scrolled by {amount}"
