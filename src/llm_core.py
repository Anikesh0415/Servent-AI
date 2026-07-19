import json
import requests
from src.config import LM_STUDIO_API_URL, LM_STUDIO_MODELS_URL, OLLAMA_API_URL, OLLAMA_MODEL, DEFAULT_LM_STUDIO_MODEL
from src.utils.json_parser import parse_json_from_text
from src.logger import logger

class LocalLLMCore:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        # Local endpoints
        self.lm_studio_url = LM_STUDIO_API_URL
        self.lm_studio_models_url = LM_STUDIO_MODELS_URL
        self.ollama_url = OLLAMA_API_URL
        self.ollama_model = OLLAMA_MODEL

    def process_intent(self, prompt, payload):
        if self.use_mock:
            print("[LocalLLMCore] Running in MOCK mode.")
            return [
                {"id": 1, "action": "speak", "target": "System is in mock mode. Please configure use_mock=False to use local LLM."}
            ]
            
        try:
            logger.info("[LocalLLMCore] Connecting to LM Studio...")
            return self._call_lm_studio(prompt, payload)
        except requests.exceptions.RequestException as e:
            logger.error(f"[LocalLLMCore] LM Studio connection failed ({e}). Falling back to Ollama...")
            try:
                return self._fallback_to_ollama(prompt, payload)
            except requests.exceptions.RequestException as ex:
                logger.error(f"[LocalLLMCore] Ollama connection failed ({ex}).")
                voice_cmd = payload.get("voice_command", "") if payload else ""
                return [{"action": "unknown", "target": voice_cmd}]
        except Exception as e:
            logger.error(f"[LocalLLMCore] Unexpected error during intent processing: {e}")
            voice_cmd = payload.get("voice_command", "") if payload else ""
            return [{"action": "unknown", "target": voice_cmd}]

    def _call_lm_studio(self, prompt, payload):
        headers = {"Content-Type": "application/json"}
        
        # Dynamically detect active model in LM Studio
        model_name = DEFAULT_LM_STUDIO_MODEL
        try:
            models_res = requests.get(self.lm_studio_models_url, timeout=2)
            if models_res.status_code == 200:
                models_data = models_res.json().get("data", [])
                if models_data and len(models_data) > 0:
                    model_name = models_data[0].get("id", model_name)
                    print(f"[LocalLLMCore] Detected active LM Studio model: '{model_name}'")
        except Exception:
            pass

        # Use the comprehensive prompt from MultiStagePlanner as the system prompt
        system_prompt = prompt if prompt else "You are ARIA. Output valid JSON array of actions."
        user_prompt = f"Process user command: {payload.get('voice_command', '') if payload else ''}"

        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "stream": False
        }
        
        # We removed response_format as it causes 400 Bad Request on some LM Studio models
            
        response = requests.post(self.lm_studio_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        result_text = response.json()["choices"][0]["message"]["content"].strip()
        
        parsed = parse_json_from_text(result_text)
        if parsed is not None:
            return parsed
        
        voice_cmd = payload.get("voice_command", "") if payload else ""
        return [{"action": "unknown", "target": voice_cmd}]

    def _fallback_to_ollama(self, prompt, payload):
        user_prompt = prompt if prompt else f"Process user command: {payload.get('voice_command', '') if payload else ''}"
        data = {
            "model": self.ollama_model,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }
        if "JSON" in user_prompt.upper():
            data["format"] = "json"
            
        # Increased timeout to 120s to prevent broken pipe during long generations
        response = requests.post(self.ollama_url, json=data, timeout=120)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        
        parsed = parse_json_from_text(result_text)
        if parsed is not None:
            return parsed
            
        voice_cmd = payload.get("voice_command", "") if payload else ""
        return [{"action": "unknown", "target": voice_cmd}]
