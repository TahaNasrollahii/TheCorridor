import { useEffect, useState } from 'react'

import Screen from '../components/Screen.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'

const MEDIA_LABELS = {
  photo: { glyph: '📷', label: 'a photo' },
  video: { glyph: '🎬', label: 'a video' },
  voice: { glyph: '🎤', label: 'a voice message' },
  audio: { glyph: '🎵', label: 'an audio clip' },
  animation: { glyph: '🎞️', label: 'a gif' },
  sticker: { glyph: '🌒', label: 'a sticker' },
  document: { glyph: '📄', label: 'a file' },
  media: { glyph: '📎', label: 'an attachment' },
}

// Bare "[MEDIA]" / "[voice]" markers from older or bot-chat entries.
const BARE = /^\[(media|photo|video|voice|audio|document|gif|sticker|animation)\]$/i

function resolveKind(m) {
  if (m.media) return m.media in MEDIA_LABELS ? m.media : 'media'
  const match = BARE.exec((m.text || '').trim())
  if (!match) return null
  const k = match[1].toLowerCase()
  if (k === 'gif') return 'animation'
  return k in MEDIA_LABELS ? k : 'media'
}

function captionOf(m, kind) {
  const t = (m.text || '').trim()
  if (kind && BARE.test(t)) return ''
  return t
}

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
          {messages.map((m, i) => {
            const kind = resolveKind(m)
            const caption = captionOf(m, kind)
            const media = kind ? MEDIA_LABELS[kind] : null
            return (
              <div key={i} className={`bubble ${m.dir === 'in' ? 'in' : 'out'}`}>
                {media && (
                  <div className="media-card">
                    <span className="media-card-glyph">{media.glyph}</span>
                    <span className="media-card-label">
                      {media.label}
                      {m.dir === 'in' && <span className="media-hint">opened in your chat ↗</span>}
                    </span>
                  </div>
                )}
                {caption && <p className="bubble-text">{caption}</p>}
                <span className="bubble-meta">
                  {m.dir === 'in' ? 'the dark' : 'you'} · {formatTime(m.ts)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </Screen>
  )
}
