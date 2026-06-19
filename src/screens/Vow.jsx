import { useEffect, useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

const SAVED =
  'the vow is sealed.\n\nit sleeps in the dark, cold and deep.\nwhen the days run out, the corridor returns —\nto wake the promise you were meant to keep.'

export default function Vow({ onBack }) {
  const d = DOOR.vow
  const [state, setState] = useState('loading') // loading | view | form | saved
  const [vow, setVow] = useState(null)
  const [text, setText] = useState('')
  const [days, setDays] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    call('vow_get')
      .then((r) => {
        if (r.vow) {
          setVow(r.vow)
          setState('view')
        } else {
          setState('form')
        }
      })
      .catch(() => setState('form'))
  }, [])

  const daysNum = parseInt(days, 10)
  const validDays = daysNum >= 1 && daysNum <= 365

  async function save() {
    if (!text.trim() || !validDays || loading) return
    setLoading(true)
    try {
      await call('vow_set', { text: text.trim(), days: daysNum })
      track('sealed a vow')
      setState('saved')
      notify('success')
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  if (state === 'loading') {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="whisper center">the dark recalls…</p>
      </Screen>
    )
  }

  if (state === 'saved') {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <blockquote className="revelation reveal">{SAVED}</blockquote>
      </Screen>
    )
  }

  if (state === 'view') {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="revelation-label">a vow already burns</p>
        <blockquote className="revelation reveal">{vow.text}</blockquote>
        <p className="prompt" style={{ marginTop: '1.25rem', fontSize: '1rem' }}>
          ⏳ {vow.days_left} {vow.days_left === 1 ? 'day' : 'days'} remain before the dark returns for it.
        </p>
        <div className="actions">
          <Button variant="ghost" onClick={() => setState('form')}>
            swear anew
          </Button>
        </div>
      </Screen>
    )
  }

  // form
  return (
    <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
      <p className="prompt">
        make a vow to yourself —
        <br />
        something you swear to do, or to become.
      </p>
      <textarea
        className="field area"
        value={text}
        maxLength={2000}
        rows={4}
        placeholder="i swear that…"
        onChange={(e) => setText(e.target.value)}
      />
      <label className="field-hint" htmlFor="vow-days">
        how many days until the dark reminds you? (1–365)
      </label>
      <input
        id="vow-days"
        className="field"
        type="number"
        inputMode="numeric"
        min={1}
        max={365}
        value={days}
        placeholder="e.g. 30"
        onChange={(e) => setDays(e.target.value)}
      />
      <div className="actions">
        <Button onClick={save} loading={loading} disabled={!text.trim() || !validDays}>
          seal the vow
        </Button>
      </div>
    </Screen>
  )
}
