import aiohttp
from bot.ai.provider import AIProvider

class GroqProvider(AIProvider):
    """Implementation of Groq API provider using aiohttp."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate_response(self, prompt: str, history: list[dict], **kwargs) -> str:
        messages = [{"role": "system", "content": prompt}] + history
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.4),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 8-second timeout to safely fit within Vercel's 10s serverless limit.
        timeout = aiohttp.ClientTimeout(total=8.0)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_url, json=payload, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Groq API Error {response.status}: {text}")
                
                data = await response.json()
                return data["choices"][0]["message"]["content"]
