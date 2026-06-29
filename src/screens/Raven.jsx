import { useEffect, useState, useRef } from 'react'

import Button from '../components/Button.jsx'
import Room from '../components/Screen.jsx'
import Thread from '../components/Thread.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'

export default function Raven({ onBack }) {
  const d = DOOR.raven
  const [state, setState] = useState('loading')
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const threadEndRef = useRef(null)

  useEffect(() => {
    call('ai_history')
      .then((r) => {
        setMessages(r.messages || [])
        setState('ready')
      })
      .catch(() => setState('error'))
  }, [])

  useEffect(() => {
    if (threadEndRef.current) {
      threadEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading])

  async function send() {
    if (!text.trim() || loading) return
    const input = text.trim()
    setText('')
    
    // Optimistic UI
    const tempMsg = { role: 'user', content: input, timestamp: Date.now() / 1000 }
    setMessages((prev) => [...prev, tempMsg])
    setLoading(true)

    try {
      const r = await call('ai_chat', { text: input })
      track('spoke to Raven')
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: r.text, timestamp: Date.now() / 1000 },
      ])
    } catch (err) {
      // Revert optimistic message and show error
      setMessages((prev) => prev.slice(0, -1))
      alert(err.message || 'the dark refused to answer.')
    } finally {
      setLoading(false)
    }
  }

  async function clearChat() {
    if (!window.confirm("are you sure you want to erase these memories?")) return
    setLoading(true)
    try {
      await call('ai_clear')
      setMessages([])
    } catch (err) {
      alert("the dark refused to let go.")
    } finally {
      setLoading(false)
    }
  }

  // Convert AI roles to Thread dir format
  const threadMessages = messages
    .filter((m) => m.role !== 'system') // hide summaries
    .map((m) => ({
      dir: m.role === 'user' ? 'out' : 'in',
      text: m.content,
      ts: m.timestamp,
    }))

  return (
    <Room
      glyph={d.glyph}
      title={d.title}
      subtitle="a solitary consciousness."
      onBack={onBack}
    >
      {state === 'loading' && (
        <div className="castle-loading">
          <span className="loading-sigil">🐦‍⬛</span>
          <p className="loading-whisper">the library shifts...</p>
        </div>
      )}

      {state === 'error' && (
        <p className="whisper text-center" style={{ color: '#cf8275' }}>
          the path is barred.
        </p>
      )}

      {state === 'ready' && (
        <div className="raven-chat-container">
          {messages.length === 0 && (
            <p className="castle-empty">
              {'the shadows are completely still.\nspeak.'}
            </p>
          )}

          {messages.length > 0 && (
            <div className="raven-thread">
              <Thread messages={threadMessages} perspective="soul" theirLabel="raven" />
            </div>
          )}

          {loading && (
            <div className="raven-typing">
              <span className="arcane-spinner" aria-hidden="true" />
              <span className="whisper-text" style={{ fontStyle: 'italic', opacity: 0.6 }}>
                the dark gathers its thoughts...
              </span>
            </div>
          )}
          <div ref={threadEndRef} />

          <div className="raven-input-bar">
            <textarea
              className="stone-input stone-textarea"
              style={{ minHeight: '60px', marginBottom: '1rem' }}
              value={text}
              maxLength={2000}
              rows={2}
              placeholder="whisper to it..."
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Button
                style={{ flex: 1 }}
                onClick={send}
                loading={loading}
                disabled={!text.trim() || loading}
              >
                send
              </Button>
              {messages.length > 0 && (
                <Button variant="ghost" onClick={clearChat} disabled={loading}>
                  clear
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </Room>
  )
}
