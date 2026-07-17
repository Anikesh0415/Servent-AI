import re

with open('server.py', 'r') as f:
    code = f.read()

# Fix Chunk 1: The broken __init__ insertion inside process_state
bad_chunk_1 = """        self.mode = "BOTH"  # BOTH, CAMERA_ONLY, VOICE_ONLY, STANDBY
        self.is_dictating = False
        self.is_meeting = False
        self.stt_thread = threading.Thread(target=self._stt_worker, daemon=True)
                self.intent_thread.start()"""

good_chunk_1 = """                self.intent_thread = threading.Thread(target=_llm_worker, daemon=True)
                self.intent_thread.start()"""

code = code.replace(bad_chunk_1, good_chunk_1)

# Fix Chunk 2: The broken ws_handler
bad_chunk_2 = re.search(r'                    else:\n          while True:.*?time\.sleep\(0\.1\)f ws_handler\(self, websocket\):', code, flags=re.DOTALL)
if bad_chunk_2:
    good_chunk_2 = """                    else:
                        self.actuator.execute_command(cmd)
                        time.sleep(0.1)
                
                if reply_text:
                    self.fsm.current_context["reply_text"] = reply_text.strip()
                else:
                    self.fsm.current_context["reply_text"] = ""
                    
            self.fsm.transition(SystemState.IDLE)

    async def ws_handler(self, websocket):"""
    code = code[:bad_chunk_2.start()] + good_chunk_2 + code[bad_chunk_2.end():]

# Fix Chunk 3: Add the missing vars in __init__
bad_chunk_3 = """        # Start the background camera thread
        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.camera_thread.start()"""

good_chunk_3 = """        # Start the background camera thread
        self.camera_thread = threading.Thread(target=self._camera_worker, daemon=True)
        self.camera_thread.start()

        self.mode = "BOTH"
        self.is_dictating = False
        self.is_meeting = False
        self.dictation_thread = None"""

code = code.replace(bad_chunk_3, good_chunk_3)

with open('server.py', 'w') as f:
    f.write(code)

print('server.py fixed successfully')
