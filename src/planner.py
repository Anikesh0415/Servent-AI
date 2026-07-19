import json
import re
import requests
from src.llm_core import LocalLLMCore
from src.logger import logger

PLANNER_SYSTEM_PROMPT = """You are ARIA, an autonomous AI controlling a Windows 11 computer.

CRITICAL RULES — NEVER VIOLATE:
1. You MUST output ONLY valid JSON, nothing else.
2. You MUST include EVERY single step — never skip any.
3. Each step must be a specific executable action, not a summary.
4. Include confidence scores (0.0 to 1.0) and expected pre/post conditions for verification.

BEHAVIORAL GUIDELINES:
- To submit web forms or chat prompts (like Gemini/ChatGPT), prefer using `key_shortcut` with "enter" instead of `click_element` on the submit button.
- In chat apps (like WhatsApp), ALWAYS explicitly search for the contact first (e.g. click search, type name, press enter) BEFORE pasting or typing messages.

STEP TYPES AVAILABLE:
- open_browser: {"action": "open_browser", "url": "https://..."}
- click_element: {"action": "click_element", "target": "description of element"}
- type_text: {"action": "type_text", "text": "exact text to type"}
- key_shortcut: {"action": "key_shortcut", "keys": "ctrl+c"}
- wait_until: {"action": "wait_until", "condition": "exact screen condition to wait for"}
- open_app: {"action": "open_app", "name": "app name"}
- scroll: {"action": "scroll", "direction": "down", "amount": 3}
- speak: {"action": "speak", "text": "what to say to user"}

OUTPUT FORMAT (strict JSON array starting with [ and ending with ]):
[
  {
    "id": 1, 
    "action": "open_browser", 
    "url": "https://gemini.google.com", 
    "description": "Open Gemini",
    "anchor_check": "Gemini homepage or chat interface visible",
    "confidence": 0.95
  }
]
"""

class MultiStagePlanner:
    """
    Production Multi-Stage Planner for Servent-AI.
    Pipeline: Intent Decomposition -> Sub-goal Mapping -> Task Plan Generation -> Action Plan JSON -> Replanning Engine.
    """
    def __init__(self):
        self.core = LocalLLMCore(use_mock=False)

    def decompose_intent(self, instruction: str, context_summary: str = "") -> dict:
        """Stage 1: Analyzes user intent and decomposes into logical sub-goals."""
        logger.info(f"Decomposing intent for: '{instruction}'")
        
        prompt = (
            f"User Command: {instruction}\n"
            f"Current System Context: {context_summary}\n"
            "Break down this request into:\n"
            "1. Primary Intent\n"
            "2. Required Apps/Websites\n"
            "3. Sub-goals sequence\n"
            "Output JSON format: {\"intent\": \"...\", \"apps\": [...], \"sub_goals\": [...]}"
        )
        
        try:
            res = self.core.process_intent(prompt, {"voice_command": instruction})
            if isinstance(res, dict):
                return res
            if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                return res[0]
        except Exception as e:
            logger.warning(f"Intent decomposition fallback ({e})")
            
        return {
            "intent": instruction,
            "apps": [],
            "sub_goals": [instruction]
        }

    def generate_action_plan(self, instruction: str, context_summary: str = "") -> list:
        """Stage 2 & 3: Generates executable JSON action steps with confidence scores."""
        # First decompose
        decomp = self.decompose_intent(instruction, context_summary)
        
        sub_goals_raw = decomp.get("sub_goals", [instruction])
        sub_goals_list = []
        for sg in sub_goals_raw:
            if isinstance(sg, dict):
                # If LLM returns a dict (e.g. {"goal": "do X"}), extract the first value
                val = next(iter(sg.values())) if sg else ""
                sub_goals_list.append(str(val))
            else:
                sub_goals_list.append(str(sg))
        sub_goals_str = ", ".join(sub_goals_list)
        
        full_prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"Context: {context_summary}\n"
            f"Target Sub-Goals: {sub_goals_str}\n"
            f"User Command: {instruction}\n"
            "Output the JSON action plan array now:"
        )
        
        logger.info(f"Generating action plan for sub-goals: {sub_goals_str}")
        
        raw_results = self.core.process_intent(full_prompt, {"voice_command": instruction})
        plan = self._clean_and_extract(raw_results)

        # Ensure confidence scores exist
        for step in plan:
            if "confidence" not in step:
                step["confidence"] = 0.90
            if "anchor_check" not in step and "target" in step:
                step["anchor_check"] = f"Visible element: {step['target']}"

        logger.info(f"Plan generated successfully with {len(plan)} steps.")
        return plan

    def replan_failed_step(self, failed_step: dict, error_reason: str, context_summary: str = "") -> list:
        """Stage 4: Active Replanning Engine when execution or visual verification fails."""
        logger.warning(f"Replanning for failed step {failed_step.get('id', '?')}: {failed_step.get('action')} ({error_reason})")
        
        prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"REPLANNING REQUIRED!\n"
            f"The following step failed during execution:\n"
            f"Failed Step: {json.dumps(failed_step)}\n"
            f"Failure Reason: {error_reason}\n"
            f"Current OS Context: {context_summary}\n"
            "Provide an alternative 1-3 step JSON action recovery sequence to bypass this error and resume the task:"
        )
        
        raw_results = self.core.process_intent(prompt, {"voice_command": f"Fix failed step {failed_step.get('action')}"})
        recovery_plan = self._clean_and_extract(raw_results)
        
        logger.info(f"Recovery plan generated: {len(recovery_plan)} alternative step(s).")
        return recovery_plan

    def _clean_and_extract(self, raw_data) -> list:
        """Parses and sanitizes LLM output into a clean list of dict steps."""
        if isinstance(raw_data, list):
            return raw_data
        
        if isinstance(raw_data, dict):
            for key in ["steps", "plan", "actions", "task_steps"]:
                if key in raw_data and isinstance(raw_data[key], list):
                    return raw_data[key]
            return [raw_data]

        if isinstance(raw_data, str):
            raw_text = raw_data.strip()
            start_idx = raw_text.find('[')
            end_idx = raw_text.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(raw_text[start_idx:end_idx+1])
                except Exception:
                    pass
        
        return [{"action": "unknown", "target": str(raw_data)}]

# Global Singleton & Backward Compatibility Function
planner_instance = MultiStagePlanner()

def generate_plan(instruction: str, context_summary: str = "") -> list:
    """Backward compatible entry point for ARIA planner."""
    return planner_instance.generate_action_plan(instruction, context_summary)

def replan_failed_step(failed_step: dict, error_reason: str, context_summary: str = "") -> list:
    """Backward compatible entry point for replanning."""
    return planner_instance.replan_failed_step(failed_step, error_reason, context_summary)


if __name__ == "__main__":
    p = MultiStagePlanner()
    print("Decomposition Test:", p.decompose_intent("Open Gemini and write a letter"))
