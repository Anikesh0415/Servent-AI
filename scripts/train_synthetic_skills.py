import os
import json
import uuid
import sys

# Ensure src is accessible
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.utils.skill_retriever import SkillRetriever
from src.logger import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SKILLS_FILE = os.path.join(DATA_DIR, "skills.json")

# Base templates for combinatorial generation
AI_MODELS = [
    ("gemini", "https://gemini.google.com"),
    ("chatgpt", "https://chatgpt.com"),
    ("claude", "https://claude.ai"),
    ("perplexity", "https://perplexity.ai"),
    ("deepseek", "https://chat.deepseek.com")
]

DESTINATION_APPS = [
    ("whatsapp", "send_whatsapp", "WhatsApp"),
    ("notepad", "open_app", "Notepad"),
    ("word", "open_app", "Microsoft Word"),
    ("vscode", "open_app", "VS Code"),
    ("email", "open_browser", "https://mail.google.com"),
    ("discord", "open_app", "Discord"),
    ("telegram", "open_app", "Telegram"),
    ("slack", "open_app", "Slack")
]

TOPICS = [
    "letter to a friend",
    "100-word essay about black holes",
    "python script for web scraping",
    "summary of quantum computing",
    "recipe for Italian pasta",
    "cover letter for software engineer",
    "email asking for vacation approval",
    "poem about rain and coffee",
    "workout routine for beginners",
    "explanation of general relativity"
]

def generate_synthetic_patterns():
    skills = []

    # 1. Load existing base skills
    if os.path.exists(SKILLS_FILE):
        try:
            with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    skills.extend(existing)
        except Exception:
            pass

    seen_descriptions = {s.get("description") for s in skills}

    # 2. Combinatorial Generation of AI -> App Patterns
    for ai_name, ai_url in AI_MODELS:
        for app_name, app_action, app_target in DESTINATION_APPS:
            for topic in TOPICS:
                desc = f"Generate {topic} using {ai_name} and paste into {app_name}"
                if desc in seen_descriptions:
                    continue
                seen_descriptions.add(desc)

                keywords = [ai_name, app_name, topic.split()[0], "generate", "copy", "paste"]
                
                if app_action == "send_whatsapp":
                    seq = f"1. {{\"action\": \"open_browser\", \"url\": \"{ai_url}\"}}\n2. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} loads\"}}\n3. {{\"action\": \"type_text\", \"text\": \"{topic}\"}}\n4. {{\"action\": \"key_shortcut\", \"keys\": \"enter\"}}\n5. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} finishes generation\"}}\n6. {{\"action\": \"semantic_copy\", \"goal\": \"Extract {topic}\"}}\n7. {{\"action\": \"send_whatsapp\", \"contact\": \"contact\", \"message\": \"[CLIPBOARD]\"}}"
                elif app_action == "open_app":
                    seq = f"1. {{\"action\": \"open_browser\", \"url\": \"{ai_url}\"}}\n2. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} loads\"}}\n3. {{\"action\": \"type_text\", \"text\": \"{topic}\"}}\n4. {{\"action\": \"key_shortcut\", \"keys\": \"enter\"}}\n5. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} finishes generation\"}}\n6. {{\"action\": \"semantic_copy\", \"goal\": \"Extract {topic}\"}}\n7. {{\"action\": \"open_app\", \"name\": \"{app_target}\"}}\n8. {{\"action\": \"key_shortcut\", \"keys\": \"ctrl+v\"}}\n9. {{\"action\": \"key_shortcut\", \"keys\": \"ctrl+s\"}}"
                else:
                    seq = f"1. {{\"action\": \"open_browser\", \"url\": \"{ai_url}\"}}\n2. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} loads\"}}\n3. {{\"action\": \"type_text\", \"text\": \"{topic}\"}}\n4. {{\"action\": \"key_shortcut\", \"keys\": \"enter\"}}\n5. {{\"action\": \"wait_until\", \"condition\": \"{ai_name} finishes generation\"}}\n6. {{\"action\": \"semantic_copy\", \"goal\": \"Extract {topic}\"}}\n7. {{\"action\": \"open_browser\", \"url\": \"{app_target}\"}}\n8. {{\"action\": \"key_shortcut\", \"keys\": \"ctrl+v\"}}"

                skills.append({
                    "keywords": keywords,
                    "description": desc,
                    "example_sequence": seq
                })

    # Save expanded skills back to file
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=4)

    logger.info(f"Generated and saved total {len(skills)} skill patterns to data/skills.json.")
    return skills

def train_chroma_db(skills):
    retriever = SkillRetriever()
    if not retriever.collection:
        logger.error("ChromaDB unavailable.")
        return

    # Delete existing collection to re-index fresh batch
    try:
        retriever.client.delete_collection("forge_skills")
        retriever.collection = retriever.client.get_or_create_collection(name="forge_skills")
    except Exception:
        pass

    docs = []
    metas = []
    ids = []

    for idx, skill in enumerate(skills):
        desc = skill.get("description", "Action Pattern")
        seq = skill.get("example_sequence", "")
        keywords = " ".join(skill.get("keywords", []))
        
        # Combine description + keywords for rich semantic embedding
        doc_text = f"Task: {desc}\nKeywords: {keywords}\nSequence:\n{seq}"
        
        docs.append(doc_text)
        metas.append({"description": desc})
        ids.append(f"skill_{idx}_{uuid.uuid4().hex[:6]}")

    # Batch add into ChromaDB
    batch_size = 100
    for i in range(0, len(docs), batch_size):
        retriever.collection.add(
            documents=docs[i:i+batch_size],
            metadatas=metas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )

    logger.info(f"Successfully indexed {len(docs)} skills into ChromaDB vector memory!")

if __name__ == "__main__":
    skills = generate_synthetic_patterns()
    train_chroma_db(skills)
