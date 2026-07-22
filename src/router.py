from enum import Enum


class Tier(Enum):
    INSTANT = "instant"  # No AI, <50ms
    FAST = "fast"  # OCR check, <200ms
    SLOW = "slow"  # Full AI, 2-4s


KNOWN_ACTIONS = {
    "whatsapp": {
        "send_message": ("send", 0.98),
        "search_contact": ("search", 0.95),
    },
    "chrome": {
        "navigate": ("address bar", 0.99),
    },
    "gemini": {
        "type_prompt": ("ask gemini", 0.95),
    },
}


def route_action(app: str, action: str, dna: dict) -> Tier:
    """Decide which tier to use"""
    if app in KNOWN_ACTIONS and action in KNOWN_ACTIONS[app]:
        pattern, conf = KNOWN_ACTIONS[app][action]
        all_text = " ".join(dna["all_text"]).lower()
        if pattern.lower() in all_text and conf > 0.85:
            return Tier.INSTANT
        return Tier.FAST

    return Tier.SLOW
