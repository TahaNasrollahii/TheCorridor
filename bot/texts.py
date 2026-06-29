"""All the static copy, quote pools and lookup tables for the corridor."""

import re

# ================== CONSTANTS ==================
DARK_REACTIONS = ["🕯️", "🌑", "🪦", "✒️", "🕸️", "🩸", "🌒", "💀", "⛓️"]
NIGHT_HOURS = range(0, 4)

CONFIRM_MESSAGES = [
    "it has been received — nameless, weightless, and true.\nif an answer stirs in the dark, it will find its way to you. 👁️",
    "the corridor has swallowed your words whole.\nthey are safe here, in the cold. 🕯️",
    "something in the dark leaned closer to read.\nyour message arrived. 🌑",
    "it reached the other side of silence.\nwhatever comes next — you will know. 🪦",
    "the walls here remember everything.\nyours has been added to the dark archive. ✒️",
    "received. the hollow holds it now.\nno name attached. no trace. no sound. 🕸️",
    "your words found their way through the black.\nthey rest here now, among the others. 🌒",
    "the messenger carried it without looking.\nit arrived. that is enough. ⛓️",
    "something that was inside you is now outside.\nthe dark has accepted it. 💀",
    "not lost. not forgotten. just held\nin a place where light doesn't reach. 🩸",
]

NIGHT_CONFIRM_MESSAGES = [
    "even at this hour, the dark was already awake.\nyour words arrived where they belong. 🌑",
    "the ones who write past midnight know something others don't.\nit was received. 🕯️",
    "this hour belongs to the broken and the restless.\nyou are not alone in the corridor. 🪦",
    "the night swallowed your message whole.\ngently. without judgment. ✒️",
]

DARK_QUOTES = [
    "even the sun is just a fire that hasn't gone out yet.",
    "the ones who smile in daylight are the ones who've learned to hide.",
    "grief is just love with nowhere left to go.",
    "some doors were never meant to be opened — and yet, here you are.",
    "the dead don't haunt places. they haunt people.",
    "silence is the loudest thing a person can say.",
    "every scar is a map of somewhere you survived.",
    "the dark doesn't come for you. you come for it.",
    "even candles burn down to nothing. that's not failure. that's purpose.",
    "you can't outrun what lives inside your own chest.",
    "the night doesn't ask permission. neither should you.",
    "some things break so quietly no one even hears it happen.",
    "the moon has no light of its own. it just refuses to disappear.",
    "what you bury doesn't die. it learns to breathe underground.",
    "the most honest conversations happen in the dark.",
]

FORTUNES = [
    "something you lost is still looking for you.",
    "the door you keep avoiding — it's already open.",
    "you will be understood. not yet. but eventually.",
    "the thing that follows you is not a threat. it is yours.",
    "a version of you survived something you never talk about. remember that.",
    "what feels like an ending is just a corridor between two darks.",
    "someone, somewhere, is writing your name without knowing why.",
    "the silence you carry will one day become music.",
    "you are further from the beginning than you think.",
    "grief is visiting you again. let it sit. it won't stay forever.",
    "the answer you're waiting for already lives inside the question.",
    "not all that is broken is meant to be fixed.",
    "you were never meant to be easy to understand.",
    "something is ending so something older can return.",
    "the wound is not who you are. but it knows you well.",
]

MOOD_RESPONSES = {
    "broken": (
        "🥀 broken.\n\n"
        "the ones who break are the ones who felt something real.\n"
        "stay inside it. don't rush the mending.\n"
        "even ruins have a kind of beauty the whole never had."
    ),
    "numb": (
        "🌫️ numb.\n\n"
        "numbness is not emptiness — it is armor.\n"
        "your body is protecting you from something it hasn't named yet.\n"
        "you don't have to feel everything at once."
    ),
    "burning": (
        "🔥 burning.\n\n"
        "good. fire means something is still alive in there.\n"
        "let it consume what no longer belongs to you.\n"
        "what survives the burning — that's what you're made of."
    ),
    "restless": (
        "🕷️ restless.\n\n"
        "the restless ones are the ones who know something is wrong\n"
        "before the world admits it.\n"
        "your unease is not a flaw. it is a compass."
    ),
}

MIRROR_RESPONSES = {
    "shadow": "a shadow that learned to walk without you. it goes where you won't.",
    "smoke": "smoke from a fire no one remembers starting. still rising. still warm.",
    "water": "still water at the bottom of something very deep. patient. cold. waiting.",
    "thorn": "a single thorn on a stem with no flower. purposeful. quiet. sharp.",
    "fog": "fog that rolls in from somewhere unnamed. familiar to everyone. belonging to no one.",
    "moth": "a moth that forgot what it was looking for — but kept flying toward it anyway.",
    "mirror": "a mirror facing another mirror. infinite. hollow. neither one showing anything real.",
    "crow": "a crow that arrived before the news. it always does.",
    "candle": "a candle that burns at both ends and calls it living.",
    "root": "a root that grew through stone. slow. certain. unseen.",
}

VOW_WRITE_TEXT = (
    "🩸\n\n"
    "make a vow to yourself —\n"
    "something you swear to do, or to become.\n\n"
    "write it now. the dark will hold you to it. ✒️"
)

VOW_DAYS_TEXT = (
    "⏳\n\n"
    "how many days until the dark reminds you?\n\n"
    "send a number between 1 and 365."
)

VOW_DAYS_ERROR = (
    "❌ the dark counts only in whole days —\n"
    "a single number, from 1 to 365.\n\n"
    "try again."
)

VOW_SAVED_TEXT = (
    "🕯️ the vow is sealed.\n\n"
    "it sleeps in the dark, cold and deep.\n"
    "when the days run out, the corridor returns —\n"
    "to wake the promise you were meant to keep."
)

VOW_KEPT_TEXT = (
    "the old vow stands, untouched.\n"
    "the dark is still counting. ✒️"
)

# The reminder the cron endpoint carries back to the soul.
VOW_REMINDER_TEXT = (
    "🕯️ the dark returns, as promised.\n\n"
    "once, in the corridor, you swore this:\n\n"
    "_{text}_\n\n"
    "the days have run their course.\n"
    "the dark remembered. do you?"
)

COUNTDOWN_REMINDER_TEXT = (
    "⏳ the moment has come.\n\n"
    "you once set the dark to count toward this:\n\n"
    "_{label}_\n"
    "🗓️ {date}\n\n"
    "the waiting is over.\n"
    "it is here now — whatever it means to you."
)

# Shown when a soul backs out of a multi-step flow (vow, countdown, ritual,
# letter, mirror, or an unsent whisper) via the inline "never mind" button.
FLOW_CANCELLED_TEXT = (
    "🌫️ nothing was kept, nothing was sent.\n"
    "the corridor waits — patient, and silent."
)

RITUAL_QUESTIONS = [
    "what is the last thing you thought about before you came here?",
    "name something you've never said out loud.",
    "what do you carry that no one knows about?",
    "if the dark could speak to you — what would it already know?",
]

MESSAGE_TYPES = {
    "confession": "🩸 CONFESSION",
    "question": "🕯️ QUESTION",
    "just_words": "🌑 JUST WORDS",
}

# Human-readable descriptions for the activity tracker.
# Each command the keeper should be notified about, and what it means.
COMMAND_ACTIVITY = {
    "start": "🚪 entered the dark",
    "help": "📖 opened the guide",
    "whisper": "✒️ opened the corridor",
    "confess": "🩸 opened confession",
    "dark": "🌑 asked for a dark quote",
    "fortune": "🔮 asked for a fortune",
    "mood": "🌫️ opened mood",
    "mirror": "🪞 looked into the mirror",
    "ritual": "🕯️ began the ritual",
    "letter": "📜 began a letter",
    "countdown": "⏳ started a countdown",
    "alias": "🪦 set an alias",
    "vow": "🩸 began a vow",
    "myarchive": "📜 opened their archive",
    "raven": "🐦‍⬛ stepped into the library",
}

# Each reply-keyboard label and what tapping it means.
REPLY_ACTIVITY = {
    "✒️ whisper to Taha": '✒️ tapped "whisper to Taha"',
    "🐦‍⬛ Raven AI": '🐦‍⬛ tapped "Raven AI"',
    "🚪 Leave Raven": '🚪 tapped "Leave Raven"',
    "🌑 a dark quote": '🌑 tapped "a dark quote"',
    "🔮 a fortune": '🔮 tapped "a fortune"',
    "🌫️ the mood": '🌫️ tapped "the mood"',
    "🪞 the mirror": '🪞 tapped "the mirror"',
    "🕯️ the ritual": '🕯️ tapped "the ritual"',
    "📜 a letter": '📜 tapped "a letter"',
    "🩸 a vow": '🩸 tapped "a vow"',
    "⏳ a countdown": '⏳ tapped "a countdown"',
    "🪦 your alias": '🪦 tapped "your alias"',
    "📖 your archive": '📖 tapped "your archive"',
    "👁️ the guide": '👁️ tapped "the guide"',
    "🚪 Enter the Corridor": '🚪 tapped "Enter the Corridor"',
}

# Each button (callback_data) and what tapping it means.
CALLBACK_ACTIVITY = {
    "cmd_start": "🚪 tapped “enter the dark”",
    "cmd_chat": "✒️ tapped “whisper”",
    "cmd_help": "📖 tapped “the guide”",
    "type_confession": "🩸 marked a message as a confession",
    "type_question": "🕯️ marked a message as a question",
    "type_just_words": "🌑 marked a message as just words",
    "mood_broken": "🥀 chose the mood “broken”",
    "mood_numb": "🌫️ chose the mood “numb”",
    "mood_burning": "🔥 chose the mood “burning”",
    "mood_restless": "🕷️ chose the mood “restless”",
    "vow_replace": "🩸 chose to replace their vow",
    "vow_keep": "✒️ chose to keep their vow",
}

SEASONS = {
    (12, 1, 2): "in the dead of winter",
    (3, 4, 5): "in the hollow of spring",
    (6, 7, 8): "in the heat of a dying summer",
    (9, 10, 11): "in the fading breath of autumn",
}

RETURNING_TEXT = (
    "you've been here before.\n"
    "the corridor remembers your footsteps —\n"
    "even if it never learned your name.\n\n"
    "write. ✒️"
)

HELP_TEXT = (
    "📖 the guide to the corridor:\n\n"
    "✒️ /start — enter the dark\n\n"
    "💬 /whisper — open the corridor and write\n\n"
    "🐦‍⬛ /raven — speak to a solitary consciousness\n\n"
    "🚪 Enter the Corridor — open the visual corridor\n\n"
    "🩸 /confess — send a confession\n"
    "    marked differently. heavier.\n\n"
    "🌑 /dark — receive a dark quote\n\n"
    "🔮 /fortune — receive your dark fortune\n\n"
    "🌫️ /mood — tell the dark how you feel\n\n"
    "🪞 /mirror — discover the shape of your inner dark\n\n"
    "🕯️ /ritual — a four-question initiation\n\n"
    "📜 /letter — write a letter you'll never send\n\n"
    "⏳ /countdown — mark a moment in time\n\n"
    "🩸 /vow — swear a vow the dark will remind you of\n\n"
    "🪦 /alias — choose a name for yourself\n\n"
    "📜 /myarchive — what the dark remembers of you\n\n"
    "📖 /help — you are here.\n\n"
    "— no names leave this place.\n"
    "— no faces are kept.\n"
    "— only the words you whispered and wept."
)

START_TEXT = (
    "you've crossed into the dark —\n"
    "no lantern, no name, no mark.\n\n"
    "leave what you carry at the door.\n"
    "the void has room for one thing more.\n\n"
    "the living keep their secrets well —\n"
    "but here, you have no face to sell.\n\n"
    "no name is asked, no light is given.\n"
    "just words — raw, cold, and forgiven.\n\n"
    "this place was built for what you hide —\n"
    "for what has nowhere left to reside.\n\n"
    "speak without a name, without a trace.\n"
    "even darkness needs a resting place. 🗝️"
)

CHAT_TEXT = (
    "the door behind you has no lock —\n"
    "no hour here, no ticking clock.\n\n"
    "what you carry has no weight,\n"
    "no witness waits, no one is late.\n\n"
    "just the hollow, soft as night —\n"
    "let it out. it's yours. write. ✒️"
)

# ---- the keeper's reply, wrapped in the dark framing ----
# Shared by the bot's /reply command, its native-reply handler, and the Mini App
# admin console so every answer reaches the soul looking identical.

# Single-message form (text-only reply). `{reply}` is the keeper's words.
# Sent with parse_mode="Markdown".
# Sent with parse_mode="MarkdownV2" so "reply" can be both bold *and* italic
# (legacy Markdown can't nest). `{reply}` must be MarkdownV2-escaped first —
# use escape_md_v2() at the call site.
KEEPER_REPLY_TEXT = (
    "_a voice returns from the other side of darkness:_\n"
    "─────────────────\n\n"
    "{reply}\n\n"
    "─────────────────\n"
    "_the dark spoke\\. now you may —_\n"
    "_*reply*, if you have something to say\\._"
)


_MD_V2_ESCAPE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_md_v2(text: str) -> str:
    """Escape text for Telegram MarkdownV2 so keeper/user content can't break the
    surrounding bold/italic formatting."""
    return _MD_V2_ESCAPE.sub(r"\\\1", text or "")

# Three-part form, used when the answer carries media: an intro line, then the
# attachment itself, then an outro line.
KEEPER_REPLY_INTRO = "_a voice returns from the other side of darkness:_"  # Markdown
KEEPER_REPLY_OUTRO = (  # MarkdownV2
    "_the dark spoke\\. now you may —\n*reply*, if you have something to say\\._"
)
