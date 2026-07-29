from openai import OpenAI
from typing import Optional

from app.config import config


class LLMClient:
    """Client for OpenAI-compatible LLM API"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or config.LLM_API_KEY
        self.base_url = base_url or config.LLM_BASE_URL
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model_name = model_name or config.LLM_MODEL_NAME

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """Generate API responses using chat completion with a system prompt."""
        try:
            response = self.client.chat.completions.create(
                model=model or self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                stream=False,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise Exception(f"Error while calling LLM client: {e}")
