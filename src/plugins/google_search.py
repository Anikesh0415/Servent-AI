from duckduckgo_search import DDGS
from src.logger import logger

def search_web(query: str, max_results: int = 3) -> str:
    """
    Performs a headless web search using DuckDuckGo.
    """
    logger.info(f"Performing headless search for: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            # Fallback for conversational queries that are too long
            if not results and len(query.split()) > 5:
                # Strip out common conversational filler
                broad_query = query.replace("whats the best", "").replace("what is the", "").replace("how to", "").strip()
                logger.info(f"Fallback search for: {broad_query}")
                results = list(ddgs.text(broad_query, max_results=max_results))
                
            if not results:
                return f"No results found for '{query}'."
                
            formatted = "Search Results:\n"
            for i, res in enumerate(results):
                formatted += f"{i+1}. {res.get('title', '')} - {res.get('body', '')}\nURL: {res.get('href', '')}\n\n"
            return formatted
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Error executing search: {e}"

def register_plugin(registry):
    registry.register(
        "google_search",
        '{"action": "google_search", "query": "search query"}',
        search_web
    )
    logger.info("Plugin registered: google_search")
