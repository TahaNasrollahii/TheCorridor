"""Redis-backed persistence.

On Vercel every webhook is a fresh, short-lived function invocation, so we
cannot keep state in module-level dicts/sets like the polling version did —
they would reset on every cold start and the multi-step flows (ritual, letter,
countdown) would lose their place between steps.

Everything that used to live in memory now lives in Redis:

    blocked_users      -> SET  "corridor:blocked"
    unique_senders     -> SET  "corridor:senders"
    returning_users    -> SET  "corridor:returning"
    user_aliases       -> HASH "corridor:aliases"      (uid -> alias)
    message_counter    -> INT  "corridor:counter"
    messages_per_day   -> HASH "corridor:per_day"      (YYYY-MM-DD -> count)
    pending_messages   -> HASH "corridor:pending:<uid>" (the message awaiting a type)
    vows               -> STR  "corridor:vow:<uid>"    (JSON vow awaiting its reminder)
    countdowns         -> STR  "corridor:countdown:<uid>:<cid>" (JSON moment awaiting its date)
    per-user stats     -> INT  "corridor:user_stat:<uid>:<name>"
    broadcast chats    -> SET  "corridor:broadcast_chats"

The FSM (aiogram states) is handled separately by RedisStorage.
"""

import json

import redis.asyncio as aioredis
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import REDIS_URL

PREFIX = "corridor"


def make_redis() -> "aioredis.Redis":
    """A plain async Redis client for our own app state."""
    return aioredis.from_url(REDIS_URL, decode_responses=True)


def make_fsm_storage() -> RedisStorage:
    """The storage aiogram uses to remember which step of a flow a user is on."""
    return RedisStorage.from_url(REDIS_URL)


class Store:
    """Thin async wrapper over Redis for all the corridor's bookkeeping."""

    def __init__(self, redis: "aioredis.Redis"):
        self.r = redis

    # ----- blocked users -----
    async def is_blocked(self, uid: int) -> bool:
        return await self.r.sismember(f"{PREFIX}:blocked", uid)

    async def block(self, uid: int) -> None:
        await self.r.sadd(f"{PREFIX}:blocked", uid)

    async def unblock(self, uid: int) -> None:
        await self.r.srem(f"{PREFIX}:blocked", uid)

    async def blocked_count(self) -> int:
        return await self.r.scard(f"{PREFIX}:blocked")

    async def blocked_list(self) -> list[int]:
        return sorted(int(x) for x in await self.r.smembers(f"{PREFIX}:blocked"))

    # ----- returning users -----
    async def is_returning(self, uid: int) -> bool:
        return await self.r.sismember(f"{PREFIX}:returning", uid)

    async def add_returning(self, uid: int) -> None:
        await self.r.sadd(f"{PREFIX}:returning", uid)

    # ----- aliases -----
    async def set_alias(self, uid: int, alias: str) -> None:
        await self.r.hset(f"{PREFIX}:aliases", str(uid), alias)

    async def get_alias(self, uid: int) -> str | None:
        return await self.r.hget(f"{PREFIX}:aliases", str(uid))

    async def all_aliases(self) -> dict[str, str]:
        return await self.r.hgetall(f"{PREFIX}:aliases")

    # ----- identities (Telegram name/username, for the keeper's chat list) -----
    # Threads are keyed only by uid, so we cache each soul's display identity here
    # and refresh it whenever they speak (or lazily via get_chat for old chats).
    async def set_identity(self, uid: int, name: str | None, username: str | None) -> None:
        await self.r.hset(
            f"{PREFIX}:identity",
            str(uid),
            json.dumps({"name": name, "username": username}),
        )

    async def all_identities(self) -> dict[int, dict]:
        raw = await self.r.hgetall(f"{PREFIX}:identity")
        out: dict[int, dict] = {}
        for k, v in raw.items():
            try:
                out[int(k)] = json.loads(v)
            except (ValueError, TypeError):
                continue
        return out

    # ----- counters / senders -----
    async def incr_counter(self) -> int:
        return await self.r.incr(f"{PREFIX}:counter")

    async def get_counter(self) -> int:
        return int(await self.r.get(f"{PREFIX}:counter") or 0)

    async def add_sender(self, uid: int) -> None:
        await self.r.sadd(f"{PREFIX}:senders", uid)

    async def senders_count(self) -> int:
        return await self.r.scard(f"{PREFIX}:senders")

    async def senders_list(self) -> list[int]:
        return sorted(int(x) for x in await self.r.smembers(f"{PREFIX}:senders"))

    # ----- broadcast recipients -----
    async def add_broadcast_chat(self, chat_id: int) -> None:
        await self.r.sadd(f"{PREFIX}:broadcast_chats", chat_id)

    async def broadcast_chat_ids(self, exclude_chat_id: int | None = None) -> list[int]:
        # Existing private chats can be recovered from older user-id based sets:
        # in a private Telegram chat, user_id == chat_id.
        tracked = await self.r.smembers(f"{PREFIX}:broadcast_chats")
        senders = await self.r.smembers(f"{PREFIX}:senders")
        returning = await self.r.smembers(f"{PREFIX}:returning")
        chat_ids = sorted(int(x) for x in tracked | senders | returning)
        if exclude_chat_id is not None:
            chat_ids = [chat_id for chat_id in chat_ids if chat_id != exclude_chat_id]
        return chat_ids

    # ----- per-day message counts -----
    async def incr_day(self, date: str) -> None:
        await self.r.hincrby(f"{PREFIX}:per_day", date, 1)

    async def get_day(self, date: str) -> int:
        return int(await self.r.hget(f"{PREFIX}:per_day", date) or 0)

    async def all_days(self) -> dict[str, int]:
        raw = await self.r.hgetall(f"{PREFIX}:per_day")
        return {k: int(v) for k, v in raw.items()}

    # ----- pending message (between "send" and "pick a type") -----
    async def set_pending(self, uid: int, data: dict[str, str]) -> None:
        key = f"{PREFIX}:pending:{uid}"
        await self.r.hset(key, mapping=data)
        await self.r.expire(key, 3600)  # forget unconfirmed messages after an hour

    async def pop_pending(self, uid: int) -> dict[str, str] | None:
        key = f"{PREFIX}:pending:{uid}"
        data = await self.r.hgetall(key)
        await self.r.delete(key)
        return data or None

    # ----- vows (a promise the dark will remind you of) -----
    async def set_vow(self, uid: int, vow: dict) -> None:
        await self.r.set(f"{PREFIX}:vow:{uid}", json.dumps(vow))

    async def get_vow(self, uid: int) -> dict | None:
        raw = await self.r.get(f"{PREFIX}:vow:{uid}")
        return json.loads(raw) if raw else None

    async def delete_vow(self, uid: int) -> None:
        await self.r.delete(f"{PREFIX}:vow:{uid}")

    async def all_vow_keys(self) -> list[str]:
        return [k async for k in self.r.scan_iter(match=f"{PREFIX}:vow:*")]

    # ----- countdowns (a moment the dark counts toward, and reminds you of) -----
    # Unlike a vow (one per soul, a day-count), a soul may keep several
    # countdowns at once, each toward an absolute Persian-calendar date. So each
    # lives in its own key ``corridor:countdown:<uid>:<cid>``; ``cid`` comes from
    # a shared counter so keys never collide. The cron sweeps them like vows and
    # delivers one reminder when the moment arrives (``notified`` flips to True).
    async def next_countdown_id(self) -> int:
        return await self.r.incr(f"{PREFIX}:countdown_seq")

    async def save_countdown(self, uid: int, cid: int, data: dict) -> None:
        await self.r.set(f"{PREFIX}:countdown:{uid}:{cid}", json.dumps(data))

    async def get_countdown(self, uid: int, cid: int) -> dict | None:
        raw = await self.r.get(f"{PREFIX}:countdown:{uid}:{cid}")
        return json.loads(raw) if raw else None

    async def delete_countdown(self, uid: int, cid: int) -> None:
        await self.r.delete(f"{PREFIX}:countdown:{uid}:{cid}")

    async def user_countdowns(self, uid: int) -> list[tuple[int, dict]]:
        """Every countdown a soul is keeping, soonest first."""
        out: list[tuple[int, dict]] = []
        async for key in self.r.scan_iter(match=f"{PREFIX}:countdown:{uid}:*"):
            raw = await self.r.get(key)
            if not raw:
                continue
            try:
                cid = int(key.rsplit(":", 1)[1])
            except (ValueError, IndexError):
                continue
            out.append((cid, json.loads(raw)))
        out.sort(key=lambda c: c[1].get("target", 0))
        return out

    async def all_countdown_keys(self) -> list[str]:
        # The ``countdown:*`` glob (colon after "countdown") deliberately
        # excludes the ``countdown_seq`` counter (underscore after "countdown").
        return [k async for k in self.r.scan_iter(match=f"{PREFIX}:countdown:*")]

    # ----- per-user stats -----
    async def incr_user_messages(self, uid: int) -> None:
        await self.r.incr(f"{PREFIX}:user_stat:{uid}:messages")

    async def incr_user_rituals(self, uid: int) -> None:
        await self.r.incr(f"{PREFIX}:user_stat:{uid}:rituals")

    async def incr_user_letters(self, uid: int) -> None:
        await self.r.incr(f"{PREFIX}:user_stat:{uid}:letters")

    async def set_first_seen(self, uid: int, when: str) -> None:
        # only the first arrival counts — never overwrite an earlier date
        await self.r.setnx(f"{PREFIX}:user_stat:{uid}:first_seen", when)

    async def get_user_stats(self, uid: int) -> dict[str, str | int]:
        base = f"{PREFIX}:user_stat:{uid}"
        messages, rituals, letters, first_seen = await self.r.mget(
            f"{base}:messages",
            f"{base}:rituals",
            f"{base}:letters",
            f"{base}:first_seen",
        )
        return {
            "messages": int(messages or 0),
            "rituals": int(rituals or 0),
            "letters": int(letters or 0),
            "first_seen": first_seen,
        }

    # ----- inbox thread (Mini App conversation with the keeper) -----
    # A per-user list of the back-and-forth: the words the soul carried in
    # ("out") and the keeper's answers ("in"). Keeper replies are appended here
    # *in addition to* being sent as bot messages, so the app can show a thread
    # while the chat keeps working exactly as before.
    THREAD_MAX = 200

    async def add_thread_message(self, uid: int, entry: dict) -> None:
        key = f"{PREFIX}:thread:{uid}"
        await self.r.rpush(key, json.dumps(entry))
        await self.r.ltrim(key, -self.THREAD_MAX, -1)

    async def get_thread(self, uid: int) -> list[dict]:
        raw = await self.r.lrange(f"{PREFIX}:thread:{uid}", 0, -1)
        return [json.loads(x) for x in raw]

    async def all_thread_uids(self) -> list[int]:
        """Every soul that has a conversation thread — the keeper's chat list.
        The ``thread:*`` glob deliberately excludes ``thread_unread:*`` keys
        (different separator after ``thread``)."""
        prefix = f"{PREFIX}:thread:"
        uids = []
        async for key in self.r.scan_iter(match=f"{prefix}*"):
            try:
                uids.append(int(key[len(prefix):]))
            except ValueError:
                continue  # ignore any non-numeric stragglers
        return uids

    async def thread_tail(self, uid: int) -> dict | None:
        """The last message in a thread — cheap preview for the chat list,
        avoids loading all THREAD_MAX entries just to show one line."""
        raw = await self.r.lindex(f"{PREFIX}:thread:{uid}", -1)
        return json.loads(raw) if raw else None

    async def incr_unread(self, uid: int) -> None:
        await self.r.incr(f"{PREFIX}:thread_unread:{uid}")

    async def get_unread(self, uid: int) -> int:
        return int(await self.r.get(f"{PREFIX}:thread_unread:{uid}") or 0)

    async def clear_unread(self, uid: int) -> None:
        await self.r.delete(f"{PREFIX}:thread_unread:{uid}")
