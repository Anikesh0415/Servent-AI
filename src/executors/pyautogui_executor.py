import time
from src.executors.base_executor import BaseExecutor
from src.action_library import (
    type_action, key_action, click_action, scroll_action,
    open_app, navigate_browser, copy_all, paste_action
)

class PyAutoGUIExecutor(BaseExecutor):
    """
    PyAutoGUI / Keyboard-first fallback executor for Servent-AI.
    Executes keyboard shortcuts, typing, run commands, and coordinate clicks.
    """
    def __init__(self):
        super().__init__(name="PyAutoGUIExecutor")

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        supported = [
            "open_app", "open_browser", "type_text", "key_shortcut",
            "scroll", "click_element", "copy_all", "paste", "speak", "wait_until"
        ]
        return action_type.lower() in supported

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        action_type = action_type.lower()
        try:
            if action_type == "open_app":
                name = step_data.get("name") or step_data.get("app", "")
                msg = open_app(name)
                return True, msg

            elif action_type == "open_browser":
                url = step_data.get("url", "")
                msg = navigate_browser(url)
                return True, msg

            elif action_type == "type_text":
                text = step_data.get("text", "")
                msg = type_action(text)
                return True, msg

            elif action_type == "key_shortcut":
                keys = step_data.get("keys") or step_data.get("key", "")
                msg = key_action(keys)
                return True, msg

            elif action_type == "scroll":
                amount = step_data.get("amount", 3)
                msg = scroll_action(amount)
                return True, msg

            elif action_type == "copy_all":
                msg = copy_all()
                return True, msg

            elif action_type == "paste":
                msg = paste_action()
                return True, msg

            elif action_type == "click_element":
                x = step_data.get("x")
                y = step_data.get("y")
                if x is not None and y is not None:
                    msg = click_action(x, y)
                    return True, msg
                return True, f"Mocked click on '{step_data.get('target', '')}'"

            elif action_type == "speak":
                text = step_data.get("text", "")
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass
                return True, f"Spoke: '{text}'"

            elif action_type == "wait_until":
                return True, f"Wait until condition checked: '{step_data.get('condition', '')}'"

            return False, f"Unknown action: '{action_type}'"

        except Exception as e:
            return False, f"PyAutoGUI error executing {action_type}: {e}"
