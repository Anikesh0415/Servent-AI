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
from src.event_bus import event_bus
from src.utils.migrate_memory import migrate_skills
from src.config import WAKE_WORDS, NOISE_GATE_THRESHOLD
from src.tts_module import tts_manager

class AIF_Server:
    def __init__(self):
        print("Initializing AIF Headless Server...")
        migrate_skills()
        self.fsm = AIF_StateMachine()
        self.tracker = HandTracker()
        self.stt = SpeechRecognizer(noise_threshold=NOISE_GATE_THRESHOLD)
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
        
        # Dwell-Clicking state
        self.dwell_start_time = None
        self.dwell_threshold = 0.6  # 600ms default
        self.last_dwell_x = 0
        self.last_dwell_y = 0
        
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

        event_bus.subscribe("update_noise_gate", self.on_noise_gate_update)
        
    def on_noise_gate_update(self, threshold: float):
        self.stt.noise_threshold = threshold
        logger.info(f"Noise gate updated to {threshold}")

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
            
        import asyncio
        if hasattr(self, 'connected_clients') and self.connected_clients:
            msg = json.dumps({"type": "CHAT_HISTORY", "history": self.chat_history})
            for client in list(self.connected_clients):
                try:
                    if hasattr(self, 'loop') and self.loop:
                        asyncio.run_coroutine_threadsafe(client.send(msg), self.loop)
                except Exception as e:
                    print(f"WS push error: {e}")

    def confirm_plan(self):
        """Triggers execution of the planned steps."""
        if self.fsm.state == SystemState.AWAITING_CONFIRMATION:
            self.fsm.transition(SystemState.EXECUTING)
            
            async def _exec_worker():
                pending_plan = self.fsm.current_context.get("pending_plan", [])
                
                def update_ui(msg):
                    if msg.startswith("__INJECT__:"):
                        self.fsm.current_context["inject_html"] = msg.replace("__INJECT__:", "")
                    else:
                        self.fsm.current_context["reply_text"] = msg
                    
                try:
                    await execute_task_plan(pending_plan, update_callback=update_ui)
                except Exception as e:
                    update_ui(f"Error during execution: {e}")
                    
                import asyncio
                await asyncio.sleep(1)
                self.fsm.transition(SystemState.IDLE)
                
            import asyncio
            asyncio.create_task(_exec_worker())

    def _toggle_site_blocking(self, block: bool):
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        blocked_sites = ["www.youtube.com", "youtube.com", "www.twitter.com", "twitter.com", "www.reddit.com", "reddit.com", "www.facebook.com", "facebook.com"]
        redirect_ip = "127.0.0.1"
        
        try:
            with open(hosts_path, 'r') as f:
                lines = f.readlines()
                
            if block:
                # Add blocks if not present
                with open(hosts_path, 'a') as f:
                    for site in blocked_sites:
                        if not any(site in line for line in lines):
                            f.write(f"{redirect_ip} {site}\n")
                print("Focus Mode: Distracting sites blocked in hosts file.")
            else:
                # Remove blocks
                with open(hosts_path, 'w') as f:
                    for line in lines:
                        if not any(site in line for site in blocked_sites) or line.strip() == "":
                            f.write(line)
                print("Focus Mode: Distracting sites unblocked.")
        except PermissionError:
            print("[Warning] Could not modify hosts file. Please run the server as Administrator for OS-level distraction blocking.")
        except Exception as e:
            print(f"Error toggling site blocking: {e}")

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
                            if any(ww.lower() in text.lower() for ww in WAKE_WORDS):
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
                time.sleep(1) # Prevent CPU spinning if camera is unavailable
                continue
                
            img = cv2.flip(img, 1)
            h, w, _ = img.shape
            
            # Send to mediapipe async
            self.tracker.process_frame(img)
            
            # Extract coordinates for UI and Mouse Control
            lm_list, is_pinching, is_fist, is_peace_sign = self.tracker.get_position(w, h, hand_no=0)
            
            if is_peace_sign:
                if not getattr(self, 'peace_triggered', False):
                    self.peace_triggered = True
                    print("Peace sign detected! Triggering Vision capture...")
                    
                    # Capture the current frame and save to a temporary file in the ui folder
                    cv2.imwrite(r"ui\vision_capture.jpg", img)
                    
                    # Queue a task to process the vision capture
                    self.fsm.current_context["pending_plan"] = [
                        {
                            "action": "background_vision_capture",
                            "target": "vision_capture.jpg"
                        }
                    ]
                    
                    import asyncio
                    def _start_vision_worker():
                        self.fsm.transition(SystemState.EXECUTING)
                        asyncio.run(self.exec_mgr.execute_step(self.fsm.current_context["pending_plan"][0]))
                        self.fsm.transition(SystemState.IDLE)
                        
                    threading.Thread(target=_start_vision_worker, daemon=True).start()
                    time.sleep(2) # Cooldown
            else:
                self.peace_triggered = False
            
            # --- CLUTCH MECHANISM ---
            if is_fist:
                if not hasattr(self, 'fist_start_time') or self.fist_start_time is None:
                    self.fist_start_time = time.time()
                elif (time.time() - self.fist_start_time) > 0.8: # 800ms threshold
                    self.clutch_engaged = not getattr(self, 'clutch_engaged', False)
                    self.fist_start_time = None
                    event_bus.publish("clutch_status", self.clutch_engaged)
                    time.sleep(1.0) # Cooldown
            else:
                self.fist_start_time = None
                
            if getattr(self, 'clutch_engaged', False):
                self.hand_data_for_ui = lm_list
                time.sleep(1/30)
                continue
            # ------------------------
            
            self.hand_data_for_ui = lm_list
            
            if len(lm_list) != 0:
                event_bus.publish("vision_telemetry", True)
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
                    
                    # Dwell-Click Logic (Bypass Pinch requirement)
                    dist = math.hypot(curr_x - self.last_dwell_x, curr_y - self.last_dwell_y)
                    if dist < 15: # Cursor is hovering still
                        if self.dwell_start_time is None:
                            self.dwell_start_time = time.time()
                        elif (time.time() - self.dwell_start_time) >= self.dwell_threshold:
                            if not getattr(self, 'is_dwell_clicked', False):
                                pyautogui.click()
                                self.is_dwell_clicked = True
                                # Reset dwell after click to prevent spamming
                                self.dwell_start_time = None 
                    else:
                        self.dwell_start_time = None
                        self.is_dwell_clicked = False
                        self.last_dwell_x = curr_x
                        self.last_dwell_y = curr_y
                        
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
                event_bus.publish("vision_telemetry", False)
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
            if getattr(self, 'intent_task', None) is None or self.intent_task.done():
                async def _react_worker():
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
                            tts_manager.speak_async("Hello! I am your AI assistant.")
                        except Exception:
                            pass
                        self.fsm.transition(SystemState.IDLE)
                        return
                    # -----------------------------
                    
                    try:
                        # --- Smart Intent Router ---
                        settings = self.fsm.current_context.get("settings", {})
                        
                        if clean_text in ["generate-flashcard", "generate-snippet", "generate-handwritten", "generate-mindmap"]:
                            # Fetch recent context for the LLM
                            recent_context = self.fsm.current_context.get("reply_text", "")
                            plan = [
                                {
                                    "action": "generate_ui_component", 
                                    "target": clean_text,
                                    "context": recent_context
                                }
                            ]
                        elif clean_text in ["format-project", "run-tests", "build-prod", "start-server", "review-code"]:
                            # Map developer macros to terminal commands
                            cmd_map = {
                                "format-project": "npx prettier --write .",
                                "run-tests": "npm run test",
                                "build-prod": "npm run build",
                                "start-server": "npm run dev",
                                "review-code": "git diff"
                            }
                            plan = [
                                {
                                    "action": "run_terminal",
                                    "command": cmd_map.get(clean_text, "echo 'Unknown command'"),
                                    "cwd": self.fsm.current_context.get("settings", {}).get("devFolder", "E:\\AIF_Project\\ui")
                                }
                            ]
                        else:
                            plan = await plan_task(instruction, update_callback=update_ui)
                        # ---------------------------
                        if plan:
                            self.fsm.current_context["pending_plan"] = plan
                            steps_strs = []
                            for i, s in enumerate(plan):
                                action = s.get('action', '').replace('_', ' ').title()
                                target = s.get('target', s.get('name', s.get('url', s.get('text', s.get('keys', '')))))
                                desc = f"- {action}: {target}"
                                if s.get('action') == "send_whatsapp":
                                    desc += f"\n   (Macro: Opens Native WhatsApp Desktop -> Wait 2s -> Ctrl+F '{s.get('contact', '')}' -> Type '{s.get('message', '')}' -> Enter)"
                                steps_strs.append(desc)
                            steps_summary = "\n".join(steps_strs)
                            update_ui(f"PROPOSED PLAN:\n{steps_summary}\n\nSay 'YES' / click Confirm to execute, or 'NO' to cancel.")
                            
                            # Announce confirmation via TTS
                            try:
                                tts_manager.speak_async("I have generated a plan. Please check the dashboard and confirm to proceed.")
                            except Exception:
                                pass
                                
                            self.fsm.transition(SystemState.AWAITING_CONFIRMATION)
                        else:
                            update_ui("Failed to generate a plan.")
                            self.fsm.transition(SystemState.IDLE)
                    except Exception as e:
                        update_ui(f"Error: {e}")
                        self.fsm.transition(SystemState.IDLE)
                    
                import asyncio
                self.intent_task = asyncio.create_task(_react_worker())
            
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
                
                inject_html = context.get("inject_html", "")
                if inject_html:
                    await websocket.send(json.dumps({"type": "INJECT_UI", "html": inject_html}))
                    self.fsm.current_context["inject_html"] = ""
                
                # Clear reply text after sending to prevent loops
                if reply_text:
                    self.append_to_history("SYSTEM", reply_text)
                    self.fsm.current_context["reply_text"] = ""
                    await websocket.send(json.dumps({"type": "CHAT_HISTORY", "history": self.chat_history}))
                    
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
                        
                        if hasattr(self, 'exec_mgr') and hasattr(self.exec_mgr, 'headless_executor'):
                            self.exec_mgr.headless_executor.llm_core.swap_model(mode)
                            
                        print(f"Ecosystem mode changed to: {mode}")
                    elif cmd == "CONFIRM_PLAN":
                        print("UI confirmation received!")
                        self.confirm_plan()
                    elif cmd == "REJECT_PLAN":
                        print("UI rejection received!")
                        self.reject_plan()
                    elif cmd == "BLOCK_SITES":
                        self._toggle_site_blocking(True)
                    elif cmd == "UNBLOCK_SITES":
                        self._toggle_site_blocking(False)
                    elif cmd == "CLEAR_HISTORY":
                        self.fsm.current_context["history"] = []
                        self.fsm.current_context["voice_text"] = ""
                        self.fsm.current_context["reply_text"] = ""
                        self.fsm.current_context["pending_plan"] = []
                        self.fsm.state = SystemState.IDLE
                        self.chat_history = []
                        try:
                            with open(self.chat_history_file, 'w', encoding='utf-8') as f:
                                json.dump([], f)
                        except Exception as e:
                            print(f"Failed to clear history file: {e}")
                            
                        if hasattr(self, 'connected_clients') and self.connected_clients:
                            msg = json.dumps({"type": "CHAT_HISTORY", "history": self.chat_history})
                            for client in list(self.connected_clients):
                                try:
                                    asyncio.create_task(client.send(msg))
                                except Exception:
                                    pass
                        print("Chat history cleared by UI.")
                    elif cmd == "ABORT_EXECUTION":
                        print("KILL-SWITCH ACTIVATED via UI!")
                        self.memory_mgr.abort_flag = True
                        self.fsm.current_context["reply_text"] = "🛑 TASK ABORTED BY KILL-SWITCH!"
                        if self.fsm.state == SystemState.EXECUTING:
                            self.fsm.transition(SystemState.IDLE)
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
                        text_cmd = payload.get("text")
                        if text_cmd:
                            # Reset system state if stuck
                            if self.fsm.state != SystemState.IDLE:
                                self.fsm.transition(SystemState.IDLE)
                                
                            img_path = self.fsm.current_context.get("uploaded_image")
                            if img_path:
                                text_cmd = f"[IMAGE_ATTACHED: {img_path}] " + text_cmd
                            
                            # Log user input to history
                            display_text = payload.get("text")
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
        import asyncio
        self.loop = asyncio.get_running_loop()
        print("Starting WebSocket Server on ws://0.0.0.0:8765 (Available on Local Network)")
        async with websockets.serve(self.ws_handler, "0.0.0.0", 8765):
            await asyncio.Future()

    def start_server(self):
        # Run WebSocket server in a background thread
        ws_thread = threading.Thread(target=lambda: asyncio.run(self.main_server()), daemon=True)
        ws_thread.start()
        
        # Launch HUD in the main thread if available
        try:
            from src.hud import launch_hud
            from src.fsm_module import SystemState
            
            def kill_callback():
                self.memory_mgr.abort_flag = True
                self.fsm.current_context["reply_text"] = "🛑 TASK ABORTED BY KILL-SWITCH!"
                if self.fsm.state == SystemState.EXECUTING:
                    self.fsm.transition(SystemState.IDLE)
                    
            launch_hud(killswitch_cb=kill_callback)
        except Exception as e:
            print(f"[HUD] HUD GUI closed or not supported ({e}). Running in background mode.")

        # CRITICAL: Keep main thread alive so closing HUD window NEVER terminates the backend!
        print("[AIF Server] Backend active & listening on ws://0.0.0.0:8765. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("[AIF Server] Shutting down.")

if __name__ == '__main__':
    server = AIF_Server()
    server.start_server()
