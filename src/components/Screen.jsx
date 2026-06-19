import { isDev } from '../lib/telegram.js'

// Consistent layout for every non-home screen: a glyph, a title, an optional
// whispered subtitle, then the body. Inside Telegram, going back is handled by
// the native back button (see setBackButton in App), so the on-screen back is
// shown only in the dev preview, where no native button exists.
export default function Screen({ glyph, title, subtitle, children, onBack }) {
  return (
    <div className="screen">
      <header className="screen-head">
        {isDev && onBack && (
          <button
            type="button"
            className="back"
            onClick={onBack}
            aria-label="back to the corridor"
          >
            ←
          </button>
        )}
        {glyph && <div className="screen-glyph">{glyph}</div>}
        <h1 className="screen-title">{title}</h1>
        {subtitle && <p className="screen-sub">{subtitle}</p>}
      </header>
      <div className="screen-body">{children}</div>
    </div>
  )
}
