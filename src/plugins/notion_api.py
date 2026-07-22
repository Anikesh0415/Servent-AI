import os
import requests
from src.logger import logger

def create_notion_page(parent_page_id: str, title: str, content: str) -> str:
    """
    Creates a new page in Notion.
    Requires NOTION_TOKEN in environment variables.
    """
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        return "Error: NOTION_TOKEN not found in environment variables. Please set it in your .env file."
        
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # We create a simple page with a title and a single text block
    data = {
        "parent": { "page_id": parent_page_id },
        "properties": {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": content
                            }
                        }
                    ]
                }
            }
        ]
    }
    
    try:
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            return f"Successfully created Notion page '{title}'."
        else:
            return f"Notion API Error: {res.status_code} - {res.text}"
    except Exception as e:
        logger.error(f"Failed to connect to Notion API: {e}")
        return f"Error interacting with Notion: {e}"

def register_plugin(registry):
    registry.register(
        "create_notion_page",
        '{"action": "create_notion_page", "parent_page_id": "id", "title": "page title", "content": "text content"}',
        create_notion_page
    )
    logger.info("Plugin registered: notion_api")
