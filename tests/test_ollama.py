import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from src.llm_core import LocalLLMCore

core = LocalLLMCore()
payload = {
    "voice_command": "open gemini and give it a prompt asking how to code than wait for result for generate and than copy the result,after that open whatsapp and search for friends forever and paste the msg and atlast send the msg",
    "gesture_context": {}
}

prompt = f"""
You are the Action Intelligence Framework, a local OS agent and conversational assistant.
Convert the user's voice command into a JSON array of actions.
Possible actions: "open", "close", "type", "search", "click", "speak", "hotkey", "wait", "unknown".
For "type", put the text to type in the "target" field.
For "hotkey", put the keys in the "target" field (e.g., "ctrl+f", "ctrl+c", "ctrl+v", "enter").
For "wait", put the number of seconds in the "target" field (e.g., "2", "5").
If you need to copy or paste, use the "hotkey" action with "ctrl+c" or "ctrl+v".
If the user asks a general knowledge question (e.g. "how to code"), answer the question natively and put your verbal response in the "target" field of a "speak" action.
If the user asks to search the web or search youtube, use the "search" action. 
To send a message in a desktop app like WhatsApp, you must chain commands: open the app, wait 2 seconds, use hotkey 'ctrl+f' to search, type the contact name, wait 1 second, use hotkey 'enter', type the message.

User says: "{payload['voice_command']}"
"""

print("Sending to Ollama...")
result = core._fallback_to_ollama(prompt, payload)
print("Result:")
print(json.dumps(result, indent=2))
