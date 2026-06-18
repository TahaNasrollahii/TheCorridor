"""All bot handlers, registered on a single Router.

Compared to the original polling bot, the only structural changes are:

  * handlers that talk to the keeper take an injected ``bot: Bot`` instead of a
    module-level global (each Vercel invocation builds its own Bot);
  * handlers that read/write counters, blocks, aliases, etc. take an injected
    ``store: Store`` instead of module-level dicts/sets;
  * the "pending message" is stored in Redis (chat_id + message_id + text)
    rather than holding the whole Message object in memory.

The conversational copy and behaviour are otherwise identical.
"""

import random
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReactionTypeEmoji,
)

from bot.config import ADMIN_ID
from bot.storage import Store
from bot.texts import (
    CHAT_TEXT,
    CONFIRM_MESSAGES,
    DARK_QUOTES,
    DARK_REACTIONS,
    FORTUNES,
    HELP_TEXT,
    MESSAGE_TYPES,
    MIRROR_RESPONSES,
    MOOD_RESPONSES,
    NIGHT_CONFIRM_MESSAGES,
    NIGHT_HOURS,
    RETURNING_TEXT,
    RITUAL_QUESTIONS,
    SEASONS,
    START_TEXT,
)

router = Router()


# ================== STATES ==================
class RitualStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()


class LetterState(StatesGroup):
    writing = State()


class CountdownState(StatesGroup):
    waiting = State()


class MirrorState(StatesGroup):
    waiting = State()


# ================== HELPERS ==================
def get_text(message: Message) -> str:
    return message.text or message.caption or "[MEDIA]"


def get_season(month: int) -> str:
    for months, label in SEASONS.items():
        if month in months:
            return label
    return ""


def get_now_info() -> tuple[str, str, bool]:
    now = datetime.now(timezone.utc)
    time_str = now.strftime("%H:%M UTC")
    date_str = now.strftime("%Y-%m-%d")
    season = get_season(now.month)
    is_night = now.hour in NIGHT_HOURS
    full_time = f"{time_str} — {date_str} — {season}"
    return full_time, date_str, is_night


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚪 enter the dark", callback_data="cmd_start"),
            InlineKeyboardButton(text="✒️ speak", callback_data="cmd_chat"),
        ],
        [
            InlineKeyboardButton(text="📖 the guide", callback_data="cmd_help"),
        ],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📜 the archive", callback_data="admin_archive"),
            InlineKeyboardButton(text="🚫 cast out", callback_data="admin_block_prompt"),
        ],
        [
            InlineKeyboardButton(text="🔓 lift the curse", callback_data="admin_unblock_prompt"),
            InlineKeyboardButton(text="🌑 refresh", callback_data="admin_stats"),
        ],
    ])


def message_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🩸 confession", callback_data="type_confession"),
            InlineKeyboardButton(text="🕯️ question", callback_data="type_question"),
            InlineKeyboardButton(text="🌑 just words", callback_data="type_just_words"),
        ]
    ])


def mood_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥀 broken", callback_data="mood_broken"),
            InlineKeyboardButton(text="🌫️ numb", callback_data="mood_numb"),
        ],
        [
            InlineKeyboardButton(text="🔥 burning", callback_data="mood_burning"),
            InlineKeyboardButton(text="🕷️ restless", callback_data="mood_restless"),
        ],
    ])


async def get_stats_text(store: Store) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = await store.get_day(today)
    days = await store.all_days()
    if days:
        peak_day = max(days, key=days.get)
        peak_count = days[peak_day]
    else:
        peak_day, peak_count = "none", 0
    counter = await store.get_counter()
    senders = await store.senders_count()
    blocked = await store.blocked_count()
    refreshed_at = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    return (
        f"📜 the dark archive speaks:\n\n"
        f"📩 total messages received: {counter}\n"
        f"👤 unique souls who wrote: {senders}\n"
        f"🕯️ messages today: {today_count}\n"
        f"🌑 darkest day: {peak_day} ({peak_count} messages)\n"
        f"🚫 souls cast out: {blocked}\n\n"
        f"🕰️ last refreshed: {refreshed_at}"
    )


# ================== START ==================
@router.message(Command("start"))
async def start(message: Message, state: FSMContext, bot: Bot, store: Store):
    await state.clear()
    user = message.from_user
    identifier = f"@{user.username}" if user.username else f"ID: {user.id}"

    if user.id == ADMIN_ID:
        stats_text = await get_stats_text(store)
        await message.answer(
            f"🌑 the keeper returns.\n\n{stats_text}",
            reply_markup=admin_keyboard(),
        )
        return

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🌑 a soul arrived\n\n👤 {identifier} just started the bot",
        )
    except Exception:
        pass

    if await store.is_returning(user.id):
        await message.answer(RETURNING_TEXT, reply_markup=main_keyboard())
    else:
        await store.add_returning(user.id)
        await message.answer(START_TEXT, reply_markup=main_keyboard())


# ================== HELP ==================
@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(HELP_TEXT, reply_markup=main_keyboard())


# ================== CHAT ==================
@router.message(Command("chat"))
async def chat(message: Message):
    await message.answer(CHAT_TEXT, reply_markup=main_keyboard())


# ================== DARK QUOTE ==================
@router.message(Command("dark"))
async def dark_quote(message: Message):
    quote = random.choice(DARK_QUOTES)
    await message.answer(f"🌑\n\n_{quote}_")


# ================== FORTUNE ==================
@router.message(Command("fortune"))
async def fortune(message: Message):
    fortune_text = random.choice(FORTUNES)
    await message.answer(f"🔮 the dark has read you:\n\n_{fortune_text}_")


# ================== MOOD ==================
@router.message(Command("mood"))
async def mood(message: Message):
    await message.answer(
        "how does the dark find you tonight?\n\nchoose — and it will answer. 🌫️",
        reply_markup=mood_keyboard(),
    )


@router.callback_query(F.data.startswith("mood_"))
async def cb_mood(callback: CallbackQuery):
    mood_key = callback.data.replace("mood_", "")
    response = MOOD_RESPONSES.get(mood_key)
    if not response:
        await callback.answer()
        return
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(response)


# ================== MIRROR ==================
@router.message(Command("mirror"))
async def mirror(message: Message, state: FSMContext):
    await state.set_state(MirrorState.waiting)
    await message.answer(
        "🪞\n\n"
        "if the darkness inside you had a shape —\n"
        "what would it be?\n\n"
        "answer in one word."
    )


@router.message(MirrorState.waiting)
async def mirror_response(message: Message, state: FSMContext):
    await state.clear()
    word = message.text.strip().lower() if message.text else ""

    matched = None
    for key in MIRROR_RESPONSES:
        if key in word:
            matched = MIRROR_RESPONSES[key]
            break

    if not matched:
        matched = random.choice(list(MIRROR_RESPONSES.values()))

    await message.answer(f"🪞 the mirror speaks:\n\n_{matched}_")


# ================== RITUAL ==================
@router.message(Command("ritual"))
async def ritual_start(message: Message, state: FSMContext):
    await state.set_state(RitualStates.q1)
    await state.update_data(answers=[])
    await message.answer(
        "🕯️ the ritual begins.\n\n"
        "four questions. answer honestly.\n"
        "what is gathered here will be sent to the keeper.\n\n"
        f"I. {RITUAL_QUESTIONS[0]}"
    )


@router.message(RitualStates.q1)
async def ritual_q1(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q2)
    await message.answer(f"II. {RITUAL_QUESTIONS[1]}")


@router.message(RitualStates.q2)
async def ritual_q2(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q3)
    await message.answer(f"III. {RITUAL_QUESTIONS[2]}")


@router.message(RitualStates.q3)
async def ritual_q3(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q4)
    await message.answer(f"IV. {RITUAL_QUESTIONS[3]}")


@router.message(RitualStates.q4)
async def ritual_q4(message: Message, state: FSMContext, bot: Bot, store: Store):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    alias = await store.get_alias(user_id)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    full_time, _, _ = get_now_info()

    ritual_record = (
        f"🕯️ RITUAL COMPLETED\n\n"
        f"👤 {user_id} (@{username})\n"
        f"{alias_line}"
        f"🕰️ {full_time}\n\n"
        f"I. {RITUAL_QUESTIONS[0]}\n→ {answers[0]}\n\n"
        f"II. {RITUAL_QUESTIONS[1]}\n→ {answers[1]}\n\n"
        f"III. {RITUAL_QUESTIONS[2]}\n→ {answers[2]}\n\n"
        f"IV. {RITUAL_QUESTIONS[3]}\n→ {answers[3]}"
    )

    try:
        await bot.send_message(ADMIN_ID, ritual_record)
    except Exception:
        pass

    await message.answer(
        "🕯️ the ritual is complete.\n\n"
        "what you gave has been received.\n"
        "the corridor holds it now —\n"
        "sealed, nameless, and still."
    )


# ================== LETTER ==================
@router.message(Command("letter"))
async def letter_start(message: Message, state: FSMContext):
    await state.set_state(LetterState.writing)
    await message.answer(
        "📜\n\n"
        "write a letter to someone\n"
        "you will never send it to.\n\n"
        "take your time.\n"
        "when you're done — just send. ✒️"
    )


@router.message(LetterState.writing)
async def letter_receive(message: Message, state: FSMContext, bot: Bot, store: Store):
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    alias = await store.get_alias(user_id)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    full_time, _, _ = get_now_info()
    text = get_text(message)

    try:
        await bot.send_message(
            ADMIN_ID,
            f"📜 UNSENT LETTER\n\n"
            f"👤 {user_id} (@{username})\n"
            f"{alias_line}"
            f"🕰️ {full_time}\n\n"
            f"{text}",
        )
    except Exception:
        pass

    await message.answer(
        "📜 the letter has been folded and kept.\n\n"
        "it will never reach them.\n"
        "but it exists now — and that is something."
    )


# ================== COUNTDOWN ==================
@router.message(Command("countdown"))
async def countdown_start(message: Message, state: FSMContext):
    await state.set_state(CountdownState.waiting)
    await message.answer(
        "⏳\n\n"
        "name a moment you are counting toward.\n\n"
        "write it like this:\n"
        "YYYY-MM-DD | what it is\n\n"
        "example:\n"
        "2026-12-31 | the end of this year"
    )


@router.message(CountdownState.waiting)
async def countdown_receive(message: Message, state: FSMContext):
    await state.clear()

    if not message.text or "|" not in message.text:
        await message.answer(
            "❌ the format was lost in the dark.\n\ntry again:\nYYYY-MM-DD | what it is"
        )
        return

    try:
        parts = message.text.split("|", 1)
        date_part = parts[0].strip()
        label = parts[1].strip() if len(parts) > 1 else "the unnamed moment"
        target = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        if target < now:
            await message.answer(
                f"⏳ __{label}__\n\n"
                f"that moment has already passed.\n"
                f"it lives behind you now —\n"
                f"in the part of the corridor you can no longer see."
            )
            return

        delta = target - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60

        await message.answer(
            f"⏳ __{label}__\n\n"
            f"{days} days, {hours} hours, and {minutes} minutes\n"
            f"stand between you and that moment.\n\n"
            f"the dark is already counting."
        )

    except ValueError:
        await message.answer(
            "❌ the date couldn't be read.\n\n"
            "use this format exactly:\n"
            "YYYY-MM-DD | what it is"
        )


# ================== CONFESS ==================
@router.message(Command("confess"))
async def confess(message: Message):
    await message.answer(
        "speak your confession.\n"
        "no name. no face. no mercy asked.\n\n"
        "write it — and send. 🩸"
    )


# ================== ALIAS ==================
@router.message(Command("alias"))
async def set_alias(message: Message, store: Store):
    parts = message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "choose a name for yourself.\n"
            "something dark. something true.\n\n"
            "format: /alias the name you choose\n\n"
            "only the keeper will see it. 🪦"
        )
        return

    alias = parts[1].strip()[:32]
    await store.set_alias(message.from_user.id, alias)
    await message.answer(
        f"from now on, you arrive as:\n\n"
        f"__{alias}__\n\n"
        f"the keeper will know. no one else will. ✒️"
    )


# ================== BLOCK / UNBLOCK ==================
@router.message(Command("block"))
async def block_user(message: Message, store: Store):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("format: /block user_id")
            return
        uid = int(parts[1])
        await store.block(uid)
        await message.answer(f"🚫 {uid} has been cast out of the corridor.")
    except Exception as e:
        await message.answer(f"❌ error: {e}")


@router.message(Command("unblock"))
async def unblock_user(message: Message, store: Store):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("format: /unblock user_id")
            return
        uid = int(parts[1])
        await store.unblock(uid)
        await message.answer(f"🔓 {uid} has been let back through the gate.")
    except Exception as e:
        await message.answer(f"❌ error: {e}")


# ================== STATS ==================
@router.message(Command("stats"))
async def stats(message: Message, store: Store):
    if message.from_user.id != ADMIN_ID:
        return
    stats_text = await get_stats_text(store)
    await message.answer(stats_text, reply_markup=admin_keyboard())


# ================== ADMIN CALLBACKS ==================
@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, store: Store):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("you don't belong here.", show_alert=True)
        return
    try:
        stats_text = await get_stats_text(store)
        await callback.message.edit_text(stats_text, reply_markup=admin_keyboard())
    except Exception:
        pass
    await callback.answer("🌑 the archive stirs...")


@router.callback_query(F.data == "admin_archive")
async def cb_admin_archive(callback: CallbackQuery, store: Store):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("you don't belong here.", show_alert=True)
        return

    senders = await store.senders_list()
    aliases = await store.all_aliases()
    if senders:
        senders_list = "\n".join(
            f"• {uid}" + (f" — {aliases[str(uid)]}" if str(uid) in aliases else "")
            for uid in senders
        )
    else:
        senders_list = "none yet"

    blocked = await store.blocked_list()
    blocked_list = "\n".join(f"• {uid}" for uid in blocked) if blocked else "none cast out"

    days = await store.all_days()
    if days:
        sorted_days = sorted(days.items(), reverse=True)
        daily_list = "\n".join(f"• {day}: {count}" for day, count in sorted_days[:10])
    else:
        daily_list = "nothing yet"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = await store.get_day(today)

    archive_text = (
        f"📜 the dark archive — full record:\n\n"
        f"👤 souls who wrote ({len(senders)}):\n{senders_list}\n\n"
        f"🚫 cast out ({len(blocked)}):\n{blocked_list}\n\n"
        f"🕯️ messages by day (last 10):\n{daily_list}\n\n"
        f"📩 today ({today}): {today_count} messages"
    )

    try:
        await callback.message.answer(archive_text)
    except Exception:
        pass
    await callback.answer("📜 the archive opens...")


@router.callback_query(F.data == "admin_block_prompt")
async def cb_block_prompt(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("you don't belong here.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("send the user_id to cast out:\n/block user_id")


@router.callback_query(F.data == "admin_unblock_prompt")
async def cb_unblock_prompt(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("you don't belong here.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("send the user_id to lift the curse:\n/unblock user_id")


# ================== USER CALLBACKS ==================
@router.callback_query(F.data == "cmd_start")
async def cb_start(callback: CallbackQuery, store: Store):
    await callback.answer()
    user_id = callback.from_user.id
    if await store.is_returning(user_id):
        await callback.message.answer(RETURNING_TEXT, reply_markup=main_keyboard())
    else:
        await store.add_returning(user_id)
        await callback.message.answer(START_TEXT, reply_markup=main_keyboard())


@router.callback_query(F.data == "cmd_chat")
async def cb_chat(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(CHAT_TEXT, reply_markup=main_keyboard())


@router.callback_query(F.data == "cmd_help")
async def cb_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(HELP_TEXT, reply_markup=main_keyboard())


# ================== MESSAGE TYPE CALLBACKS ==================
@router.callback_query(F.data.startswith("type_"))
async def cb_message_type(callback: CallbackQuery, bot: Bot, store: Store):
    user_id = callback.from_user.id
    msg_type = callback.data.replace("type_", "")
    label = MESSAGE_TYPES.get(msg_type, "🌑 JUST WORDS")

    pending = await store.pop_pending(user_id)
    if not pending:
        await callback.answer("something was lost. try again.", show_alert=True)
        return

    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    username = pending.get("username") or "no_username"
    alias = await store.get_alias(user_id)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    text = pending.get("text") or "[MEDIA]"
    chat_id = int(pending["chat_id"])
    message_id = int(pending["message_id"])
    full_time, date_str, is_night = get_now_info()

    counter = await store.incr_counter()
    await store.add_sender(user_id)
    await store.incr_day(date_str)

    try:
        await bot.send_message(
            ADMIN_ID,
            f"📩 {label}  #{counter}\n\n"
            f"👤 Sender: {user_id} (@{username})\n"
            f"{alias_line}"
            f"💬 Carried: {text}\n"
            f"🕰️ {full_time}\n\n"
            f"To answer:\n/reply {user_id} your message",
        )
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=chat_id,
            message_id=message_id,
        )
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"⚠️ something was lost in transit:\n{e}")

    try:
        reaction_emoji = random.choice(DARK_REACTIONS)
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=reaction_emoji)],
        )
    except Exception:
        pass

    confirm = random.choice(NIGHT_CONFIRM_MESSAGES if is_night else CONFIRM_MESSAGES)
    await bot.send_message(chat_id, confirm)


# ================== ADMIN REPLY ==================
@router.message(Command("reply"))
async def admin_reply(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = None
        reply_text = None

        if message.reply_to_message and message.reply_to_message.text:
            for line in message.reply_to_message.text.split("\n"):
                if "Sender:" in line:
                    after = line.split("Sender:")[1].strip()
                    user_id = int(after.split(" ")[0])
                    break
            parts = message.text.split(" ", 1)
            reply_text = parts[1] if len(parts) > 1 else None

        if not user_id:
            parts2 = message.text.split(" ", 2)
            if len(parts2) < 3:
                await message.answer("format:\n/reply user_id message")
                return
            user_id = int(parts2[1])
            reply_text = parts2[2]

        if not reply_text:
            await message.answer("format: /reply user_id message")
            return

        await bot.send_message(
            user_id,
            f"a voice returns from the other side of darkness:\n\n{reply_text}\n\n"
            f"─────────────────\n"
            f"the dark spoke. now you may —\n"
            f"reply, if you have something to say.",
            parse_mode="Markdown"
        )
        await message.answer("✔ delivered into the dark")
    except Exception as e:
        await message.answer(f"❌ error:\n{e}")


# ================== ADMIN REPLY (ANY CONTENT) ==================
@router.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
async def admin_reply_any(message: Message, bot: Bot):
    """Admin replies (Telegram native reply) to an archive message with ANY
    content — text, photo(s), video, voice, document, etc. — and it is carried
    back to the sender, wrapped in the dark framing."""
    replied = message.reply_to_message
    replied_text = replied.text or replied.caption or ""
    if "Sender:" not in replied_text:
        return

    user_id = None
    for line in replied_text.split("\n"):
        if "Sender:" in line:
            after = line.split("Sender:")[1].strip()
            try:
                user_id = int(after.split(" ")[0])
            except ValueError:
                user_id = None
            break

    if not user_id:
        return

    try:
        await bot.send_message(
            user_id,
            "a voice returns from the other side of darkness:",
        )
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await bot.send_message(
            user_id,
            "_the dark spoke. now you may —\nreply, if you have something to say._",
            parse_mode="Markdown",
        )
        await message.answer("✔ delivered into the dark")
    except Exception as e:
        await message.answer(f"❌ error:\n{e}")


# ================== USER → ADMIN ==================
@router.message()
async def handle_all(message: Message, state: FSMContext, store: Store):
    if message.text and message.text.startswith("/"):
        return

    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if await store.is_blocked(user_id):
        return

    await store.set_pending(user_id, {
        "chat_id": str(message.chat.id),
        "message_id": str(message.message_id),
        "text": get_text(message),
        "username": message.from_user.username or "no_username",
    })
    await message.answer(
        "before it arrives —\nwhat does this carry? 🩸",
        reply_markup=message_type_keyboard(),
    )
