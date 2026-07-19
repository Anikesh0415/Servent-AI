import pyautogui
import pyperclip
import time
import webbrowser

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0  # No inter-call delays — we control timing ourselves

# ---------------------------------------------------------------------------
# KEYBOARD-FIRST URL / APP MAP
# ---------------------------------------------------------------------------
import time
import pyperclip
from src.llm_core import LocalLLMCore
from src.config import BROWSER_APP_MAP

# ---------------------------------------------------------------------------
# CORE PRIMITIVES
# ---------------------------------------------------------------------------

def _hotkey(*keys):
    """Thin wrapper around pyautogui.hotkey."""
    pyautogui.hotkey(*keys)
    time.sleep(0.05)


def type_action(text: str) -> str:
    """
    Types text using clipboard paste for speed and reliability.
    Avoids key-by-key typing which drops characters at high speed.
    Preserves the original clipboard contents.
    """
    try:
        original_clipboard = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(0.05)
        _hotkey('ctrl', 'v')
        time.sleep(0.05)
        pyperclip.copy(original_clipboard)
        return f"Typed: '{text}'"
    except Exception as e:
        return f"Error typing text: {e}"


def key_action(key: str) -> str:
    """Presses a single named key (e.g. 'enter', 'tab', 'esc', 'f5') or shortcut ('ctrl+c')."""
    try:
        if '+' in key:
            keys = [k.strip() for k in key.split('+')]
            _hotkey(*keys)
        else:
            pyautogui.press(key)
            time.sleep(0.05)
        return f"Pressed: '{key}'"
    except Exception as e:
        return f"Error pressing key: {e}"


def click_action(x: int, y: int) -> str:
    """
    Last-resort mouse click. Only used when NO keyboard alternative exists.
    ARIA is instructed to avoid this action whenever possible.
    """
    try:
        pyautogui.moveTo(x, y, duration=0.15)
        pyautogui.click()
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error clicking: {e}"


def scroll_action(amount: int) -> str:
    """Scrolls the active window by `amount` (positive = up, negative = down)."""
    pyautogui.scroll(amount)
    return f"Scrolled by {amount}"


# ---------------------------------------------------------------------------
# KEYBOARD-FIRST HIGH-LEVEL ACTIONS
# ---------------------------------------------------------------------------

def _windows_search(query: str) -> str:
    """Helper to open apps/urls via Windows Search."""
    try:
        pyautogui.press('win')
        time.sleep(0.8)          # Wait for Search menu to appear
        type_action(query)
        time.sleep(0.5)          # Wait for search results
        pyautogui.press('enter')
        return f"Windows Search executed for: {query}"
    except Exception as e:
        return f"Error executing Windows Search: {e}"


def open_app(app_name: str) -> str:
    """
    Opens an app or website using Windows Search.
    """
    app_lower = app_name.lower().strip()
    target = BROWSER_APP_MAP.get(app_lower)

    if target:
        _windows_search(target)
        return f"Opened browser to: {target}"
    else:
        _windows_search(app_name)
        return f"Launched via Search: {app_name}"


def navigate_browser(url: str) -> str:
    """
    Navigates to a URL by using the Windows Search.
    """
    _windows_search(url)
    return f"Navigated to: {url}"


def copy_all() -> str:
    """Selects all text in the focused element and copies to clipboard."""
    _hotkey('ctrl', 'a')
    time.sleep(0.1)
    _hotkey('ctrl', 'c')
    time.sleep(0.2)
    return "Selected all and copied to clipboard."

def semantic_copy(extraction_goal: str) -> str:
    """
    Copies all text on the screen, passes it to the local LLM to extract 
    exactly the information matching the extraction_goal, and places the 
    clean extracted text back into the clipboard.
    """
    import pyautogui
    # Click empty space (e.g., center-left) to drop focus from any input boxes
    sz = pyautogui.size()
    pyautogui.click(sz.width // 4, sz.height // 2)
    time.sleep(0.2)
    
    _hotkey('ctrl', 'a')
    time.sleep(0.1)
    _hotkey('ctrl', 'c')
    time.sleep(0.3)
    
    raw_text = pyperclip.paste()
    if not raw_text or len(raw_text.strip()) == 0:
        return "Failed to copy raw text from screen."
        
    prompt = f"Here is raw, messy text copied from a webpage/screen:\n\n---\n{raw_text[:8000]}\n---\n\nExtract exactly the information that matches this goal: '{extraction_goal}'. Output ONLY the extracted text and absolutely nothing else."
    
    llm = LocalLLMCore()
    extracted_text = llm.query_llm([{"role": "user", "content": prompt}])
    
    pyperclip.copy(extracted_text)
    return f"Semantically extracted data and placed into clipboard."


def paste_action() -> str:
    """Pastes clipboard content into the focused element."""
    _hotkey('ctrl', 'v')
    return "Pasted clipboard content."
