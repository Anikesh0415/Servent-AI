import time
from src.planner import generate_plan
from src.action_library import open_app_action, type_action, key_action, click_action, scroll_action
from src.vision import verify_action_success

def execute_react_loop(instruction: str, update_callback=None):
    """
    Executes the full ReAct loop for a given instruction.
    1. Plan (ARIA)
    2. Act -> Verify (VISTA) -> Loop
    """
    def notify(msg):
        print(f"[Agent Loop] {msg}")
        if update_callback:
            update_callback(msg)
            
    notify(f"Thinking about: '{instruction}'...")
    
    # 1. PLAN Phase
    plan = generate_plan(instruction)
    
    if not plan:
        notify("Failed to generate a plan.")
        return
        
    notify(f"ARIA generated plan with {len(plan)} steps.")
    
    # 2. EXECUTE Phase
    for step_idx, step in enumerate(plan):
        action_type = step.get("action")
        action_desc = str(step)
        
        notify(f"Step {step_idx+1}/{len(plan)}: Executing {action_type}...")
        
        # Execute action
        try:
            if action_type == "open_app":
                open_app_action(step.get("app", ""))
            elif action_type == "type":
                type_action(step.get("text", ""))
            elif action_type == "key":
                key_action(step.get("key", ""))
            elif action_type == "click":
                click_action(step.get("x", 0), step.get("y", 0))
            elif action_type == "scroll":
                scroll_action(step.get("amount", 0))
            else:
                notify(f"Unknown action: {action_type}")
                continue
        except Exception as e:
            notify(f"Action failed: {e}")
            continue
            
        # Give the UI time to update before capturing screen
        time.sleep(1.0)
        
        # 3. VERIFY Phase (VISTA) - OPTIMIZATION: Only verify open_app
        # Running VISTA takes ~8s per step, so we skip it for everything else to ensure instant response.
        if action_type not in ["open_app"]:
            notify(f"Skipping VISTA verification for instant action: {action_type}")
            continue
            
        notify(f"Verifying {action_type} with VISTA (Takes ~8s)...")
        
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            is_success = verify_action_success(action_desc)
            if is_success:
                success = True
                notify(f"Step {step_idx+1} verified successfully.")
                break
            else:
                if attempt < max_retries - 1:
                    notify(f"Verification failed (Attempt {attempt+1}/{max_retries}). Retrying in 2s...")
                    time.sleep(2)
        
        if not success:
            notify(f"Warning: Step {step_idx+1} could not be verified by VISTA. Proceeding anyway...")
            
    notify("Task execution complete.")

if __name__ == "__main__":
    execute_react_loop("open youtube")
