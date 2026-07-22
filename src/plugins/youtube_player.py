import pywhatkit
from src.logger import logger

def play_youtube_video(query: str) -> str:
    """
    Searches YouTube and immediately plays the most relevant video.
    """
    logger.info(f"Playing YouTube video for: {query}")
    try:
        pywhatkit.playonyt(query)
        return f"Playing YouTube video matching '{query}' in your default browser."
    except Exception as e:
        logger.error(f"Failed to play YouTube video: {e}")
        return f"Error playing YouTube video: {e}"

def register_plugin(registry):
    registry.register(
        "play_youtube_video",
        '{"action": "play_youtube_video", "query": "video title or topic"}',
        play_youtube_video
    )
    logger.info("Plugin registered: youtube_player")
