import os
from src.llm_core import LocalLLMCore

llm = LocalLLMCore(use_mock=False)
prompt = "open gemini,and give it a prompt asking to generate a letter for balram asking how he is from anikesh. wait for result to be generated copy the letter and open whatsapp paste it into chat and sending him"
payload = {"voice_command": prompt, "gesture_context": {}}

print(f"Testing Prompt: {prompt}")
result = llm.process_intent("", payload)
print(f"Result: {result}")
