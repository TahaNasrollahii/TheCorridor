import { useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

export default function Fortune({ onBack }) {
  const d = DOOR.fortune
  const [fortune, setFortune] = useState(null)
  const [loading, setLoading] = useState(false)

  async function read() {
    setLoading(true)
    try {
      const r = await call('fortune')
      setFortune(r.fortune)
      notify('success')
    } catch {
      /* the dark would not read */
    } finally {
      setLoading(false)
    }
  }

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle={d.sub} onBack={onBack}>
      {fortune && (
        <>
          <p className="revelation-label">the dark has read you</p>
          <blockquote className="revelation reveal">{fortune}</blockquote>
        </>
      )}
      <div className="actions">
        <Button onClick={read} loading={loading}>
          {fortune ? 'read again' : 'read me'}
        </Button>
      </div>
    </Screen>
  )
}
