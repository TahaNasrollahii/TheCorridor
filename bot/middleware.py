"""Activity tracking.

The keeper wants to know *everything* a soul does in the corridor — not only
when a finished message is carried through, but every command typed and every
button tapped, the moment it happens.

This is an aiogram outer middleware attached to both the message and
callback-query observers. For each incoming event it sends the keeper a short,
clean notice of who did what and when, then lets the normal handler run.

It deliberately stays quiet for:
  * the keeper's own actions (you don't need to be told what you just did);
  * plain (non-command) messages — those already produce a full delivery
    notice once the sender chooses what the message carries, so announcing
    them here too would only double up.
"""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import ADMIN_ID
from bot.storage import Store
from bot.texts import CALLBACK_ACTIVITY, COMMAND_ACTIVITY
from bot.timeutil import tehran_stamp


def _command_of(message: Message) -> str | None:
    text = message.text or ""
    if not text.startswith("/"):
        return None
    # "/ritual" or "/alias the name" or "/start@thebot" -> "ritual" / "alias" / "start"
    first = text.split()[0]
    return first[1:].split("@", 1)[0].lower()


async def _notify(bot: Any, store: Store, user: Any, action: str) -> None:
    if user is None or user.id == ADMIN_ID:
        return

    name = f"@{user.username}" if user.username else (user.full_name or "a nameless soul")
    alias = await store.get_alias(user.id)
    alias_line = f"🪦 {alias}\n" if alias else ""
    when = tehran_stamp()

    notice = (
        "👁️ a soul stirs in the corridor\n"
        "─────────────────\n"
        f"👤 {name}\n"
        f"🆔 {user.id}\n"
        f"{alias_line}"
        f"✦ {action}\n"
        f"🕰️ {when}"
    )
    try:
        await bot.send_message(ADMIN_ID, notice)
    except Exception:
        pass


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot = data.get("bot")
        store: Store | None = data.get("store")

        if bot is not None and store is not None:
            action = None
            user = None

            if isinstance(event, Message):
                command = _command_of(event)
                if command is not None:
                    user = event.from_user
                    action = COMMAND_ACTIVITY.get(command, f"⌨️ used /{command}")

            elif isinstance(event, CallbackQuery):
                user = event.from_user
                cdata = event.data or ""
                # the keeper's own admin buttons aren't worth announcing
                if not cdata.startswith("admin_"):
                    action = CALLBACK_ACTIVITY.get(cdata, f"🔘 tapped a button ({cdata})")

            if action is not None:
                await _notify(bot, store, user, action)

        return await handler(event, data)
