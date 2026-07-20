import time
from src.planner import generate_plan, replan_failed_step, planner_instance
from src.vision import verify_anchor, smart_wait_for_completion, preflight_check
from src.context_manager import ContextManager
from src.memory_manager import MemoryManager
from src.execution_manager import ExecutionManager
from src.logger import logger
from src.macro_orchestrator import macro_orchestrator

# Configuration Constants
ACTION_PAUSE         = 0.5   # seconds after standard actions
APP_OPEN_WAIT        = 2.0   # seconds before first anchor check on app open
OPEN_APP_MAX_RETRIES = 3     # retry count for page/app load anchors
OPEN_APP_RETRY_DELAY = 2.0   # seconds between retries

context_mgr = ContextManager()
memory_mgr  = MemoryManager()
exec_mgr    = ExecutionManager()


def plan_task(instruction: str, update_callback=None) -> list:
    """
    Generates the ARIA plan using multi-stage planning and OS context.
    """
    def notify(msg: str):
        logger.info(f"[Agent Planner] {msg}")
        if update_callback:
            update_callback(msg)

    notify(f"Analyzing instruction: '{instruction}'...")

    # Get active OS context summary for planner
    ctx_summary = context_mgr.get_summary_prompt_context()
    plan = planner_instance.generate_action_plan(instruction, ctx_summary)

    # Re-plan if too few steps for complex requests
    complex_kw = ["and", "then", "copy", "send", "open", "paste"]
    is_complex = any(kw in instruction.lower() for kw in complex_kw)
    
    if plan and is_complex and len(plan) < 4:
        notify(f"⚠️ Only {len(plan)} steps generated for complex task — re-planning stricter...")
        plan = planner_instance.generate_action_plan(
            instruction + " [IMPORTANT: This requires multiple apps/actions, list ALL steps]",
            ctx_summary
        )

    if not plan:
        notify("ARIA failed to generate a plan.")
        return []

    # Store plan in memory
    memory_mgr.initialize_task(instruction, plan)

    notify(f"ARIA plan generated: {len(plan)} step(s).")
    return plan


def execute_task_plan(plan: list, update_callback=None) -> bool:
    """
    Executes the generated ARIA plan using the Observe -> Execute -> Verify -> Reflect -> Replan loop.
    """
    def notify(msg: str):
        logger.info(f"[Agent Loop] {msg}")
        if update_callback:
            update_callback(msg)

    if not plan:
        notify("No plan to execute.")
        return False

    notify(f"Starting execution of {len(plan)} step(s)...")

    for idx, step in enumerate(plan):
        action_type  = step.get("action", "").lower()
        target       = step.get("target") or step.get("name") or step.get("url") or ""
        anchor_check = step.get("anchor_check", "")

        memory_mgr.update_task_step(idx, status="executing")
        notify(f"Step {idx+1}/{len(plan)}: {action_type} ({target})")

        # ── 1. OBSERVE & PREFLIGHT ──────────────────────────────────────────
        pre_res = preflight_check(target)
        if not pre_res["clear_to_proceed"]:
            notify(f"⚠️ Preflight Warning: {pre_res['popup_description']}")

        # ── 1.5. SAFETY GUARDRAIL ───────────────────────────────────────────
        def is_safe_action(action: str, tgt: str) -> bool:
            if action in ["type_text", "key_shortcut"]:
                blacklist = ["del ", "format ", "rmdir", "rd /s", "powershell -enc", "reg add", "net user", "drop table"]
                if any(bad in tgt.lower() for bad in blacklist):
                    return False
            return True
            
        if not is_safe_action(action_type, target):
            notify(f"🛑 SECURITY ALERT: Blocked destructive action '{target}'")
            memory_mgr.log_action(action_type, str(target), "Blocked by Safety Guardrail", False)
            memory_mgr.complete_task(success=False)
            return False

        # ── 2. EXECUTE ──────────────────────────────────────────────────────
        try:
            success, exec_msg = exec_mgr.execute_step(step)
        except Exception as e:
            success, exec_msg = False, f"Crash during execution: {e}"
            
        if not success:
            notify(f"Action execution warning: {exec_msg}")
        elif action_type.startswith("background_") or action_type == "summarize_youtube":
            notify(f"Result: {exec_msg}")

        # ── 3. VERIFY ───────────────────────────────────────────────────────
        NO_VERIFY = {"scroll", "copy_all", "paste", "speak", "wait_until", "hover_element", "read_file", "write_file", "run_terminal", "summarize_youtube", "generate_study_html", "search_knowledge_base"}
        if action_type in NO_VERIFY or not anchor_check:
            time.sleep(ACTION_PAUSE)
            memory_mgr.log_action(action_type, str(target), exec_msg, True, "No verification needed")
            continue

        if action_type in {"open_app", "open_browser"}:
            notify(f"Waiting {APP_OPEN_WAIT}s for page/app to load...")
            time.sleep(APP_OPEN_WAIT)
            max_retries = OPEN_APP_MAX_RETRIES
        else:
            time.sleep(ACTION_PAUSE)
            max_retries = 1

        verified = False
        
        for attempt in range(max_retries):
            notify(f"VISTA anchor check (attempt {attempt+1}/{max_retries}): '{anchor_check}'")
            try:
                anchor_met = verify_anchor(anchor_check)
            except Exception as e:
                notify(f"VISTA check crashed: {e}")
                anchor_met = False
                
            if anchor_met:
                notify("Anchor confirmed ✓")
                verified = True
                memory_mgr.log_action(action_type, str(target), exec_msg, True, "Anchor confirmed")
                break
            else:
                if attempt < max_retries - 1:
                    notify(f"Anchor not yet visible, retrying in {OPEN_APP_RETRY_DELAY}s...")
                    time.sleep(OPEN_APP_RETRY_DELAY)
                    try:
                        exec_mgr.execute_step(step)
                    except Exception:
                        pass

        # ── 4. REFLECT & REPLAN ─────────────────────────────────────────────
        if not verified:
            notify(f"Step {idx+1} verification failed. Initiating Reflection & Replanning...")
            error_reason = f"Anchor check '{anchor_check}' was not met."
            
            ctx_summary = context_mgr.get_summary_prompt_context()
            ui_tree_snapshot = context_mgr.capture_ui_accessibility_tree()
            
            notify(f"UI Snapshot captured: {len(ui_tree_snapshot)} chars. Generating recovery plan...")
            recovery_plan = replan_failed_step(step, error_reason, ctx_summary, ui_tree_snapshot)
            
            if recovery_plan:
                notify(f"Executing {len(recovery_plan)} recovery step(s)...")
                for rec_step in recovery_plan:
                    rec_action = rec_step.get("action", "").lower()
                    notify(f"Recovery Step: {rec_action}")
                    try:
                        rec_success, rec_msg = exec_mgr.execute_step(rec_step)
                        if not rec_success:
                            notify(f"Recovery step failed: {rec_msg}")
                            break # Cascade failure, stop recovery
                    except Exception as e:
                        notify(f"Recovery step crashed: {e}")
                        break
                    time.sleep(1.0)
                
                # Final check after recovery
                try:
                    if verify_anchor(anchor_check):
                        notify("Recovery successful! Anchor confirmed ✓")
                        verified = True
                except Exception as e:
                    notify(f"VISTA check crashed during recovery: {e}")
            
        if not verified:
            notify(f"Task stopped: Step {idx+1} could not be verified.")
            memory_mgr.complete_task(success=False)
            return False

    notify("Plan execution completed successfully.")
    return True


def run_autonomous_agent(instruction: str, update_callback=None) -> bool:
    """
    The top-level entry point. Uses MacroOrchestrator to break down massive prompts.
    """
    def notify(msg: str):
        logger.info(f"[Macro Orchestrator] {msg}")
        if update_callback:
            update_callback(msg)

    notify("Checking if instruction requires Macro Loop Orchestration...")
    macro_plan = macro_orchestrator.analyze_instruction(instruction)
    
    if macro_plan.get("is_loop"):
        iterations = macro_plan.get("iterations", 1)
        notify(f"🚀 MASIVE LOOP DETECTED! Iterations: {iterations}")
        
        # 1. Setup Phase
        setup_task = macro_plan.get("setup_instructions")
        if setup_task:
            notify(f"Phase 1/3: Running Setup -> {setup_task}")
            setup_plan = plan_task(setup_task, update_callback)
            if not execute_task_plan(setup_plan, update_callback):
                notify("Setup failed. Aborting Macro.")
                return False
                
        # 2. Loop Phase
        loop_task = macro_plan.get("loop_instructions")
        if loop_task:
            notify(f"Phase 2/3: Executing Loop {iterations} times...")
            for i in range(iterations):
                notify(f"--- LOOP ITERATION {i+1} OF {iterations} ---")
                iter_plan = plan_task(loop_task, update_callback)
                if not execute_task_plan(iter_plan, update_callback):
                    notify(f"Loop iteration {i+1} failed! Attempting to continue next iteration...")
                    # In a real system, you might break or retry, but let's continue to be robust
                    
        # 3. Teardown Phase
        teardown_task = macro_plan.get("teardown_instructions")
        if teardown_task:
            notify(f"Phase 3/3: Running Teardown -> {teardown_task}")
            teardown_plan = plan_task(teardown_task, update_callback)
            execute_task_plan(teardown_plan, update_callback)
            
        notify("✅ Macro Orchestration Completed Successfully!")
        return True

    else:
        notify("Standard linear task detected. Routing to standard planner.")
        plan = plan_task(instruction, update_callback)
        return execute_task_plan(plan, update_callback)



def execute_react_loop(instruction: str, update_callback=None):
    """
    Executes the full ReAct loop for backward compatibility.
    """
    plan = plan_task(instruction, update_callback)
    if not plan:
        return
    execute_task_plan(plan, update_callback)


def trigger_self_healing_learning() -> str:
    """
    Exposed hook for the UI's `/learn` slash command.
    Tells the MemoryManager to compile the last successful task into a permanent skill.
    """
    result = memory_mgr.compile_learned_skill()
    logger.info(f"Self-Healing Triggered: {result}")
    return result


if __name__ == "__main__":
    execute_react_loop("open browser to google.com")
