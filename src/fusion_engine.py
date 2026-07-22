import json


class FusionEngine:
    def __init__(self):
        pass

    def fuse_context(
        self,
        voice_text,
        gesture_coords,
        gesture_type="pointing",
        screen_resolution=(1920, 1080),
    ):
        """
        Combines voice and gesture data into a structured prompt/payload.
        """
        if not voice_text:
            return None

        payload = {
            "voice_command": voice_text,
            "gesture_context": {
                "active": gesture_coords is not None,
                "type": gesture_type if gesture_coords else "none",
                "coordinates": gesture_coords,
                "screen_resolution": screen_resolution,
            },
        }

        return payload

    def generate_llm_prompt(self, fused_payload):
        """
        Formats the payload into a prompt for the local LLM.
        """
        prompt = f"""You are the Action Intelligence Framework. You map user multimodal input to computer commands.
Output ONLY a valid JSON object with the following keys:
- action: The action to take (e.g., "click", "open", "type", "search", "read")
- target: What the action applies to
- parameters: Any additional information needed (e.g., coordinates, text to type)

User Input Data:
{json.dumps(fused_payload, indent=2)}

JSON Output:"""
        return prompt


# Test
if __name__ == "__main__":
    engine = FusionEngine()
    payload = engine.fuse_context(
        voice_text="click on this folder", gesture_coords=(1024, 768)
    )
    prompt = engine.generate_llm_prompt(payload)
    print(prompt)
