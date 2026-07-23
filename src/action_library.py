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


class ActionRegistry:
    def __init__(self):
        self.actions = {}
        self.descriptions = {}

    def register(self, name, description, func):
        self.actions[name] = func
        self.descriptions[name] = description

    def get_prompt_text(self):
        return "\n".join(
            [f"- {name}: {desc}" for name, desc in self.descriptions.items()]
        )

    def execute(self, action_name, **kwargs):
        if action_name in self.actions:
            return self.actions[action_name](**kwargs)
        return f"Error: Unknown action '{action_name}'"


action_registry = ActionRegistry()


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
        _hotkey("ctrl", "v")
        time.sleep(0.05)
        pyperclip.copy(original_clipboard)
        return f"Typed: '{text}'"
    except Exception as e:
        return f"Error typing text: {e}"


def key_action(key: str) -> str:
    """Presses a single named key (e.g. 'enter', 'tab', 'esc', 'f5') or shortcut ('ctrl+c')."""
    try:
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
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


def click_text(target: str, index: int = 1) -> str:
    """Uses Coordinate OCR to find text on screen and click its exact coordinates."""
    from src.vision import ocr_screen_search

    res = ocr_screen_search(target)
    if res["found"] and res["coords"]:
        x, y = res["coords"]
        return click_action(x, y)
    elif res["found"] and not res["coords"]:
        return f"Found '{target}', but OCR coordinate engine is unavailable."
    else:
        return f"Could not find '{target}' on screen."


# ---------------------------------------------------------------------------
# KEYBOARD-FIRST HIGH-LEVEL ACTIONS
# ---------------------------------------------------------------------------


def _windows_search(query: str) -> str:
    """Helper to open apps/urls via Windows Search."""
    try:
        pyautogui.press("win")
        time.sleep(0.8)  # Wait for Search menu to appear
        type_action(query)
        time.sleep(0.5)  # Wait for search results
        pyautogui.press("enter")
        return f"Windows Search executed for: {query}"
    except Exception as e:
        return f"Error executing Windows Search: {e}"


APP_ALIASES = {
    "whatsaap": "WhatsApp",
    "whatsapp": "WhatsApp",
    "whats app": "WhatsApp",
    "watsapp": "WhatsApp",
    "watsap": "WhatsApp",
    "gugle": "Google Chrome",
    "google": "Google Chrome",
    "chrome": "Google Chrome",
    "notpad": "Notepad",
    "notepad": "Notepad",
    "calc": "Calculator",
    "calculator": "Calculator",
    "spotify": "Spotify",
    "spotifi": "Spotify",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
}

def open_app(app_name: str) -> str:
    """
    Opens an app or website using direct browser launch or Windows Search.
    """
    app_lower = app_name.lower().strip()
    
    # Check typo aliases first
    if app_lower in APP_ALIASES:
        app_name = APP_ALIASES[app_lower]
        app_lower = app_name.lower()

    target = BROWSER_APP_MAP.get(app_lower)

    # Force Brave Browser if available
    brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    if os.path.exists(brave_path):
        webbrowser.register('brave', None, webbrowser.BackgroundBrowser(brave_path))
        browser = webbrowser.get('brave')
    else:
        browser = webbrowser

    if target:
        browser.open(target)
        return f"Opened browser to: {target}"
    elif app_lower.startswith(("http://", "https://", "www.")):
        url = app_name if app_name.startswith("http") else "https://" + app_name
        browser.open(url)
        return f"Opened browser to: {url}"
    else:
        _windows_search(app_name)
        return f"Launched via Search: {app_name}"


def navigate_browser(url: str) -> str:
    """
    Navigates to a URL using the default system browser.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    if os.path.exists(brave_path):
        webbrowser.register('brave', None, webbrowser.BackgroundBrowser(brave_path))
        browser = webbrowser.get('brave')
    else:
        browser = webbrowser
        
    browser.open(url)
    return f"Navigated to: {url}"


def close_app(target: str = "") -> str:
    """Closes active window or taskkills target process."""
    import os
    if target:
        target_clean = target.lower().strip().replace(".exe", "")
        # Common process names
        proc_map = {
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "whatsapp": "WhatsApp.exe",
            "notepad": "notepad.exe",
            "calculator": "CalculatorApp.exe",
            "spotify": "Spotify.exe",
            "vscode": "Code.exe",
            "code": "Code.exe"
        }
        if target_clean in proc_map:
            os.system(f"taskkill /f /im {proc_map[target_clean]} >nul 2>&1")
            return f"Closed {target}"
    # Fallback to Alt+F4 active window close
    _hotkey("alt", "f4")
    return "Closed active window."


def take_screenshot(target: str = "") -> str:
    """Takes a screenshot and saves it to Desktop."""
    import os
    import datetime
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(desktop, f"Screenshot_{timestamp}.png")
        img = pyautogui.screenshot()
        img.save(filename)
        return f"Screenshot saved to Desktop: Screenshot_{timestamp}.png"
    except Exception as e:
        _hotkey("win", "prtsc")
        return "Saved screenshot via Windows shortcut."


def search_web(query: str) -> str:
    """Performs a web search on Google."""
    import urllib.parse
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    return f"Searched Google for: '{query}'"


def play_spotify(query: str) -> str:
    """Searches and plays music on Spotify."""
    import os
    import urllib.parse
    encoded = urllib.parse.quote_plus(query)
    # Open Spotify web search or app search URI
    webbrowser.open(f"https://open.spotify.com/search/{encoded}")
    time.sleep(2.0)
    _hotkey("enter")
    return f"Playing '{query}' on Spotify."


def send_whatsapp(contact: str, message: str) -> str:
    """Opens WhatsApp, searches contact, and sends message."""
    open_app("WhatsApp")
    time.sleep(2.0)
    _hotkey("ctrl", "f")
    time.sleep(0.5)
    type_action(contact)
    time.sleep(0.8)
    _hotkey("enter")
    time.sleep(0.8)
    type_action(message)
    time.sleep(0.3)
    _hotkey("enter")
    return f"Sent message to '{contact}' on WhatsApp: '{message}'"


def set_timer(minutes: str = "10") -> str:
    """Opens Clock app and sets a timer."""
    import os
    os.system("start ms-clock:")
    time.sleep(1.5)
    _windows_search(f"{minutes} minute timer")
    return f"Set a {minutes} minute timer on Clock app."


def copy_all() -> str:
    """Selects all text in the focused element and copies to clipboard."""
    _hotkey("ctrl", "a")
    time.sleep(0.1)
    _hotkey("ctrl", "c")
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

    _hotkey("ctrl", "a")
    time.sleep(0.1)
    _hotkey("ctrl", "c")
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
    _hotkey("ctrl", "v")
    return "Pasted clipboard content."


# Register core actions
action_registry.register(
    "open_browser", '{"action": "open_browser", "url": "https://..."}', navigate_browser
)
action_registry.register(
    "click_element",
    '{"action": "click_element", "target": "description"}',
    click_action,
)
action_registry.register(
    "type_text", '{"action": "type_text", "text": "exact text"}', type_action
)
action_registry.register(
    "key_shortcut", '{"action": "key_shortcut", "keys": "ctrl+c"}', key_action
)
action_registry.register(
    "open_app", '{"action": "open_app", "name": "app name"}', open_app
)
action_registry.register(
    "close_app", '{"action": "close_app", "target": "app name"}', close_app
)
action_registry.register(
    "take_screenshot", '{"action": "take_screenshot", "target": "desktop"}', take_screenshot
)
action_registry.register(
    "search_web", '{"action": "search_web", "query": "search query"}', search_web
)
action_registry.register(
    "play_spotify", '{"action": "play_spotify", "query": "song name"}', play_spotify
)
action_registry.register(
    "send_whatsapp", '{"action": "send_whatsapp", "contact": "name", "message": "text"}', send_whatsapp
)
action_registry.register(
    "set_timer", '{"action": "set_timer", "minutes": "10"}', set_timer
)
action_registry.register(
    "scroll", '{"action": "scroll", "direction": "down", "amount": 3}', scroll_action
)
action_registry.register(
    "semantic_copy", '{"action": "semantic_copy", "goal": "what data"}', semantic_copy
)
action_registry.register(
    "click_text",
    '{"action": "click_text", "text": "exact word to click", "index": 1}',
    click_text,
)


# Dynamic Plugin Loader
def load_plugins():
    import os
    import importlib
    from src.logger import logger

    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_dir):
        return

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"src.plugins.{filename[:-3]}"
            try:
                mod = importlib.import_module(module_name)
                if hasattr(mod, "register_plugin"):
                    mod.register_plugin(action_registry)
                logger.info(f"Loaded plugin: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {module_name}: {e}")


load_plugins()
