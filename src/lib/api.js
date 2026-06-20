// Single entry point to the backend. Every call goes to /api/app with the
// action name; the verified Telegram identity travels in the init-data header.
//
// In dev (outside Telegram) we can't reach the Python function or sign a
// request, so calls resolve from `devMock` instead — enough to build the UI.

import { getInitData, isDev } from './telegram.js'

// Fire-and-forget activity ping to the keeper. Never blocks the UI or surfaces
// errors — if it fails, the action the user took still happened.
export function track(label) {
  call('activity', { label }).catch(() => {})
}

export async function call(action, payload = {}) {
  if (isDev) {
    await new Promise((r) => setTimeout(r, 250)) // fake a little latency
    return devMock(action, payload)
  }

  const res = await fetch('/api/app', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': getInitData(),
    },
    body: JSON.stringify({ action, ...payload }),
  })

  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `${action} failed (${res.status})`)
  }
  return data
}

// ---- dev fixtures -------------------------------------------------------
const MOCK_MOODS = {
  broken: '🥀 broken.\n\nthe ones who break are the ones who felt something real.\nstay inside it. don’t rush the mending.',
  numb: '🌫️ numb.\n\nnumbness is not emptiness — it is armor.\nyou don’t have to feel everything at once.',
  burning: '🔥 burning.\n\ngood. fire means something is still alive in there.',
  restless: '🕷️ restless.\n\nyour unease is not a flaw. it is a compass.',
}

function devMock(action, payload = {}) {
  switch (action) {
    case 'me':
      return {
        ok: true,
        user: { id: 1, username: 'wanderer', first_name: 'Wanderer' },
        is_admin: true,
      }
    case 'dark':
      return { ok: true, quote: 'the most honest conversations happen in the dark.' }
    case 'fortune':
      return { ok: true, fortune: 'something you lost is still looking for you.' }
    case 'mood':
      return { ok: true, response: MOCK_MOODS[payload.mood] || MOCK_MOODS.numb }
    case 'mirror':
      return {
        ok: true,
        response: 'smoke from a fire no one remembers starting. still rising. still warm.',
      }
    case 'send':
      return { ok: true, confirm: 'the corridor has swallowed your words whole.\nthey are safe here, in the cold. 🕯️' }
    case 'inbox':
      return {
        ok: true,
        messages: [
          { dir: 'out', text: 'i don’t know why i came here.', kind: '🌑 JUST WORDS', ts: 1718700000 },
          { dir: 'out', text: '', media: 'voice', kind: '🩸 CONFESSION', ts: 1718700300 },
          { dir: 'in', text: 'no one ever does. that’s how they find it.', kind: 'reply', ts: 1718703600 },
          { dir: 'in', text: '', media: 'photo', kind: 'reply', ts: 1718703900 },
        ],
      }
    case 'ritual_questions':
      return {
        ok: true,
        questions: [
          'what is the last thing you thought about before you came here?',
          'name something you’ve never said out loud.',
          'what do you carry that no one knows about?',
          'if the dark could speak to you — what would it already know?',
        ],
      }
    case 'ritual':
    case 'letter':
      return { ok: true }
    case 'vow_get':
      return { ok: true, vow: null }
    case 'vow_set':
      return { ok: true, vow: { text: payload.text, days_left: payload.days } }
    case 'countdown':
      if (!payload.date) return { ok: true, today: '1405/03/29' }
      return {
        ok: true,
        label: 'the end of the year',
        target_jalali: '1405/10/11',
        passed: false,
        days: 196,
        hours: 7,
        minutes: 42,
      }
    case 'alias_get':
      return { ok: true, alias: '' }
    case 'alias_set':
      return { ok: true, alias: payload.alias }
    case 'archive':
      return {
        ok: true,
        alias: 'the hollow one',
        stats: { messages: 7, rituals: 1, letters: 2, first_seen: '2026-02-14' },
        vow: { text: 'i will stop waiting for permission to begin.', days_left: 23 },
      }
    case 'unread':
      return { ok: true, unread: 0 }
    case 'activity':
      return { ok: true }
    case 'admin_threads':
      return {
        ok: true,
        threads: [
          { uid: 42, name: 'Mara', username: 'mara_void', alias: 'the hollow one', last_text: 'are you still there?', last_kind: '🌑 JUST WORDS', last_media: null, last_dir: 'out', ts: 1718703900, new: true },
          { uid: 7, name: 'Ash', username: null, alias: '', last_text: '', last_kind: '🩸 CONFESSION', last_media: 'voice', last_dir: 'out', ts: 1718700300, new: true },
          { uid: 13, name: null, username: 'echo', alias: '', last_text: 'no one ever does. that’s how they find it.', last_kind: 'reply', last_media: null, last_dir: 'in', ts: 1718600000, new: false },
          { uid: 99, name: null, username: null, alias: '', last_text: 'i left something here.', last_kind: '🌑 JUST WORDS', last_media: null, last_dir: 'out', ts: 1718500000, new: true },
        ],
      }
    case 'admin_thread':
      return {
        ok: true,
        uid: payload.uid,
        messages: [
          { dir: 'out', text: 'i don’t know why i came here.', kind: '🌑 JUST WORDS', ts: 1718700000 },
          { dir: 'in', text: 'no one ever does. that’s how they find it.', kind: 'reply', ts: 1718703600 },
          { dir: 'out', text: 'are you still there?', kind: '🌑 JUST WORDS', ts: 1718703900 },
        ],
      }
    case 'admin_reply':
      return { ok: true }
    default:
      throw new Error(`no dev mock for "${action}"`)
  }
}
