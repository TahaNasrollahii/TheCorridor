// The back-and-forth bubble list, shared by the soul's inbox and the keeper's
// console. `perspective` decides whose messages sit on the right (their own):
//   - 'soul'   → the soul reads it: their words ('out') on the right,
//                the dark's answers ('in') on the left.
//   - 'keeper' → the keeper reads it: their replies ('in') on the right,
//                the soul's words ('out') on the left.
// Media files never live in the thread (only a kind label) — the real file is in
// whichever Telegram chat received it, hence the "opened in your chat" hint on
// anything incoming.

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

export function formatTime(ts) {
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

export default function Thread({ messages, perspective = 'soul', theirLabel }) {
  const theirs = perspective === 'keeper' ? theirLabel || 'the soul' : 'the dark'

  return (
    <div className="thread">
      {messages.map((m, i) => {
        const kind = resolveKind(m)
        const caption = captionOf(m, kind)
        const media = kind ? MEDIA_LABELS[kind] : null
        // "mine" = the viewer's own message → right-aligned ('out' styling).
        const mine = perspective === 'keeper' ? m.dir === 'in' : m.dir === 'out'
        return (
          <div key={i} className={`bubble ${mine ? 'out' : 'in'}`}>
            {media && (
              <div className="media-card">
                <span className="media-card-glyph">{media.glyph}</span>
                <span className="media-card-label">
                  {media.label}
                  {!mine && <span className="media-hint">opened in your chat ↗</span>}
                </span>
              </div>
            )}
            {caption && <p className="bubble-text">{caption}</p>}
            <span className="bubble-meta">
              {mine ? 'you' : theirs} · {formatTime(m.ts)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
