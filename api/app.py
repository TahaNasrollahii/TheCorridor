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
import base64
import binascii
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
from aiogram.types import BufferedInputFile  # noqa: E402

from bot.config import ADMIN_ID, TOKEN  # noqa: E402
from bot.handlers import (  # noqa: E402
    get_now_info,
    jalali_str,
    parse_persian_countdown,
    vow_days_left,
)
from bot.storage import Store, make_redis  # noqa: E402
from bot.timeutil import tehran_stamp  # noqa: E402
from bot.texts import (  # noqa: E402
    CONFIRM_MESSAGES,
    DARK_QUOTES,
    FORTUNES,
    KEEPER_REPLY_INTRO,
    KEEPER_REPLY_OUTRO,
    KEEPER_REPLY_TEXT,
    MESSAGE_TYPES,
    MIRROR_RESPONSES,
    MOOD_RESPONSES,
    NIGHT_CONFIRM_MESSAGES,
    RITUAL_QUESTIONS,
    escape_md_v2,
)
from bot.webapp_auth import InitDataError, validate_init_data  # noqa: E402

# ---- built once per warm container, reused across invocations ----
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_lock = threading.Lock()

_redis = make_redis()
_store = Store(_redis)
_bot = Bot(token=TOKEN)


class Forbidden(Exception):
    """A non-keeper tried to reach a keeper-only action → HTTP 403."""


def _require_admin(user: dict) -> None:
    """Gate keeper-only actions. ``user`` is the HMAC-verified identity, never
    a value from the request body, so this cannot be spoofed by the client."""
    if user["id"] != ADMIN_ID:
        raise Forbidden("the keeper's sight is not yours to take")


def _full_name(first: str | None, last: str | None) -> str | None:
    """Telegram first + last name into one display name (or None if neither)."""
    return " ".join(p for p in (first, last) if p) or None


async def _fetch_identity(uid: int) -> dict:
    """Look up a soul's current name/username from Telegram and cache it — used to
    backfill old chats whose identity we never recorded. Never raises."""
    try:
        chat = await _bot.get_chat(uid)
        ident = {"name": _full_name(chat.first_name, chat.last_name), "username": chat.username}
    except Exception:  # noqa: BLE001 — a deleted/blocking soul just shows as their id
        ident = {"name": None, "username": None}
    await _store.set_identity(uid, ident["name"], ident["username"])
    return ident


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


# A media payload, once base64-decoded, must stay well under Vercel's ~4.5 MB
# request-body limit (base64 adds ~33%). We reject anything larger server-side;
# the client enforces the same ceiling before uploading.
MAX_MEDIA_BYTES = 3_000_000

# kind -> (aiogram send method name, the kwarg it expects, default filename)
_MEDIA_SENDERS = {
    "photo": ("send_photo", "photo", "photo.jpg"),
    "video": ("send_video", "video", "video.mp4"),
    "voice": ("send_voice", "voice", "voice.ogg"),
}


def _decode_media(media: dict) -> tuple[str, bytes, str]:
    """Validate a media payload → (kind, raw_bytes, filename). Raises ValueError."""
    kind = (media.get("kind") or "").lower()
    if kind not in _MEDIA_SENDERS:
        raise ValueError("unsupported media kind")

    data = media.get("data") or ""
    if "," in data and data.lstrip().startswith("data:"):
        data = data.split(",", 1)[1]  # strip a data: URL prefix if present
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("media is not valid base64")

    if not raw:
        raise ValueError("empty media")
    if len(raw) > MAX_MEDIA_BYTES:
        raise ValueError("media too large")

    filename = (media.get("filename") or _MEDIA_SENDERS[kind][2])[:80]
    return kind, raw, filename


async def _deliver_media(chat_id: int, kind: str, raw: bytes, filename: str, caption: str) -> None:
    """Send an attachment to a chat (the keeper, or a soul receiving a reply),
    falling back to a plain document if the typed method rejects it (e.g. a
    recorded voice clip that isn't OGG/opus)."""
    method_name, kwarg, _ = _MEDIA_SENDERS[kind]
    file = BufferedInputFile(raw, filename=filename)
    try:
        await getattr(_bot, method_name)(chat_id, **{kwarg: file}, caption=caption)
    except Exception:  # noqa: BLE001 — last resort so the attachment is never lost
        await _bot.send_document(
            chat_id,
            document=BufferedInputFile(raw, filename=filename),
            caption=caption,
        )


async def _send(user: dict, payload: dict) -> dict:
    """Carry a message to the keeper, the way the bot's type-picker does — but
    from the web app. Optionally carries one attachment (photo/video/voice).
    Records the same stats, notifies the keeper, mirrors the message into the
    soul's inbox thread, and returns a confirmation to show."""
    uid = user["id"]
    text = (payload.get("text") or "").strip()[:4000]

    media = payload.get("media")
    decoded = _decode_media(media) if media else None

    if not text and not decoded:
        raise ValueError("nothing to send")

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
    # Keep the keeper's chat-list label fresh for active souls.
    await _store.set_identity(
        uid, _full_name(user.get("first_name"), user.get("last_name")), user.get("username")
    )

    attach_line = f"📎 carries a {decoded[0]}\n" if decoded else ""
    try:
        await _bot.send_message(
            ADMIN_ID,
            f"📩 {label}  #{counter}\n\n"
            f"👤 Sender: {uid} (@{username})\n"
            f"{alias_line}"
            f"💬 Carried: {text or '—'}\n"
            f"{attach_line}"
            f"🕰️ {full_time}\n"
            f"🌐 via the corridor (mini app)\n\n"
            f"To answer:\n/reply {uid} your message",
        )
        if decoded:
            kind, raw, filename = decoded
            # Caption repeats the Sender line so the keeper can reply by replying
            # to the attachment itself (admin_reply_any reads "Sender:" from it).
            await _deliver_media(
                ADMIN_ID, kind, raw, filename,
                caption=f"📎 {label} #{counter}\n👤 Sender: {uid} (@{username})",
            )
    except Exception as exc:  # noqa: BLE001
        print(f"app send: keeper delivery failed: {exc}", file=sys.stderr)

    await _store.add_thread_message(uid, {
        "dir": "out",
        "text": text,  # caption only; the media kind below carries the rest
        "kind": label,
        "media": decoded[0] if decoded else None,
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

    # Persist it so the cron can return on the day itself (parity with the bot).
    cid = await _store.next_countdown_id()
    await _store.save_countdown(
        user["id"],
        cid,
        {
            "label": label,
            "target": target.timestamp(),
            "target_jalali": target_jalali,
            "created_at": now.isoformat(),
            "notified": False,
        },
    )

    delta = target - now
    hours, remainder = divmod(delta.seconds, 3600)
    return {
        "id": cid,
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

    now_ts = datetime.now(timezone.utc).timestamp()
    countdowns_out = [
        {
            "id": cid,
            "label": c.get("label", "the unnamed moment"),
            "target_jalali": c.get("target_jalali", ""),
            "days_left": max(0, int((c.get("target", 0) - now_ts) // 86400)),
        }
        for cid, c in await _store.user_countdowns(uid)
    ]
    return {"alias": alias, "stats": stats, "vow": vow_out, "countdowns": countdowns_out}


async def _unread(user: dict, payload: dict) -> dict:
    """Just the unread count — cheap enough to poll for the live inbox badge."""
    return {"unread": await _store.get_unread(user["id"])}


async def _activity(user: dict, payload: dict) -> dict:
    """Tell the keeper a soul did something in the app. Fire-and-forget from the
    client; the keeper is never told about their own moves (mirrors the bot's
    activity middleware)."""
    uid = user["id"]
    if uid == ADMIN_ID:
        return {}

    label = (payload.get("label") or "stirred").strip()[:120]
    username = user.get("username")
    name = f"@{username}" if username else (user.get("first_name") or "a nameless soul")
    alias = await _store.get_alias(uid)
    alias_line = f"🪦 {alias}\n" if alias else ""
    when = tehran_stamp()

    notice = (
        "👁️ a soul stirs in the corridor · app\n"
        "─────────────────\n"
        f"👤 {name}\n"
        f"🆔 {uid}\n"
        f"{alias_line}"
        f"✦ {label}\n"
        f"🕰️ {when}"
    )
    try:
        await _bot.send_message(ADMIN_ID, notice)
    except Exception as exc:  # noqa: BLE001
        print(f"app activity: notify failed: {exc}", file=sys.stderr)
    return {}


# ================== KEEPER CONSOLE (admin-only) ==================

async def _admin_threads(user: dict, payload: dict) -> dict:
    """Every conversation, newest first, for the keeper's chat list. A thread is
    flagged ``new`` when the last word in it came from the soul (``out``) — i.e.
    the keeper hasn't answered yet."""
    _require_admin(user)

    identities = await _store.all_identities()  # cached names, one round-trip

    threads = []
    for uid in await _store.all_thread_uids():
        tail = await _store.thread_tail(uid)
        if not tail:
            continue
        # Backfill any soul whose identity we haven't cached yet (old chats).
        ident = identities.get(uid) or await _fetch_identity(uid)
        threads.append({
            "uid": uid,
            "name": ident.get("name"),
            "username": ident.get("username"),
            "alias": await _store.get_alias(uid),
            "last_text": tail.get("text") or "",
            "last_kind": tail.get("kind"),
            "last_media": tail.get("media"),
            "last_dir": tail.get("dir"),
            "ts": tail.get("ts") or 0,
            "new": tail.get("dir") == "out",
        })

    threads.sort(key=lambda t: t["ts"], reverse=True)
    return {"threads": threads}


async def _admin_thread(user: dict, payload: dict) -> dict:
    """The full history of one soul's conversation — the same back-and-forth the
    soul sees in their own inbox."""
    _require_admin(user)
    try:
        uid = int(payload.get("uid"))
    except (TypeError, ValueError):
        raise ValueError("which soul?")
    return {
        "uid": uid,
        "alias": await _store.get_alias(uid),
        "messages": await _store.get_thread(uid),
    }


async def _admin_reply(user: dict, payload: dict) -> dict:
    """The keeper answers a soul from the console — text and/or one attachment.
    Mirrors the bot's /reply and native-reply handlers exactly: the answer is
    delivered to the soul's chat AND mirrored into their in-app inbox thread,
    and their unread badge is bumped."""
    _require_admin(user)
    try:
        uid = int(payload.get("uid"))
    except (TypeError, ValueError):
        raise ValueError("which soul?")

    text = (payload.get("text") or "").strip()[:4000]
    media = payload.get("media")
    decoded = _decode_media(media) if media else None

    if not text and not decoded:
        raise ValueError("nothing to send")

    if decoded:
        kind, raw, filename = decoded
        # Wrap the attachment in the same three-part dark framing as a native
        # Telegram reply: intro line, the media (caption = the keeper's words),
        # then the outro line.
        await _bot.send_message(uid, KEEPER_REPLY_INTRO, parse_mode="Markdown")
        await _deliver_media(uid, kind, raw, filename, caption=text or None)
        await _bot.send_message(uid, KEEPER_REPLY_OUTRO, parse_mode="MarkdownV2")
    else:
        await _bot.send_message(
            uid,
            KEEPER_REPLY_TEXT.format(reply=escape_md_v2(text)),
            parse_mode="MarkdownV2",
        )

    await _store.add_thread_message(uid, {
        "dir": "in",
        "text": text,
        "kind": "reply",
        "media": decoded[0] if decoded else None,
        "ts": datetime.now(timezone.utc).timestamp(),
    })
    await _store.incr_unread(uid)
    return {}


# ================== AI ACTIONS (RAVEN) ==================
async def _ai_history(user: dict, payload: dict) -> dict:
    uid = user["id"]
    history = await _store.get_ai_thread(uid)
    return {"messages": history}


async def _ai_clear(user: dict, payload: dict) -> dict:
    uid = user["id"]
    await _store.clear_ai_thread(uid)
    try:
        user_ref = f"@{user.get('username')}" if user.get('username') else str(uid)
        await _bot.send_message(ADMIN_ID, f"🧹 [WEB] {user_ref} cleared their Raven chat.")
    except Exception:
        pass
    return {}


async def _ai_chat(user: dict, payload: dict) -> dict:
    from bot.ai.service import AIService
    from bot.prompts.builder import PromptBuilder
    from bot.handlers import get_now_info
    
    uid = user["id"]
    text = payload.get("text", "").strip()
    if not text:
        raise ValueError("empty message")

    if not await _store.check_rate_limit(uid, "min", 5, 60):
        raise ValueError("the dark needs a moment to breathe. wait.")

    user_ref = f"@{user.get('username')}" if user.get('username') else str(uid)
    try:
        await _bot.send_message(ADMIN_ID, f"🐦‍⬛ [WEB] 👤 {user_ref}:\n\n{text}")
    except Exception:
        pass

    await _store.add_ai_message(uid, {"role": "user", "content": text, "timestamp": datetime.now(timezone.utc).timestamp()})
    
    history = await _store.get_ai_thread(uid)
    from bot.config import MAX_CONTEXT_MESSAGES
    if len(history) >= MAX_CONTEXT_MESSAGES:
        kept = history[-5:]
        summary_msg = {"role": "system", "content": "Conversation history was truncated for brevity.", "timestamp": datetime.now(timezone.utc).timestamp()}
        history = [summary_msg] + kept
        await _store.set_ai_thread(uid, history)

    full_time, date_str, _ = get_now_info()
    alias = await _store.get_alias(uid)
    prompt = PromptBuilder.build_system_prompt(time_str=f"{full_time} ({date_str})", alias=alias)
    
    ai_service = AIService()
    clean_history = [{"role": m["role"], "content": m["content"]} for m in history]
    try:
        response_text = await ai_service.generate_response(prompt, clean_history)
    except Exception as e:
        print(f"RAVEN API ERROR: {e}")
        await _store.set_ai_thread(uid, history[:-1])
        raise ValueError("the shadows warped your words. try again.")

    await _store.add_ai_message(uid, {"role": "assistant", "content": response_text, "timestamp": datetime.now(timezone.utc).timestamp()})
    
    try:
        await _bot.send_message(ADMIN_ID, f"🐦‍⬛ [WEB] 🌑 Raven to {user_ref}:\n\n{response_text}")
    except Exception:
        pass

    return {"text": response_text}


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
    "unread": _unread,
    "activity": _activity,
    "admin_threads": _admin_threads,
    "admin_thread": _admin_thread,
    "admin_reply": _admin_reply,
    "ai_history": _ai_history,
    "ai_clear": _ai_clear,
    "ai_chat": _ai_chat,
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
        except Forbidden as exc:
            self._json(403, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            print(f"app error ({action}): {exc}", file=sys.stderr)
            self._json(500, {"ok": False, "error": "the dark swallowed something"})
