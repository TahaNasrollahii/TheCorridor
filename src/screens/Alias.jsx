import { useEffect, useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

export default function Alias({ onBack }) {
  const d = DOOR.alias
  const [alias, setAlias] = useState('')
  const [saved, setSaved] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    call('alias_get')
      .then((r) => setAlias(r.alias || ''))
      .catch(() => {})
  }, [])

  async function save() {
    if (!alias.trim() || loading) return
    setLoading(true)
    try {
      const r = await call('alias_set', { alias: alias.trim() })
      setSaved(r.alias)
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
        choose a name for yourself.
        <br />
        something dark. something true.
      </p>
      <input
        className="field"
        dir="auto"
        value={alias}
        maxLength={32}
        placeholder="the name you choose…"
        onChange={(e) => {
          setAlias(e.target.value)
          setSaved(null)
        }}
        onKeyDown={(e) => e.key === 'Enter' && save()}
      />
      <p className="field-hint" style={{ marginBottom: 0 }}>
        only the keeper will see it.
      </p>
      <div className="actions">
        <Button onClick={save} loading={loading} disabled={!alias.trim()}>
          take the name
        </Button>
      </div>

      {saved && (
        <p className="revelation reveal" style={{ marginTop: '1.75rem' }}>
          from now on, you arrive as
          <br />
          <span className="name-given fa" dir="auto">{saved}</span>
        </p>
      )}
    </Screen>
  )
}
