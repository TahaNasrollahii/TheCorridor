import { useEffect, useState } from 'react'

import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts * 1000).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export default function Inbox({ onBack }) {
  const d = DOOR.inbox
  const [state, setState] = useState('loading') // loading | ready | error
  const [messages, setMessages] = useState([])

  useEffect(() => {
    call('inbox')
      .then((r) => {
        setMessages(r.messages || [])
        setState('ready')
      })
      .catch(() => setState('error'))
  }, [])

  return (
    <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
      {state === 'loading' && <p className="whisper center">listening to the dark…</p>}

      {state === 'error' && (
        <p className="whisper center error">the dark would not answer.</p>
      )}

      {state === 'ready' && messages.length === 0 && (
        <p className="empty">
          {'nothing has returned yet.\nwhat you send will live here —\nand so will every answer.'}
        </p>
      )}

      {state === 'ready' && messages.length > 0 && (
        <div className="thread">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.dir === 'in' ? 'in' : 'out'}`}>
              <p className="bubble-text">{m.text}</p>
              <span className="bubble-meta">
                {m.dir === 'in' ? 'the dark' : 'you'} · {formatTime(m.ts)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Screen>
  )
}
