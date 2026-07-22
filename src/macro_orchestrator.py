from src.llm_core import LocalLLMCore
from src.logger import logger

PASS1_PROMPT = """You are a Loop Detector AI. Analyze the user's prompt. 
Does it contain a repetitive loop? (Look for phrases like "for each", "every", "repeat", "iterate").

CRITICAL: Output ONLY valid JSON in this exact format:
{
  "is_loop": true or false,
  "iterations": number (e.g. 10, or 0 if unknown)
}

User Prompt: {instruction}
JSON Output:"""

PASS2_PROMPT = """You are a Software Architect. The following user prompt is a Loop Macro.
Break it down into three parts:
1. setup_instructions: What to do before the loop starts.
2. loop_instructions: The specific actions to perform ONCE during each iteration of the loop.
3. teardown_instructions: What to do after all iterations are complete.

CRITICAL: Output ONLY valid JSON in this exact format:
{
  "setup_instructions": "...",
  "loop_instructions": "...",
  "teardown_instructions": "..."
}

User Prompt: {instruction}
JSON Output:"""


class MacroOrchestrator:
    def __init__(self):
        self.core = LocalLLMCore(use_mock=False)

    def analyze_instruction(self, instruction: str) -> dict:
        """Parses a user instruction using Multi-Pass Chain of Thought."""

        # Simple heuristic check before calling LLM
        loop_keywords = [
            "for each",
            "for every",
            "every",
            "each",
            "repeat",
            "iterate",
            "loop",
            "sequentially",
        ]
        if not any(kw in instruction.lower() for kw in loop_keywords):
            return {"is_loop": False}

        logger.info("Macro Orchestrator Pass 1: Detecting Loop...")
        prompt1 = PASS1_PROMPT.replace("{instruction}", instruction)

        try:
            res1 = self.core.process_intent(prompt1, {"voice_command": instruction})
            if isinstance(res1, list) and len(res1) > 0 and isinstance(res1[0], dict):
                res1 = res1[0]

            if isinstance(res1, dict) and res1.get("is_loop"):
                iterations = res1.get("iterations", 1)
                logger.info(
                    f"Macro Orchestrator Pass 2: Extracting Logic for {iterations} iterations..."
                )

                prompt2 = PASS2_PROMPT.replace("{instruction}", instruction)
                res2 = self.core.process_intent(prompt2, {"voice_command": instruction})

                if (
                    isinstance(res2, list)
                    and len(res2) > 0
                    and isinstance(res2[0], dict)
                ):
                    res2 = res2[0]

                if isinstance(res2, dict):
                    res2["is_loop"] = True
                    res2["iterations"] = iterations
                    return res2

        except Exception as e:
            logger.warning(f"Macro orchestration failed: {e}")

        return {"is_loop": False}


macro_orchestrator = MacroOrchestrator()
