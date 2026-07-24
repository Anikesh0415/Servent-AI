import os
import json
import time

MEMORY_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "long_term_memory.json"
)


class MemoryManager:
    """
    Unified Memory System for Forge.
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
            "status": "idle",
        }
        self.action_history = []
        self.long_term_memory = self._load_long_term_memory()

        # BIO-ORGANOID INTEGRATION
        self.use_bio_engine = False
        self.bio_weights = {}
        try:
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
                    print(f"[Bio-Engine] Neuromorphic Memory Enabled. tau={self.bio_weights.get('ltp_decay_tau_days')} days")
        except Exception as e:
            print(f"[Bio-Engine] Failed to load bio engine configs: {e}")

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
            "start_time": time.time(),
        }
        self.abort_flag = False

    def update_task_step(self, step_index: int, status: str = "executing"):
        """Updates the current step index and status."""
        self.task_memory["current_step_index"] = step_index
        self.task_memory["status"] = status

    def complete_task(self, success: bool = True):
        """Marks the current task as finished."""
        self.task_memory["status"] = "completed" if success else "failed"
        self.task_memory["end_time"] = time.time()

    # --- ACTION HISTORY ---
    def log_action(
        self,
        action_type: str,
        target: str,
        result: str,
        success: bool,
        verification_notes: str = "",
    ):
        """Appends an executed action entry to rolling action history."""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action_type,
            "target": target,
            "result": result,
            "success": success,
            "notes": verification_notes,
        }
        self.action_history.append(entry)

        with open("logs/audit.log", "a", encoding="utf-8") as f:
            f.write(
                f"[{entry['timestamp']}] {action_type} -> {target} | Success: {success} | Note: {verification_notes}\n"
            )

        if len(self.action_history) > self.max_history_size:
            self.action_history.pop(0)

    def get_recent_history_context(self, limit: int = 5) -> list:
        """Returns the last `limit` action entries for planner context."""
        history = self.action_history[-limit:]

        if self.use_bio_engine and self.bio_weights:
            import datetime
            import math
            current_time = datetime.datetime.now()
            tau_days = self.bio_weights.get("ltp_decay_tau_days", 1.0)
            
            decayed_history = []
            for entry in history:
                entry_time = datetime.datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
                days_old = (current_time - entry_time).total_seconds() / 86400.0
                
                # Biological exponential decay: e^(-t / tau)
                retention_strength = math.exp(-days_old / tau_days)
                
                # If memory is weaker than 10%, we prune it (organoid forgets)
                if retention_strength > 0.1:
                    entry_copy = entry.copy()
                    entry_copy["synaptic_weight"] = round(retention_strength, 4)
                    decayed_history.append(entry_copy)
                else:
                    print(f"[Bio-Engine] Pruned weak memory from context (weight < 0.1): {entry['action']}")
                    
            return decayed_history

        return history

    # --- LONG-TERM PERSISTENT MEMORY ---
    def _load_long_term_memory(self) -> dict:
        """Loads persistent memory from file or initializes defaults."""
        os.makedirs(os.path.dirname(MEMORY_FILE_PATH), exist_ok=True)
        if os.path.exists(MEMORY_FILE_PATH):
            try:
                with open(MEMORY_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(
                    f"[MemoryManager] Warning: failed to load long term memory ({e}). Resetting."
                )

        # Default long-term preferences
        return {
            "preferred_browser": "chrome",
            "frequent_apps": {
                "notepad": "notepad.exe",
                "vscode": "code",
                "calculator": "calc.exe",
            },
            "user_preferences": {
                "auto_confirm_safe_actions": True,
                "voice_speed": "normal",
            },
            "episodic_facts": [],
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

    def add_episodic_fact(self, fact: str):
        """Adds a verified user fact to episodic memory."""
        if "episodic_facts" not in self.long_term_memory:
            self.long_term_memory["episodic_facts"] = []
        if fact not in self.long_term_memory["episodic_facts"]:
            self.long_term_memory["episodic_facts"].append(fact)
            self.save_long_term_memory()

    def compile_learned_skill(self) -> str:
        """
        Self-Healing Memory: Compiles the currently successful task plan into a new reusable
        skill block and appends it to data/skills.json automatically!
        """
        goal = self.task_memory.get("current_goal")
        steps = self.task_memory.get("plan_steps", [])
        if not goal or not steps:
            return "No valid goal or steps to compile."

        skill_file = os.path.join(
            os.path.dirname(__file__), "..", "data", "skills.json"
        )
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                skills_db = json.load(f)
        except Exception as e:
            return f"Failed to load skills DB: {e}"

        # Build example sequence
        seq_lines = [f"When asked to {goal.lower()}, generate this exact sequence:"]
        for idx, step in enumerate(steps, 1):
            # Clean step of runtime IDs to make it a generic template
            clean_step = {
                k: v
                for k, v in step.items()
                if k not in ["id", "confidence", "anchor_check", "description"]
            }
            seq_lines.append(f"{idx}. {json.dumps(clean_step)}")

        new_skill = {
            "keywords": [goal.split()[0].lower(), "auto-learned", goal.lower()],
            "description": f"Auto-learned skill for: {goal}",
            "example_sequence": "\n".join(seq_lines),
        }

        skills_db.append(new_skill)

        try:
            with open(skill_file, "w", encoding="utf-8") as f:
                json.dump(skills_db, f, indent=4)

            # Add to Vector Database for Semantic Memory
            try:
                from src.utils.skill_retriever import retriever

                if retriever.collection:
                    import uuid

                    doc_id = str(uuid.uuid4())
                    retriever.collection.add(
                        documents=[new_skill["example_sequence"]],
                        metadatas=[{"description": new_skill["description"]}],
                        ids=[doc_id],
                    )
            except Exception as e:
                print(f"[MemoryManager] Failed to add skill to ChromaDB: {e}")

            return f"Successfully learned and saved new skill for: '{goal}'"
        except Exception as e:
            return f"Error saving new skill: {e}"


if __name__ == "__main__":
    mm = MemoryManager()
    mm.initialize_task("Test Goal", [{"action": "open_app", "name": "notepad"}])
    mm.log_action("open_app", "notepad", "Opened via Run", True)
    print("Action History:", mm.get_recent_history_context())
