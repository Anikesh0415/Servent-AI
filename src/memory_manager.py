import os
import json
import time

MEMORY_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "long_term_memory.json")

class MemoryManager:
    """
    Unified Memory System for Servent-AI.
    Manages Working Memory, Task Memory, Action History, and Long-Term Persistent Memory.
    """
    def __init__(self, max_history_size: int = 50):
        self.max_history_size = max_history_size
        self.working_memory = {}
        self.task_memory = {
            "current_goal": "",
            "sub_goals": [],
            "plan_steps": [],
            "current_step_index": 0,
            "status": "idle"
        }
        self.action_history = []
        self.long_term_memory = self._load_long_term_memory()

    # --- WORKING MEMORY ---
    def set_working_value(self, key: str, value):
        """Stores a temporary key-value pair for the duration of a task session."""
        self.working_memory[key] = value

    def get_working_value(self, key: str, default=None):
        """Retrieves a working memory value."""
        return self.working_memory.get(key, default)

    def clear_working_memory(self):
        """Clears transient working memory."""
        self.working_memory = {}

    # --- TASK MEMORY ---
    def initialize_task(self, goal: str, plan_steps: list, sub_goals: list = None):
        """Initializes task memory with a new goal and plan."""
        self.clear_working_memory()
        self.task_memory = {
            "current_goal": goal,
            "sub_goals": sub_goals or [],
            "plan_steps": plan_steps,
            "current_step_index": 0,
            "status": "in_progress",
            "start_time": time.time()
        }

    def update_task_step(self, step_index: int, status: str = "executing"):
        """Updates the current step index and status."""
        self.task_memory["current_step_index"] = step_index
        self.task_memory["status"] = status

    def complete_task(self, success: bool = True):
        """Marks the current task as finished."""
        self.task_memory["status"] = "completed" if success else "failed"
        self.task_memory["end_time"] = time.time()

    # --- ACTION HISTORY ---
    def log_action(self, action_type: str, target: str, result: str, success: bool, verification_notes: str = ""):
        """Appends an executed action entry to rolling action history."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action_type,
            "target": target,
            "result": result,
            "success": success,
            "notes": verification_notes
        }
        self.action_history.append(entry)
        if len(self.action_history) > self.max_history_size:
            self.action_history.pop(0)

    def get_recent_history_context(self, limit: int = 5) -> list:
        """Returns the last `limit` action entries for planner context."""
        return self.action_history[-limit:]

    # --- LONG-TERM PERSISTENT MEMORY ---
    def _load_long_term_memory(self) -> dict:
        """Loads persistent memory from file or initializes defaults."""
        os.makedirs(os.path.dirname(MEMORY_FILE_PATH), exist_ok=True)
        if os.path.exists(MEMORY_FILE_PATH):
            try:
                with open(MEMORY_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[MemoryManager] Warning: failed to load long term memory ({e}). Resetting.")
        
        # Default long-term preferences
        return {
            "preferred_browser": "chrome",
            "frequent_apps": {
                "notepad": "notepad.exe",
                "vscode": "code",
                "calculator": "calc.exe"
            },
            "user_preferences": {
                "auto_confirm_safe_actions": True,
                "voice_speed": "normal"
            }
        }

    def save_long_term_memory(self):
        """Persists long-term memory to disk."""
        try:
            os.makedirs(os.path.dirname(MEMORY_FILE_PATH), exist_ok=True)
            with open(MEMORY_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.long_term_memory, f, indent=2)
        except Exception as e:
            print(f"[MemoryManager] Error saving long term memory: {e}")

    def update_preference(self, category: str, key: str, value):
        """Updates a preference and saves to disk."""
        if category not in self.long_term_memory:
            self.long_term_memory[category] = {}
        self.long_term_memory[category][key] = value
        self.save_long_term_memory()


if __name__ == "__main__":
    mm = MemoryManager()
    mm.initialize_task("Test Goal", [{"action": "open_app", "name": "notepad"}])
    mm.log_action("open_app", "notepad", "Opened via Run", True)
    print("Action History:", mm.get_recent_history_context())
