import sys
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
from src.agent_loop import execute_react_loop, plan_task, execute_task_plan
from src.action_library import type_action, key_action
from src.context_manager import ContextManager
from src.memory_manager import MemoryManager
from src.execution_manager import ExecutionManager
from src.security import SecurityManager
from src.logger import logger

class AIF_Server:
    def __init__(self):
        print("Initializing AIF Headless Server...")
        self.fsm = AIF_StateMachine()
        self.tracker = HandTracker()
        self.stt = SpeechRecognizer()
        self.fusion = FusionEngine()
        
        # Core Architectural Managers
        self.context_mgr = ContextManager()
        self.memory_mgr = MemoryManager()
        self.exec_mgr = ExecutionManager()
        self.security_mgr = SecurityManager(safe_mode=True)
        logger.info("AIF Server initialized with Context, Memory, Execution, and Security Managers.")
        
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
        
        self.chat_history_file = os.path.join(os.path.dirname(__file__), "chat_history.json")
        self.chat_history = self._load_history()

    def _load_history(self):
        if os.path.exists(self.chat_history_file):
            try:
                with open(self.chat_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def append_to_history(self, sender, text):
        if not text:
            return
        self.chat_history.append({"sender": sender, "text": text})
        # Keep only last 100 messages to prevent massive bloat
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]
        try:
            with open(self.chat_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def confirm_plan(self):
        """Triggers execution of the planned steps."""
        if self.fsm.state == SystemState.AWAITING_CONFIRMATION:
            self.fsm.transition(SystemState.EXECUTING)
            
            def _exec_worker():
                pending_plan = self.fsm.current_context.get("pending_plan", [])
                
                def update_ui(msg):
                    self.fsm.current_context["reply_text"] = msg
                    
                try:
                    execute_task_plan(pending_plan, update_callback=update_ui)
                except Exception as e:
                    update_ui(f"Error during execution: {e}")
                    
                time.sleep(1)
                self.fsm.transition(SystemState.IDLE)
                
            threading.Thread(target=_exec_worker, daemon=True).start()

    def reject_plan(self):
        """Rejects the planned steps and goes back to IDLE."""
        if self.fsm.state == SystemState.AWAITING_CONFIRMATION:
            self.fsm.current_context["reply_text"] = "Plan rejected by user. Resetting to standby."
            self.fsm.transition(SystemState.IDLE)

    def _stt_worker(self):
        while True:
            if self.is_meeting:
                time.sleep(1)
                continue
                
            if self.mode in ["BOTH", "VOICE_ONLY"] and not self.is_meeting:
                if self.fsm.state == SystemState.IDLE:
                    text = self.stt.listen()
                    if text and not self.is_meeting:
                        if self.is_dictating:
                            print(f"Dictating: {text}")
                            # Immediately type what is spoken and press enter
                            type_action(text)
                            time.sleep(0.1)
                            key_action('enter')
                        else:
                            self.fsm.current_context["voice_text"] = text
                            if "servent" in text.lower() or "servant" in text.lower():
                                print(f"Wake word detected! Intent: {text}")
                                self.fsm.transition(SystemState.PROCESSING_INTENT)
                elif self.fsm.state == SystemState.AWAITING_CONFIRMATION:
                    text = self.stt.listen()
                    if text:
                        text_lower = text.lower()
                        print(f"[Confirmation Phase] Heard: '{text}'")
                        if "yes" in text_lower or "confirm" in text_lower or "proceed" in text_lower or "go ahead" in text_lower:
                            print("Voice confirmation received! Executing plan...")
                            self.confirm_plan()
                        elif "no" in text_lower or "cancel" in text_lower or "reject" in text_lower:
                            print("Voice rejection received! Rejecting plan...")
                            self.reject_plan()
            time.sleep(0.1)

    def _camera_worker(self):
        """Runs the camera completely invisibly in a background thread."""
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
            import requests
            print("Requesting meeting summary from Ollama...")
            payload = {
                "model": "qwen2.5:1.5b",
                "prompt": f"Summarize the following meeting transcription in bullet points:\n\n{text}",
                "stream": False
            }
            try:
                res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
                summary_text = res.json().get("response", "Failed to summarize.")
            except Exception as e:
                summary_text = f"Error generating summary: {e}"
                        
            self.fsm.current_context["reply_text"] = "MEETING SUMMARY:\n" + summary_text
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
                def _react_worker():
                    context = self.fsm.get_context()
                    instruction = context.get("voice_text", "")
                    
                    def update_ui(msg):
                        # Use reply_text for logs to the UI
                        self.fsm.current_context["reply_text"] = msg

                    # --- Conversational Bypass ---
                    clean_text = instruction.strip().lower()
                    conversational_phrases = ["hi", "hello", "hey", "sup", "what's up", "how are you", "who are you", "thanks", "thank you"]
                    if clean_text in conversational_phrases:
                        update_ui(f"Hello! I am your AI assistant. How can I help you today?")
                        try:
                            import pyttsx3
                            engine = pyttsx3.init()
                            engine.say("Hello! I am your AI assistant.")
                            engine.runAndWait()
                        except Exception:
                            pass
                        self.fsm.transition(SystemState.IDLE)
                        return
                    # -----------------------------
                    
                    try:
                        # --- Smart Intent Router ---
                        settings = self.fsm.current_context.get("settings", {})
                        is_headless = settings.get("headlessMode", True) # Default to true for safety
                        
                        if is_headless and ("youtube" in instruction.lower() or "youtu.be" in instruction.lower()):
                            plan = [
                                {"action": "background_api_call", "target": "YouTube Transcript API"},
                                {"action": "background_llm_summarize", "target": "Hermes 8B Local"}
                            ]
                        else:
                            plan = plan_task(instruction, update_callback=update_ui)
                        # ---------------------------
                        if plan:
                            self.fsm.current_context["pending_plan"] = plan
                            steps_summary = "\n".join([f"- {s.get('action', '').replace('_', ' ').title()}: {s.get('name', s.get('url', s.get('text', s.get('keys', s.get('target', '')))))}" for s in plan])
                            update_ui(f"PROPOSED PLAN:\n{steps_summary}\n\nSay 'YES' / click Confirm to execute, or 'NO' to cancel.")
                            
                            # Announce confirmation via TTS
                            try:
                                import pyttsx3
                                engine = pyttsx3.init()
                                engine.say("I have generated a plan. Please check the dashboard and confirm to proceed.")
                                engine.runAndWait()
                            except Exception:
                                pass
                                
                            self.fsm.transition(SystemState.AWAITING_CONFIRMATION)
                        else:
                            update_ui("Failed to generate a plan.")
                            self.fsm.transition(SystemState.IDLE)
                    except Exception as e:
                        update_ui(f"Error: {e}")
                        self.fsm.transition(SystemState.IDLE)
                    
                self.intent_thread = threading.Thread(target=_react_worker, daemon=True)
                self.intent_thread.start()
            
        elif self.fsm.state == SystemState.EXECUTING:
            # ReAct loop is running in thread, updates are sent via callback
            pass

        elif self.fsm.state == SystemState.AWAITING_CONFIRMATION:
            pass

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
                elif self.fsm.state == SystemState.AWAITING_CONFIRMATION:
                    action_text = "Awaiting confirmation..."
                
                reply_text = context.get("reply_text", "")
                data = {
                    "state": self.fsm.state.name,
                    "hand": [{"id": p[0], "x": p[1], "y": p[2], "z": p[3]} for p in self.hand_data_for_ui],
                    "voice_text": context.get("voice_text", ""),
                    "reply_text": reply_text,
                    "action_text": action_text
                }
                await websocket.send(json.dumps(data))
                
                # Clear reply text after sending to prevent loops
                if reply_text:
                    self.append_to_history("SYSTEM", reply_text)
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
                    elif cmd == "CONFIRM_PLAN":
                        print("UI confirmation received!")
                        self.confirm_plan()
                    elif cmd == "REJECT_PLAN":
                        print("UI rejection received!")
                        self.reject_plan()
                    elif cmd == "SELECT_FOLDER":
                        import tkinter as tk
                        from tkinter import filedialog
                        root = tk.Tk()
                        root.attributes('-topmost', True)
                        root.withdraw()
                        folder_path = filedialog.askdirectory()
                        root.destroy()
                        if folder_path:
                            # Normalize path for JSON/Websocket
                            folder_path = folder_path.replace("/", "\\")
                            await websocket.send(json.dumps({"type": "FOLDER_SELECTED", "path": folder_path}))
                    elif cmd == "IMAGE_UPLOAD":
                        img_data = payload.get("image")
                        if img_data:
                            import base64
                            import os
                            try:
                                img_bytes = base64.b64decode(img_data.split(',')[1])
                                img_path = os.path.abspath("uploaded_image.png")
                                with open(img_path, "wb") as f:
                                    f.write(img_bytes)
                                self.fsm.current_context["uploaded_image"] = img_path
                                print(f"Image uploaded and saved to {img_path}")
                            except Exception as e:
                                print(f"Failed to process image: {e}")
                    elif cmd == "TEXT_INPUT":
                        if self.fsm.state != SystemState.IDLE:
                            print('Ignoring TEXT_INPUT: system is busy')
                        else:
                            text_cmd = payload.get("text")
                            if text_cmd:
                                img_path = self.fsm.current_context.get("uploaded_image")
                                if img_path:
                                    text_cmd = f"[IMAGE_ATTACHED: {img_path}] " + text_cmd
                                
                                # Log user input to history
                                display_text = payload.get("text") # Log clean text
                                self.append_to_history("USER", display_text)

                                self.fsm.current_context["voice_text"] = text_cmd
                                self.fsm.current_context["reply_text"] = ""
                                self.fsm.transition(SystemState.PROCESSING_INTENT)
                                self.process_state()
                                
                    elif cmd == "GET_HISTORY":
                        await websocket.send(json.dumps({
                            "type": "CHAT_HISTORY",
                            "history": self.chat_history
                        }))
                    elif cmd == "UPDATE_SETTINGS":
                        self.fsm.current_context["settings"] = payload.get("settings", {})
                        print(f"Settings updated: {self.fsm.current_context['settings']}")
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
        print("Starting WebSocket Server on ws://0.0.0.0:8765 (Available on Local Network)")
        async with websockets.serve(self.ws_handler, "0.0.0.0", 8765):
            await asyncio.Future()

    def start_server(self):
        asyncio.run(self.main_server())

if __name__ == '__main__':
    server = AIF_Server()
    server.start_server()
