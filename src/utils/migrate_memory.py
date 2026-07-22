import os
import json
import uuid
import sys

# Ensure src is accessible
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)

from src.utils.skill_retriever import retriever
from src.logger import logger

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)
SKILLS_FILE = os.path.join(DATA_DIR, "skills.json")


def migrate_skills():
    """
    Migrates legacy JSON skills into ChromaDB vector memory.
    """
    logger.info("Starting Semantic Memory Migration check...")

    if not retriever.collection:
        logger.error("ChromaDB collection is not available. Aborting migration.")
        return

    try:
        count = retriever.collection.count()
        if count > 0:
            logger.info(
                f"ChromaDB already populated with {count} skills. Skipping migration."
            )
            return

        if not os.path.exists(SKILLS_FILE):
            logger.info("No legacy skills.json found. Skipping migration.")
            return

        with open(SKILLS_FILE, "r", encoding="utf-8") as f:
            skills = json.load(f)

        if not skills:
            logger.info("Legacy skills.json is empty. Skipping migration.")
            return

        logger.info(
            f"Found {len(skills)} legacy skills. Indexing into Semantic Memory (ChromaDB)..."
        )

        docs = []
        metas = []
        ids = []

        for skill in skills:
            docs.append(skill.get("example_sequence", ""))
            metas.append({"description": skill.get("description", "Action Sequence")})
            ids.append(str(uuid.uuid4()))

        retriever.collection.add(documents=docs, metadatas=metas, ids=ids)

        logger.info(
            f"Successfully migrated {len(skills)} skills into ChromaDB Vector Space."
        )

    except Exception as e:
        logger.error(f"Migration failed: {e}")


if __name__ == "__main__":
    migrate_skills()
