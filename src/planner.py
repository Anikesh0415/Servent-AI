import json
import re
import urllib.parse
from src.llm_core import LocalLLMCore
from src.logger import logger
from src.config import BROWSER_APP_MAP
from src.utils.skill_retriever import get_relevant_examples

PLANNER_SYSTEM_PROMPT = """You are ARIA, an autonomous AI controlling a Windows 11 computer.

CRITICAL RULES — NEVER VIOLATE:
1. You MUST output ONLY valid JSON, nothing else.
2. You MUST include EVERY single step — never skip any.
3. Each step must be a specific executable action, not a summary.
4. Include confidence scores (0.0 to 1.0) and expected pre/post conditions for verification.

BEHAVIORAL GUIDELINES:
- To submit web forms or chat prompts (like Gemini/ChatGPT), prefer using `key_shortcut` with "enter" instead of `click_element` on the submit button.
- For actions that have a dedicated plugin macro (like sending a WhatsApp message, playing YouTube, setting alarms, or searching Google), you MUST use the dedicated macro instead of manually stringing together UI steps.
- If the user asks for a task that involves an application or website that does NOT have a dedicated macro, use the `dynamic_task` action so the smart agent can generate and execute the code dynamically.

STEP TYPES AVAILABLE:
{DYNAMIC_STEP_TYPES}

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
    Production Multi-Stage Planner for Forge.
    Pipeline: Intent Decomposition -> Sub-goal Mapping -> Task Plan Generation -> Action Plan JSON -> Replanning Engine.
    """

    def __init__(self):
        self.core = LocalLLMCore(use_mock=False)
        self.use_bio_engine = False
        self.bio_weights = {}
        try:
            import json, os
            config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.use_bio_engine = config.get("USE_BIO_ORGANOID_ENGINE", False)
            if self.use_bio_engine:
                weights_path = os.path.join(os.path.dirname(__file__), "..", "data", "bio_weights.json")
                if os.path.exists(weights_path):
                    with open(weights_path, "r", encoding="utf-8") as f:
                        self.bio_weights = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load bio engine config in Planner: {e}")

    async def decompose_intent(self, instruction: str, context_summary: str = "") -> dict:
        """Stage 1: Analyzes user intent and decomposes into logical sub-goals."""
        logger.info(f"Decomposing intent for: '{instruction}'")

        # 0. Safety Guardrail: Vague Intent Catching
        vague_keywords = [
            "make it better",
            "do that thing",
            "fix the errors",
            "do it again",
        ]
        if len(instruction.split()) <= 6 and not any(
            app in instruction.lower()
            for app in [
                "app",
                "website",
                "mail",
                "whatsapp",
                "browser",
                "chrome",
                "desktop",
            ]
        ):
            if (
                any(kw in instruction.lower() for kw in vague_keywords)
                or len(instruction.split()) <= 3
            ):
                logger.warning("Vague intent detected. Requesting clarification.")
                return {
                    "intent": "Clarify ambiguous request",
                    "apps": [],
                    "sub_goals": [
                        {
                            "action": "speak",
                            "text": "I'm not sure exactly what you mean. Could you clarify what you would like me to do?",
                        }
                    ],
                }

        prompt = (
            f"User Command: {instruction}\n"
            f"Current System Context: {context_summary}\n"
            "Break down this request into:\n"
            "1. Primary Intent\n"
            "2. Required Apps/Websites\n"
            "3. Sub-goals sequence\n\n"
            "CRITICAL BEHAVIORAL GUIDELINES TO CONSIDER FOR SUB-GOALS:\n"
            "- For actions with dedicated plugin macros (e.g. sending a WhatsApp message), you MUST output the macro action instead of manual UI steps.\n"

            "- 'Paste' or 'Copy' must be translated to keyboard shortcuts.\n\n"
            'Output JSON format: {"intent": "...", "apps": [...], "sub_goals": ["goal 1", "goal 2"]}'
        )

        logger.info(f"Decomposing intent for: '{instruction}'")

        try:
            res = await self.core.process_intent(prompt, {"voice_command": instruction})
            if isinstance(res, dict):
                return res
            if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                return res[0]
        except Exception as e:
            logger.warning(f"Intent decomposition fallback ({e})")

        return {"intent": instruction, "apps": [], "sub_goals": [instruction]}

    def _extract_whatsapp_plan(self, clean_inst: str) -> list:
        if not any(w in clean_inst for w in ["whatsapp", "whatsaap", "watsapp", "watsap"]):
            return None
        
        words = clean_inst.split()
        if len(words) <= 3 and not any(w in clean_inst for w in ["message", "send", "msg", "text", "say", "hi", "hello", "to"]):
            return [{"action": "open_app", "target": "WhatsApp", "name": "WhatsApp"}]

        quote_match = re.search(r'["\'](.*?)["\']', clean_inst)
        msg_text = quote_match.group(1).strip() if quote_match else ""

        work_str = re.sub(r'["\'].*?["\']', '', clean_inst)

        contact = ""
        if " to " in work_str:
            parts = work_str.split(" to ", 1)
            target_part = parts[1].strip()
            c_words = [w for w in target_part.split() if w not in ["whatsapp", "whatsaap", "watsapp", "watsap", "on", "in", "app"]]
            if c_words:
                contact = c_words[0]
            if not msg_text:
                left_words = [w for w in parts[0].split() if w not in ["open", "launch", "start", "whatsapp", "whatsaap", "watsapp", "and", "send", "message", "msg", "text", "say", "a", "the", "on", "in"]]
                if left_words:
                    msg_text = " ".join(left_words)
        
        if not contact:
            for kw in ["message ", "msg ", "text ", "send "]:
                if kw in work_str:
                    after_kw = work_str.split(kw, 1)[1].strip()
                    ak_words = [w for w in after_kw.split() if w not in ["whatsapp", "whatsaap", "watsapp", "watsap", "on", "in", "app", "a", "the"]]
                    if ak_words:
                        contact = ak_words[0]
                        if not msg_text and len(ak_words) > 1:
                            msg_text = " ".join(ak_words[1:])
                    break

        if not contact:
            stop_words = ["open", "launch", "start", "whatsapp", "whatsaap", "watsapp", "watsap", "and", "to", "send", "message", "msg", "text", "saying", "say", "on", "in", "a", "the", "with"]
            rem_words = [w for w in work_str.split() if w not in stop_words]
            if rem_words:
                contact = rem_words[0]
                if not msg_text and len(rem_words) > 1:
                    msg_text = " ".join(rem_words[1:])

        if not contact:
            contact = "contact"
        if not msg_text:
            msg_text = "Hello"

        logger.info(f"[Planner Fast-Path] Dedicated WhatsApp: Contact='{contact}', Msg='{msg_text}'")
        return [{
            "action": "send_whatsapp",
            "contact": contact,
            "message": msg_text,
            "target": f"WhatsApp {contact}: '{msg_text}'",
            "name": f"WhatsApp {contact}"
        }]

    async def generate_action_plan(
        self, instruction: str, context_summary: str = ""
    ) -> list:
        clean_inst = instruction.strip().lower()
        
        # 0. Smart Agent Fallback for Complex Multi-App Instructions
        word_count = len(clean_inst.split())
        threshold = 15
        if self.use_bio_engine and self.bio_weights:
            # Scale threshold based on organoid activation threshold
            bio_thresh = self.bio_weights.get("spike_activation_threshold_uv", 230)
            threshold = max(5, int(bio_thresh / 15.0)) # Neuromorphic mapping
            logger.info(f"[Bio-Engine] Using dynamic instruction threshold: {threshold} (derived from spike_threshold)")
            
        if word_count > threshold or clean_inst.count(" and ") >= 2:
            logger.info("[Planner Fast-Path] Complex instruction detected, routing to Smart Agent (dynamic_task).")
            return [{"action": "dynamic_task", "target": instruction, "name": "Dynamic Task"}]

        # Handle comma-separated multi-tasks (e.g. "open notepad, open calculator")
        if "," in clean_inst:
            parts = [p.strip() for p in clean_inst.split(",")]
            all_steps = []
            for part in parts:
                if part:
                    part_steps = await self.generate_action_plan(part, context_summary)
                    if part_steps:
                        all_steps.extend(part_steps)
            if all_steps:
                return all_steps

        # Dedicated WhatsApp Fast-Path Router
        wa_plan = self._extract_whatsapp_plan(clean_inst)
        if wa_plan:
            return wa_plan

        # Comprehensive Fast-Path Router for 1-Action Commands (Instant 0ms Execution)
        words = clean_inst.split()

        # 1. Open / Launch app or website
        for prefix in ["open ", "launch ", "start "]:
            if clean_inst.startswith(prefix) and len(words) <= 4 and "and" not in clean_inst:
                target_name = clean_inst[len(prefix):].strip()
                logger.info(f"[Planner Fast-Path] Direct open target: {target_name}")
                return [{"action": "open_app", "target": target_name, "name": target_name}]

        # 2. Close window or app
        if clean_inst in ["close", "close window", "exit", "close app"] or (clean_inst.startswith("close ") and len(words) <= 3):
            target_name = clean_inst.replace("close", "").replace("app", "").replace("window", "").strip()
            logger.info(f"[Planner Fast-Path] Direct close target: {target_name}")
            return [{"action": "close_app", "target": target_name}]

        # 3. Minimize / Maximize window
        if any(w in clean_inst for w in ["minimize", "minimise"]):
            return [{"action": "key_shortcut", "keys": "win+down"}]
        if any(w in clean_inst for w in ["maximize", "maximise"]):
            return [{"action": "key_shortcut", "keys": "win+up"}]

        # 4. Media Controls (Play, Pause, Mute, Volume)
        if clean_inst in ["play", "pause", "play/pause", "toggle play", "resume"]:
            return [{"action": "key_shortcut", "keys": "playpause"}]
        if "volume up" in clean_inst or clean_inst == "louder":
            return [{"action": "key_shortcut", "keys": "volumeup"}]
        if "volume down" in clean_inst or clean_inst == "quieter":
            return [{"action": "key_shortcut", "keys": "volumedown"}]
        if clean_inst in ["mute", "unmute"]:
            return [{"action": "key_shortcut", "keys": "volumemute"}]

        # 5. Take Screenshot
        if any(w in clean_inst for w in ["screenshot", "screen shot", "take screenshot", "capture screen"]):
            return [{"action": "take_screenshot", "target": "desktop"}]

        # 5.5 Timer
        if "timer" in clean_inst:
            nums = re.findall(r'\d+', clean_inst)
            minutes = nums[0] if nums else "10"
            return [{"action": "set_timer", "minutes": minutes}]

        # =========================================================================
        # =========================================================================
        # UNIVERSAL DOUBLE-ACTION SYNTHESIZER (Works for ANY Service / App / Action)
        # =========================================================================

        # 1. UNIVERSAL PATTERN: "open <service> and <action>"
        # Examples:
        # - "open antigravity and ask 'how black holes work'"
        # - "open claude and write 'a python script'"
        # - "open perplexity and search quantum computing"
        # - "open github and search transformers"
        if clean_inst.startswith(("open ", "launch ", "start ")) and " and " in clean_inst:
            parts = clean_inst.split(" and ", 1)
            target_service = parts[0].replace("open", "").replace("launch", "").replace("start", "").strip()
            second_action = parts[1].strip()

            service_url = BROWSER_APP_MAP.get(target_service)
            if not service_url or not service_url.startswith("http"):
                if target_service in ["antigravity", "gemini"]:
                    service_url = f"https://{target_service}.google.com"
                elif target_service in ["claude", "perplexity"]:
                    service_url = f"https://{target_service}.ai"
                else:
                    service_url = f"https://{target_service}.com"

            prompt_match = re.search(r'["\'](.*?)["\']', second_action)
            action_text = prompt_match.group(1) if prompt_match else second_action
            for prefix in ["give it a prompt ", "give a prompt ", "ask ", "prompt ", "write ", "search ", "generate "]:
                if action_text.startswith(prefix):
                    action_text = action_text[len(prefix):].strip()

            logger.info(f"[Planner Fast-Path] Universal Double Action: {target_service} -> '{action_text}'")
            return [
                {"action": "open_browser", "url": service_url, "target": f"Open {target_service.title()}", "name": f"Open {target_service.title()}"},
                {"action": "type_text", "text": action_text, "target": f"Input: '{action_text}'", "name": f"Input: '{action_text}'"},
                {"action": "key_shortcut", "keys": "enter", "target": "Submit"}
            ]

        # 2. UNIVERSAL PATTERN: "<action> on/in <service>"
        # Examples:
        # - "search quantum computing on perplexity"
        # - "ask how black holes work on antigravity"
        # - "search transformers on github"
        # - "play rock music on youtube"
        if " on " in clean_inst or " in " in clean_inst:
            sep = " on " if " on " in clean_inst else " in "
            parts = clean_inst.split(sep, 1)
            first_action = parts[0].strip()
            rest = parts[1].strip()
            
            rest_words = rest.split()
            target_service = rest_words[0].strip() if rest_words else ""
            query_rest = " ".join(rest_words[1:]) if len(rest_words) > 1 else ""
            
            # Combine first action and rest of query for specific searches
            full_query = first_action + " " + query_rest

            if target_service in BROWSER_APP_MAP or len(target_service.split()) <= 2:
                service_url = BROWSER_APP_MAP.get(target_service)
                
                # Dedicated overrides for YouTube & Spotify
                if target_service in ["youtube", "yt"]:
                    query = full_query.replace("search", "").replace("play", "").replace("for", "").replace("about", "").replace("abt", "").strip()
                    encoded_q = urllib.parse.quote_plus(query)
                    return [{"action": "open_browser", "url": f"https://www.youtube.com/results?search_query={encoded_q}", "target": f"YouTube: {query}", "name": f"YouTube: {query}"}]
                elif target_service == "spotify":
                    query = full_query.replace("search", "").replace("play", "").replace("for", "").strip()
                    return [{"action": "play_spotify", "query": query, "target": f"Play on Spotify: {query}", "name": f"Spotify: {query}"}]
                elif target_service == "whatsapp":
                    quote_match = re.search(r'["\'](.*?)["\']', full_query)
                    msg_text = quote_match.group(1) if quote_match else ""
                    clean_first = re.sub(r'["\'].*?["\']', '', full_query)
                    clean_first = re.sub(r'\b(send|message|msg|text|say|to|on|in|a)\b', ' ', clean_first).strip()
                    words_rem = [w for w in clean_first.split() if w]
                    
                    if not msg_text and len(words_rem) >= 2:
                        contact = words_rem[0]
                        msg_text = " ".join(words_rem[1:])
                    elif not msg_text and len(words_rem) == 1:
                        contact = words_rem[0]
                        msg_text = "Hello"
                    else:
                        contact = words_rem[0] if words_rem else "contact"
                        if not msg_text:
                            msg_text = "Hello"

                    return [{"action": "send_whatsapp", "contact": contact, "message": msg_text, "target": f"WhatsApp {contact}: '{msg_text}'", "name": f"WhatsApp {contact}"}]

                if not service_url or not service_url.startswith("http"):
                    if target_service in ["antigravity", "gemini"]:
                        service_url = f"https://{target_service}.google.com"
                    elif target_service in ["claude", "perplexity"]:
                        service_url = f"https://{target_service}.ai"
                    else:
                        service_url = f"https://{target_service}.com"

                prompt_match = re.search(r'["\'](.*?)["\']', first_action)
                action_text = prompt_match.group(1) if prompt_match else first_action
                for prefix in ["search ", "google ", "ask ", "prompt ", "play ", "find "]:
                    if action_text.startswith(prefix):
                        action_text = action_text[len(prefix):].strip()

                logger.info(f"[Planner Fast-Path] Universal Action on Service: {target_service} -> '{action_text}'")
                return [
                    {"action": "open_browser", "url": service_url, "target": f"Open {target_service.title()}", "name": f"Open {target_service.title()}"},
                    {"action": "type_text", "text": action_text, "target": f"Input: '{action_text}'", "name": f"Input: '{action_text}'"},
                    {"action": "key_shortcut", "keys": "enter", "target": "Submit"}
                ]

        # 3. UNIVERSAL PATTERN: "<action> <service> [about/for/to] <query>"
        # Examples: "ask chatgpt about quantum physics", "search youtube for cats"
        if words[0] in ["ask", "prompt", "query", "search", "tell", "check"]:
            if len(words) >= 2:
                target_service = words[1].replace("'", "").replace('"', '').strip()
                # Special alias handling
                if target_service == "yt":
                    target_service = "youtube"
                
                if target_service in BROWSER_APP_MAP:
                    action_text = " ".join(words[2:])
                    if action_text.startswith(("about ", "for ", "to ", "abt ", "on ")):
                        action_text = action_text.split(" ", 1)[1]
                    
                    service_url = BROWSER_APP_MAP.get(target_service)
                    if not service_url or not service_url.startswith("http"):
                        if target_service in ["antigravity", "gemini"]:
                            service_url = f"https://{target_service}.google.com"
                        elif target_service in ["claude", "perplexity"]:
                            service_url = f"https://{target_service}.ai"
                        else:
                            service_url = f"https://{target_service}.com"

                    logger.info(f"[Planner Fast-Path] Universal Double Action (Direct): {target_service} -> '{action_text}'")
                    
                    if target_service == "youtube":
                        encoded_q = urllib.parse.quote_plus(action_text)
                        return [{"action": "open_browser", "url": f"https://www.youtube.com/results?search_query={encoded_q}", "target": f"YouTube: {action_text}", "name": f"YouTube: {action_text}"}]
                    elif target_service == "spotify":
                        return [{"action": "play_spotify", "query": action_text, "target": f"Play on Spotify: {action_text}", "name": f"Spotify: {action_text}"}]
                    
                    return [
                        {"action": "open_browser", "url": service_url, "target": f"Open {target_service.title()}", "name": f"Open {target_service.title()}"},
                        {"action": "type_text", "text": action_text, "target": f"Input: '{action_text}'", "name": f"Input: '{action_text}'"},
                        {"action": "key_shortcut", "keys": "enter", "target": "Submit"}
                    ]

        # 4. Web Search (Fallback)
        if (clean_inst.startswith("search ") or clean_inst.startswith("google ")) and len(words) >= 2:
            query = clean_inst.replace("search", "").replace("google", "").strip()
            return [{"action": "search_web", "target": query, "query": query, "name": query}]

        # First decompose
        decomp = await self.decompose_intent(instruction, context_summary)

        sub_goals_raw = decomp.get("sub_goals", [instruction])

        # If the intent decomposition already generated a hardcoded action plan (e.g. clarification)
        if (
            sub_goals_raw
            and isinstance(sub_goals_raw[0], dict)
            and sub_goals_raw[0].get("action") == "speak"
        ):
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

        from src.action_library import action_registry

        system_prompt = PLANNER_SYSTEM_PROMPT.replace(
            "{DYNAMIC_STEP_TYPES}", action_registry.get_prompt_text()
        )

        if "[DEV_MODE:" in instruction:
            system_prompt += """
### DEVELOPER MODE UNLOCKED ###
You are now operating as an AI Software Engineer. You have direct access to the file system and terminal.
You may use the following exclusive Developer Actions:
- read_file: {"action": "read_file", "path": "absolute path to file"}
- write_file: {"action": "write_file", "path": "absolute path to file", "content": "exact code to write"}
- run_terminal: {"action": "run_terminal", "command": "bash/cmd string", "cwd": "absolute directory path"}
- search_knowledge_base: {"action": "search_knowledge_base", "query": "semantic query", "path": "absolute path to folder to scan"}
When asked to code, debug, or write scripts, USE THESE ACTIONS INSTEAD of opening VS Code via UI clicks.
"""
        elif "[STUDENT_MODE:" in instruction:

            url_match = re.search(r"\[STUDENT_MODE: (.*?)\]", instruction)
            url_context = (
                f"The user provided this URL/Path: {url_match.group(1)}"
                if url_match
                else ""
            )
            system_prompt += f"""
### STUDENT MODE UNLOCKED ###
You are now operating as an AI Tutor. {url_context}
You may use the following exclusive Student Actions:
- summarize_youtube: {{"action": "summarize_youtube", "url": "YouTube URL to extract transcript from"}}
- generate_study_html: {{"action": "generate_study_html", "path": "study.html", "html_content": "<html><body><h1>Study Guide</h1></body></html>"}}
- read_file: {{"action": "read_file", "path": "absolute path to document file"}}
- write_file: {{"action": "write_file", "path": "absolute path to save notes", "content": "notes content"}}
- search_knowledge_base: {{"action": "search_knowledge_base", "query": "semantic query", "path": "absolute path to folder to scan"}}
For 3D diagrams or quizzes, use `generate_study_html` to output a fully self-contained HTML document (e.g. using Three.js for 3D, or vanilla JS for a quiz).
"""

        if "[IMAGE_ATTACHED:" in instruction:
            from src.vision import ask_moondream

            match = re.search(r"\[IMAGE_ATTACHED: (.*?)\]", instruction)
            if match:
                img_path = match.group(1)
                logger.info(f"Analyzing attached image: {img_path}")
                try:
                    analysis = ask_moondream(
                        "Describe everything you see in this image in detail, including any text, code, errors, or UI elements.",
                        img_path,
                    )
                    system_prompt += f"\n\n### ATTACHED IMAGE ANALYSIS ###\nThe user attached an image to this prompt. The Moondream Vision Model analyzed it and reported the following:\n{analysis}\nUse this visual context to satisfy the user's request.\n"
                except Exception as e:
                    logger.warning(f"Failed to analyze attached image: {e}")

        full_prompt = (
            f"{system_prompt}\n\n"
            f"Context: {context_summary}\n"
            f"Target Sub-Goals: {sub_goals_str}\n"
            f"User Command: {instruction}\n"
            f"{dynamic_examples}\n"
            "CRITICAL BEHAVIOR RULES:\n"
            "1. Translate sub-goals into VALID actions. 'Paste' is NOT an action (use type_text or key_shortcut).\n"
            "2. DO NOT blindly copy sub-goals or output 'unknown' thought steps.\n"
            "3. If using an example from the skills list, you MUST REPLACE placeholders like <Prompt for Gemini> or <Video Name> with the ACTUAL text requested by the user. NEVER output literal '<...>' tags.\n"
            "4. You MUST use dedicated plugin macros when available.\n\n"
            "Output the JSON action plan array now:"
        )

        logger.info(f"Generating action plan for sub-goals: {sub_goals_str}")

        raw_results = await self.core.process_intent(
            full_prompt, {"voice_command": instruction}
        )
        plan = self._clean_and_extract(raw_results)

        # Ensure confidence scores exist and validate actions
        from src.action_library import action_registry
        for step in plan:
            action_name = step.get("action", "")
            if action_name not in action_registry.actions and action_name not in ["unknown", "dynamic_task", "open_app", "close_app", "key_shortcut", "type_text", "take_screenshot", "set_timer", "open_browser", "search_web", "wait_until", "semantic_copy"]:
                # If the LLM hallucinated an action, or output "unknown", force it to dynamic_task
                step["action"] = "dynamic_task"
                
            if step.get("action") == "unknown":
                step["action"] = "dynamic_task"

            if "confidence" not in step:
                step["confidence"] = 0.90
            if "anchor_check" not in step and "target" in step:
                step["anchor_check"] = f"Visible element: {step['target']}"

        logger.info(f"Plan generated successfully with {len(plan)} steps.")
        return plan

    async def replan_failed_step(
        self,
        failed_step: dict,
        error_reason: str,
        context_summary: str = "",
        ui_tree_snapshot: str = "",
    ) -> list:
        """Stage 4: Active Replanning Engine when execution or visual verification fails."""
        logger.warning(
            f"Replanning for failed step {failed_step.get('id', '?')}: {failed_step.get('action')} ({error_reason})"
        )

        from src.action_library import action_registry

        system_prompt = PLANNER_SYSTEM_PROMPT.replace(
            "{DYNAMIC_STEP_TYPES}", action_registry.get_prompt_text()
        )

        ui_snapshot_block = (
            f"Visual UI Snapshot (Buttons/Inputs on Screen):\n{ui_tree_snapshot}\n"
            if ui_tree_snapshot
            else ""
        )

        prompt = (
            f"{system_prompt}\n\n"
            f"REPLANNING REQUIRED!\n"
            f"The following step failed during execution:\n"
            f"Failed Step: {json.dumps(failed_step)}\n"
            f"Failure Reason: {error_reason}\n"
            f"Current OS Context: {context_summary}\n"
            f"{ui_snapshot_block}"
            "Provide an alternative 1-3 step JSON action recovery sequence to bypass this error and resume the task:"
        )

        raw_results = await self.core.process_intent(
            prompt, {"voice_command": f"Fix failed step {failed_step.get('action')}"}
        )
        recovery_plan = self._clean_and_extract(raw_results)

        logger.info(
            f"Recovery plan generated: {len(recovery_plan)} alternative step(s)."
        )
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

        logger.info(
            f"[Planner] Unknown action parsed, routing to dynamic_task."
        )
        return [{"action": "dynamic_task", "target": str(raw_data)}]


# Global Singleton & Backward Compatibility Function
planner_instance = MultiStagePlanner()


async def generate_plan(instruction: str, context_summary: str = "") -> list:
    """Backward compatible entry point for ARIA planner."""
    return await planner_instance.generate_action_plan(instruction, context_summary)


async def replan_failed_step(
    failed_step: dict,
    error_reason: str,
    context_summary: str = "",
    ui_tree_snapshot: str = "",
) -> list:
    """Backward compatible entry point for replanning."""
    return await planner_instance.replan_failed_step(
        failed_step, error_reason, context_summary, ui_tree_snapshot
    )


if __name__ == "__main__":
    p = MultiStagePlanner()
    print("Decomposition Test:", p.decompose_intent("Open Gemini and write a letter"))
