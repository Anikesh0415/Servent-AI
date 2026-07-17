import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import queue
import time

class SpeechRecognizer:
    def __init__(self, model_size="small.en", device="cpu", compute_type="default"):
        print(f"Loading CPU-Optimized Whisper model '{model_size}'...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("Whisper model loaded.")
        
        device_info = sd.query_devices(sd.default.device[0])
        self.native_sr = int(device_info['default_samplerate'])
        self.target_sr = 16000
        
        self.audio_queue = queue.Queue()
        self.is_recording = False
        
    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_queue.put(indata.copy())
            
    def listen(self, duration=None, meeting_mode=False):
        """
        Continuously listens until a sentence is completed (detects 1.5s of silence).
        If meeting_mode is True, it listens indefinitely until self.is_recording = False.
        """
        print(f"Listening (Streaming Mode, Meeting={meeting_mode})... Speak now!")
        self.audio_queue.queue.clear()
        self.is_recording = True
        
        audio_chunks = []
        silence_frames = 0
        speech_started = False
        
        # We process in chunks of 0.25 seconds
        chunk_duration = 0.25
        chunk_frames = int(self.native_sr * chunk_duration)
        silence_threshold = 0.05  # Amplitude threshold
        max_silence = 6  # 6 * 0.25 = 1.5 seconds of silence to stop recording
        
        try:
            with sd.InputStream(samplerate=self.native_sr, channels=1, dtype='float32', callback=self._audio_callback):
                while self.is_recording:
                    # Collect enough audio for one chunk
                    current_chunk = []
                    collected_frames = 0
                    while collected_frames < chunk_frames and self.is_recording:
                        try:
                            data = self.audio_queue.get(timeout=0.1)
                            current_chunk.append(data)
                            collected_frames += len(data)
                        except queue.Empty:
                            pass
                            
                    if not current_chunk:
                        continue
                        
                    chunk_np = np.concatenate(current_chunk).flatten()
                    audio_chunks.append(chunk_np)
                    
                    # Energy check
                    max_amp = np.max(np.abs(chunk_np))
                    if max_amp > silence_threshold:
                        speech_started = True
                        silence_frames = 0
                    else:
                        if speech_started:
                            silence_frames += 1
                            if not meeting_mode and silence_frames >= max_silence:
                                break
                                
                    # Timeout fallback if they just leave it on for 30 seconds (only in non-meeting mode)
                    if not meeting_mode and len(audio_chunks) > int(30 / chunk_duration):
                        break
                        
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            self.is_recording = False
            
        if not audio_chunks:
            return ""
            
        full_audio = np.concatenate(audio_chunks)
        
        # If the audio is completely silent or extremely short, ignore it
        if not speech_started or len(full_audio) < self.native_sr * 0.5:
            return ""
            
        # Manually resample to 16kHz for Whisper
        if self.native_sr != self.target_sr:
            original_times = np.arange(len(full_audio))
            target_times = np.linspace(0, len(full_audio) - 1, int(len(full_audio) * self.target_sr / self.native_sr))
            full_audio = np.interp(target_times, original_times, full_audio).astype(np.float32)
            
        print("Transcribing...")
        segments, info = self.model.transcribe(
            full_audio, 
            beam_size=5, 
            vad_filter=True, 
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False
        )
        text = ""
        for segment in segments:
            text += segment.text + " "
            
        return text.strip()

# For testing standalone
def main():
    recognizer = SpeechRecognizer(model_size="large-v3-turbo", device="cpu", compute_type="int8")
    while True:
        print("\nReady.")
        input("Press Enter to start streaming (auto-stops when you stop speaking)...")
        text = recognizer.listen()
        print(f"\n[You said]: {text}")
        print("-" * 40)

if __name__ == "__main__":
    main()
