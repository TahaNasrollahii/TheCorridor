"""Mini App JSON API — a single Vercel serverless function.

Vercel's Hobby plan caps a project at a handful of serverless functions, so
instead of one file per Mini App endpoint, EVERY Mini App request hits this one
function. The client POSTs JSON ``{"action": "...", ...}`` and we dispatch on
``action`` to a handler in ``ACTIONS``.

Auth: the client sends Telegram's signed ``initData`` in the
``X-Telegram-Init-Data`` header. We HMAC-validate it (see ``bot.webapp_auth``)
and pass the verified user dict to the handler — handlers never trust a user id
from the body.

Like the webhook, the Bot / Redis connections are built once per warm container
and a lock serializes the shared event loop so it is never run concurrently.
"""

import asyncio
import json
import os
import random
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

# Make the top-level `bot` package importable regardless of how Vercel invokes us.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot  # noqa: E402

from bot.config import ADMIN_ID, TOKEN  # noqa: E402
from bot.handlers import (  # noqa: E402
    get_now_info,
    jalali_str,
    parse_persian_countdown,
    vow_days_left,
)
from bot.storage import Store, make_redis  # noqa: E402
from bot.texts import (  # noqa: E402
    CONFIRM_MESSAGES,
    DARK_QUOTES,
    FORTUNES,
    MESSAGE_TYPES,
    MIRROR_RESPONSES,
    MOOD_RESPONSES,
    NIGHT_CONFIRM_MESSAGES,
    RITUAL_QUESTIONS,
)
from bot.webapp_auth import InitDataError, validate_init_data  # noqa: E402

# ---- built once per warm container, reused across invocations ----
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_lock = threading.Lock()

_redis = make_redis()
_store = Store(_redis)
_bot = Bot(token=TOKEN)


# ================== ACTION HANDLERS ==================
# Each handler receives (user: dict, payload: dict) and returns a JSON-able dict.
# `user` is the verified Telegram user; `payload` is the rest of the request body.

async def _me(user: dict, payload: dict) -> dict:
    """Who the corridor sees you as — identity, keeper status, unread answers."""
    uid = user["id"]
    return {
        "user": {
            "id": uid,
            "username": user.get("username"),
            "first_name": user.get("first_name"),
        },
        "is_admin": uid == ADMIN_ID,
        "unread": await _store.get_unread(uid),
    }


async def _dark(user: dict, payload: dict) -> dict:
    """A single dark quote drawn from the void."""
    return {"quote": random.choice(DARK_QUOTES)}


async def _fortune(user: dict, payload: dict) -> dict:
    """A dark fortune — the void's reading of you."""
    return {"fortune": random.choice(FORTUNES)}


async def _mood(user: dict, payload: dict) -> dict:
    """The dark's answer to how you feel. ``payload["mood"]`` is the chosen key."""
    key = (payload.get("mood") or "").strip().lower()
    response = MOOD_RESPONSES.get(key)
    if not response:
        raise ValueError("unknown mood")
    return {"response": response}


async def _mirror(user: dict, payload: dict) -> dict:
    """Reflect a one-word answer. Matches the bot: substring match, else random."""
    word = (payload.get("word") or "").strip().lower()
    matched = None
    for key, value in MIRROR_RESPONSES.items():
        if key in word:
            matched = value
            break
    if not matched:
        matched = random.choice(list(MIRROR_RESPONSES.values()))
    return {"response": matched}


async def _send(user: dict, payload: dict) -> dict:
    """Carry a message to the keeper, the way the bot's type-picker does — but
    from the web app. Records the same stats, notifies the keeper, and mirrors
    the message into the soul's inbox thread. Returns a confirmation to show."""
    uid = user["id"]
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("empty message")
    if len(text) > 4000:
        text = text[:4000]

    msg_type = payload.get("type") or "just_words"
    label = MESSAGE_TYPES.get(msg_type, MESSAGE_TYPES["just_words"])

    full_time, date_str, is_night = get_now_info()
    confirm = random.choice(NIGHT_CONFIRM_MESSAGES if is_night else CONFIRM_MESSAGES)

    # Blocked souls are silently ignored — they get a confirmation like anyone
    # else, but nothing is delivered or recorded (same effect as the bot).
    if await _store.is_blocked(uid):
        return {"confirm": confirm}

    username = user.get("username") or "no_username"
    alias = await _store.get_alias(uid)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""

    counter = await _store.incr_counter()
    await _store.add_sender(uid)
    await _store.incr_day(date_str)
    await _store.incr_user_messages(uid)

    try:
        await _bot.send_message(
            ADMIN_ID,
            f"📩 {label}  #{counter}\n\n"
            f"👤 Sender: {uid} (@{username})\n"
            f"{alias_line}"
            f"💬 Carried: {text}\n"
            f"🕰️ {full_time}\n"
            f"🌐 via the corridor (mini app)\n\n"
            f"To answer:\n/reply {uid} your message",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"app send: keeper notify failed: {exc}", file=sys.stderr)

    await _store.add_thread_message(uid, {
        "dir": "out",
        "text": text,
        "kind": label,
        "ts": datetime.now(timezone.utc).timestamp(),
    })

    return {"confirm": confirm}


async def _inbox(user: dict, payload: dict) -> dict:
    """The full back-and-forth with the keeper. Opening it clears the unread mark."""
    uid = user["id"]
    messages = await _store.get_thread(uid)
    await _store.clear_unread(uid)
    return {"messages": messages}


async def _ritual_questions(user: dict, payload: dict) -> dict:
    """The four questions of the rite, so the app stays in sync with the bot."""
    return {"questions": list(RITUAL_QUESTIONS)}


async def _ritual(user: dict, payload: dict) -> dict:
    """Submit the four answers — carried to the keeper as a completed rite."""
    answers = payload.get("answers")
    if not isinstance(answers, list) or len(answers) != 4:
        raise ValueError("the ritual needs four answers")
    answers = [(str(a).strip() or "[no answer]")[:2000] for a in answers]

    uid = user["id"]
    username = user.get("username") or "no_username"
    alias = await _store.get_alias(uid)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    full_time, _, _ = get_now_info()

    record = (
        "🕯️ RITUAL COMPLETED\n\n"
        f"👤 {uid} (@{username})\n"
        f"{alias_line}"
        f"🕰️ {full_time}\n"
        f"🌐 via the corridor (mini app)\n\n"
        f"I. {RITUAL_QUESTIONS[0]}\n→ {answers[0]}\n\n"
        f"II. {RITUAL_QUESTIONS[1]}\n→ {answers[1]}\n\n"
        f"III. {RITUAL_QUESTIONS[2]}\n→ {answers[2]}\n\n"
        f"IV. {RITUAL_QUESTIONS[3]}\n→ {answers[3]}"
    )

    await _store.incr_user_rituals(uid)
    try:
        await _bot.send_message(ADMIN_ID, record)
    except Exception as exc:  # noqa: BLE001
        print(f"app ritual: keeper notify failed: {exc}", file=sys.stderr)
    return {}


async def _letter(user: dict, payload: dict) -> dict:
    """An unsent letter — kept by the keeper, never delivered to its addressee."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("empty letter")
    text = text[:4000]

    uid = user["id"]
    username = user.get("username") or "no_username"
    alias = await _store.get_alias(uid)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    full_time, _, _ = get_now_info()

    await _store.incr_user_letters(uid)
    try:
        await _bot.send_message(
            ADMIN_ID,
            f"📜 UNSENT LETTER\n\n"
            f"👤 {uid} (@{username})\n"
            f"{alias_line}"
            f"🕰️ {full_time}\n"
            f"🌐 via the corridor (mini app)\n\n"
            f"{text}",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"app letter: keeper notify failed: {exc}", file=sys.stderr)
    return {}


async def _vow_get(user: dict, payload: dict) -> dict:
    """The vow currently burning, if any."""
    vow = await _store.get_vow(user["id"])
    if not vow:
        return {"vow": None}
    return {"vow": {"text": vow["text"], "days_left": vow_days_left(vow)}}


async def _vow_set(user: dict, payload: dict) -> dict:
    """Swear (or replace) a vow the dark will remind you of in N days."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("empty vow")
    text = text[:2000]

    try:
        days = int(payload.get("days"))
    except (TypeError, ValueError):
        raise ValueError("days must be a whole number")
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")

    now = datetime.now(timezone.utc)
    vow = {
        "text": text,
        "created_at": now.isoformat(),
        "remind_at": (now + timedelta(days=days)).timestamp(),
        "reminded": False,
    }
    await _store.set_vow(user["id"], vow)
    return {"vow": {"text": text, "days_left": days}}


async def _countdown(user: dict, payload: dict) -> dict:
    """Parse a Persian-calendar date into a countdown. Empty input → today's date."""
    raw = (payload.get("date") or "").strip()
    now = datetime.now(timezone.utc)
    if not raw:
        return {"today": jalali_str(now)}

    try:
        target, label = parse_persian_countdown(raw)
    except ValueError:
        return {"error": "unreadable"}

    target_jalali = jalali_str(target)
    if target < now:
        return {"label": label, "target_jalali": target_jalali, "passed": True}

    delta = target - now
    hours, remainder = divmod(delta.seconds, 3600)
    return {
        "label": label,
        "target_jalali": target_jalali,
        "passed": False,
        "days": delta.days,
        "hours": hours,
        "minutes": remainder // 60,
    }


async def _alias_get(user: dict, payload: dict) -> dict:
    return {"alias": await _store.get_alias(user["id"])}


async def _alias_set(user: dict, payload: dict) -> dict:
    alias = (payload.get("alias") or "").strip()[:32]
    if not alias:
        raise ValueError("empty alias")
    await _store.set_alias(user["id"], alias)
    return {"alias": alias}


async def _archive(user: dict, payload: dict) -> dict:
    """What the dark remembers of you — the /myarchive screen."""
    uid = user["id"]
    stats = await _store.get_user_stats(uid)
    alias = await _store.get_alias(uid)
    vow = await _store.get_vow(uid)
    vow_out = {"text": vow["text"], "days_left": vow_days_left(vow)} if vow else None
    return {"alias": alias, "stats": stats, "vow": vow_out}


ACTIONS = {
    "me": _me,
    "dark": _dark,
    "fortune": _fortune,
    "mood": _mood,
    "mirror": _mirror,
    "send": _send,
    "inbox": _inbox,
    "ritual_questions": _ritual_questions,
    "ritual": _ritual,
    "letter": _letter,
    "vow_get": _vow_get,
    "vow_set": _vow_set,
    "countdown": _countdown,
    "alias_get": _alias_get,
    "alias_set": _alias_set,
    "archive": _archive,
}


async def _dispatch(action: str, user: dict, payload: dict) -> dict:
    handler = ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"unknown action: {action}")
    return await handler(user, payload)


# ================== HTTP ==================
class handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # A browser hitting the API directly just confirms it is alive.
        self._json(200, {"ok": True, "corridor": "open"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "bad json"})
            return

        init_data = self.headers.get("X-Telegram-Init-Data", "")
        try:
            user = validate_init_data(init_data)
        except InitDataError as exc:
            self._json(401, {"ok": False, "error": str(exc)})
            return

        action = body.pop("action", None)
        if not action:
            self._json(400, {"ok": False, "error": "missing action"})
            return

        try:
            with _lock:
                result = _loop.run_until_complete(_dispatch(action, user, body))
            self._json(200, {"ok": True, **result})
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            print(f"app error ({action}): {exc}", file=sys.stderr)
            self._json(500, {"ok": False, "error": "the dark swallowed something"})
