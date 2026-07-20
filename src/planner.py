import json
import re
import requests
from src.llm_core import LocalLLMCore
from src.logger import logger
from src.utils.skill_retriever import get_relevant_examples

PLANNER_SYSTEM_PROMPT = """You are ARIA, an autonomous AI controlling a Windows 11 computer.

CRITICAL RULES — NEVER VIOLATE:
1. You MUST output ONLY valid JSON, nothing else.
2. You MUST include EVERY single step — never skip any.
3. Each step must be a specific executable action, not a summary.
4. Include confidence scores (0.0 to 1.0) and expected pre/post conditions for verification.

BEHAVIORAL GUIDELINES:
- To submit web forms or chat prompts (like Gemini/ChatGPT), prefer using `key_shortcut` with "enter" instead of `click_element` on the submit button.
- In chat apps (like WhatsApp), ALWAYS explicitly search for the contact first BEFORE pasting or typing messages.
- Specifically in WhatsApp, to search for a contact: use `key_shortcut` with "ctrl+f", then `type_text` the contact name, then `wait_until` results load, then use `key_shortcut` with "tab", and finally `key_shortcut` with "enter" to open the chat. NEVER use `click_element` to select the chat.

STEP TYPES AVAILABLE:
- open_browser: {"action": "open_browser", "url": "https://..."}
- click_element: {"action": "click_element", "target": "description of element"}
- type_text: {"action": "type_text", "text": "exact text to type"}
- key_shortcut: {"action": "key_shortcut", "keys": "ctrl+c"}
- wait_until: {"action": "wait_until", "condition": "exact screen condition to wait for"}
- open_app: {"action": "open_app", "name": "app name"}
- scroll: {"action": "scroll", "direction": "down", "amount": 3}
- speak: {"action": "speak", "text": "what to say to user"}
- semantic_copy: {"action": "semantic_copy", "goal": "what exact data to extract from the screen into clipboard"}
- hover_element: {"action": "hover_element", "target": "exact text on screen to hover over"}
- click_text: {"action": "click_text", "text": "exact word to click", "index": 1} (use index if there are multiple identical buttons, defaults to 1)

OUTPUT FORMAT (strict JSON object containing a 'steps' array):
{
  "steps": [
    {
      "id": 1, 
      "action": "open_browser", 
      "url": "https://gemini.google.com", 
      "description": "Open Gemini",
      "anchor_check": "Gemini homepage or chat interface visible",
      "confidence": 0.95
    }
  ]
}
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
        
        # 0. Safety Guardrail: Vague Intent Catching
        vague_keywords = ["make it better", "do that thing", "fix the errors", "do it again"]
        if len(instruction.split()) <= 6 and not any(app in instruction.lower() for app in ["app", "website", "mail", "whatsapp", "browser", "chrome", "desktop"]):
            if any(kw in instruction.lower() for kw in vague_keywords) or len(instruction.split()) <= 3:
                logger.warning("Vague intent detected. Requesting clarification.")
                return {
                    "intent": "Clarify ambiguous request",
                    "apps": [],
                    "sub_goals": [{"action": "speak", "text": "I'm not sure exactly what you mean. Could you clarify what you would like me to do?"}]
                }
        
        prompt = (
            f"User Command: {instruction}\n"
            f"Current System Context: {context_summary}\n"
            "Break down this request into:\n"
            "1. Primary Intent\n"
            "2. Required Apps/Websites\n"
            "3. Sub-goals sequence\n\n"
            "CRITICAL BEHAVIORAL GUIDELINES TO CONSIDER FOR SUB-GOALS:\n"
            "- In chat apps (WhatsApp), explicitly searching for a contact (ctrl+f, type name, tab, enter) is REQUIRED before sending messages.\n"
            "- 'Paste' or 'Copy' must be translated to keyboard shortcuts.\n\n"
            "Output JSON format: {\"intent\": \"...\", \"apps\": [...], \"sub_goals\": [\"goal 1\", \"goal 2\"]}"
        )
        
        logger.info(f"Decomposing intent for: '{instruction}'")
        
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
        # First decompose
        decomp = self.decompose_intent(instruction, context_summary)
        
        sub_goals_raw = decomp.get("sub_goals", [instruction])
        
        # If the intent decomposition already generated a hardcoded action plan (e.g. clarification)
        if sub_goals_raw and isinstance(sub_goals_raw[0], dict) and sub_goals_raw[0].get("action") == "speak":
            return sub_goals_raw

        sub_goals_list = []
        for sg in sub_goals_raw:
            if isinstance(sg, dict):
                val = next(iter(sg.values())) if sg else ""
                sub_goals_list.append(str(val))
            else:
                sub_goals_list.append(str(sg))
        sub_goals_str = ", ".join(sub_goals_list)
        
        dynamic_examples = get_relevant_examples(instruction, max_examples=2)
        
        system_prompt = PLANNER_SYSTEM_PROMPT
        if "[DEV_MODE:" in instruction:
            system_prompt += """
### DEVELOPER MODE UNLOCKED ###
You are now operating as an AI Software Engineer. You have direct access to the file system and terminal.
You may use the following exclusive Developer Actions:
- read_file: {"action": "read_file", "path": "absolute path to file"}
- write_file: {"action": "write_file", "path": "absolute path to file", "content": "exact code to write"}
- run_terminal: {"action": "run_terminal", "command": "bash/cmd string", "cwd": "absolute directory path"}
When asked to code, debug, or write scripts, USE THESE ACTIONS INSTEAD of opening VS Code via UI clicks.
"""

        if "[IMAGE_ATTACHED:" in instruction:
            import re
            from src.vision import ask_moondream
            match = re.search(r"\[IMAGE_ATTACHED: (.*?)\]", instruction)
            if match:
                img_path = match.group(1)
                logger.info(f"Analyzing attached image: {img_path}")
                try:
                    analysis = ask_moondream("Describe everything you see in this image in detail, including any text, code, errors, or UI elements.", img_path)
                    system_prompt += f"\n\n### ATTACHED IMAGE ANALYSIS ###\nThe user attached an image to this prompt. The Moondream Vision Model analyzed it and reported the following:\n{analysis}\nUse this visual context to satisfy the user's request.\n"
                except Exception as e:
                    logger.warning(f"Failed to analyze attached image: {e}")

        full_prompt = (
            f"{system_prompt}\n\n"
            f"Context: {context_summary}\n"
            f"Target Sub-Goals: {sub_goals_str}\n"
            f"User Command: {instruction}\n"
            f"{dynamic_examples}\n"
            "CRITICAL: Translate the sub-goals into VALID actions. 'Paste Text' is NOT an action (use type_text or key_shortcut). Do NOT blindly copy the sub-goals. You MUST implement the BEHAVIORAL GUIDELINES exactly (e.g., use ctrl+f, tab, enter for WhatsApp).\n"
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

    def replan_failed_step(self, failed_step: dict, error_reason: str, context_summary: str = "", ui_tree_snapshot: str = "") -> list:
        """Stage 4: Active Replanning Engine when execution or visual verification fails."""
        logger.warning(f"Replanning for failed step {failed_step.get('id', '?')}: {failed_step.get('action')} ({error_reason})")
        
        ui_snapshot_block = f"Visual UI Snapshot (Buttons/Inputs on Screen):\n{ui_tree_snapshot}\n" if ui_tree_snapshot else ""
        
        prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"REPLANNING REQUIRED!\n"
            f"The following step failed during execution:\n"
            f"Failed Step: {json.dumps(failed_step)}\n"
            f"Failure Reason: {error_reason}\n"
            f"Current OS Context: {context_summary}\n"
            f"{ui_snapshot_block}"
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
            from src.utils.json_parser import parse_json_from_text
            parsed = parse_json_from_text(raw_data)
            if parsed is not None:
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    for key in ["steps", "plan", "actions", "task_steps"]:
                        if key in parsed and isinstance(parsed[key], list):
                            return parsed[key]
                    return [parsed]
        
        logger.error(f"[Planner] Failed to extract action plan from LLM output. Returning unknown step.")
        return [{"action": "unknown", "target": str(raw_data)}]

# Global Singleton & Backward Compatibility Function
planner_instance = MultiStagePlanner()

def generate_plan(instruction: str, context_summary: str = "") -> list:
    """Backward compatible entry point for ARIA planner."""
    return planner_instance.generate_action_plan(instruction, context_summary)

def replan_failed_step(failed_step: dict, error_reason: str, context_summary: str = "", ui_tree_snapshot: str = "") -> list:
    """Backward compatible entry point for replanning."""
    return planner_instance.replan_failed_step(failed_step, error_reason, context_summary, ui_tree_snapshot)


if __name__ == "__main__":
    p = MultiStagePlanner()
    print("Decomposition Test:", p.decompose_intent("Open Gemini and write a letter"))
