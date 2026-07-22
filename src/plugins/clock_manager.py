import time
import threading
from datetime import datetime
from src.logger import logger

# We will need a reference to the global event bus or websocket to send notifications.
# For simplicity, we just log the alarm since the UI could poll, or we can use win10toast.

def get_current_time() -> str:
    """Returns the current system time and date."""
    now = datetime.now()
    return f"Current time is {now.strftime('%I:%M %p on %A, %B %d, %Y')}."

def set_alarm(seconds: int, message: str) -> str:
    """Sets a background timer that will trigger an alert after X seconds."""
    
    def _alarm_thread():
        time.sleep(float(seconds))
        logger.info(f"[ALARM TRIGGERED] {message}")
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast("ARIA Alarm", message, duration=5, threaded=True)
        except ImportError:
            logger.warning("win10toast not installed, could not show Windows notification.")

    t = threading.Thread(target=_alarm_thread, daemon=True)
    t.start()
    return f"Alarm set for {seconds} seconds from now. Message: '{message}'"

def register_plugin(registry):
    registry.register(
        "get_time",
        '{"action": "get_time"}',
        get_current_time
    )
    registry.register(
        "set_alarm",
        '{"action": "set_alarm", "seconds": 60, "message": "wake up"}',
        set_alarm
    )
    logger.info("Plugin registered: clock_manager")
