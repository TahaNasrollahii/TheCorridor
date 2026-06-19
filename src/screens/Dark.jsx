import { useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

export default function Dark({ onBack }) {
  const d = DOOR.dark
  const [quote, setQuote] = useState(null)
  const [loading, setLoading] = useState(false)

  async function draw() {
    setLoading(true)
    try {
      const r = await call('dark')
      setQuote(r.quote)
      track('drew a dark quote')
      notify('success')
    } catch {
      /* the void stayed silent */
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle={d.sub} onBack={onBack}>
      {quote && <blockquote className="revelation reveal">{quote}</blockquote>}
      <div className="actions">
        <Button onClick={draw} loading={loading}>
          {quote ? 'draw again' : 'draw from the void'}
        </Button>
      </div>
    </Screen>
  )
}
