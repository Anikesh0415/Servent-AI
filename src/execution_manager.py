import time
from typing import Dict, Any, Tuple, List

from src.executors.pyautogui_executor import PyAutoGUIExecutor
from src.executors.ui_automation_executor import UIAutomationExecutor
from src.executors.dev_executor import DevExecutor
from src.executors.student_executor import StudentExecutor
from src.executors.headless_executor import HeadlessExecutor
from src.logger import logger
from src.security import SecurityManager


class ExecutionManager:
    """
    Central Execution Manager for Forge.
    Coordinates execution backends (UIAutomation -> PyAutoGUI fallback).
    Enforces security checks and structured action logging.
    """

    def __init__(self, security_manager=None) -> None:
        self.executors: List[Any] = [
            HeadlessExecutor(),
            StudentExecutor(),  # Try student execution first
            DevExecutor(),  # Then developer execution
            UIAutomationExecutor(),
            PyAutoGUIExecutor(),
        ]
        self.security: SecurityManager = (
            security_manager if security_manager else SecurityManager(safe_mode=True)
        )

    async def execute_step(self, step_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Executes a single action step with backend fallback and risk logging.

        Args:
            step_data (Dict[str, Any]): The JSON payload containing action details.

        Returns:
            Tuple[bool, str]: A tuple containing execution success state and a descriptive message.
        """
        import asyncio
        import inspect

        action_type = step_data.get("action", "").lower()
        target = (
            step_data.get("target")
            or step_data.get("query")
            or step_data.get("url")
            or step_data.get("name")
            or step_data.get("text")
            or ""
        )
        step_id = step_data.get("id", 0)

        # 1. Security Risk Assessment
        risk_level = self.security.classify_action(action_type, step_data)
        logger.info(
            f"Executing Step [{step_id}] {action_type} (Risk: {risk_level.name}) | Target: '{target}'"
        )

        start_time = time.time()
        success = False
        result_msg = ""

        # 2. Try Executors in Priority Order
        for executor in self.executors:
            if executor.can_handle(action_type, step_data):
                try:
                    if inspect.iscoroutinefunction(executor.execute):
                        success, result_msg = await executor.execute(
                            action_type, step_data
                        )
                    else:
                        # Offload blocking GUI/System calls to thread
                        success, result_msg = await asyncio.to_thread(
                            executor.execute, action_type, step_data
                        )

                    if success:
                        logger.info(
                            f"Step [{step_id}] succeeded via {executor.name}: {result_msg}"
                        )
                        break
                    else:
                        logger.warning(
                            f"{executor.name} failed step [{step_id}]: {result_msg}. Trying fallback..."
                        )
                except Exception as e:
                    logger.warning(f"Exception in {executor.name} ({e})")

        duration = time.time() - start_time
        logger.log_action_execution(
            step_id, action_type, str(target), success, duration, {"msg": result_msg}
        )

        return success, result_msg


if __name__ == "__main__":
    em = ExecutionManager()
    status, msg = em.execute_step(
        {"id": 1, "action": "speak", "text": "Testing Execution Manager"}
    )
    print("Execution Result:", status, msg)
