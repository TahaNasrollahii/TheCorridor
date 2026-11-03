import os

# ================== CONFIG ==================
# Telegram bot token from @BotFather
TOKEN = os.getenv("TOKEN", "")

# Your Telegram numeric user id (the "keeper")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Redis connection url (Upstash gives you a rediss://... url)
REDIS_URL = os.getenv("REDIS_URL", "")

# Optional shared secret. If set, Telegram sends it back in the
# X-Telegram-Bot-Api-Secret-Token header so we can reject forged requests.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Shared secret guarding the /api/cron endpoint. An external scheduler
# (cron-job.org) must send it as `Authorization: Bearer <CRON_SECRET>`.
CRON_SECRET = os.getenv("CRON_SECRET", "")

# Public URL of the deployed Mini App (e.g. https://your-project.vercel.app).
# Used to add a "open the corridor" button to the reply keyboard. Leave blank
# and that button is simply omitted.
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

# ================== AI CONFIG ==================
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")

# Map deprecated Groq model IDs (e.g. if still set in Vercel env vars) to active replacements
DEPRECATED_AI_MODELS = {
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
    "qwen/qwen3-32b": "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct": "qwen/qwen3.8-27b",
    "meta-llama/llama-4-maverick-17b-128e-instruct": "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile": "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama3-70b-8192": "qwen/qwen3.8-27b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
}
_raw_ai_model = os.getenv("AI_MODEL", "qwen/qwen3.8-27b").strip() or "qwen/qwen3.8-27b"
AI_MODEL = DEPRECATED_AI_MODELS.get(_raw_ai_model, _raw_ai_model)
AI_API_KEY = os.getenv("AI_API_KEY", "")

# Tunable AI behavior
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "4"))

# Rate limiting and Caching
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "50"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))

