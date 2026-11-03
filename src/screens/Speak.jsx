import { useEffect, useRef, useState } from 'react'

import Button from '../components/Button.jsx'
import Room from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { toBase64, tooBig } from '../lib/media.js'
import { haptic, notify } from '../lib/telegram.js'

// The Whispering Chamber — speak words into the dark
export default function Speak({ onBack }) {
  const d = DOOR.speak
  const [text, setText] = useState('')
  const [media, setMedia] = useState(null)
  const [mediaError, setMediaError] = useState('')
  const [attaching, setAttaching] = useState(false)
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [confirm, setConfirm] = useState(null)
  const [loading, setLoading] = useState(false)

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
      setMediaError('too heavy for the castle — keep it under 3 MB.')
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
      setMediaError('the castle could not reach your microphone.')
    }
  }

  async function send() {
    if ((!text.trim() && !media) || loading || recording) return
    setLoading(true)
    try {
      const payload = { text: text.trim() }
      if (media) {
        payload.media = {
          kind: media.kind,
          data: media.data,
          mime: media.mime,
          filename: media.filename,
        }
      }
      const r = await call('send', payload)
      track(media ? `sent a ${media.kind} to the keeper` : 'sent words to the keeper')
      setConfirm(r.confirm)
      setText('')
      clearMedia()
      notify('success')
    } catch {
      /* keep their words so they can retry */
    } finally {
      setLoading(false)
    }
  }

  if (confirm) {
    return (
      <Room glyph={d.glyph} title={d.title} onBack={onBack}>
        <blockquote className="revelation revelation-animate">{confirm}</blockquote>
        <div className="actions-row">
          <Button variant="ghost" onClick={() => setConfirm(null)}>
            speak again
          </Button>
        </div>
      </Room>
    )
  }

  return (
    <Room
      glyph={d.glyph}
      title={d.title}
      subtitle="no name. no face. no trace."
      onBack={onBack}
    >
      <textarea
        className="stone-input stone-textarea"
        value={text}
        maxLength={4000}
        rows={5}
        placeholder="let it out..."
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
        <div className="attach-bar">
          <button type="button" className="attach-stone" onClick={() => photoInput.current?.click()}>
            📷 photo
          </button>
          <button type="button" className="attach-stone" onClick={() => videoInput.current?.click()}>
            🎬 video
          </button>
          <button
            type="button"
            className={`attach-stone${recording ? ' recording' : ''}`}
            onClick={toggleRecord}
          >
            {recording ? `⏺ ${seconds}s · stop` : '🎤 voice'}
          </button>
        </div>
      )}

      {attaching && (
        <p className="attach-loading">
          <span className="arcane-spinner" aria-hidden="true" /> drawing it into the dark...
        </p>
      )}

      {media && (
        <div className="media-preview-chip revelation-animate">
          <MediaPreview media={media} />
          <span className="media-preview-label">{media.kind}</span>
          <button type="button" className="media-preview-remove" onClick={clearMedia} aria-label="remove">
            ×
          </button>
        </div>
      )}

      {mediaError && <p className="whisper error text-center mt-small">{mediaError}</p>}

      <div className="actions-row">
        <Button
          onClick={send}
          loading={loading}
          loadingText={media ? 'carrying it through...' : 'sending into the dark...'}
          disabled={(!text.trim() && !media) || recording || attaching}
        >
          send into the dark
        </Button>
      </div>
    </Room>
  )
}

function MediaPreview({ media }) {
  if (media.kind === 'photo') {
    return <img className="media-preview-thumb" src={media.previewUrl} alt="" />
  }
  if (media.kind === 'video') {
    return <video className="media-preview-thumb" src={media.previewUrl} muted playsInline />
  }
  return (
    <audio className="media-preview-audio" src={media.previewUrl} controls />
  )
}
