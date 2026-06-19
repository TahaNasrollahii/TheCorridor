import { useEffect, useState } from 'react'

import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'

export default function Archive({ onBack }) {
  const d = DOOR.archive
  const [state, setState] = useState('loading')
  const [data, setData] = useState(null)

  useEffect(() => {
    call('archive')
      .then((r) => {
        setData(r)
        setState('ready')
      })
      .catch(() => setState('error'))
  }, [])

  if (state === 'loading') {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="whisper center">the dark remembers…</p>
      </Screen>
    )
  }

  if (state === 'error') {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="whisper center error">the archive would not open.</p>
      </Screen>
    )
  }

  const { alias, stats, vow } = data

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle="what the dark remembers of you" onBack={onBack}>
      <div className="stat-list">
        <Stat glyph="🪦" label="known as" value={alias || 'no one'} fa={!!alias} />
        <Stat glyph="📩" label="words carried" value={stats.messages} />
        <Stat glyph="🕯️" label="rituals completed" value={stats.rituals} />
        <Stat glyph="📜" label="letters left unsent" value={stats.letters} />
        <Stat
          glyph="🚪"
          label="first crossed the threshold"
          value={stats.first_seen || 'lost to the dark'}
        />
      </div>

      <div className="vow-card">
        {vow ? (
          <>
            <p className="revelation-label" style={{ margin: '0 0 0.75rem' }}>
              🩸 a vow burns
            </p>
            <blockquote className="revelation" style={{ margin: 0, fontSize: '1.25rem' }}>
              {vow.text}
            </blockquote>
            <p className="muted center" style={{ marginTop: '0.75rem' }}>
              ⏳ {vow.days_left} {vow.days_left === 1 ? 'day' : 'days'} until the dark returns for it
            </p>
          </>
        ) : (
          <p className="muted center" style={{ margin: 0 }}>
            🩸 no vow burns in the dark
          </p>
        )}
      </div>

      <p className="archive-foot">
        nothing here has a name.
        <br />
        only what you chose to leave behind.
      </p>
    </Screen>
  )
}

function Stat({ glyph, label, value, fa }) {
  return (
    <div className="stat">
      <span className="stat-glyph">{glyph}</span>
      <span className="stat-label">{label}</span>
      <span className={`stat-value${fa ? ' fa' : ''}`} dir="auto">
        {value}
      </span>
    </div>
  )
}
