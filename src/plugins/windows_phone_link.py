import time
import pyautogui
import pyperclip
from src.action_library import _windows_search
from src.logger import logger

def send_sms_message(contact: str, message: str) -> str:
    """
    Automates Windows Phone Link to send an SMS message.
    Requires the user's phone to be linked to Windows Phone Link.
    """
    logger.info(f"Opening Phone Link to message '{contact}'")
    _windows_search("Phone Link")
    
    # Wait for Phone Link to load
    time.sleep(4)
    
    # Focus search bar in Phone Link (Ctrl+N for new message)
    pyautogui.hotkey('ctrl', 'n')
    time.sleep(1)
    
    # Type contact name
    pyperclip.copy(contact)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2)
    
    # Select the contact
    pyautogui.press('down')
    time.sleep(0.5)
    pyautogui.press('enter')
    time.sleep(1)
    
    # Type message and send
    pyperclip.copy(message)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    
    return f"Successfully queued SMS message to {contact} via Phone Link."

def register_plugin(registry):
    registry.register(
        "send_sms_message",
        '{"action": "send_sms_message", "contact": "name or number", "message": "msg"}',
        send_sms_message
    )
    logger.info("Plugin registered: windows_phone_link")
