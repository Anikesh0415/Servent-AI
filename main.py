import sys
import os
import threading
import time
import cv2
import math
import numpy as np
import pyautogui

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.cv_module import HandTracker
from src.stt_module import SpeechRecognizer
from src.fsm_module import AIF_StateMachine, SystemState
from src.fusion_engine import FusionEngine
from src.llm_core import LocalLLMCore
from src.actuation_layer import ActuationLayer

class AIF_System:
    def __init__(self):
        print("Initializing Action Intelligence Framework (AIF)...")
        self.fsm = AIF_StateMachine()
        self.tracker = HandTracker()
        self.stt = SpeechRecognizer(model_size="tiny.en")
        self.fusion = FusionEngine()
        self.llm = LocalLLMCore(use_mock=True)
        self.actuator = ActuationLayer()
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self.latest_gesture_coords = None
        self.listening_thread = None
        
        # Disable pyautogui failsafe for this specific experimental build 
        # (Allows mouse to hit screen corners without throwing exception)
        pyautogui.FAILSAFE = False
        
        # Screen dimensions
        self.screen_w, self.screen_h = pyautogui.size()
        
        # Smoothing variables for mouse
        self.prev_x, self.prev_y = 0, 0
        self.smoothing = 5
        
        # Pinch state to avoid multiple rapid clicks
        self.is_pinching = False

    def run(self):
        """Main system loop. OpenCV GUI MUST run in the main thread."""
        print("\n" + "="*50)
        print("AIF System V2.0 Ready.")
        print("- Move your index finger to control the mouse cursor.")
        print("- Pinch your thumb and index finger together to click.")
        print("- Press 's' in the camera window to start voice command listening.")
        print("- Press 'q' in the camera window to exit.")
        print("="*50 + "\n")
        
        p_time = 0
        
        try:
            while True:
                success, img = self.cap.read()
                if success:
                    img = cv2.flip(img, 1)
                    
                    c_time = time.time()
                    fps = 1 / (c_time - p_time) if (c_time - p_time) > 0 else 0
                    p_time = c_time
                    
                    # draw_hands now applies the Sci-Fi HUD and 3D sphere
                    img = self.tracker.find_hands(img, state_name=self.fsm.state.name, fps=int(fps))
                    lm_list = self.tracker.get_position(img)
                    
                    if len(lm_list) != 0:
                        # Index Finger Tip = 8, Thumb Tip = 4
                        x1, y1 = lm_list[8][1], lm_list[8][2]
                        x2, y2 = lm_list[4][1], lm_list[4][2]
                        
                        self.latest_gesture_coords = (x1, y1)
                        
                        # 1. Mouse Movement Logic
                        # Increase frame reduction to create a smaller, highly sensitive active tracking area
                        # so the user doesn't have to stretch their hand out of the camera's field of view.
                        frame_rx = 300 
                        frame_ry = 200
                        h, w, _ = img.shape
                        cv2.rectangle(img, (frame_rx, frame_ry), (w - frame_rx, h - frame_ry), (0, 100, 255), 1)
                        cv2.putText(img, "ACTIVE TRACKING ZONE", (frame_rx, frame_ry - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 255), 1)
                        
                        # Interpolate coordinates
                        screen_x = np.interp(x1, (frame_rx, w - frame_rx), (0, self.screen_w))
                        screen_y = np.interp(y1, (frame_ry, h - frame_ry), (0, self.screen_h))
                        
                        # Smooth mouse movement
                        curr_x = self.prev_x + (screen_x - self.prev_x) / self.smoothing
                        curr_y = self.prev_y + (screen_y - self.prev_y) / self.smoothing
                        
                        # Move the actual OS mouse
                        pyautogui.moveTo(curr_x, curr_y)
                        self.prev_x, self.prev_y = curr_x, curr_y
                        
                        # 2. Pinch to Click Logic
                        length = math.hypot(x2 - x1, y2 - y1)
                        if length < 40:
                            # Highlight pinch
                            cv2.circle(img, (x1, y1), 15, (0, 0, 255), cv2.FILLED)
                            cv2.putText(img, "CLICK DETECTED", (x1+20, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            
                            if not self.is_pinching:
                                pyautogui.click()
                                self.is_pinching = True
                        else:
                            self.is_pinching = False
                            
                    else:
                        self.latest_gesture_coords = None

                    cv2.imshow("AIF Vision", img)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s') and self.fsm.state == SystemState.IDLE:
                    print("\n[Trigger] Start listening...")
                    self.fsm.transition(SystemState.LISTENING)

                self.process_state()

        except KeyboardInterrupt:
            print("\nShutting down AIF...")
        finally:
            self.cap.release()
            cv2.destroyAllWindows()

    def process_state(self):
        """Handles non-GUI state logic."""
        if self.fsm.state == SystemState.LISTENING:
            if self.listening_thread is None or not self.listening_thread.is_alive():
                self.listening_thread = threading.Thread(target=self._listen_worker, daemon=True)
                self.listening_thread.start()

        elif self.fsm.state == SystemState.PROCESSING_INTENT:
            print("[PROCESSING] Fusing data and querying LLM...")
            context = self.fsm.get_context()
            
            payload = self.fusion.fuse_context(
                voice_text=context["voice_text"],
                gesture_coords=context["gesture_coords"]
            )
            
            prompt = self.fusion.generate_llm_prompt(payload)
            json_command = self.llm.process_intent(prompt, payload)
            
            print(f"[LLM Decision]: {json_command}")
            self.fsm.current_context["json_command"] = json_command
            self.fsm.transition(SystemState.EXECUTING)
            
        elif self.fsm.state == SystemState.EXECUTING:
            command = self.fsm.get_context().get("json_command")
            if command:
                self.actuator.execute_command(command)
                
            self.fsm.reset_context()
            self.fsm.transition(SystemState.IDLE)

    def _listen_worker(self):
        """Background worker for capturing audio."""
        start_coords = self.latest_gesture_coords
        voice_command = self.stt.listen(duration=4)
        print(f"\n[Heard]: {voice_command}")
        
        if voice_command:
            self.fsm.update_context(
                voice_text=voice_command, 
                gesture_coords=start_coords
            )
            self.fsm.transition(SystemState.PROCESSING_INTENT)
        else:
            print("[No voice detected, returning to IDLE]")
            self.fsm.transition(SystemState.IDLE)

if __name__ == "__main__":
    system = AIF_System()
    system.run()
