import os
import subprocess
from src.logger import logger

class DevExecutor:
    """
    Execution backend for Developer Mode (Coding Assistant Capabilities).
    Allows Servent-AI to read/write code files and execute terminal commands.
    """
    def __init__(self):
        self.name = "DevExecutor"

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        supported = ["read_file", "write_file", "run_terminal"]
        return action_type.lower() in supported

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        action_type = action_type.lower()

        if action_type == "read_file":
            filepath = step_data.get("path", "")
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                # Truncate content to avoid blowing up memory/logs if file is massive
                if len(content) > 10000:
                    content = content[:10000] + "\n...[TRUNCATED]"
                return True, f"File contents:\n{content}"
            except Exception as e:
                return False, f"Failed to read file: {e}"

        elif action_type == "write_file":
            filepath = step_data.get("path", "")
            content = step_data.get("content", "")
            try:
                # Create directories if they don't exist
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, f"Successfully wrote to {filepath}"
            except Exception as e:
                return False, f"Failed to write file: {e}"

        elif action_type == "run_terminal":
            command = step_data.get("command", "")
            cwd = step_data.get("cwd", os.getcwd())
            try:
                logger.info(f"[DevExecutor] Running command: {command} in {cwd}")
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30 # Prevent hanging commands
                )
                output = result.stdout if result.stdout else result.stderr
                if len(output) > 5000:
                    output = output[-5000:] + "\n...[TRUNCATED]"
                if result.returncode == 0:
                    return True, f"Command successful:\n{output}"
                else:
                    return False, f"Command failed (Code {result.returncode}):\n{output}"
            except subprocess.TimeoutExpired:
                return False, "Command timed out after 30 seconds."
            except Exception as e:
                return False, f"Terminal error: {e}"

        return False, f"Unknown dev action: {action_type}"
