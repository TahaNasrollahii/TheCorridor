import { SECTIONS } from '../lib/doors.js'
import { haptic } from '../lib/telegram.js'

// The Entrance Hall — the first room of the castle.
// Arched doorways lead deeper into the castle. Each doorway is a threshold
// you cross, not a button you press.
export default function Home({ me, navigate }) {
  const name = me?.user?.username
    ? `@${me.user.username}`
    : me?.user?.first_name || null

  let index = 0

  // The keeper's passage is hidden from ordinary souls
  const sections = SECTIONS.filter((s) => !s.admin || me?.is_admin)

  return (
    <div className="entrance-hall">
      {/* The castle gate — your first sight */}
      <header className="castle-gate">
        <div className="great-candle" aria-hidden="true">🕯️</div>
        <h1 className="castle-title">the corridor</h1>
        <p className="castle-subtitle">no name is asked. no light is given.</p>
      </header>

      {/* Decorative arch divider */}
      <div className="arch-line" aria-hidden="true" />

      {/* The corridor of doorways */}
      <nav className="corridor">
        {sections.map((section) => (
          <section className="corridor-section" key={section.label}>
            <div className="wall-inscription">{section.label}</div>
            {section.doors.map((door) => (
              <button
                key={door.key}
                className="archway"
                style={{ animationDelay: `${0.06 * index++}s` }}
                onClick={() => {
                  haptic('light')
                  navigate(door.key)
                }}
              >
                <span className="archway-glyph">{door.glyph}</span>
                <span className="archway-text">
                  <span className="archway-title">{door.title}</span>
                  <span className="archway-sub">{door.sub}</span>
                </span>
                {door.key === 'inbox' && me?.unread > 0 && (
                  <span className="ember-badge">{me.unread}</span>
                )}
                <span className="archway-passage" aria-hidden="true">
                  <span className="archway-passage-line" />
                  <span className="archway-passage-dot" />
                </span>
              </button>
            ))}
          </section>
        ))}
      </nav>

      {/* Carved inscription at the bottom */}
      <footer className="entrance-inscription">
        {name ? (
          <>
            the castle sees you as <span style={{ color: 'rgba(176,141,87,0.5)' }}>a nameless soul</span>
          </>
        ) : (
          'a soul enters, unnamed'
        )}
        {me?.is_admin && <span style={{ color: 'var(--ember-soft)' }}> · the keeper</span>}
      </footer>
    </div>
  )
}
