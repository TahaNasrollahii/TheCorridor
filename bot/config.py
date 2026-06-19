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
