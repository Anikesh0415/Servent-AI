import json
import requests

class LocalLLMCore:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        # Local endpoints
        self.lm_studio_url = "http://localhost:1234/v1/chat/completions"
        self.lm_studio_models_url = "http://localhost:1234/v1/models"
        self.ollama_url = "http://localhost:11434/api/generate"
        self.ollama_model = "qwen2.5:1.5b"

    def process_intent(self, prompt, payload):
        if self.use_mock:
            print("[LocalLLMCore] Running in MOCK mode.")
            return [
                {"id": 1, "action": "speak", "target": "System is in mock mode. Please configure use_mock=False to use local LLM."}
            ]
            
        try:
            print("[LocalLLMCore] Connecting to LM Studio...")
            return self._call_lm_studio(prompt, payload)
        except Exception as e:
            print(f"[LocalLLMCore] LM Studio connection failed ({e}). Falling back to Ollama...")
            try:
                return self._fallback_to_ollama(prompt, payload)
            except Exception as ex:
                print(f"[LocalLLMCore] Ollama connection failed ({ex}).")
                # Fallback to a basic parser or returning unknown
                voice_cmd = payload.get("voice_command", "") if payload else ""
                return [{"action": "unknown", "target": voice_cmd}]

    def _call_lm_studio(self, prompt, payload):
        headers = {"Content-Type": "application/json"}
        
        # Dynamically detect active model in LM Studio
        model_name = "lmstudio-community/gemma-4-E4B-it-GGUF"
        try:
            models_res = requests.get(self.lm_studio_models_url, timeout=2)
            if models_res.status_code == 200:
                models_data = models_res.json().get("data", [])
                if models_data and len(models_data) > 0:
                    model_name = models_data[0].get("id", model_name)
                    print(f"[LocalLLMCore] Detected active LM Studio model: '{model_name}'")
        except Exception:
            pass

        system_prompt = (
            "You are the Action Intelligence Framework, a local OS agent.\n"
            "Convert user commands into a valid JSON array of actions.\n"
            "Possible actions: \"open_app\", \"open_browser\", \"type_text\", \"key_shortcut\", \"click_element\", \"scroll\", \"speak\", \"wait_until\", \"unknown\"."
        )
        user_prompt = prompt if prompt else f"Process user command: {payload.get('voice_command', '') if payload else ''}"

        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
            "stream": False
        }
        response = requests.post(self.lm_studio_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        result_text = response.json()["choices"][0]["message"]["content"].strip()
        return self._clean_and_parse_json(result_text)

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
        response = requests.post(self.ollama_url, json=data, timeout=15)
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        return self._clean_and_parse_json(result_text)

    def _clean_and_parse_json(self, raw_text):
        raw_text = raw_text.strip()
        
        # Try to extract JSON array
        start_idx = raw_text.find('[')
        end_idx = raw_text.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = raw_text[start_idx:end_idx+1]
            try:
                return json.loads(json_str)
            except Exception:
                pass

        # Try to extract JSON object
        start_idx_dict = raw_text.find('{')
        end_idx_dict = raw_text.rfind('}')
        if start_idx_dict != -1 and end_idx_dict != -1 and end_idx_dict > start_idx_dict:
            json_str = raw_text[start_idx_dict:end_idx_dict+1]
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict):
                    return [parsed]
                return parsed
            except Exception:
                pass

        try:
            return json.loads(raw_text)
        except Exception:
            return [{"action": "unknown", "target": raw_text}]
