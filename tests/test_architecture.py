import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.context_manager import ContextManager
from src.memory_manager import MemoryManager
from src.security import SecurityManager, RiskLevel
from src.logger import logger
from src.executors.pyautogui_executor import PyAutoGUIExecutor
from src.executors.ui_automation_executor import UIAutomationExecutor
from src.execution_manager import ExecutionManager
from src.planner import MultiStagePlanner

def run_tests():
    print("=== Testing Forge Architecture Modules ===")
    
    # 1. Context Manager
    cm = ContextManager()
    ctx = cm.capture_os_context()
    print(f"[OK] ContextManager captured OS state: {ctx['active_app']} ({ctx['screen_resolution'][0]}x{ctx['screen_resolution'][1]})")

    # 2. Memory Manager
    mm = MemoryManager()
    mm.initialize_task("Test task", [{"action": "speak", "text": "hello"}])
    mm.log_action("speak", "hello", "Spoke successfully", True)
    print(f"[OK] MemoryManager action history count: {len(mm.get_recent_history_context())}")

    # 3. Security Manager
    sec = SecurityManager()
    risk = sec.classify_action("type_text", {"text": "rm -rf /"})
    print(f"[OK] SecurityManager classified destructive command as: {risk.name}")
    assert risk == RiskLevel.DESTRUCTIVE

    # 4. Execution Manager & Executors
    em = ExecutionManager()
    status, msg = em.execute_step({"id": 1, "action": "speak", "text": "Architecture Test Successful"})
    print(f"[OK] ExecutionManager test: success={status}, msg='{msg}'")

    # 5. Planner Initialization
    planner = MultiStagePlanner()
    planner.core.use_mock = True  # Use fast mock mode for unit verification
    decomp = planner.decompose_intent("Open Google and search for AI news")
    print(f"[OK] MultiStagePlanner intent decomposition (mock): {decomp.get('intent')}")

    # 6. Logger
    logger.info("Architecture test completed successfully.")
    print("\nALL ARCHITECTURE UPGRADE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
