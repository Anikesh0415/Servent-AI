import json
import httpx
import asyncio
from src.config import (
    LM_STUDIO_API_URL,
    LM_STUDIO_MODELS_URL,
    OLLAMA_API_URL,
    OLLAMA_MODEL,
    DEFAULT_LM_STUDIO_MODEL,
)
from src.utils.json_parser import parse_json_from_text
from src.logger import logger


class LocalLLMCore:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        self.lm_studio_url = LM_STUDIO_API_URL
        self.lm_studio_models_url = LM_STUDIO_MODELS_URL
        self.ollama_url = OLLAMA_API_URL
        self.ollama_model = OLLAMA_MODEL
        
    def swap_model(self, mode: str):
        """Dynamically swap heavy models for smaller quantized versions during intense dev workflows"""
        if mode == "DEVELOPER":
            logger.info("Dynamic Hardware Swapping: Unloading heavy model, loading CodeLlama (Quantized) to save VRAM...")
            self.ollama_model = "codellama:7b"
        else:
            logger.info("Dynamic Hardware Swapping: Loading primary Hermes 8B model...")
            self.ollama_model = OLLAMA_MODEL

    async def process_intent(self, prompt, payload):
        if self.use_mock:
            print("[LocalLLMCore] Running in MOCK mode.")
            return [
                {
                    "id": 1,
                    "action": "speak",
                    "target": "System is in mock mode. Please configure use_mock=False to use local LLM.",
                }
            ]

        try:
            logger.info("[LocalLLMCore] Connecting to LM Studio...")
            return await self._call_lm_studio(prompt, payload)
        except Exception as e:
            logger.error(
                f"[LocalLLMCore] LM Studio connection failed ({e}). Falling back to Ollama..."
            )
            try:
                return await self._fallback_to_ollama(prompt, payload)
            except Exception as ex:
                logger.error(f"[LocalLLMCore] Ollama connection failed ({ex}).")
                voice_cmd = payload.get("voice_command", "") if payload else ""
                return [{"action": "unknown", "target": voice_cmd}]

    async def _call_lm_studio(self, prompt, payload):
        headers = {"Content-Type": "application/json"}
        model_name = DEFAULT_LM_STUDIO_MODEL

        async with httpx.AsyncClient() as client:
            try:
                models_res = await client.get(self.lm_studio_models_url, timeout=2.0)
                if models_res.status_code == 200:
                    models_data = models_res.json().get("data", [])
                    if models_data and len(models_data) > 0:
                        model_name = models_data[0].get("id", model_name)
                        print(
                            f"[LocalLLMCore] Detected active LM Studio model: '{model_name}'"
                        )
            except Exception:
                pass

            try:
                from src.context_manager import ContextManager
                from src.config import IDE_APP_NAMES, IDE_MODEL_LMSTUDIO

                ctx = ContextManager().capture_os_context()
                active_app = ctx.get("active_app", "")
                if any(ide.lower() in active_app.lower() for ide in IDE_APP_NAMES):
                    model_name = IDE_MODEL_LMSTUDIO
                    logger.info(
                        f"[LocalLLMCore] IDE '{active_app}' detected. Swapping to Cognitive Coding Model: {model_name}"
                    )
            except Exception as e:
                pass

            system_prompt = (
                prompt
                if prompt
                else "You are Forge. Output valid JSON array of actions."
            )
            user_prompt = f"Process user command: {payload.get('voice_command', '') if payload else ''}"

            data = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
                "stream": False,
            }

            response = await client.post(
                self.lm_studio_url, headers=headers, json=data, timeout=15.0
            )
            response.raise_for_status()
            result_text = response.json()["choices"][0]["message"]["content"].strip()

            parsed = parse_json_from_text(result_text)
            if parsed is not None:
                return parsed

            voice_cmd = payload.get("voice_command", "") if payload else ""
            return [{"action": "unknown", "target": voice_cmd}]

    async def _fallback_to_ollama(self, prompt, payload):
        user_prompt = (
            prompt
            if prompt
            else f"Process user command: {payload.get('voice_command', '') if payload else ''}"
        )
        data = {
            "model": self.ollama_model,
            "prompt": user_prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }
        if "JSON" in user_prompt.upper():
            data["format"] = "json"

        async with httpx.AsyncClient() as client:
            response = await client.post(self.ollama_url, json=data, timeout=15.0)
            response.raise_for_status()
            result_text = response.json().get("response", "").strip()

            parsed = parse_json_from_text(result_text)
            if parsed is not None:
                return parsed

            voice_cmd = payload.get("voice_command", "") if payload else ""
            return [{"action": "unknown", "target": voice_cmd}]

    async def query_llm(self, prompt, stop_tokens=None):
        """
        Generic text generation endpoint for summaries, translations, etc.
        """
        headers = {"Content-Type": "application/json"}
        model_name = DEFAULT_LM_STUDIO_MODEL

        async with httpx.AsyncClient() as client:
            try:
                models_res = await client.get(self.lm_studio_models_url, timeout=2.0)
                if models_res.status_code == 200:
                    models_data = models_res.json().get("data", [])
                    if models_data and len(models_data) > 0:
                        model_name = models_data[0].get("id", model_name)
            except Exception:
                pass

            data = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Forge, a helpful and precise AI assistant. Output direct and clear responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "stream": False,
            }
            if stop_tokens:
                data["stop"] = stop_tokens

            try:
                response = await client.post(
                    self.lm_studio_url, headers=headers, json=data, timeout=120.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(
                    f"[LocalLLMCore] LM Studio query_llm failed: {e}. Falling back to Ollama."
                )
                data_ollama = {
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                }
                if stop_tokens:
                    data_ollama["options"]["stop"] = stop_tokens

                response_ollama = await client.post(
                    self.ollama_url, json=data_ollama, timeout=120.0
                )
                response_ollama.raise_for_status()
                return response_ollama.json().get("response", "").strip()
