import { useState } from 'react'

import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { haptic, notify } from '../lib/telegram.js'

const MOODS = [
  { key: 'broken', glyph: '🥀', label: 'broken' },
  { key: 'numb', glyph: '🌫️', label: 'numb' },
  { key: 'burning', glyph: '🔥', label: 'burning' },
  { key: 'restless', glyph: '🕷️', label: 'restless' },
]

export default function Mood({ onBack }) {
  const d = DOOR.mood
  const [active, setActive] = useState(null)
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)

  async function pick(mood) {
    if (loading) return
    setActive(mood.key)
    setLoading(true)
    haptic('light')
    try {
      const r = await call('mood', { mood: mood.key })
      setResponse(r.response)
      notify('success')
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle="how does the dark find you?" onBack={onBack}>
      <div className="chips">
        {MOODS.map((m) => (
          <button
            key={m.key}
            type="button"
            className={`chip${active === m.key ? ' active' : ''}`}
            onClick={() => pick(m)}
          >
            <span className="chip-glyph">{m.glyph}</span>
            <span>{m.label}</span>
          </button>
        ))}
      </div>

      {response && <blockquote className="revelation reveal" key={active}>{response}</blockquote>}
    </Screen>
  )
}
