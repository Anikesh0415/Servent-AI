import time
import webbrowser
import pyautogui
import pyperclip
from src.logger import logger

def send_whatsapp_message(contact: str, message: str) -> str:
    """
    Automates WhatsApp Web to send a message to a specific contact.
    Requires the user to be logged into web.whatsapp.com in their default browser.
    """
    logger.info(f"Opening WhatsApp Web to message '{contact}'")
    webbrowser.open("https://web.whatsapp.com")
    
    # Wait for WhatsApp Web to load
    # In a fully autonomous agent, we'd use vision anchors, but a static wait works for a robust macro
    time.sleep(12) 
    
    # Focus the search bar (Ctrl + Alt + / on Windows, or Tab multiple times, but Ctrl+Alt+/ is standard for WA Web search)
    pyautogui.hotkey('ctrl', 'alt', '/')
    time.sleep(1)
    
    # Type contact name
    pyperclip.copy(contact)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2)  # Wait for search results
    
    # Tab to the chat list and select the top result
    pyautogui.press('tab')
    time.sleep(0.5)
    pyautogui.press('enter')
    time.sleep(1)
    
    # Type message and send
    pyperclip.copy(message)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    
    return f"Successfully sent WhatsApp message to {contact}."

def register_plugin(registry):
    registry.register(
        "send_whatsapp_message",
        '{"action": "send_whatsapp_message", "contact": "name", "message": "msg"}',
        send_whatsapp_message
    )
    logger.info("Plugin registered: whatsapp_automation")
