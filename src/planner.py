import json
import re
import requests


# ---------------------------------------------------------------------------
# RESILIENT JSON PARSING HELPERS
# ---------------------------------------------------------------------------

def clean_and_parse_json(raw_text: str):
    """Aggressively finds and parses the first JSON array in the text."""
    raw_text = raw_text.strip()
    
    # Try to find the outermost array bounds
    start_idx = raw_text.find('[')
    end_idx = raw_text.rfind(']')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_text[start_idx:end_idx+1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass # Fall back to full text parse

    # Strip opening fence (e.g. ```json or ```)
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
    # Strip closing fence
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("\n", 1)[0]
        
    return json.loads(raw_text.strip())


def extract_steps(parsed_data) -> list:
    """
    Self-healing converter: accepts a list or a dict wrapper and always
    returns a flat list of action steps.
    """
    if isinstance(parsed_data, list):
        return parsed_data

    if isinstance(parsed_data, dict):
        # Heuristic 1: look for common wrapper keys
        for key in ["steps", "plan", "actions", "task_steps", "sequence"]:
            if key in parsed_data and isinstance(parsed_data[key], list):
                print(f"[ARIA Parser] Extracted steps from dict key: '{key}'")
                return parsed_data[key]

        # Heuristic 2: single-step dict — wrap it in a list
        if "action" in parsed_data or "type" in parsed_data or "description" in parsed_data:
            print("[ARIA Parser] Wrapped single-action dict into list.")
            return [parsed_data]

    raise ValueError(f"Could not extract a valid steps list from: {type(parsed_data)}")

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Phase 1: Upgraded to Qwen 14B for maximum reasoning (Heavy but extremely accurate)
PLANNER_MODEL = "qwen2.5:14b"

# ---------------------------------------------------------------------------
# ARIA SYSTEM PROMPT
# ---------------------------------------------------------------------------
PLANNER_SYSTEM_PROMPT = """You are ARIA, an autonomous AI controlling a Windows 11 computer.

CRITICAL RULES — NEVER VIOLATE:
1. You MUST output ONLY valid JSON, nothing else
2. You MUST include EVERY single step — never skip any
3. For tasks involving multiple apps, expect 8–15+ steps
4. NEVER output fewer than 5 steps for any command with 'and', 'then', 'copy', 'send', 'open'
5. Each step must be a specific executable action, not a summary

STEP TYPES AVAILABLE:
- open_browser: {"action": "open_browser", "url": "https://..."}
- click_element: {"action": "click_element", "target": "description of element"}
- type_text: {"action": "type_text", "text": "exact text to type"}
- key_shortcut: {"action": "key_shortcut", "keys": "ctrl+c"}
- wait_until: {"action": "wait_until", "condition": "exact screen condition to wait for"}
- open_app: {"action": "open_app", "name": "app name"}
- scroll: {"action": "scroll", "direction": "down", "amount": 3}
- speak: {"action": "speak", "text": "what to say to user"}

OUTPUT FORMAT (strict JSON array - you MUST start with [ and end with ]):
[
  {"id": 1, "action": "...", "description": "why this step", ...params}
]

EXAMPLE — 'Open Gemini, write a letter, send via WhatsApp':
[
  {"id": 1, "action": "open_browser", "url": "https://gemini.google.com", "description": "Open Gemini"},
  {"id": 2, "action": "wait_until", "condition": "Gemini chat interface loaded with text input visible"},
  {"id": 3, "action": "click_element", "target": "Ask Gemini text input box"},
  {"id": 4, "action": "type_text", "text": "Write a formal letter from Anikesh to Balram asking how Balram is doing"},
  {"id": 5, "action": "key_shortcut", "keys": "enter"},
  {"id": 6, "action": "wait_until", "condition": "Gemini response has fully loaded, no loading indicator visible"},
  {"id": 7, "action": "key_shortcut", "keys": "ctrl+a", "description": "Select all response text"},
  {"id": 8, "action": "key_shortcut", "keys": "ctrl+c", "description": "Copy the letter"},
  {"id": 9, "action": "open_app", "name": "WhatsApp"},
  {"id": 10, "action": "wait_until", "condition": "WhatsApp main window visible with chat list"},
  {"id": 11, "action": "click_element", "target": "search contacts box"},
  {"id": 12, "action": "type_text", "text": "Balram"},
  {"id": 13, "action": "click_element", "target": "Balram in search results"},
  {"id": 14, "action": "click_element", "target": "message input box"},
  {"id": 15, "action": "key_shortcut", "keys": "ctrl+v"},
  {"id": 16, "action": "key_shortcut", "keys": "enter"},
  {"id": 17, "action": "speak", "text": "Letter sent to Balram successfully"}
]

DO NOT output anything other than the JSON object."""


def generate_plan(instruction: str) -> list:
    """
    Calls ARIA (qwen2.5:3b) to generate a structured action plan.
    - keep_alive: -1  → model pinned in RAM permanently.
    - format: json    → Ollama enforces valid JSON at the token level.
    - temperature: 0  → Fully deterministic / no hallucinations.
    Uses clean_and_parse_json + extract_steps for bulletproof parsing.
    """
    prompt = f"User Request: {instruction}\nOutput the JSON action plan now."

    payload = {
        "model": PLANNER_MODEL,
        "system": PLANNER_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.0,
            "num_predict": 4096,
        }
    }

    result_text = ""
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=300)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()

        # Step 1: Strip markdown fences and parse JSON
        parsed = clean_and_parse_json(result_text)

        # Step 2: Self-heal dict wrappers into a flat list
        return extract_steps(parsed)

    except json.JSONDecodeError as e:
        print(f"[ARIA Planner] JSON decode error: {e}")
        print(f"[ARIA Planner] Raw response was: {result_text[:300]}")
        # Last-resort regex fallback: find any [...] or {...} block
        for pattern in [r'\[.*?\]', r'\{.*?\}']:
            match = re.search(pattern, result_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    return extract_steps(parsed)
                except Exception:
                    pass
        return []
    except ValueError as e:
        print(f"[ARIA Parser Error] {e}")
        return []
    except Exception as e:
        print(f"[ARIA Planner Error] {e}")
        return []


if __name__ == "__main__":
    plan = generate_plan("open notepad and type hello world")
    print(f"Generated Plan:\n{json.dumps(plan, indent=2)}")
