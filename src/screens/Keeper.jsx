import { useEffect, useRef, useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import Thread, { formatTime } from '../components/Thread.jsx'
import { call } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { toBase64, tooBig } from '../lib/media.js'
import { haptic, notify, setBackButton } from '../lib/telegram.js'

// The keeper's console: every soul's conversation in one place. Two views —
// the list of chats, and one open chat with its full history and a reply box.

const PREVIEW_GLYPH = {
  photo: '📷',
  video: '🎬',
  voice: '🎤',
  audio: '🎵',
  animation: '🎞️',
  sticker: '🌒',
  document: '📄',
}

// The keeper's label for a soul, per preference:
//   name + username → "name - @username"
//   name only       → "name - id"
//   username only    → "@username - id"
//   neither          → "id"
function who(t) {
  const name = (t.name || '').trim()
  const username = t.username ? `@${t.username}` : ''
  if (name && username) return `${name} - ${username}`
  if (name) return `${name} - ${t.uid}`
  if (username) return `${username} - ${t.uid}`
  return `${t.uid}`
}

// A shorter label for cramped spots (bubble meta): name, else @username, else id.
function shortName(t) {
  if (t.name) return t.name.trim()
  if (t.username) return `@${t.username}`
  return `${t.uid}`
}

function preview(t) {
  if (t.last_media) return `${PREVIEW_GLYPH[t.last_media] || '📎'} ${t.last_media}`
  const text = (t.last_text || '').trim()
  if (!text) return '—'
  return t.last_dir === 'in' ? `you: ${text}` : text
}

export default function Keeper({ me, onBack }) {
  const d = DOOR.keeper
  const [selected, setSelected] = useState(null) // the open chat's thread, or null

  // Native Telegram back: while a chat is open, back returns to the list;
  // otherwise it leaves the console. (No-op in dev — Screen's ← is used there.)
  useEffect(() => {
    setBackButton(true, selected ? () => setSelected(null) : onBack)
  }, [selected, onBack])

  const back = selected ? () => setSelected(null) : onBack

  // Defense in depth — the server 403s any admin_* call from a non-keeper, but
  // never even show the console to a non-admin who reached this key.
  if (!me?.is_admin) {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="whisper center error">this sight is not yours.</p>
      </Screen>
    )
  }

  if (selected) {
    return <Chat thread={selected} onBack={back} />
  }
  return <ChatList onOpen={setSelected} onBack={onBack} />
}

function ChatList({ onOpen, onBack }) {
  const d = DOOR.keeper
  const [state, setState] = useState('loading') // loading | ready | error
  const [threads, setThreads] = useState([])

  // Load on mount, then a light poll so new arrivals surface without reopening.
  useEffect(() => {
    let alive = true
    const run = async () => {
      try {
        const r = await call('admin_threads')
        if (alive) {
          setThreads(r.threads || [])
          setState('ready')
        }
      } catch {
        if (alive) setState((s) => (s === 'loading' ? 'error' : s))
      }
    }
    run()
    const id = setInterval(run, 15000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  return (
    <Screen glyph={d.glyph} title={d.title} subtitle="every voice in the corridor" onBack={onBack}>
      {state === 'loading' && <p className="whisper center">gathering the voices…</p>}
      {state === 'error' && <p className="whisper center error">the dark would not answer.</p>}

      {state === 'ready' && threads.length === 0 && (
        <p className="empty">{'no one has spoken yet.\nthe corridor is silent.'}</p>
      )}

      {state === 'ready' && threads.length > 0 && (
        <div className="chat-list">
          {threads.map((t) => (
            <button
              key={t.uid}
              className={`chat-row${t.new ? ' is-new' : ''}`}
              onClick={() => {
                haptic('light')
                onOpen(t)
              }}
            >
              <span className="chat-row-main">
                <span className="chat-row-name">
                  {who(t)}
                  {t.new && <span className="chat-row-dot" aria-label="unanswered" />}
                </span>
                <span className="chat-row-preview">{preview(t)}</span>
              </span>
              <span className="chat-row-time">{formatTime(t.ts)}</span>
            </button>
          ))}
        </div>
      )}
    </Screen>
  )
}

function Chat({ thread, onBack }) {
  const d = DOOR.keeper
  const uid = thread.uid
  const [state, setState] = useState('loading') // loading | ready | error
  const [messages, setMessages] = useState([])

  async function load() {
    try {
      const r = await call('admin_thread', { uid })
      setMessages(r.messages || [])
      setState('ready')
    } catch {
      setState('error')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid])

  return (
    <Screen glyph={d.glyph} title={who(thread)} subtitle={`#${uid}`} onBack={onBack}>
      {state === 'loading' && <p className="whisper center">opening the thread…</p>}
      {state === 'error' && <p className="whisper center error">the dark would not answer.</p>}

      {state === 'ready' && (
        <>
          {messages.length === 0 ? (
            <p className="empty">{'nothing yet between you.'}</p>
          ) : (
            <Thread messages={messages} perspective="keeper" theirLabel={shortName(thread)} />
          )}
          <Composer uid={uid} onSent={load} />
        </>
      )}
    </Screen>
  )
}

function Composer({ uid, onSent }) {
  const [text, setText] = useState('')
  const [media, setMedia] = useState(null) // {kind, data, mime, filename, previewUrl}
  const [mediaError, setMediaError] = useState('')
  const [attaching, setAttaching] = useState(false)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [sending, setSending] = useState(false)

  const photoInput = useRef(null)
  const videoInput = useRef(null)
  const recorder = useRef(null)
  const chunks = useRef([])
  const timer = useRef(null)

  useEffect(() => {
    return () => {
      if (media?.previewUrl) URL.revokeObjectURL(media.previewUrl)
      if (timer.current) clearInterval(timer.current)
      if (recorder.current && recorder.current.state !== 'inactive') {
        recorder.current.stop()
        recorder.current.stream?.getTracks().forEach((t) => t.stop())
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function clearMedia() {
    if (media?.previewUrl) URL.revokeObjectURL(media.previewUrl)
    setMedia(null)
    setMediaError('')
  }

  async function attach(file, kind) {
    if (!file) return
    setMediaError('')
    if (tooBig(file.size)) {
      setMediaError('too heavy for the corridor — keep it under 3 MB.')
      return
    }
    setAttaching(true)
    try {
      const data = await toBase64(file)
      clearMedia()
      setMedia({
        kind,
        data,
        mime: file.type,
        filename: file.name || `${kind}`,
        previewUrl: URL.createObjectURL(file),
      })
      haptic('light')
    } catch {
      setMediaError('that file could not be read.')
    } finally {
      setAttaching(false)
    }
  }

  async function toggleRecord() {
    if (recording) {
      recorder.current?.stop()
      return
    }
    setMediaError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mime = MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : undefined
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      chunks.current = []
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        clearInterval(timer.current)
        setRecording(false)
        const blob = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' })
        if (tooBig(blob.size)) {
          setMediaError('that recording is too long — keep it under 3 MB.')
          return
        }
        setAttaching(true)
        const data = await toBase64(blob)
        setAttaching(false)
        const ext = (rec.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
        clearMedia()
        setMedia({
          kind: 'voice',
          data,
          mime: rec.mimeType || 'audio/webm',
          filename: `voice.${ext}`,
          previewUrl: URL.createObjectURL(blob),
        })
        notify('success')
      }
      recorder.current = rec
      rec.start()
      setRecording(true)
      setSeconds(0)
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000)
      haptic('medium')
    } catch {
      setMediaError('the corridor could not reach your microphone.')
    }
  }

  async function send() {
    if ((!text.trim() && !media) || sending || recording) return
    setSending(true)
    try {
      const payload = { uid, text: text.trim() }
      if (media) {
        payload.media = {
          kind: media.kind,
          data: media.data,
          mime: media.mime,
          filename: media.filename,
        }
      }
      await call('admin_reply', payload)
      setText('')
      clearMedia()
      notify('success')
      onSent?.()
    } catch {
      /* keep their words so they can retry */
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="composer">
      <textarea
        className="field area"
        value={text}
        maxLength={4000}
        rows={3}
        placeholder="answer from the dark…"
        onChange={(e) => setText(e.target.value)}
      />

      <input
        ref={photoInput}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => attach(e.target.files?.[0], 'photo')}
      />
      <input
        ref={videoInput}
        type="file"
        accept="video/*"
        hidden
        onChange={(e) => attach(e.target.files?.[0], 'video')}
      />

      {!media && !attaching && (
        <div className="attach-row">
          <button type="button" className="attach-btn" onClick={() => photoInput.current?.click()}>
            📷 photo
          </button>
          <button type="button" className="attach-btn" onClick={() => videoInput.current?.click()}>
            🎬 video
          </button>
          <button
            type="button"
            className={`attach-btn${recording ? ' rec' : ''}`}
            onClick={toggleRecord}
          >
            {recording ? `⏺ ${seconds}s · stop` : '🎤 voice'}
          </button>
        </div>
      )}

      {attaching && (
        <p className="attaching">
          <span className="btn-spinner" aria-hidden="true" /> drawing it into the dark…
        </p>
      )}

      {media && (
        <div className="media-chip reveal">
          <MediaPreview media={media} />
          <span className="media-name">{media.kind}</span>
          <button type="button" className="media-remove" onClick={clearMedia} aria-label="remove">
            ×
          </button>
        </div>
      )}

      {mediaError && (
        <p className="whisper error center" style={{ marginTop: '0.75rem' }}>{mediaError}</p>
      )}

      <div className="actions">
        <Button
          onClick={send}
          loading={sending}
          loadingText="carrying it through…"
          disabled={(!text.trim() && !media) || recording || attaching}
        >
          send into the dark
        </Button>
      </div>
    </div>
  )
}

function MediaPreview({ media }) {
  if (media.kind === 'photo') {
    return <img className="media-thumb" src={media.previewUrl} alt="" />
  }
  if (media.kind === 'video') {
    return <video className="media-thumb" src={media.previewUrl} muted playsInline />
  }
  return <audio className="media-audio" src={media.previewUrl} controls />
}
