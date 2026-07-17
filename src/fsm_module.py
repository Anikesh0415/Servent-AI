from enum import Enum
import time

class SystemState(Enum):
    IDLE = 1
    LISTENING = 2
    PROCESSING_INTENT = 3
    EXECUTING = 4
    AUTONOMOUS_VISION = 5
    ERROR = 6

class AIF_StateMachine:
    def __init__(self):
        self.state = SystemState.IDLE
        self.current_context = {
            "voice_text": "",
            "gesture_coords": None,
            "gesture_type": None
        }
        
    def transition(self, new_state):
        print(f"[FSM] Transitioning: {self.state.name} -> {new_state.name}")
        self.state = new_state
        
    def reset_context(self):
        self.current_context = {
            "voice_text": "",
            "gesture_coords": None,
            "gesture_type": None
        }

    def update_context(self, voice_text=None, gesture_coords=None, gesture_type=None):
        if voice_text is not None:
            self.current_context["voice_text"] = voice_text
        if gesture_coords is not None:
            self.current_context["gesture_coords"] = gesture_coords
        if gesture_type is not None:
            self.current_context["gesture_type"] = gesture_type

    def get_context(self):
        return self.current_context

# Basic test
if __name__ == "__main__":
    fsm = AIF_StateMachine()
    fsm.transition(SystemState.LISTENING)
    fsm.update_context(voice_text="open file", gesture_coords=(500, 300))
    print(f"Context: {fsm.get_context()}")
    fsm.transition(SystemState.PROCESSING_INTENT)
    fsm.transition(SystemState.EXECUTING)
    fsm.transition(SystemState.IDLE)
    fsm.reset_context()
