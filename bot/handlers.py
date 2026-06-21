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

import asyncio
import random
import re
from datetime import datetime, timedelta, timezone

import jdatetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReactionTypeEmoji,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from bot.config import ADMIN_ID, WEBAPP_URL
from bot.storage import Store
from bot.timeutil import tehran_now, tehran_stamp
from bot.texts import (
    CHAT_TEXT,
    CONFIRM_MESSAGES,
    DARK_QUOTES,
    DARK_REACTIONS,
    FLOW_CANCELLED_TEXT,
    FORTUNES,
    HELP_TEXT,
    KEEPER_REPLY_INTRO,
    KEEPER_REPLY_OUTRO,
    KEEPER_REPLY_TEXT,
    MESSAGE_TYPES,
    escape_md_v2,
    MIRROR_RESPONSES,
    MOOD_RESPONSES,
    NIGHT_CONFIRM_MESSAGES,
    NIGHT_HOURS,
    RETURNING_TEXT,
    RITUAL_QUESTIONS,
    SEASONS,
    START_TEXT,
    VOW_DAYS_ERROR,
    VOW_DAYS_TEXT,
    VOW_KEPT_TEXT,
    VOW_SAVED_TEXT,
    VOW_WRITE_TEXT,
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


class VowState(StatesGroup):
    writing = State()
    days = State()


class BroadcastState(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirmation = State()


# ================== HELPERS ==================
def get_text(message: Message) -> str:
    return message.text or message.caption or "[MEDIA]"


def media_kind(message: Message) -> str | None:
    """The kind of attachment a message carries, for inbox display — or None."""
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.voice:
        return "voice"
    if message.audio:
        return "audio"
    if message.animation:
        return "animation"
    if message.video_note:
        return "video"
    if message.sticker:
        return "sticker"
    if message.document:
        return "document"
    return None


def get_season(month: int) -> str:
    for months, label in SEASONS.items():
        if month in months:
            return label
    return ""


def get_now_info() -> tuple[str, str, bool]:
    now = tehran_now()
    time_str = now.strftime("%H:%M Tehran")
    date_str = now.strftime("%Y-%m-%d")
    season = get_season(now.month)
    is_night = now.hour in NIGHT_HOURS
    full_time = f"{time_str} — {date_str} — {season}"
    return full_time, date_str, is_night


# Persian (۰-۹) and Arabic-Indic (٠-٩) digits → ASCII, so users can type
# their date however their keyboard produces it.
_DIGIT_MAP = {
    **{ord("۰") + i: str(i) for i in range(10)},
    **{ord("٠") + i: str(i) for i in range(10)},
}

# Persian month names, in order, so people can write the month as a word.
_PERSIAN_MONTHS = {
    "فروردین": 1, "اردیبهشت": 2, "خرداد": 3,
    "تیر": 4, "مرداد": 5, "شهریور": 6,
    "مهر": 7, "آبان": 8, "آذر": 9,
    "دی": 10, "بهمن": 11, "اسفند": 12,
}


def normalize_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def parse_persian_countdown(raw: str) -> tuple[datetime, str]:
    """Parse a flexible Persian-calendar countdown line into (target_utc, label).

    Accepts the date and label separated by ``|`` or just whitespace, the date
    written with any of ``- / . ‏`` (or spaces) between parts, Persian/Arabic or
    ASCII digits, and the month as a number or a Persian month name. Examples
    that all work::

        1405/03/29 | زمان مرگم سال
        ۱۴۰۵-۱۰-۱۱ the end of the year
        29 خرداد 1405

    Raises ``ValueError`` if the date can't be understood.
    """
    text = normalize_digits(raw).strip()

    # Split the label off: explicit "|" wins, otherwise everything after the
    # date tokens is the label.
    label = ""
    if "|" in text:
        date_part, label = text.split("|", 1)
    else:
        date_part = text

    tokens = [t for t in re.split(r"[\s\-/.،]+", date_part.strip()) if t]

    nums: list[int] = []
    month_from_name: int | None = None
    leftover: list[str] = []
    for tok in tokens:
        if tok.isdigit():
            nums.append(int(tok))
        elif tok in _PERSIAN_MONTHS:
            month_from_name = _PERSIAN_MONTHS[tok]
        else:
            leftover.append(tok)

    # If a month name was used, the two remaining numbers are day and year.
    if month_from_name is not None:
        if len(nums) != 2:
            raise ValueError("need a day and a year alongside the month name")
        a, b = nums
        # Year is the 4-digit one (or the larger); the other is the day.
        year, day = (a, b) if a > 31 else (b, a)
        month = month_from_name
    else:
        if len(nums) != 3:
            raise ValueError("need year, month and day")
        year, month, day = nums

    jdate = jdatetime.date(year, month, day)  # raises ValueError if invalid
    gdate = jdate.togregorian()
    target = datetime(gdate.year, gdate.month, gdate.day, tzinfo=timezone.utc)

    # If "|" wasn't used, any non-date words become the label.
    if not label.strip() and leftover:
        label = " ".join(leftover)

    return target, label.strip() or "the unnamed moment"


def jalali_str(dt: datetime) -> str:
    """A Gregorian datetime formatted as a Persian (Jalali) date string."""
    j = jdatetime.date.fromgregorian(date=dt.date())
    return j.strftime("%Y/%m/%d")


def vow_days_left(vow: dict) -> int:
    """Whole days remaining until a vow's reminder, never below zero."""
    remind_at = datetime.fromtimestamp(vow["remind_at"], tz=timezone.utc)
    delta = remind_at - datetime.now(timezone.utc)
    return max(0, delta.days)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """A single 'never mind' button attached to every multi-step prompt, so a
    soul can leave a flow (vow, countdown, ritual, letter, mirror, whisper)
    without finishing it. Handled by ``cb_cancel_flow``."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌫️ never mind", callback_data="cancel_flow")]
    ])


def vow_replace_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🩸 swear anew", callback_data="vow_replace"),
            InlineKeyboardButton(text="✒️ let it stand", callback_data="vow_keep"),
        ]
    ])


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


# ================== REPLY KEYBOARD ==================
# A persistent keyboard beneath the message box. Telegram does not allow custom
# colors or animated/custom emoji on reply-keyboard buttons, so the aesthetic
# comes from static emoji + the corridor's voice in the labels. Tapping a button
# sends its label as plain text; ``REPLY_LABELS`` maps each label back to the
# command its handler already implements.
REPLY_LABELS = {
    "✒️ whisper to Taha": "chat",
    "🌑 a dark quote": "dark",
    "🔮 a fortune": "fortune",
    "🌫️ the mood": "mood",
    "🪞 the mirror": "mirror",
    "🕯️ the ritual": "ritual",
    "📜 a letter": "letter",
    "🩸 a vow": "vow",
    "⏳ a countdown": "countdown",
    "🪦 your alias": "alias",
    "📖 your archive": "myarchive",
    "👁️ the guide": "help",
}


def corridor_keyboard() -> ReplyKeyboardMarkup:
    """The persistent dark keyboard. A web-app launch button leads the rows when
    a WEBAPP_URL is configured (reply-keyboard buttons may open Mini Apps)."""
    rows: list[list[KeyboardButton]] = []

    rows.append([KeyboardButton(text="✒️ whisper to Taha")])

    if WEBAPP_URL:
        rows.append([
            KeyboardButton(
                text="🚪 open the corridor",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ])

    rows += [
        [KeyboardButton(text="🌑 a dark quote"), KeyboardButton(text="🔮 a fortune")],
        [KeyboardButton(text="🌫️ the mood"), KeyboardButton(text="🪞 the mirror")],
        [KeyboardButton(text="🕯️ the ritual"), KeyboardButton(text="📜 a letter")],
        [KeyboardButton(text="🩸 a vow"), KeyboardButton(text="⏳ a countdown")],
        [KeyboardButton(text="🪦 your alias"), KeyboardButton(text="📖 your archive")],
        [KeyboardButton(text="👁️ the guide")],
    ]

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=False,
        input_field_placeholder="Whisper…",
    )


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
        [
            InlineKeyboardButton(text="📣 broadcast", callback_data="admin_broadcast"),
        ],
    ])


def message_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🩸 confession", callback_data="type_confession"),
            InlineKeyboardButton(text="🕯️ question", callback_data="type_question"),
            InlineKeyboardButton(text="🌑 just words", callback_data="type_just_words"),
        ],
        [InlineKeyboardButton(text="🌫️ never mind", callback_data="cancel_flow")],
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


async def deliver_to_keeper(
    bot: Bot,
    store: Store,
    *,
    user_id: int,
    username: str,
    chat_id: int,
    message_id: int,
    text: str,
    label: str,
    media: str | None = None,
) -> None:
    """Carry one message to the keeper: notify, forward, react, confirm."""
    alias = await store.get_alias(user_id)
    alias_line = f"🪦 Alias: {alias}\n" if alias else ""
    full_time, date_str, is_night = get_now_info()

    counter = await store.incr_counter()
    await store.add_sender(user_id)
    await store.incr_day(date_str)
    await store.incr_user_messages(user_id)

    # Mirror the carried words into the soul's inbox thread, so the Mini App
    # can show the conversation alongside the chat. The bare "[MEDIA]" sentinel
    # becomes an empty caption — the media kind carries the meaning instead.
    await store.add_thread_message(user_id, {
        "dir": "out",
        "text": "" if text == "[MEDIA]" else text,
        "kind": label,
        "media": media,
        "ts": datetime.now(timezone.utc).timestamp(),
    })

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
    await bot.send_message(chat_id, confirm, reply_markup=corridor_keyboard())


async def get_stats_text(store: Store) -> str:
    today = tehran_now().strftime("%Y-%m-%d")
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
    refreshed_at = tehran_now().strftime("%H:%M:%S Tehran")
    return (
        f"📜 the dark archive speaks:\n\n"
        f"📩 total messages received: {counter}\n"
        f"👤 unique souls who wrote: {senders}\n"
        f"🕯️ messages today: {today_count}\n"
        f"🌑 darkest day: {peak_day} ({peak_count} messages)\n"
        f"🚫 souls cast out: {blocked}\n\n"
        f"🕰️ last refreshed: {refreshed_at}"
    )


async def run_broadcast(
    bot: Bot,
    *,
    admin_chat_id: int,
    from_chat_id: int,
    message_id: int,
    recipients: list[int],
) -> None:
    sent = 0
    failed = 0

    for chat_id in recipients:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await bot.send_message(admin_chat_id, f"✅ Sent to {sent} users. Failed: {failed}")


# ================== START ==================
@router.message(Command("start"))
async def start(message: Message, state: FSMContext, bot: Bot, store: Store):
    await state.clear()
    user = message.from_user
    identifier = f"@{user.username}" if user.username else f"ID: {user.id}"

    _, date_str, _ = get_now_info()
    await store.set_first_seen(user.id, date_str)

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

    # Install the persistent dark keyboard beneath the message box.
    await message.answer(
        "the corridor opens beneath you.\nchoose a door — or simply speak. 🕯️",
        reply_markup=corridor_keyboard(),
    )


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
        "answer in one word.",
        reply_markup=cancel_keyboard(),
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
        f"I. {RITUAL_QUESTIONS[0]}",
        reply_markup=cancel_keyboard(),
    )


@router.message(RitualStates.q1)
async def ritual_q1(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q2)
    await message.answer(f"II. {RITUAL_QUESTIONS[1]}", reply_markup=cancel_keyboard())


@router.message(RitualStates.q2)
async def ritual_q2(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q3)
    await message.answer(f"III. {RITUAL_QUESTIONS[2]}", reply_markup=cancel_keyboard())


@router.message(RitualStates.q3)
async def ritual_q3(message: Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get("answers", [])
    answers.append(message.text or "[no answer]")
    await state.update_data(answers=answers)
    await state.set_state(RitualStates.q4)
    await message.answer(f"IV. {RITUAL_QUESTIONS[3]}", reply_markup=cancel_keyboard())


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

    await store.incr_user_rituals(user_id)

    try:
        await bot.send_message(ADMIN_ID, ritual_record)
    except Exception:
        pass

    await message.answer(
        "🕯️ the ritual is complete.\n\n"
        "what you gave has been received and kept.\n"
        "the corridor holds it in the dark —\n"
        "a secret that has never wept."
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
        "when you're done — just send. ✒️",
        reply_markup=cancel_keyboard(),
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

    await store.incr_user_letters(user_id)

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
    today = jalali_str(tehran_now())
    await message.answer(
        "⏳\n\n"
        "name a moment you are counting toward.\n\n"
        "give the date in the Persian calendar — however you like:\n"
        "  • ۱۴۰۵/۱۰/۱۱\n"
        "  • 1405-10-11\n"
        "  • 11 دی 1405\n\n"
        "then, if you wish, name it after the date or a “|”.\n\n"
        "for example:\n"
        "1405/10/11 زمان مرگم سال\n\n"
        f"(today is {today})",
        reply_markup=cancel_keyboard(),
    )


@router.message(CountdownState.waiting)
async def countdown_receive(message: Message, state: FSMContext, store: Store):
    await state.clear()

    if not message.text:
        await message.answer(
            "❌ the moment was lost in the dark.\n\n"
            "name a Persian-calendar date, like:\n"
            "1405/10/11 زمان مرگم سال"
        )
        return

    try:
        target, label = parse_persian_countdown(message.text)
    except ValueError:
        await message.answer(
            "❌ the date couldn't be read.\n\n"
            "write a Persian-calendar date — year, month, day — like:\n"
            "۱۴۰۵/۱۰/۱۱  ·  1405-10-11  ·  11 دی 1405"
        )
        return

    now = datetime.now(timezone.utc)
    target_jalali = jalali_str(target)

    if target < now:
        await message.answer(
            f"⏳ __{label}__\n"
            f"🗓️ {target_jalali}\n\n"
            f"that moment has already passed.\n"
            f"it lives behind you now —\n"
            f"in the part of the corridor you can no longer see."
        )
        return

    delta = target - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60

    # Persist it so the dark can return on the day itself — the cron sweeps
    # every stored countdown and delivers one reminder once its date arrives.
    cid = await store.next_countdown_id()
    await store.save_countdown(
        message.from_user.id,
        cid,
        {
            "label": label,
            "target": target.timestamp(),
            "target_jalali": target_jalali,
            "created_at": now.isoformat(),
            "notified": False,
        },
    )

    await message.answer(
        f"⏳ __{label}__\n"
        f"🗓️ {target_jalali}\n\n"
        f"{days} days, {hours} hours, and {minutes} minutes\n"
        f"stand between you and that moment.\n\n"
        f"the dark is already counting —\n"
        f"and will return to you when the day arrives."
    )


# ================== VOW ==================
@router.message(Command("vow"))
async def vow_start(message: Message, state: FSMContext, store: Store):
    existing = await store.get_vow(message.from_user.id)
    if existing:
        days = vow_days_left(existing)
        await message.answer(
            "🕯️ a vow already burns in the dark:\n\n"
            f"_{existing['text']}_\n\n"
            f"⏳ {days} days remain before the dark returns for it.\n\n"
            "swear anew, or let it stand?",
            reply_markup=vow_replace_keyboard(),
        )
        return

    await state.set_state(VowState.writing)
    await message.answer(VOW_WRITE_TEXT, reply_markup=cancel_keyboard())


@router.callback_query(F.data == "vow_keep")
async def cb_vow_keep(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(VOW_KEPT_TEXT)


@router.callback_query(F.data == "vow_replace")
async def cb_vow_replace(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await state.set_state(VowState.writing)
    await callback.message.answer(VOW_WRITE_TEXT, reply_markup=cancel_keyboard())


@router.message(VowState.writing)
async def vow_write(message: Message, state: FSMContext):
    text = get_text(message)
    await state.update_data(vow_text=text)
    await state.set_state(VowState.days)
    await message.answer(VOW_DAYS_TEXT, reply_markup=cancel_keyboard())


@router.message(VowState.days)
async def vow_days(message: Message, state: FSMContext, store: Store):
    raw = (message.text or "").strip()
    try:
        days = int(raw)
    except ValueError:
        await message.answer(VOW_DAYS_ERROR, reply_markup=cancel_keyboard())
        return

    if not 1 <= days <= 365:
        await message.answer(VOW_DAYS_ERROR, reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    await state.clear()

    now = datetime.now(timezone.utc)
    remind_at = now + timedelta(days=days)
    vow = {
        "text": data.get("vow_text", "[no vow]"),
        "created_at": now.isoformat(),
        "remind_at": remind_at.timestamp(),
        "reminded": False,
    }
    await store.set_vow(message.from_user.id, vow)
    await message.answer(VOW_SAVED_TEXT)


# ================== MY ARCHIVE ==================
@router.message(Command("myarchive"))
async def my_archive(message: Message, store: Store):
    user_id = message.from_user.id
    stats = await store.get_user_stats(user_id)
    alias = await store.get_alias(user_id)
    vow = await store.get_vow(user_id)

    alias_line = f"🪦 known as: {alias}" if alias else "🪦 known as: no one"
    first_seen = stats["first_seen"] or "lost to the dark"

    if vow:
        vow_line = (
            f"🩸 a vow burns:\n   _{vow['text']}_\n"
            f"   ⏳ {vow_days_left(vow)} days until the dark returns for it"
        )
    else:
        vow_line = "🩸 no vow burns in the dark"

    countdowns = await store.user_countdowns(user_id)
    if countdowns:
        now_ts = datetime.now(timezone.utc).timestamp()
        moments = []
        for _cid, c in countdowns:
            days = max(0, int((c.get("target", 0) - now_ts) // 86400))
            moments.append(
                f"   ⏳ _{c.get('label', 'the unnamed moment')}_ — "
                f"{c.get('target_jalali', '')} ({days} days)"
            )
        countdown_line = "🕰️ moments you count toward:\n" + "\n".join(moments)
    else:
        countdown_line = "🕰️ no moments counted toward"

    await message.answer(
        "📜 what the dark remembers of you:\n\n"
        f"{alias_line}\n"
        f"📩 words carried into the corridor: {stats['messages']}\n"
        f"🕯️ rituals completed: {stats['rituals']}\n"
        f"📜 letters left unsent: {stats['letters']}\n"
        f"{vow_line}\n"
        f"{countdown_line}\n"
        f"🚪 first crossed the threshold: {first_seen}\n\n"
        "— nothing here has a name.\n"
        "— only what you chose to leave behind."
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


# ================== BROADCAST ==================
@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(BroadcastState.waiting_for_content)
    await message.answer(
        "Send me the message you want to broadcast (text, photo, video, sticker — anything)."
    )


@router.message(BroadcastState.waiting_for_content, F.from_user.id == ADMIN_ID)
async def broadcast_content(message: Message, state: FSMContext, store: Store):
    recipients = await store.broadcast_chat_ids(exclude_chat_id=message.chat.id)
    await state.update_data(
        broadcast_from_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
        broadcast_recipients=recipients,
    )
    await state.set_state(BroadcastState.waiting_for_confirmation)
    await message.answer(f"Ready to send to {len(recipients)} users. Confirm? (yes/no)")


@router.message(BroadcastState.waiting_for_confirmation, F.from_user.id == ADMIN_ID)
async def broadcast_confirm(message: Message, state: FSMContext, bot: Bot):
    answer = (message.text or "").strip().lower()
    if answer not in {"yes", "no"}:
        await message.answer("Please reply yes or no.")
        return

    data = await state.get_data()
    await state.clear()

    if answer == "no":
        await message.answer("Broadcast cancelled.")
        return

    recipients = [int(chat_id) for chat_id in data.get("broadcast_recipients", [])]
    await message.answer("Broadcast started.")
    await run_broadcast(
        bot,
        admin_chat_id=message.chat.id,
        from_chat_id=int(data["broadcast_from_chat_id"]),
        message_id=int(data["broadcast_message_id"]),
        recipients=recipients,
    )


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


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("you don't belong here.", show_alert=True)
        return

    await callback.answer()
    await state.set_state(BroadcastState.waiting_for_content)
    await callback.message.answer(
        "Send me the message you want to broadcast (text, photo, video, sticker — anything)."
    )


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

    today = tehran_now().strftime("%Y-%m-%d")
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


# ================== CANCEL ANY FLOW ==================
@router.callback_query(F.data == "cancel_flow")
async def cb_cancel_flow(callback: CallbackQuery, state: FSMContext, store: Store):
    """Back out of any multi-step flow. Clears the FSM state (vow/countdown/
    ritual/letter/mirror) and drops any pending whisper, so nothing is kept or
    carried to the keeper. Safe to tap even when nothing is in progress."""
    await state.clear()
    await store.pop_pending(callback.from_user.id)
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(FLOW_CANCELLED_TEXT, reply_markup=corridor_keyboard())


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

    await deliver_to_keeper(
        bot,
        store,
        user_id=user_id,
        username=pending.get("username") or "no_username",
        chat_id=int(pending["chat_id"]),
        message_id=int(pending["message_id"]),
        text=pending.get("text") or "[MEDIA]",
        label=label,
        media=pending.get("media") or None,
    )


# ================== ADMIN REPLY ==================
@router.message(Command("reply"))
async def admin_reply(message: Message, bot: Bot, store: Store):
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
            KEEPER_REPLY_TEXT.format(reply=escape_md_v2(reply_text)),
            parse_mode="MarkdownV2"
        )
        await store.add_thread_message(user_id, {
            "dir": "in",
            "text": reply_text,
            "kind": "reply",
            "ts": datetime.now(timezone.utc).timestamp(),
        })
        await store.incr_unread(user_id)
        await message.answer("✔ delivered into the dark")
    except Exception as e:
        await message.answer(f"❌ error:\n{e}")


# ================== ADMIN REPLY (ANY CONTENT) ==================
@router.message(F.reply_to_message, F.from_user.id == ADMIN_ID)
async def admin_reply_any(message: Message, bot: Bot, store: Store):
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
            KEEPER_REPLY_INTRO,
            parse_mode="Markdown"
        )
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await bot.send_message(
            user_id,
            KEEPER_REPLY_OUTRO,
            parse_mode="MarkdownV2"
        )
        await store.add_thread_message(user_id, {
            "dir": "in",
            "text": message.text or message.caption or "",
            "kind": "reply",
            "media": media_kind(message),
            "ts": datetime.now(timezone.utc).timestamp(),
        })
        await store.incr_unread(user_id)
        await message.answer("✔ delivered into the dark")
    except Exception as e:
        await message.answer(f"❌ error:\n{e}")


# ================== REPLY KEYBOARD DISPATCH ==================
@router.message(F.text.in_(REPLY_LABELS))
async def reply_keyboard_dispatch(
    message: Message, state: FSMContext, bot: Bot, store: Store
):
    """A tap on the persistent keyboard arrives as the label's plain text. Route
    it to the same handler the matching command uses, so the keyboard and the
    slash commands behave identically.

    Sits before ``handle_all`` so these labels are never mistaken for an
    anonymous message. It does, however, respect an in-progress flow: if the
    user is mid-ritual/letter/vow/countdown, the text is their answer, so we
    fall through and let the FSM handler take it.
    """
    if await state.get_state() is not None:
        return await handle_all(message, state, bot, store)

    command = REPLY_LABELS[message.text]
    if command == "chat":
        return await chat(message)
    elif command == "dark":
        return await dark_quote(message)
    elif command == "fortune":
        return await fortune(message)
    elif command == "mood":
        return await mood(message)
    elif command == "mirror":
        return await mirror(message, state)
    elif command == "ritual":
        return await ritual_start(message, state)
    elif command == "letter":
        return await letter_start(message, state)
    elif command == "vow":
        return await vow_start(message, state, store)
    elif command == "countdown":
        return await countdown_start(message, state)
    elif command == "alias":
        return await set_alias(message, store)
    elif command == "myarchive":
        return await my_archive(message, store)
    elif command == "help":
        return await help_command(message)

    await message.answer("·", reply_markup=corridor_keyboard())


# ================== USER → ADMIN ==================
@router.message()
async def handle_all(message: Message, state: FSMContext, bot: Bot, store: Store):
    if message.text and message.text.startswith("/"):
        return

    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    if await store.is_blocked(user_id):
        return

    # A reply to one of the bot's own messages is a continuation of the
    # conversation — carry it straight through without asking what it is.
    replied = message.reply_to_message
    if replied and replied.from_user and replied.from_user.is_bot:
        await deliver_to_keeper(
            bot,
            store,
            user_id=user_id,
            username=message.from_user.username or "no_username",
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=get_text(message),
            label="↩️ REPLY",
            media=media_kind(message),
        )
        return

    await store.set_pending(user_id, {
        "chat_id": str(message.chat.id),
        "message_id": str(message.message_id),
        "text": get_text(message),
        "username": message.from_user.username or "no_username",
        "media": media_kind(message) or "",
    })
    await message.answer(
        "before it arrives —\nwhat does this carry? 🩸",
        reply_markup=message_type_keyboard(),
    )
