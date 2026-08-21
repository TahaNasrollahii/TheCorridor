import asyncio
from bot.config import (
    AI_PROVIDER, AI_MODEL, AI_API_KEY, 
    TEMPERATURE, MAX_TOKENS, MAX_CONTEXT_MESSAGES
)
from bot.ai.providers.groq_provider import GroqProvider

class AIService:
    """Orchestrates AI provider communication and manages retries."""

    def __init__(self):
        self.provider = self._get_provider()
        self.temperature = TEMPERATURE
        self.max_tokens = MAX_TOKENS
        
    def _get_provider(self):
        provider_name = AI_PROVIDER.lower()
        if provider_name == "groq":
            return GroqProvider(api_key=AI_API_KEY, model=AI_MODEL)
        # Fallback to groq
        return GroqProvider(api_key=AI_API_KEY, model=AI_MODEL)

    async def generate_response(self, prompt: str, history: list[dict]) -> str:
        """
        Calls the AI provider with exponential backoff on failure.
        """
        max_retries = 2
        base_delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                response = await self.provider.generate_response(
                    prompt=prompt,
                    history=history,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                import re
                if "<think>" in response:
                    if "</think>" in response:
                        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
                    else:
                        response = "..." # Thought was cut off
                return response
            except Exception as e:
                if attempt == max_retries:
                    print(f"AI Service failed after {max_retries} retries: {e}")
                    raise e
                await asyncio.sleep(base_delay * (2 ** attempt))
