from enum import Enum


class RiskLevel(Enum):
    SAFE = 1  # Read-only actions, navigation, scrolling
    MODERATE = 2  # Typing, clicking non-critical UI elements, switching apps
    DESTRUCTIVE = 3  # Deleting files, modifying system settings, closing apps without saving, sending emails/messages


class SecurityManager:
    """
    Security & Permission Policy Manager for Forge.
    Protects user data, flags destructive actions, and handles permission levels.
    """

    def __init__(self, safe_mode: bool = True):
        self.safe_mode = safe_mode
        self.destructive_keywords = [
            "delete",
            "rm",
            "remove",
            "format",
            "shutdown",
            "restart",
            "erase",
            "drop",
            "terminate",
            "kill",
            "uninstall",
            "send_email",
            "send_message",
        ]

    def classify_action(self, action_type: str, params: dict = None) -> RiskLevel:
        """Categorizes an action into SAFE, MODERATE, or DESTRUCTIVE."""
        action_type = action_type.lower()

        # Safe read-only actions
        if action_type in [
            "scroll",
            "speak",
            "wait_until",
            "copy_all",
            "inspect_screen",
        ]:
            return RiskLevel.SAFE

        # Navigation & typing
        if action_type in ["open_browser", "open_app", "key_shortcut"]:
            return RiskLevel.MODERATE

        if action_type == "type_text":
            text = (params.get("text") if params else "") or ""
            if any(kw in text.lower() for kw in self.destructive_keywords):
                return RiskLevel.DESTRUCTIVE
            return RiskLevel.MODERATE

        if action_type == "click_element":
            target = (params.get("target") if params else "") or ""
            if any(kw in target.lower() for kw in self.destructive_keywords):
                return RiskLevel.DESTRUCTIVE
            return RiskLevel.MODERATE

        # Default fallback check on action name
        if any(kw in action_type for kw in self.destructive_keywords):
            return RiskLevel.DESTRUCTIVE

        return RiskLevel.MODERATE

    def requires_user_confirmation(self, action_type: str, params: dict = None) -> bool:
        """Determines if an action strictly requires explicit user confirmation."""
        risk = self.classify_action(action_type, params)
        if risk == RiskLevel.DESTRUCTIVE:
            return True
        if self.safe_mode and risk == RiskLevel.MODERATE:
            # Safe mode requires confirmation for moderate actions unless auto-approved
            return True
        return False

    def sanitize_text(self, text: str) -> str:
        """Redacts potential secrets (API keys, passwords) from prompt or log text."""
        import re

        # Redact patterns looking like sk-..., Bearer ..., API keys
        text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", text)
        text = re.sub(r"Bearer\s+[a-zA-Z0-9\-\_\.]+", "Bearer [REDACTED_TOKEN]", text)
        return text


if __name__ == "__main__":
    sec = SecurityManager(safe_mode=True)
    print("Open Browser:", sec.classify_action("open_browser"))
    print(
        "Delete File Command:", sec.classify_action("type_text", {"text": "rm -rf /"})
    )
    print(
        "Requires Confirmation for Delete:",
        sec.requires_user_confirmation("type_text", {"text": "delete all files"}),
    )
