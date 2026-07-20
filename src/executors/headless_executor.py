import time
from src.logger import logger
from src.llm_core import LocalLLMCore

class HeadlessExecutor:
    """
    Execution backend for Headless/Background Actions.
    Does not interact with the GUI to prevent interrupting the user.
    """
    def __init__(self):
        self.name = "HeadlessExecutor"
        self.temp_transcript = ""
        self.llm_core = LocalLLMCore(use_mock=False)

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        supported = ["background_api_call", "background_llm_summarize"]
        return action_type.lower() in supported

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        action_type = action_type.lower()
        target = step_data.get("target", "")
        url = step_data.get("url", "")
        
        if action_type == "background_api_call":
            if "YouTube" in target or "youtube" in target.lower():
                try:
                    from youtube_transcript_api import YouTubeTranscriptApi
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
                    
                    if len(full_text) > 12000:
                        full_text = full_text[:12000] + "...[TRUNCATED]"
                        
                    self.temp_transcript = full_text
                    return True, "YouTube transcript downloaded successfully in the background."
                except Exception as e:
                    return False, f"Failed to fetch transcript: {e}"
            return False, "Unknown API target."
            
        elif action_type == "background_llm_summarize":
            if not self.temp_transcript:
                return False, "No transcript available to summarize."
                
            prompt = f"Please provide a concise, well-structured summary of the following video transcript. Extract key points and organize them clearly:\n\n{self.temp_transcript}"
            
            logger.info("Piping transcript to LLM for summarization...")
            summary = self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
            self.temp_transcript = "" 
            
            formatted_summary = f"**Video Summary:**\n\n{summary}"
            return True, formatted_summary
            
        return False, "Unknown headless action."
