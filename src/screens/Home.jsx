import { SECTIONS } from '../lib/doors.js'
import { haptic } from '../lib/telegram.js'

// The corridor itself: a descent of doors. Each door enters with a staggered
// fade so the list assembles out of the dark rather than snapping in.
export default function Home({ me, navigate }) {
  const name = me?.user?.username
    ? `@${me.user.username}`
    : me?.user?.first_name || null

  let index = 0

  // Admin-only sections (the keeper's console) are hidden from ordinary souls.
  const sections = SECTIONS.filter((s) => !s.admin || me?.is_admin)

  return (
    <div className="home">
      <div className="ember" aria-hidden="true" />

      <header className="hero">
        <div className="candle" aria-hidden="true">🕯️</div>
        <h1 className="title">the corridor</h1>
        <p className="whisper">no name is asked. no light is given.</p>
      </header>

      <nav className="doors">
        {sections.map((section) => (
          <section className="door-section" key={section.label}>
            <div className="section-label">{section.label}</div>
            {section.doors.map((door) => (
              <button
                key={door.key}
                className="door"
                style={{ animationDelay: `${0.045 * index++}s` }}
                onClick={() => {
                  haptic('light')
                  navigate(door.key)
                }}
              >
                <span className="door-glyph">{door.glyph}</span>
                <span className="door-text">
                  <span className="door-title">{door.title}</span>
                  <span className="door-sub">{door.sub}</span>
                </span>
                {door.key === 'inbox' && me?.unread > 0 && (
                  <span className="door-badge">{me.unread}</span>
                )}
                <span className="door-chevron" aria-hidden="true">
                  ›
                </span>
              </button>
            ))}
          </section>
        ))}
      </nav>

      <footer className="home-foot">
        {name ? (
          <>
            the corridor sees you as a <span className="name">faceless soul</span>
          </>
        ) : (
          'a nameless soul'
        )}
        {me?.is_admin && <span className="keeper"> · the keeper</span>}
      </footer>
    </div>
  )
}
