import json
import requests
import re

OLLAMA_API_URL = "http://localhost:11434/api/generate"
PLANNER_MODEL = "qwen2.5:1.5b" # ARIA Model

# The system prompt enforces the schema for the planner
PLANNER_SYSTEM_PROMPT = """You are ARIA, the Master Planner agent for a desktop automation system.
Your job is to break down the user's high-level request into a JSON array of atomic UI actions.

AVAILABLE ACTIONS:
- "open_app": {"action": "open_app", "app": "<name>"}
- "type": {"action": "type", "text": "<text>"}
- "key": {"action": "key", "key": "<key_name>"}
- "click": {"action": "click", "x": <int>, "y": <int>}
- "scroll": {"action": "scroll", "amount": <int>}

RULES:
1. Output ONLY a valid JSON array of action objects.
2. NO markdown formatting, NO conversational text, NO explanation.
3. Keep steps logical and sequential.
4. IMPORTANT: When the user asks you to search for something, generate text, or submit a prompt, you MUST output a "type" action followed IMMEDIATELY by a {"action": "key", "key": "enter"} action to submit it.

EXAMPLE INPUT: "Search for cute cats on youtube"
EXAMPLE OUTPUT:
[
  {"action": "open_app", "app": "youtube"},
  {"action": "type", "text": "cute cats"},
  {"action": "key", "key": "enter"}
]

EXAMPLE INPUT: "generate letter to balram asking how he is"
EXAMPLE OUTPUT:
[
  {"action": "type", "text": "generate letter to balram asking how he is"},
  {"action": "key", "key": "enter"}
]
"""

# JSON Schema for Ollama constrained decoding
PLANNER_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open_app", "type", "key", "click", "scroll"]
            },
            "app": {"type": "string"},
            "text": {"type": "string"},
            "key": {"type": "string"},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "amount": {"type": "integer"}
        },
        "required": ["action"]
    }
}

def generate_plan(instruction: str) -> list:
    """Generates a plan of actions using the ARIA model."""
    prompt = f"User Request: {instruction}\nGenerate the JSON action plan."
    
    payload = {
        "model": PLANNER_MODEL,
        "system": PLANNER_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": PLANNER_SCHEMA,
        "options": {
            "temperature": 0.0 # Deterministic planning
        }
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        
        # Parse the JSON
        plan = json.loads(result_text)
        return plan
    except Exception as e:
        print(f"[ARIA Planner Error] Failed to generate plan: {e}")
        return []

if __name__ == "__main__":
    plan = generate_plan("open notepad and type hello")
    print(f"Generated Plan: {json.dumps(plan, indent=2)}")
