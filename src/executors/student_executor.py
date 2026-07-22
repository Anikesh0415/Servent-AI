import os
import re
from src.logger import logger
from src.llm_core import LocalLLMCore


class StudentExecutor:
    """
    Execution backend for Student Mode (AI Tutor Capabilities).
    Allows Forge to read YouTube transcripts, generate quizzes, and diagram HTML.
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
                api = YouTubeTranscriptApi()
                transcript_list_obj = api.list(video_id)

                transcript_obj = None
                for t in transcript_list_obj:
                    transcript_obj = t
                    break

                if not transcript_obj:
                    return False, "No transcript available for this video."

                transcript_list = transcript_obj.fetch()
                full_text = " ".join([getattr(t, "text", "") for t in transcript_list])

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
            filepath = step_data.get("path", "study_material.html")
            
            # Prevent hallucinated literal strings from the prompt template
            if "absolute path to save html" in filepath or "path/to/" in filepath:
                filepath = "study_material.html"
                
            filepath = os.path.abspath(filepath)
            
            if not filepath.endswith(".html"):
                filepath += ".html"
                
            content = step_data.get("html_content", "")
            
            # If the LLM failed to output content, provide a fallback template
            if not content or len(content.strip()) < 10 or "Full HTML/JS code" in content:
                content = """<!DOCTYPE html>
<html>
<head>
    <title>Study Material</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f4f4f9; color: #333; } .container { text-align: center; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }</style>
</head>
<body>
    <div class="container">
        <h2>Hmm, the AI forgot to write the code!</h2>
        <p>The AI decided to create a study file, but didn't output the raw HTML payload properly.</p>
        <p>Please ask the AI to try again, or use the <strong>generate-mindmap</strong> macro in the chat!</p>
    </div>
</body>
</html>"""

            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                # Open the generated HTML in the default web browser automatically
                import webbrowser

                webbrowser.open(f"file://{os.path.abspath(filepath)}")

                return True, f"Successfully generated and opened {filepath}"
            except Exception as e:
                return False, f"Failed to generate study HTML: {e}"

        return False, f"Unknown student action: {action_type}"
