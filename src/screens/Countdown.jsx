import { useEffect, useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

export default function Countdown({ onBack }) {
  const d = DOOR.countdown
  const [today, setToday] = useState(null)
  const [date, setDate] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    call('countdown')
      .then((r) => setToday(r.today))
      .catch(() => {})
  }, [])

  async function reckon() {
    if (!date.trim() || loading) return
    setLoading(true)
    setError(false)
    try {
      const r = await call('countdown', { date: date.trim() })
      if (r.error) {
        setError(true)
        setResult(null)
      } else {
        setResult(r)
        track('reckoned a countdown')
        notify('success')
      }
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle="mark a moment in time" onBack={onBack}>
      <p className="prompt" style={{ fontSize: '1.05rem' }}>
        name a moment you are counting toward.
        <br />
        the dark will count the days — and return to you when it arrives.
      </p>

      <input
        className="field fa"
        dir="auto"
        value={date}
        maxLength={120}
        placeholder="1405/10/11 زمان مرگم سال"
        onChange={(e) => setDate(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && reckon()}
      />
      <p className="field-hint" style={{ marginBottom: 0 }}>
        <span className="muted">the date first — Persian calendar, as year / month / day.</span>
        <br />
        <span className="muted">then a name for the moment, if you wish.</span>
        <br />
        <br />
        accepts:&nbsp; ۱۴۰۵/۱۰/۱۱ · 1405-10-11 · ۱۱ دی ۱۴۰۵
        {today && (
          <>
            <br />
            <span className="muted">today is {today}</span>
          </>
        )}
      </p>

      <div className="actions">
        <Button onClick={reckon} loading={loading} disabled={!date.trim()}>
          begin the count
        </Button>
      </div>

      {error && (
        <p className="whisper center error" style={{ marginTop: '1.5rem' }}>
          the date couldn’t be read.
        </p>
      )}

      {result && result.passed && (
        <div className="count-result reveal">
          <p className="count-label fa" dir="auto">{result.label}</p>
          <p className="count-date">🗓️ {result.target_jalali}</p>
          <p className="prompt" style={{ marginTop: '1rem' }}>
            that moment has already passed.
            <br />
            it lives behind you now.
          </p>
        </div>
      )}

      {result && !result.passed && (
        <div className="count-result reveal">
          <p className="count-label fa" dir="auto">{result.label}</p>
          <p className="count-date">🗓️ {result.target_jalali}</p>
          <div className="count-grid">
            <Unit n={result.days} label="days" />
            <Unit n={result.hours} label="hours" />
            <Unit n={result.minutes} label="minutes" />
          </div>
          <p className="muted center">
            the dark is counting —
            <br />
            and will return to you on the day.
          </p>
        </div>
      )}
    </Screen>
  )
}

function Unit({ n, label }) {
  return (
    <div className="count-unit">
      <span className="count-num">{n}</span>
      <span className="count-unit-label">{label}</span>
    </div>
  )
}
