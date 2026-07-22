import json
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "nova_memory.db")


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS task_graphs 
                   (task_desc TEXT PRIMARY KEY, graph TEXT)""")
    conn.commit()


_init_db()


def find_matching_graph(task_description: str) -> dict:
    """Check if we've done a similar task before"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT task_desc, graph FROM task_graphs").fetchall()

    best_match, best_score = None, 0
    for row in rows:
        stored_words = set(row[0].lower().split())
        task_words = set(task_description.lower().split())
        score = len(stored_words & task_words) / len(stored_words | task_words)
        if score > 0.7 and score > best_score:
            best_match, best_score = row, score

    if best_match:
        return json.loads(best_match[1])  # Return cached graph
    return None


def save_graph(task: str, graph: dict, duration: float):
    """Save successful task graph"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO task_graphs 
                   (task_desc, graph) VALUES (?,?)""",
        (task, json.dumps(graph)),
    )
    conn.commit()
