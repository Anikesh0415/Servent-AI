import time
from src.planner import generate_plan
from src.action_library import (
    open_app, navigate_browser,
    type_action, key_action,
    click_action, scroll_action,
    copy_all, paste_action,
)
from src.vision import verify_anchor, smart_wait_for_completion

# How long to wait after open_app before starting verification
APP_OPEN_WAIT  = 3.0   # seconds — enough for a browser tab to appear
# How long to wait after any instant action before the next step
ACTION_PAUSE   = 0.3   # seconds

# For open_app, VISTA will retry verification up to this many times
OPEN_APP_MAX_RETRIES = 3
OPEN_APP_RETRY_DELAY = 2.0   # seconds between retries


def execute_react_loop(instruction: str, update_callback=None):
    """
    Executes the full ReAct loop:
      Plan (ARIA) → Act → Anchor-Verify (VISTA) → loop

    Verification strategy (Phase 4):
      - open_app / navigate_browser : VISTA checks the anchor up to 3×,
                                      waits between retries (page may still load).
      - type / key                  : VISTA checks anchor ONCE, then moves on.
      - copy_all / paste / click … : skipped — these are instant & unambiguous.
    """
    def notify(msg: str):
        print(f"[Agent Loop] {msg}")
        if update_callback:
            update_callback(msg)

    notify(f"Thinking about: '{instruction}'...")

    # ── 1. PLAN ────────────────────────────────────────────────────────────
    plan = generate_plan(instruction)

    # CRITICAL CHECK: re-plan if too few steps
    complex_kw = ["and", "then", "copy", "send", "open", "paste"]
    is_complex = any(kw in instruction.lower() for kw in complex_kw)
    
    if plan and is_complex and len(plan) < 4:
        notify(f"⚠️ Only {len(plan)} steps generated for complex task — re-planning stricter...")
        plan = generate_plan(instruction + " [IMPORTANT: This requires multiple apps/actions, list ALL steps]")

    if not plan:
        notify("ARIA failed to generate a plan. Aborting.")
        return

    notify(f"ARIA plan: {len(plan)} step(s).")

    # ── 2. EXECUTE + VERIFY ────────────────────────────────────────────────
    for idx, step in enumerate(plan):
        action_type  = step.get("action", "").lower()
        anchor_check = step.get("anchor_check", "")   # Phase 4 anchor

        notify(f"Step {idx+1}/{len(plan)}: {action_type}")

        # ── ACT ────────────────────────────────────────────────────────────
        try:
            if action_type == "open_app":
                open_app(step.get("app", ""))

            elif action_type == "navigate_browser":
                navigate_browser(step.get("url", ""))

            elif action_type == "type":
                type_action(step.get("text", ""))

            elif action_type == "key":
                key_action(step.get("key", ""))

            elif action_type == "click":
                click_action(step.get("x", 0), step.get("y", 0))

            elif action_type == "scroll":
                scroll_action(step.get("amount", 0))

            elif action_type == "copy_all":
                copy_all()

            elif action_type == "paste":
                paste_action()

            elif action_type == "wait_until":
                condition = step.get("condition", "")
                if condition:
                    notify(f"Waiting for condition: '{condition}'...")
                    success = smart_wait_for_completion(condition)
                    if not success:
                        notify(f"Wait timeout for: {condition}")
                        return
                    continue # Skip anchor verify since wait handles it

            elif action_type == "speak":
                text = step.get("text", "")
                notify(f"Speaking: {text}")
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass

            else:
                notify(f"Unknown action '{action_type}' — skipping.")
                continue

        except Exception as e:
            notify(f"Action raised an exception: {e}")
            continue

        # ── VERIFY (Phase 4: anchor-based) ─────────────────────────────────

        # Actions that need no verification — they are instant and deterministic
        NO_VERIFY = {"scroll", "copy_all", "paste", "click", "speak", "wait_until"}
        if action_type in NO_VERIFY or not anchor_check:
            time.sleep(ACTION_PAUSE)
            continue

        # For page-loading actions: give the OS a head-start before asking VISTA
        if action_type in {"open_app", "navigate_browser"}:
            notify(f"Waiting {APP_OPEN_WAIT}s for page/app to load...")
            time.sleep(APP_OPEN_WAIT)
            max_retries = OPEN_APP_MAX_RETRIES
        else:
            # For type / key: short pause, single check
            time.sleep(ACTION_PAUSE)
            max_retries = 1

        # Run anchor verification
        verified = False
        
        # New Retry Logic from Fix #2
        for attempt in range(max_retries):
            notify(f"VISTA anchor check (attempt {attempt+1}/{max_retries}): '{anchor_check}'")
            if verify_anchor(anchor_check):
                notify(f"Anchor confirmed ✓")
                verified = True
                break
            else:
                if attempt < max_retries - 1:
                    notify(f"Anchor not yet visible, retrying in {OPEN_APP_RETRY_DELAY}s...")
                    time.sleep(OPEN_APP_RETRY_DELAY)
                    
                    # Re-execute action on retry
                    notify(f"Re-executing action: {action_type}")
                    try:
                        if action_type == "open_app":
                            open_app(step.get("app", ""))
                        elif action_type == "navigate_browser":
                            navigate_browser(step.get("url", ""))
                        elif action_type == "type":
                            type_action(step.get("text", ""))
                        elif action_type == "key":
                            key_action(step.get("key", ""))
                        elif action_type == "click":
                            click_action(step.get("x", 0), step.get("y", 0))
                        elif action_type == "scroll":
                            scroll_action(step.get("amount", 0))
                    except Exception as e:
                        notify(f"Retry execution failed: {e}")

        if not verified:
            notify(f"Step {idx+1} failed after {max_retries} retries. Task paused.")
            return

    notify("Task complete.")


if __name__ == "__main__":
    execute_react_loop("open youtube and search for lo-fi music")
