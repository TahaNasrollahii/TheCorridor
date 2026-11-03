import aiohttp
from bot.ai.provider import AIProvider

FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

EXCLUDED_MODEL_KEYWORDS = (
    "whisper",
    "orpheus",
    "tts",
    "guard",
    "safeguard",
    "embed",
    "rerank",
)


class GroqProvider(AIProvider):
    """Implementation of Groq API provider using aiohttp."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.models_url = "https://api.groq.com/openai/v1/models"

    @staticmethod
    def _is_model_unavailable(status: int, error_text: str) -> bool:
        if status not in (400, 404):
            return False
        lowered = error_text.lower()
        return any(
            token in lowered
            for token in (
                "model_not_found",
                "model_decommissioned",
                "does not exist",
                "decommissioned",
                "model_not_active",
            )
        )

    async def _discover_live_chat_models(self, session: aiohttp.ClientSession, headers: dict, tried: set[str]) -> list[str]:
        try:
            async with session.get(self.models_url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                models = [
                    m.get("id", "")
                    for m in data.get("data", [])
                    if isinstance(m, dict) and m.get("id")
                ]
                candidates = [
                    m for m in models
                    if m not in tried
                    and not any(k in m.lower() for k in EXCLUDED_MODEL_KEYWORDS)
                ]
                # Prefer qwen or gpt-oss or llama instruct/chat models first
                candidates.sort(
                    key=lambda m: (
                        0 if "qwen" in m.lower() else
                        1 if "gpt-oss-120b" in m.lower() else
                        2 if "gpt-oss" in m.lower() else
                        3 if "llama" in m.lower() else
                        4
                    )
                )
                return candidates
        except Exception:
            return []

    async def generate_response(self, prompt: str, history: list[dict], **kwargs) -> str:
        messages = [{"role": "system", "content": prompt}] + history

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        candidate_models = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]
        tried: set[str] = set()
        last_error: Exception | None = None

        # 8-second timeout to safely fit within Vercel's 10s serverless limit.
        timeout = aiohttp.ClientTimeout(total=8.0)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            idx = 0
            discovered = False
            while idx < len(candidate_models):
                model_id = candidate_models[idx]
                idx += 1
                if model_id in tried:
                    continue
                tried.add(model_id)

                payload = {
                    "model": model_id,
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.4),
                    "max_tokens": kwargs.get("max_tokens", 1024),
                }

                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        err = Exception(f"Groq API Error {response.status}: {text}")
                        if self._is_model_unavailable(response.status, text):
                            last_error = err
                            if idx >= len(candidate_models) and not discovered:
                                discovered = True
                                live_models = await self._discover_live_chat_models(session, headers, tried)
                                candidate_models.extend(live_models[:3])
                            continue
                        raise err

                    data = await response.json()
                    self.model = model_id
                    return data["choices"][0]["message"].get("content") or ""

        if last_error is not None:
            raise last_error
        raise Exception("Groq API Error: No available models responded.")
