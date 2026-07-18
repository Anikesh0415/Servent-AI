import pyautogui
import pyperclip
import time
import webbrowser

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0  # No inter-call delays — we control timing ourselves

# ---------------------------------------------------------------------------
# KEYBOARD-FIRST URL / APP MAP
# ---------------------------------------------------------------------------
BROWSER_APP_MAP = {
    "youtube":    "https://youtube.com",
    "gemini":     "https://gemini.google.com",
    "chatgpt":    "https://chatgpt.com",
    "google":     "https://google.com",
    "gmail":      "https://mail.google.com",
    "github":     "https://github.com",
    "wikipedia":  "https://wikipedia.org",
}

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
    """
    pyperclip.copy(text)
    time.sleep(0.05)
    _hotkey('ctrl', 'v')
    return f"Typed: '{text}'"


def key_action(key: str) -> str:
    """Presses a single named key (e.g. 'enter', 'tab', 'esc', 'f5')."""
    pyautogui.press(key)
    time.sleep(0.05)
    return f"Pressed: '{key}'"


def click_action(x: int, y: int) -> str:
    """
    Last-resort mouse click. Only used when NO keyboard alternative exists.
    ARIA is instructed to avoid this action whenever possible.
    """
    pyautogui.moveTo(x, y, duration=0.15)
    pyautogui.click()
    return f"Clicked at ({x}, {y})"


def scroll_action(amount: int) -> str:
    """Scrolls the active window by `amount` (positive = up, negative = down)."""
    pyautogui.scroll(amount)
    return f"Scrolled by {amount}"


# ---------------------------------------------------------------------------
# KEYBOARD-FIRST HIGH-LEVEL ACTIONS
# ---------------------------------------------------------------------------

def open_app(app_name: str) -> str:
    """
    Opens an app or website using keyboard-only methods.
    - For known websites: Win+R -> browser URL -> Enter.
    - For unknown apps:   Win+R -> app name -> Enter.
    Avoids relying on the Start Menu search which is flaky.
    """
    app_lower = app_name.lower().strip()
    target = BROWSER_APP_MAP.get(app_lower)

    if target:
        # Open URL in default browser via Win+R -> run dialog
        _hotkey('win', 'r')
        time.sleep(0.6)          # Wait for Run dialog to appear
        type_action(target)
        time.sleep(0.1)
        pyautogui.press('enter')
        return f"Opened browser to: {target}"
    else:
        # Unknown app — open via Win+R with the app name
        _hotkey('win', 'r')
        time.sleep(0.6)
        type_action(app_lower)
        time.sleep(0.1)
        pyautogui.press('enter')
        return f"Launched via Run: {app_lower}"


def navigate_browser(url: str) -> str:
    """
    Navigates to a URL by using the Windows Run dialog (Win+R).
    This ensures the default browser opens it even if not currently focused.
    """
    _hotkey('win', 'r')
    time.sleep(0.6)
    type_action(url)
    time.sleep(0.1)
    pyautogui.press('enter')
    return f"Navigated to: {url}"


def copy_all() -> str:
    """Selects all text in the focused element and copies to clipboard."""
    _hotkey('ctrl', 'a')
    time.sleep(0.05)
    _hotkey('ctrl', 'c')
    time.sleep(0.1)
    return "Selected all and copied to clipboard."


def paste_action() -> str:
    """Pastes clipboard content into the focused element."""
    _hotkey('ctrl', 'v')
    return "Pasted clipboard content."
