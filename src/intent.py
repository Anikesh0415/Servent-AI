from dataclasses import dataclass


@dataclass
class Intent:
    action_type: str  # DRAFT_AND_SEND, COPY_AND_SEND, etc.
    source_app: str
    dest_app: str
    recipient: str

    def validate_action(self, proposed_action: dict, screen_state: dict) -> bool:
        """Check if action serves the original intent"""
        if self.recipient and "chat_name" in screen_state:
            if self.recipient.lower() not in screen_state["chat_name"].lower():
                print(f"⚠️ Intent violation: wrong chat!")
                return False
        return True
