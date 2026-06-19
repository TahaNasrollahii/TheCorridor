import { useEffect, useState } from 'react'

import Button from '../components/Button.jsx'
import Screen from '../components/Screen.jsx'
import { call, track } from '../lib/api.js'
import { DOOR } from '../lib/doors.js'
import { notify } from '../lib/telegram.js'

const NUMERALS = ['I', 'II', 'III', 'IV']
const CONFIRM =
  'the ritual is complete.\n\nwhat you gave has been received and kept.\nthe corridor holds it in the dark —\na secret that has never wept.'

export default function Ritual({ onBack }) {
  const d = DOOR.ritual
  const [questions, setQuestions] = useState(null)
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState([])
  const [current, setCurrent] = useState('')
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    call('ritual_questions')
      .then((r) => setQuestions(r.questions))
      .catch(() => setQuestions([]))
  }, [])

  async function advance() {
    if (loading) return
    const filled = [...answers, current.trim() || '[no answer]']
    setCurrent('')

    if (filled.length < 4) {
      setAnswers(filled)
      setStep(step + 1)
      return
    }

    setLoading(true)
    try {
      await call('ritual', { answers: filled })
      track('completed the ritual')
      setDone(true)
      notify('success')
    } catch {
      setAnswers(filled) // let them try the final submit again
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <blockquote className="revelation reveal">{CONFIRM}</blockquote>
      </Screen>
    )
  }

  if (!questions) {
    return (
      <Screen glyph={d.glyph} title={d.title} onBack={onBack}>
        <p className="whisper center">the rite gathers…</p>
      </Screen>
    )
  }

  const last = step === 3
  return (
    <Screen
      glyph={d.glyph}
      title={d.title}
      subtitle="four questions. answer honestly."
      onBack={onBack}
    >
      <div className="step-marks">
        {NUMERALS.map((n, i) => (
          <span key={n} className={`step-mark${i === step ? ' on' : ''}${i < step ? ' past' : ''}`}>
            {n}
          </span>
        ))}
      </div>

      <p className="prompt" key={step}>
        {questions[step]}
      </p>

      <textarea
        className="field area"
        value={current}
        maxLength={2000}
        rows={4}
        placeholder="speak…"
        onChange={(e) => setCurrent(e.target.value)}
      />

      <div className="actions">
        <Button onClick={advance} loading={loading}>
          {last ? 'complete the rite' : 'continue'}
        </Button>
      </div>
    </Screen>
  )
}
