import os
import time
import pyperclip
import pyautogui

class ContextManager:
    """
    Centralized Context Manager for Servent-AI.
    Tracks active window, focused app, clipboard snapshot, resolution, and active task state.
    """
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_clipboard = ""
        self.active_app = "Unknown"
        self.active_window_title = "Unknown"
        self.execution_progress = 0.0
        self.current_task_description = ""
        
    def capture_os_context(self) -> dict:
        """Captures real-time OS state including window title and clipboard."""
        self._update_active_window()
        self._update_clipboard()
        
        return {
            "active_app": self.active_app,
            "active_window_title": self.active_window_title,
            "clipboard": self.last_clipboard,
            "screen_resolution": (self.screen_width, self.screen_height),
            "mouse_position": pyautogui.position(),
            "timestamp": time.time()
        }

    def _update_active_window(self):
        """Attempts to retrieve the title of the currently focused window."""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            if win:
                self.active_window_title = win.title or "Unknown"
                # Simple heuristic to extract app name from title
                parts = self.active_window_title.split(" - ")
                self.active_app = parts[-1] if len(parts) > 1 else parts[0]
            else:
                self.active_window_title = "Desktop / Unknown"
                self.active_app = "Explorer"
        except Exception:
            # Fallback for platforms where pygetwindow might fail
            self.active_window_title = "Windows Workspace"
            self.active_app = "Windows"

    def _update_clipboard(self):
        """Snapshots current clipboard text safely."""
        try:
            text = pyperclip.paste()
            if text and isinstance(text, str):
                # Limit length to avoid memory bloat
                self.last_clipboard = text[:2000]
        except Exception:
            pass

    def set_task_progress(self, task_description: str, progress_ratio: float):
        """Updates current execution progress ratio (0.0 to 1.0)."""
        self.current_task_description = task_description
        self.execution_progress = max(0.0, min(1.0, progress_ratio))

    def get_summary_prompt_context(self) -> str:
        """Returns a string formatted for inclusion in LLM prompts."""
        ctx = self.capture_os_context()
        return (
            f"Active App: {ctx['active_app']} | Focused Window: {ctx['active_window_title']} | "
            f"Screen: {ctx['screen_resolution'][0]}x{ctx['screen_resolution'][1]}"
        )


if __name__ == "__main__":
    cm = ContextManager()
    print("OS Context:", cm.capture_os_context())
    print("Summary:", cm.get_summary_prompt_context())
