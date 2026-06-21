"""Vercel serverless endpoint that delivers due vow + countdown reminders.

A scheduler GETs this endpoint once a day. The primary scheduler is Vercel's own
managed cron (see ``vercel.json`` -> ``crons``), which — because a ``CRON_SECRET``
env var is set — automatically attaches ``Authorization: Bearer <CRON_SECRET>``.
An external service (cron-job.org) may also call it as a backup; the per-item
``reminded``/``notified`` flags make repeated sweeps idempotent.

On each call we sweep every stored vow and countdown and, for any whose moment
has come and that hasn't been delivered yet, carry the reminder back to its
author and mark it done.

It is guarded by a shared secret: the scheduler must send
``Authorization: Bearer <CRON_SECRET>``. If CRON_SECRET is unset the guard is
disabled (handy for local testing), mirroring how WEBHOOK_SECRET behaves.

Like the webhook, the Bot and Redis connections are built once per warm
container and reused, and a lock serializes the shared event loop so it is never
run concurrently.
"""

import asyncio
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

# Make the top-level `bot` package importable regardless of how Vercel invokes us.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402

from bot.config import CRON_SECRET, TOKEN  # noqa: E402
from bot.storage import Store, make_redis  # noqa: E402
from bot.texts import COUNTDOWN_REMINDER_TEXT, VOW_REMINDER_TEXT  # noqa: E402

# ---- built once per warm container, reused across invocations ----
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_lock = threading.Lock()

_redis = make_redis()
_store = Store(_redis)
_bot = Bot(token=TOKEN)


async def _run_reminders() -> int:
    """Deliver every due, un-reminded vow. Returns how many were sent."""
    now = datetime.now(timezone.utc).timestamp()
    sent = 0

    for key in await _store.all_vow_keys():
        # key looks like "corridor:vow:<uid>"
        try:
            uid = int(key.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue

        vow = await _store.get_vow(uid)
        if not vow or vow.get("reminded"):
            continue
        if vow.get("remind_at", 0) > now:
            continue

        try:
            await _bot.send_message(uid, VOW_REMINDER_TEXT.format(text=vow["text"]))
        except Exception as exc:
            # the soul may have blocked the bot — leave the vow for a later sweep
            print(f"cron: could not remind {uid}: {exc}", file=sys.stderr)
            continue

        vow["reminded"] = True
        await _store.set_vow(uid, vow)
        sent += 1

    return sent


async def _run_countdowns() -> int:
    """Deliver every countdown whose moment has arrived. Returns how many were sent."""
    now = datetime.now(timezone.utc).timestamp()
    sent = 0

    for key in await _store.all_countdown_keys():
        # key looks like "corridor:countdown:<uid>:<cid>"
        parts = key.split(":")
        if len(parts) != 4:
            continue
        try:
            uid, cid = int(parts[2]), int(parts[3])
        except ValueError:
            continue

        countdown = await _store.get_countdown(uid, cid)
        if not countdown or countdown.get("notified"):
            continue
        if countdown.get("target", 0) > now:
            continue

        try:
            await _bot.send_message(
                uid,
                COUNTDOWN_REMINDER_TEXT.format(
                    label=countdown.get("label", "the unnamed moment"),
                    date=countdown.get("target_jalali", ""),
                ),
            )
        except Exception as exc:
            # the soul may have blocked the bot — leave it for a later sweep
            print(f"cron: could not send countdown to {uid}: {exc}", file=sys.stderr)
            continue

        countdown["notified"] = True
        await _store.save_countdown(uid, cid, countdown)
        sent += 1

    return sent


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes = b"ok") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Reject anything without the shared secret if one is configured.
        if CRON_SECRET:
            received = self.headers.get("Authorization", "")
            if received != f"Bearer {CRON_SECRET}":
                self._send(401, b"unauthorized")
                return

        try:
            with _lock:
                vows = _loop.run_until_complete(_run_reminders())
                countdowns = _loop.run_until_complete(_run_countdowns())
            self._send(200, f"vows: {vows}, countdowns: {countdowns}".encode("utf-8"))
        except Exception as exc:
            print(f"cron error: {exc}", file=sys.stderr)
            self._send(200, b"error")
