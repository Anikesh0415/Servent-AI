import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "nova_memory.db")


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS task_genomes 
                   (task_desc TEXT PRIMARY KEY, ctg_json TEXT, avg_duration REAL)""")
    conn.commit()


_init_db()


def text_similarity(t1: str, t2: str) -> float:
    w1 = set(t1.lower().split())
    w2 = set(t2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def save_task_genome(task_desc: str, ctg: dict, duration: float):
    """Save successful task as reusable genome"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO task_genomes
        (task_desc, ctg_json, avg_duration) VALUES (?, ?, ?)""",
        (task_desc, json.dumps(ctg), duration),
    )
    conn.commit()
    print(f"✅ Genome saved: {task_desc} in {duration:.1f}s")


def load_task_genome(task_desc: str) -> dict:
    """Find matching genome for instant execution"""
    conn = sqlite3.connect(DB_PATH)
    genomes = conn.execute("SELECT task_desc, ctg_json FROM task_genomes").fetchall()

    for stored_desc, ctg_json in genomes:
        if text_similarity(task_desc, stored_desc) > 0.75:
            print(f"⚡ Genome match → skipping planning")
            return json.loads(ctg_json)
    return None
