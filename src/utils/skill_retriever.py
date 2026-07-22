import os
import chromadb
from src.logger import logger

# Paths
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
)
SKILLS_FILE = os.path.join(DATA_DIR, "skills.json")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")


class SkillRetriever:
    def __init__(self):
        os.makedirs(CHROMA_DIR, exist_ok=True)
        try:
            self.client = chromadb.PersistentClient(path=CHROMA_DIR)
            self.collection = self.client.get_or_create_collection(name="forge_skills")
            logger.info("ChromaDB initialized for semantic skill retrieval.")
        except Exception as e:
            logger.error(f"[SkillRetriever] Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    def get_relevant_examples(self, instruction: str, max_examples: int = 2) -> str:
        """
        Retrieves the most relevant skill examples using Vector/Semantic search.
        """
        if not self.collection:
            logger.warning(
                "[SkillRetriever] ChromaDB not available, falling back to empty examples."
            )
            return ""

        try:
            # Check if collection is empty
            if self.collection.count() == 0:
                return ""

            results = self.collection.query(
                query_texts=[instruction],
                n_results=min(max_examples, self.collection.count()),
            )

            if not results["documents"] or not results["documents"][0]:
                return ""

            injection = "\nRELEVANT SKILL EXAMPLES (SEMANTIC MATCH):\n"
            for idx, doc in enumerate(results["documents"][0]):
                # the document itself will be the sequence string
                meta = (
                    results["metadatas"][0][idx]
                    if results["metadatas"] and results["metadatas"][0]
                    else {}
                )
                desc = meta.get("description", "Action Sequence")
                injection += f"--- Example {idx+1}: {desc} ---\n"
                injection += f"{doc}\n\n"

            return injection
        except Exception as e:
            logger.error(f"[SkillRetriever] Query failed: {e}")
            return ""


# Singleton instance
retriever = SkillRetriever()


def get_relevant_examples(instruction: str, max_examples: int = 2) -> str:
    """Wrapper function to maintain backward compatibility with planner.py"""
    return retriever.get_relevant_examples(instruction, max_examples)
