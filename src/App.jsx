import { useCallback, useEffect, useState } from 'react'

import Placeholder from './components/Placeholder.jsx'
import { call, track } from './lib/api.js'
import { DOOR } from './lib/doors.js'
import { SCREENS } from './lib/screens.jsx'
import { isDev, setBackButton } from './lib/telegram.js'
import Home from './screens/Home.jsx'
import Atmosphere from './components/Atmosphere.jsx'

// The shell: boots by verifying who you are, then drives a simple navigation
// stack. Home is the corridor; every other key resolves to its feature screen
// (or a Placeholder until that screen's phase lands). The native Telegram back
// button mirrors the stack depth.
export default function App() {
  const [me, setMe] = useState(null)
  const [boot, setBoot] = useState('loading') // loading | ready | error
  const [error, setError] = useState('')
  const [stack, setStack] = useState(['home'])
  const [prevView, setPrevView] = useState(null)
  const [transitioning, setTransitioning] = useState(false)

  const navigate = useCallback((key) => {
    track(`entered ${DOOR[key]?.title || key}`)
    setStack((s) => {
      setPrevView(s[s.length - 1])
      setTransitioning(true)
      return [...s, key]
    })
  }, [])
  const back = useCallback(
    () => setStack((s) => {
      if (s.length > 1) {
        setPrevView(s[s.length - 1])
        setTransitioning(true)
        return s.slice(0, -1)
      }
      return s
    }),
    [],
  )

  useEffect(() => {
    if (transitioning) {
      const timer = setTimeout(() => {
        setPrevView(null)
        setTransitioning(false)
      }, 450)
      return () => clearTimeout(timer)
    }
  }, [transitioning])

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

  // Near-real-time inbox badge: poll the unread count on an interval and
  // immediately whenever the app regains focus. Serverless can't push, so this
  // light poll is the closest thing — cheap (just a count) and self-correcting.
  useEffect(() => {
    if (boot !== 'ready') return undefined
    let alive = true
    const poll = async () => {
      try {
        const r = await call('unread')
        if (alive && typeof r.unread === 'number') {
          setMe((m) => (m ? { ...m, unread: r.unread } : m))
        }
      } catch {
        /* ignore — the next tick will try again */
      }
    }
    const id = setInterval(poll, 15000)
    const onVisible = () => {
      if (document.visibilityState === 'visible') poll()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive = false
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [boot])

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

  function renderScreen(key) {
    if (key === 'home') return <Home me={me} navigate={navigate} />
    const Comp = SCREENS[key]
    return Comp ? (
      <Comp me={me} navigate={navigate} onBack={back} />
    ) : (
      <Placeholder screenKey={key} onBack={back} />
    )
  }

  const currentView = renderScreen(current)
  const oldView = prevView ? renderScreen(prevView) : null

  return (
    <main className="app">
      <Atmosphere />
      <div className="scene-container">
        {oldView && (
          <div key={prevView + '-exit'} className="view view-exit" aria-hidden="true">
            {oldView}
          </div>
        )}
        <div key={current} className="view">
          {currentView}
        </div>
      </div>
      {isDev && <p className="devnote">dev preview — outside Telegram</p>}
    </main>
  )
}

function Boot({ children, error }) {
  return (
    <main className="corridor">
      <Atmosphere />
      <h1 className="title">the corridor</h1>
      <p className={`whisper${error ? ' error' : ''}`}>{children}</p>
    </main>
  )
}
