import { useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

export default function Mirror({ onBack }) {
  const d = DOOR.mirror
  const [word, setWord] = useState('')
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)

  async function gaze() {
    const w = word.trim()
    if (!w || loading) return
    setLoading(true)
    try {
      const r = await call('mirror', { word: w })
      setResponse(r.response)
      track('looked into the mirror')
      notify('success')
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
      <p className="prompt">
        if the darkness inside you had a shape —
        <br />
        what would it be? answer in one word.
      </p>

      <input
        className="field"
        value={word}
        maxLength={32}
        placeholder="one word…"
        onChange={(e) => setWord(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && gaze()}
      />

      <div className="actions">
        <Button onClick={gaze} loading={loading} disabled={!word.trim()}>
          look into the mirror
        </Button>
      </div>

      {response && (
        <>
          <p className="revelation-label">the mirror speaks</p>
          <blockquote className="revelation reveal" key={response}>
            {response}
          </blockquote>
        </>
      )}
    </Screen>
  )
}
