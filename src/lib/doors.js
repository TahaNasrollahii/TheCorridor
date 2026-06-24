// The corridor's doors — every feature of the bot, as a place you can enter.
// Grouped into sections that read like a descent: speak first, then reflect,
// then the rites, then what remains of you. Screen components are wired to
// these keys in screens.jsx.

export const SECTIONS = [
  {
    label: 'the keeper',
    doors: [
      { key: 'speak', glyph: '✒️', title: 'whisper', sub: 'send words into the dark' },
      { key: 'inbox', glyph: '👁️', title: 'what returned', sub: 'answers from the other side' },
    ],
  },
  {
    label: 'reflection',
    doors: [
      { key: 'mood', glyph: '🌫️', title: 'mood', sub: 'tell the dark how you feel' },
      { key: 'mirror', glyph: '🪞', title: 'the mirror', sub: 'the shape of your inner dark' },
      { key: 'dark', glyph: '🌑', title: 'a dark quote', sub: 'a whisper from the void' },
      { key: 'fortune', glyph: '🔮', title: 'fortune', sub: 'the dark has read you' },
    ],
  },
  {
    label: 'the rites',
    doors: [
      { key: 'ritual', glyph: '🕯️', title: 'the ritual', sub: 'a four-question initiation' },
      { key: 'letter', glyph: '📜', title: 'unsent letter', sub: "a letter you'll never send" },
      { key: 'vow', glyph: '🩸', title: 'a vow', sub: 'swear what the dark will keep' },
      { key: 'countdown', glyph: '⏳', title: 'countdown', sub: 'mark a moment in time' },
    ],
  },
  {
    label: 'what remains',
    doors: [
      { key: 'alias', glyph: '🪦', title: 'your alias', sub: 'choose a name for yourself' },
      { key: 'archive', glyph: '📖', title: 'your archive', sub: 'what the dark remembers of you' },
    ],
  },
  {
    // Only the keeper sees this section (Home filters on `me.is_admin`).
    label: "the keeper's sight",
    admin: true,
    doors: [
      { key: 'keeper', glyph: '👁️‍🗨️', title: 'all chats', sub: 'every voice, and what you answered' },
    ],
  },
]

// Flat lookup: key -> door metadata (glyph/title/sub), for screen headers.
export const DOOR = Object.fromEntries(
  SECTIONS.flatMap((s) => s.doors).map((d) => [d.key, d]),
)
