import threading
import pyttsx3
from src.logger import logger


class TTSManager:
    """Asynchronous Text-to-Speech Manager to prevent execution blocking."""

    def __init__(self):
        self._lock = threading.Lock()

    def _speak_worker(self, text: str):
        with self._lock:
            try:
                engine = pyttsx3.init()
                rate = engine.getProperty("rate")
                engine.setProperty("rate", rate - 20)  # slightly slower for clarity

                # Force English voice selection
                voices = engine.getProperty("voices")
                for voice in voices:
                    v_name = voice.name.lower()
                    v_id = voice.id.lower()
                    if "en" in v_id or "english" in v_name or "david" in v_name or "zira" in v_name:
                        engine.setProperty("voice", voice.id)
                        break

                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS Engine failed: {e}")

    def speak_async(self, text: str):
        """Spawns a daemon thread to speak text immediately without blocking."""
        if not text:
            return
        logger.info(f"[TTS] Speaking: '{text}'")
        thread = threading.Thread(target=self._speak_worker, args=(text,), daemon=True)
        thread.start()


tts_manager = TTSManager()
