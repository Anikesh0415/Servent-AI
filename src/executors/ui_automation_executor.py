from src.executors.base_executor import BaseExecutor
from src.logger import logger


class UIAutomationExecutor(BaseExecutor):
    """
    Windows UI Automation / Accessibility API Executor for Forge.
    Interacts with native Windows controls using pywinauto or win32gui.
    Falls back gracefully if the control is not accessible or library is missing.
    """

    def __init__(self):
        super().__init__(name="UIAutomationExecutor")
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            import pywinauto

            return True
        except ImportError:
            logger.info(
                "pywinauto not installed — UIAutomation will act as fallback check."
            )
            return False

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        if not self.available:
            return False
        return action_type.lower() in [
            "click_element",
            "type_text",
            "open_app",
            "wait_until",
        ]

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        if not self.available:
            return False, "pywinauto not available"

        action_type = action_type.lower()

        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")

            if action_type == "click_element":
                target_name = step_data.get("target", "")
                if not target_name:
                    return False, "No target provided for UIAutomation click"

                # Attempt to find control recursively within the active window
                active_win = desktop.active_window()
                if not active_win:
                    return False, "No active window found for UIAutomation click"

                controls = active_win.descendants(
                    title_re=f".*{target_name}.*", visible_only=True
                )
                if not controls:
                    # Fallback to searching top-level windows if active_win didn't have it
                    controls = desktop.windows(
                        title_re=f".*{target_name}.*", visible_only=True
                    )

                if controls:
                    controls[0].set_focus()
                    controls[0].click_input()
                    return True, f"UIAutomation clicked control: '{target_name}'"

            elif action_type == "type_text":
                text = step_data.get("text", "")
                # Type into currently focused UIA element
                active_win = desktop.active_window()
                if active_win:
                    active_win.type_keys(text, with_spaces=True)
                    return True, f"UIAutomation typed into active window: '{text}'"

            elif action_type == "wait_until":
                condition = step_data.get("condition", "")
                target_name = step_data.get("target", "")

                # If target is provided, wait specifically for that element
                if target_name:
                    active_win = desktop.active_window()
                    try:
                        if active_win:
                            active_win.descendants(
                                title_re=f".*{target_name}.*", visible_only=True
                            )[0].wait("ready", timeout=15)
                        else:
                            desktop.windows(
                                title_re=f".*{target_name}.*", visible_only=True
                            )[0].wait("ready", timeout=15)
                        return (
                            True,
                            f"Deterministic UI wait met for target: '{target_name}'",
                        )
                    except Exception:
                        return (
                            False,
                            f"Timeout waiting for target: '{target_name}' to appear",
                        )
                else:
                    return False, f"UIAutomation wait_until requires a 'target' key."

            return (
                False,
                f"UIAutomation element '{step_data.get('target', '')}' not found",
            )

        except Exception as e:
            logger.warning(f"UIAutomation execution failed ({e}). Falling back.")
            return False, str(e)
