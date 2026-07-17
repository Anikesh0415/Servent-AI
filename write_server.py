server_code = """import sys
import os
import threading
import time
import cv2
import math
import numpy as np
import pyautogui
import asyncio
import websockets
import json
import re

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.cv_module import HandTracker
from src.stt_module import SpeechRecognizer
from src.fsm_module import AIF_StateMachine, SystemState
from src.fusion_engine import FusionEngine
from src.llm_core import LocalLLMCore
from src.actuation_layer import ActuationLayer

class AIF_Server:
    def __init__(self):
        print("Initializing AIF Headless Server...")
        self.fsm = AIF_StateMachine()
        self.tracker = HandTracker()
        self.stt = SpeechRecognizer()
        self.fusion = FusionEngine()
        self.llm = LocalLLMCore(use_mock=False)
        self.actuator = ActuationLayer()
        
        self.latest_gesture_coords = None
        self.listening_thread = None
        self.is_listening_mode = False  # Boot in Standby mode
        self.is_tracking_mode = False   # Boot in Standby mode
        
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0  # CRITICAL: Fixes the massive 10 FPS lag cap
        self.screen_w, self.screen_h = pyautogui.size()
        self.prev_x, self.prev_y = 0, 0
        self.smoothing = 3  # Reduced smoothing for much faster, snappier cursor response
        self.is_pinching = False
        
        self.connected_clients = set()
        self.hand_data_for_ui = []
        
        # Start the background camera thread
        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.camera_thread.start()

        self.mode = "BOTH"
        self.is_dictating = False
        self.is_meeting = False
        self.dictation_thread = None
        
        # Start continuous STT worker
        self.stt_thread = threading.Thread(target=self._stt_worker, daemon=True)
        self.stt_thread.start()

    def _stt_worker(self):
        while True:
            if self.is_meeting:
                time.sleep(1)
                continue
                
            if self.fsm.state == SystemState.IDLE and self.mode in ["BOTH", "VOICE_ONLY"]:
                text = self.stt.listen()
                if text and not self.is_meeting:
                    if self.is_dictating:
                        print(f"Dictating: {text}")
                        self.actuator.execute_command({"action": "type", "target": text})
                    else:
                        self.fsm.current_context["voice_text"] = text
                        if "servent" in text.lower() or "servant" in text.lower():
                            print(f"Wake word detected! Intent: {text}")
                            self.fsm.transition(SystemState.PROCESSING_INTENT)
            time.sleep(0.1)

    def _camera_worker(self):
        \"\"\"Runs the camera completely invisibly in a background thread.\"\"\"
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Lower res for speed
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        while True:
            success, img = cap.read()
            if not success:
                continue
                
            img = cv2.flip(img, 1)
            h, w, _ = img.shape
            
            # Send to mediapipe async
            self.tracker.process_frame(img)
            
            # Extract coordinates for UI and Mouse Control
            lm_list = self.tracker.get_position(w, h, hand_no=0)
            self.hand_data_for_ui = lm_list
            
            if len(lm_list) != 0:
                # Extract palm center for stable movement
                px, py = lm_list[9][1], lm_list[9][2]
                self.latest_gesture_coords = (px, py)
                
                if not self.is_tracking_mode:
                    time.sleep(1/30)
                    continue
                
                # Mouse Tracking logic (Fixed bounds for high sensitivity)
                frame_rx, frame_ry = 220, 150 # Shrunk active zone
                screen_x = np.interp(px, (frame_rx, w - frame_rx), (0, self.screen_w))
                screen_y = np.interp(py, (frame_ry, h - frame_ry), (0, self.screen_h))
                
                # Cursor Movement
                curr_x = self.prev_x + (screen_x - self.prev_x) / self.smoothing
                curr_y = self.prev_y + (screen_y - self.prev_y) / self.smoothing
                
                # Robust Distance-Based Curl Detection
                hand_size = math.hypot(lm_list[9][1] - lm_list[0][1], lm_list[9][2] - lm_list[0][2])
                
                dist_index = math.hypot(lm_list[8][1] - lm_list[5][1], lm_list[8][2] - lm_list[5][2])
                dist_middle = math.hypot(lm_list[12][1] - lm_list[9][1], lm_list[12][2] - lm_list[9][2])
                dist_ring = math.hypot(lm_list[16][1] - lm_list[13][1], lm_list[16][2] - lm_list[13][2])
                
                # A finger is curled if its tip is close to its knuckle relative to hand size
                is_index_curled = dist_index < (hand_size * 0.6)
                is_middle_curled = dist_middle < (hand_size * 0.6)
                
                # Thumb curl (thumb tip close to index finger base)
                dist_thumb = math.hypot(lm_list[4][1] - lm_list[5][1], lm_list[4][2] - lm_list[5][2])
                is_thumb_curled = dist_thumb < (hand_size * 0.4)

                # Move cursor only if not scrolling
                is_scrolling = is_thumb_curled
                if not is_scrolling:
                    pyautogui.moveTo(curr_x, curr_y)
                else:
                    # If thumb is tucked, move hand up/down to scroll the page
                    dy = curr_y - self.prev_y
                    if abs(dy) > 1:
                        # hand moves up (dy < 0) -> scroll up (positive)
                        # hand moves down (dy > 0) -> scroll down (negative)
                        pyautogui.scroll(int(-dy * 5)) # Adjusted multiplier for perfect speed
                        
                self.prev_x, self.prev_y = curr_x, curr_y
                
                # Left Click (Index Curled ONLY)
                if is_index_curled and not is_middle_curled:
                    if not getattr(self, 'is_left_clicked', False):
                        pyautogui.click()
                        self.is_left_clicked = True
                else:
                    self.is_left_clicked = False

                # Right Click (Middle Curled ONLY)
                if is_middle_curled and not is_index_curled:
                    if not getattr(self, 'is_right_clicked', False):
                        pyautogui.click(button='right')
                        self.is_right_clicked = True
                else:
                    self.is_right_clicked = False
            else:
                self.latest_gesture_coords = None

            # Frame rate limit to prevent CPU hogging
            time.sleep(1/30)

    def _run_meeting(self):
        print("Starting meeting recording...")
        time.sleep(0.5)
        text = self.stt.listen(meeting_mode=True)
        print(f"Meeting ended. Transcribed {len(text)} chars. Summarizing...")
        
        if len(text) > 10:
            summary_prompt = f"The user wants a summary of a meeting. Generate a SINGLE action of type 'chat' where the 'target' is a detailed bulleted summary of this meeting transcription: {text}"
            summary_json = self.llm.process_intent(summary_prompt, {"system": "", "user_prompt": summary_prompt})
            
            summary_text = "Failed to summarize."
            if summary_json and isinstance(summary_json, list):
                for cmd in summary_json:
                    if cmd.get("action") == "chat":
                        summary_text = cmd.get("target", "")
                        
            self.fsm.current_context["reply_text"] = "MEETING SUMMARY:\\n" + summary_text
        else:
            self.fsm.current_context["reply_text"] = "Meeting was too short or no audio was detected."

    def process_state(self):
        if self.fsm.state == SystemState.IDLE:
            # Clear old context to prevent UI duplication bugs
            self.fsm.current_context["voice_text"] = ""
            self.fsm.current_context["autonomous_goal"] = ""
            pass
        elif self.fsm.state == SystemState.LISTENING:
            pass # Listening state is now handled continuously by _stt_worker

        elif self.fsm.state == SystemState.PROCESSING_INTENT:
            if getattr(self, 'intent_thread', None) is None or not self.intent_thread.is_alive():
                def _llm_worker():
                    context = self.fsm.get_context()
                    payload = self.fusion.fuse_context(
                        voice_text=context["voice_text"],
                        gesture_coords=context["gesture_coords"]
                    )
                    prompt = self.fusion.generate_llm_prompt(payload)
                    json_command = self.llm.process_intent(prompt, payload)
                    
                    self.fsm.current_context["json_command"] = json_command
                    self.fsm.transition(SystemState.EXECUTING)
                self.intent_thread = threading.Thread(target=_llm_worker, daemon=True)
                self.intent_thread.start()
            
        elif self.fsm.state == SystemState.EXECUTING:
            commands = self.fsm.get_context().get("json_command")
            reply_text = ""
            
            if commands and isinstance(commands, list):
                for cmd in commands:
                    action = cmd.get("action", "")
                    if action in ["speak", "chat"]:
                        reply_text += str(cmd.get("target", "")) + " "
                    else:
                        self.actuator.execute_command(cmd)
                        time.sleep(0.1)
                
                if reply_text:
                    self.fsm.current_context["reply_text"] = reply_text.strip()
                else:
                    self.fsm.current_context["reply_text"] = ""
                    
            self.fsm.transition(SystemState.IDLE)

    async def ws_handler(self, websocket):
        self.connected_clients.add(websocket)
        print("Web UI Connected!")
        try:
            while True:
                # Process AI state
                self.process_state()
                
                # Send data to UI
                context = self.fsm.get_context()
                
                action_text = "Standby"
                if self.fsm.state == SystemState.EXECUTING:
                    cmds = context.get("json_command", [])
                    if cmds and isinstance(cmds, list) and len(cmds) > 0:
                        first_cmd = cmds[0]
                        action_text = f"{first_cmd.get('action', '').upper()}: {first_cmd.get('target', '')}"
                elif self.fsm.state == SystemState.PROCESSING_INTENT:
                    action_text = "Analyzing intent..."
                
                data = {
                    "state": self.fsm.state.name,
                    "hand": [{"id": p[0], "x": p[1], "y": p[2], "z": p[3]} for p in self.hand_data_for_ui],
                    "voice_text": context.get("voice_text", ""),
                    "reply_text": context.get("reply_text", ""),
                    "action_text": action_text
                }
                await websocket.send(json.dumps(data))
                
                # Clear reply text after sending to prevent loops
                if context.get("reply_text"):
                    self.fsm.current_context["reply_text"] = ""
                    
                # Check for commands from UI
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    payload = json.loads(msg)
                    cmd = payload.get("command")
                    if cmd == "TOGGLE_DICTATION":
                        self.is_dictating = payload.get("state", False)
                        print(f"Dictation Mode: {self.is_dictating}")
                    elif cmd == "TOGGLE_MEETING":
                        self.is_meeting = payload.get("state", False)
                        print(f"Meeting Mode: {self.is_meeting}")
                        if self.is_meeting:
                            self.stt.is_recording = False # Interrupt normal STT
                            threading.Thread(target=self._run_meeting, daemon=True).start()
                        else:
                            self.stt.is_recording = False # Stop meeting STT
                    elif cmd == "SET_MODE":
                        mode = payload.get("mode")
                        self.mode = mode
                        if mode == "BOTH":
                            self.is_listening_mode = True
                            self.is_tracking_mode = True
                        elif mode == "CAMERA_ONLY":
                            self.is_listening_mode = False
                            self.is_tracking_mode = True
                        elif mode == "VOICE_ONLY":
                            self.is_listening_mode = True
                            self.is_tracking_mode = False
                        elif mode == "STANDBY":
                            self.is_listening_mode = False
                            self.is_tracking_mode = False
                        print(f"Ecosystem mode changed to: {mode}")
                    elif cmd == "TEXT_INPUT":
                        text_cmd = payload.get("text")
                        if text_cmd:
                            self.fsm.update_context(voice_text=text_cmd, gesture_coords=self.latest_gesture_coords)
                            self.fsm.transition(SystemState.PROCESSING_INTENT)
                except asyncio.TimeoutError:
                    pass
                    
                await asyncio.sleep(1/60) # 60 FPS UI update rate
        except websockets.exceptions.ConnectionClosed:
            print("Web UI Disconnected.")
        finally:
            self.connected_clients.remove(websocket)
            self.is_listening_mode = False
            self.is_tracking_mode = False
            if self.fsm.state == SystemState.LISTENING:
                self.fsm.transition(SystemState.IDLE)

    async def main_server(self):
        print("Starting WebSocket Server on ws://localhost:8765")
        async with websockets.serve(self.ws_handler, "localhost", 8765):
            await asyncio.Future()

    def start_server(self):
        asyncio.run(self.main_server())

if __name__ == '__main__':
    server = AIF_Server()
    server.start_server()
"""

with open("server.py", "w") as f:
    f.write(server_code)
print("Complete!")
