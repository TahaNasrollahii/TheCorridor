import { useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

const CONFIRM =
  'the letter has been folded and kept.\n\nit will never reach them.\nbut it exists now — and that is something.'

export default function Letter({ onBack }) {
  const d = DOOR.letter
  const [text, setText] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function send() {
    if (!text.trim() || loading) return
    setLoading(true)
    try {
      await call('letter', { text: text.trim() })
      setSent(true)
      notify('success')
    } catch {
      /* keep their words */
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <blockquote className="revelation reveal">{CONFIRM}</blockquote>
      </Screen>
    )
  }

  return (
    <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
      <p className="prompt">
        write a letter to someone
        <br />
        you will never send it to.
      </p>
      <textarea
        className="field area tall"
        value={text}
        maxLength={4000}
        rows={8}
        placeholder="take your time…"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="actions">
        <Button onClick={send} loading={loading} disabled={!text.trim()}>
          fold it away
        </Button>
      </div>
    </Screen>
  )
}
