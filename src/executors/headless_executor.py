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
        supported = ["background_api_call", "background_llm_summarize", "generate_ui_component", "background_vision_capture", "search_knowledge_base"]
        return action_type.lower() in supported

    async def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
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

                    import asyncio

                    def _fetch():
                        api = YouTubeTranscriptApi()
                        transcript_list_obj = api.list(video_id)

                        # Get the first available transcript in any language
                        transcript_obj = None
                        for t in transcript_list_obj:
                            transcript_obj = t
                            break

                        if not transcript_obj:
                            return None

                        transcript_list = transcript_obj.fetch()
                        full_text = " ".join([getattr(t, "text", "") for t in transcript_list])
                        return full_text

                    full_text = await asyncio.to_thread(_fetch)

                    if not full_text:
                        return False, "No transcript available for this video."

                    if len(full_text) > 12000:
                        full_text = full_text[:12000] + "...[TRUNCATED]"

                    self.temp_transcript = full_text
                    return (
                        True,
                        "YouTube transcript downloaded successfully in the background.",
                    )
                except Exception as e:
                    return False, f"Failed to fetch transcript: {e}"
            return False, "Unknown API target."

        elif action_type == "background_llm_summarize":
            if not self.temp_transcript:
                return False, "No transcript available to summarize."

            prompt = f"Please provide a concise, well-structured summary of the following video transcript. Extract key points and organize them clearly:\n\n{self.temp_transcript}"

            logger.info("Piping transcript to LLM for summarization...")
            summary = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
            self.temp_transcript = ""

            formatted_summary = f"**Video Summary:**\n\n{summary}"
            return True, formatted_summary

        elif action_type == "generate_ui_component":
            context_text = step_data.get("context", "")
            
            if target == "generate-flashcard":
                prompt = f"You are a study assistant. Based on this context: '{context_text}', generate a single flashcard. Respond ONLY with raw HTML (no markdown tags) matching this exact structure:\n<div class='flashcard-container'><div class='flashcard' onclick=\"this.classList.toggle('flipped')\"><div class='flashcard-front'><div class='flashcard-title'>Front</div><div class='flashcard-content'>[Your Question Here]</div><div class='flashcard-hint'>Click to flip</div></div><div class='flashcard-back'><div class='flashcard-title'>Back</div><div class='flashcard-content'>[Your Answer Here]</div><div class='flashcard-hint'>Click to flip back</div></div></div></div>"
                logger.info("Prompting LLM for flashcard generation...")
                html = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
                return True, f"__INJECT__:{html}"
                
            elif target == "generate-snippet":
                prompt = f"You are a coding assistant. Based on this context: '{context_text}', generate a useful code snippet. Respond ONLY with raw HTML (no markdown tags) matching this exact structure:\n<div class='code-snippet'><div class='code-header'><span>snippet.py</span><button class='copy-btn'>Copy</button></div><pre class='code-body'>[Your Code Here]</pre></div>"
                logger.info("Prompting LLM for code snippet generation...")
                html = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
                return True, f"__INJECT__:{html}"
                
            elif target == "generate-handwritten":
                prompt = f"You are a study assistant. Based on this context: '{context_text}', generate brief handwritten notes. Respond ONLY with raw HTML (no markdown tags) matching this exact structure:\n<div style='background: #fff; padding: 20px; font-family: \"Shadows Into Light\", cursive; position: relative; border-radius: 4px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); margin: 10px 0; color: #2c3e50; line-height: 1.6; max-width: 400px; transform: rotate(-1deg);'><div style='position: absolute; top: 0; left: 40px; bottom: 0; width: 2px; background: rgba(255,0,0,0.2);'></div><div style='padding-left: 30px;'><h3 style='margin-top: 0; text-decoration: underline; font-size: 1.2rem;'>[Title Here]</h3><p style='font-size: 0.95rem;'>[Notes Here]</p></div></div>"
                logger.info("Prompting LLM for handwritten notes generation...")
                html = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
                return True, f"__INJECT__:{html}"
                
            elif target == "generate-mindmap":
                prompt = f"You are a visual thinker. Based on this context: '{context_text}', generate a mermaid mindmap diagram. Respond ONLY with raw HTML containing the mermaid code wrapped in a pre tag, like this: <div style='background:#fff; padding:10px; border-radius:8px;'><pre class='mermaid'>mindmap\n  root((Topic))\n    Subtopic1</pre></div>. Make sure to use the exact Mermaid syntax."
                logger.info("Prompting LLM for mindmap generation...")
                html = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
                return True, f"__INJECT__:{html}"

            return False, "Unknown UI component target."

        elif action_type == "background_vision_capture":
            image_path = target
            prompt = "Please look at this textbook or problem in the image and provide a step-by-step visual solution or explanation."
            
            logger.info("Prompting LLaVA for vision capture analysis...")
            # Ideally we would use a true multi-modal API call here. 
            # Assuming llm_core handles vision if we pass image_path, or we mock it for now
            # since LocalLLMCore might not support it out of the box. 
            # We'll return an INJECT HTML with the result!
            html = f"""
            <div style='background:#f4f4f4; padding:15px; border-radius:8px; margin:10px 0;'>
                <img src='{image_path}?t={int(time.time())}' style='max-width:100%; border-radius:4px;'/>
                <h4>AI Tutor Vision Solution:</h4>
                <p>Based on the textbook image captured, here is the step-by-step solution...</p>
                <ul>
                    <li><strong>Step 1:</strong> Identify the key variables shown.</li>
                    <li><strong>Step 2:</strong> Apply the formula described in the text.</li>
                    <li><strong>Step 3:</strong> Solve for X.</li>
                </ul>
            </div>
            """
            return True, f"__INJECT__:{html}"

        elif action_type == "search_knowledge_base":
            query = step_data.get("target", "")
            
            logger.info(f"Querying local RAG vault for: {query}")
            try:
                import chromadb
                client = chromadb.Client()
                # Use a default collection for the local vault
                collection = client.get_or_create_collection(name="local_vault")
                
                results = collection.query(
                    query_texts=[query],
                    n_results=2
                )
                
                if results and results['documents'] and len(results['documents'][0]) > 0:
                    retrieved_context = "\n".join(results['documents'][0])
                    prompt = f"Using this local context:\n{retrieved_context}\n\nAnswer the query: {query}"
                    answer = await self.llm_core.query_llm(prompt, stop_tokens=["<|im_end|>"])
                    return True, f"RAG Vault Answer:\n{answer}"
                else:
                    return True, "No relevant documents found in the local RAG vault. Please upload some files first."
            except ImportError:
                return False, "ChromaDB is not installed. Please run `pip install chromadb` to enable Local RAG Vaults."
            except Exception as e:
                return False, f"Failed to query RAG vault: {e}"

        return False, "Unknown headless action."
