import json
import re
import requests

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Phase 1: Downsized to 3B (2.2 GB RAM) so ARIA + VISTA fit simultaneously.
PLANNER_MODEL = "qwen2.5:3b-instruct-q4_K_M"

# ---------------------------------------------------------------------------
# ARIA SYSTEM PROMPT
# ---------------------------------------------------------------------------
PLANNER_SYSTEM_PROMPT = """You are ARIA, the Master Planner for a desktop automation system.
Break the user's request into a JSON action plan.

AVAILABLE ACTIONS (use ONLY these):
  {"action": "open_app",        "app": "<name>"}
  {"action": "navigate_browser","url": "<full_url>"}
  {"action": "type",            "text": "<text>",  "anchor_check": "<what VISTA should see after this>"}
  {"action": "key",             "key": "<key_name>","anchor_check": "<what VISTA should see after this>"}
  {"action": "copy_all"}
  {"action": "paste"}
  {"action": "click",           "x": <int>, "y": <int>}
  {"action": "scroll",          "amount": <int>}

STRICT RULES:
1. Output ONLY a raw JSON array. No markdown. No explanation. No trailing text.
2. NEVER use "click" if a keyboard shortcut achieves the same result.
3. After every "type" action into a search bar or AI prompt box, you MUST add a {"action":"key","key":"enter"} step.
4. Every "type" and "key" step MUST include an "anchor_check" field: a short description of what should be visible on screen after the step succeeds (e.g. "cursor in chat box", "YouTube homepage is visible").
5. Use "navigate_browser" (not "open_app") when the browser is already open and you need to go to a URL.
6. Do NOT output any keys other than those listed above.

EXAMPLE — "open gemini and ask it to write a poem":
[
  {"action": "open_app", "app": "gemini"},
  {"action": "type", "text": "write a poem about the ocean", "anchor_check": "text visible in Gemini prompt box"},
  {"action": "key", "key": "enter", "anchor_check": "Gemini response is loading or visible"}
]

EXAMPLE — "search for python tutorials on youtube":
[
  {"action": "open_app", "app": "youtube"},
  {"action": "type", "text": "python tutorials", "anchor_check": "search text visible in YouTube search bar"},
  {"action": "key", "key": "enter", "anchor_check": "YouTube search results page is visible"}
]"""


def generate_plan(instruction: str) -> list:
    """
    Calls ARIA (qwen2.5:3b) to generate a structured action plan.
    - keep_alive: -1  → model stays pinned in RAM permanently (Phase 1).
    - format: json    → Ollama enforces valid JSON output (Phase 2).
    - temperature: 0  → Fully deterministic / no hallucinations.
    """
    prompt = f"User Request: {instruction}\nOutput the JSON action plan now."

    payload = {
        "model": PLANNER_MODEL,
        "system": PLANNER_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "format": "json",       # Phase 2: enforces valid JSON at the token level
        "keep_alive": -1,       # Phase 1: pin ARIA in RAM forever
        "options": {
            "temperature": 0.0,
            "num_predict": 512,
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()

        # The model MUST return a JSON array. Try direct parse first.
        parsed = json.loads(result_text)

        # If the model wrapped the array in a dict (e.g. {"plan": [...]}) unwrap it.
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    parsed = v
                    break

        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array, got: {type(parsed)}")

        return parsed

    except json.JSONDecodeError as e:
        print(f"[ARIA Planner] JSON decode error: {e}\nRaw response: {result_text}")
        # Last-resort: try to extract a JSON array with regex
        match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return []
    except Exception as e:
        print(f"[ARIA Planner Error] {e}")
        return []


if __name__ == "__main__":
    plan = generate_plan("open notepad and type hello world")
    print(f"Generated Plan:\n{json.dumps(plan, indent=2)}")
