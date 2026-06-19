import { useCallback, useEffect, useState } from 'react'

import Placeholder from './components/Placeholder.jsx'
import { call } from './lib/api.js'
import { SCREENS } from './lib/screens.jsx'
import { isDev, setBackButton } from './lib/telegram.js'
import Home from './screens/Home.jsx'

// The shell: boots by verifying who you are, then drives a simple navigation
// stack. Home is the corridor; every other key resolves to its feature screen
// (or a Placeholder until that screen's phase lands). The native Telegram back
// button mirrors the stack depth.
export default function App() {
  const [me, setMe] = useState(null)
  const [boot, setBoot] = useState('loading') // loading | ready | error
  const [error, setError] = useState('')
  const [stack, setStack] = useState(['home'])

  const navigate = useCallback((key) => setStack((s) => [...s, key]), [])
  const back = useCallback(
    () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)),
    [],
  )

  useEffect(() => {
    call('me')
      .then((data) => {
        setMe(data)
        setBoot('ready')
      })
      .catch((err) => {
        setError(err.message)
        setBoot('error')
      })
  }, [])

  const current = stack[stack.length - 1]

  useEffect(() => {
    setBackButton(stack.length > 1, back)
  }, [stack.length, back])

  // Opening the inbox clears the unread mark server-side, so drop the home
  // badge locally too (otherwise it lingers until the app is reopened).
  useEffect(() => {
    if (current === 'inbox') {
      setMe((m) => (m && m.unread ? { ...m, unread: 0 } : m))
    }
  }, [current])

  if (boot === 'loading') return <Boot>the dark stirs…</Boot>
  if (boot === 'error') {
    return (
      <Boot error>
        the gate would not open.
        <br />
        <span className="reason">{error}</span>
      </Boot>
    )
  }

  let view
  if (current === 'home') {
    view = <Home me={me} navigate={navigate} />
  } else {
    const Comp = SCREENS[current]
    view = Comp ? (
      <Comp me={me} navigate={navigate} onBack={back} />
    ) : (
      <Placeholder screenKey={current} onBack={back} />
    )
  }

  return (
    <main className="app">
      {/* key re-mounts on navigation so each view fades up as it enters */}
      <div key={current} className="view">
        {view}
      </div>
      {isDev && <p className="devnote">dev preview — outside Telegram</p>}
    </main>
  )
}

function Boot({ children, error }) {
  return (
    <main className="corridor">
      <div className="ember" aria-hidden="true" />
      <h1 className="title">the corridor</h1>
      <p className={`whisper${error ? ' error' : ''}`}>{children}</p>
    </main>
  )
}
