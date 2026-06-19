import { useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { haptic, notify } from '../lib/telegram.js'

const TYPES = [
  { key: 'confession', glyph: '🩸', label: 'confession' },
  { key: 'question', glyph: '🕯️', label: 'question' },
  { key: 'just_words', glyph: '🌑', label: 'just words' },
]

export default function Speak({ onBack }) {
  const d = DOOR.speak
  const [text, setText] = useState('')
  const [type, setType] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [loading, setLoading] = useState(false)

  async function send() {
    if (!text.trim() || !type || loading) return
    setLoading(true)
    try {
      const r = await call('send', { text: text.trim(), type })
      setConfirm(r.confirm)
      setText('')
      setType(null)
      notify('success')
    } catch {
      /* ignore — keep their words so they can retry */
    } finally {
      setLoading(false)
    }
  }

  if (confirm) {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <blockquote className="revelation reveal">{confirm}</blockquote>
        <div className="actions">
          <Button variant="ghost" onClick={() => setConfirm(null)}>
            speak again
          </Button>
        </div>
      </Screen>
    )
  }

  return (
    <Screen
      glyph={d.glyph}
      title={d.title}
      subtitle="no name. no face. no trace."
      onBack={onBack}
    >
      <textarea
        className="field area"
        value={text}
        maxLength={4000}
        rows={5}
        placeholder="let it out…"
        onChange={(e) => setText(e.target.value)}
      />

      <p className="field-hint">before it arrives — what does this carry?</p>
      <div className="chips chips-3">
        {TYPES.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`chip${type === t.key ? ' active' : ''}`}
            onClick={() => {
              haptic('light')
              setType(t.key)
            }}
          >
            <span className="chip-glyph">{t.glyph}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <div className="actions">
        <Button onClick={send} loading={loading} disabled={!text.trim() || !type}>
          send into the dark
        </Button>
      </div>
    </Screen>
  )
}
