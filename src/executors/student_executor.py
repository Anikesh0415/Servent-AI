import os
import re
from src.logger import logger
from src.llm_core import LocalLLMCore

class StudentExecutor:
    """
    Execution backend for Student Mode (AI Tutor Capabilities).
    Allows Servent-AI to read YouTube transcripts, generate quizzes, and diagram HTML.
    """
    def __init__(self):
        self.name = "StudentExecutor"
        self.core = LocalLLMCore(use_mock=False)

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        supported = ["summarize_youtube", "generate_study_html"]
        return action_type.lower() in supported

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        action_type = action_type.lower()

        if action_type == "summarize_youtube":
            url = step_data.get("url", "")
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                # Extract Video ID
                video_id = ""
                if "v=" in url:
                    video_id = url.split("v=")[1].split("&")[0]
                elif "youtu.be/" in url:
                    video_id = url.split("youtu.be/")[1].split("?")[0]
                else:
                    return False, "Invalid YouTube URL format."

                logger.info(f"Fetching transcript for YouTube ID: {video_id}")
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                
                full_text = " ".join([t['text'] for t in transcript_list])
                
                # Truncate if too long (keep around 10k chars for 8B model limits)
                if len(full_text) > 10000:
                    full_text = full_text[:10000] + "...[TRUNCATED]"
                
                return True, f"YouTube Transcript:\n{full_text}"
            except ImportError:
                return False, "youtube-transcript-api is not installed."
            except Exception as e:
                return False, f"Failed to fetch transcript: {e}"
                
        elif action_type == "generate_study_html":
            # Action used to generate HTML quizzes or 3D Mermaid/ThreeJS diagrams and open them
            filepath = step_data.get("path", os.path.abspath("study_material.html"))
            content = step_data.get("html_content", "")
            try:
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                # Open the generated HTML in the default web browser automatically
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(filepath)}")
                
                return True, f"Successfully generated and opened {filepath}"
            except Exception as e:
                return False, f"Failed to generate study HTML: {e}"

        return False, f"Unknown student action: {action_type}"
