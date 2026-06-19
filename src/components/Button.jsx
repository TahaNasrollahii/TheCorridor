import { haptic } from '../lib/telegram.js'

// The corridor's action button. `variant`: 'primary' (ember) or 'ghost'.
// While `loading`, shows `loadingText` (or a spinner dot) and an ember pulse.
export default function Button({
  children,
  onClick,
  disabled = false,
  loading = false,
  loadingText,
  variant = 'primary',
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant}${loading ? ' is-loading' : ''}`}
      disabled={disabled || loading}
      onClick={(e) => {
        haptic('medium')
        onClick?.(e)
      }}
    >
      {loading ? (
        <span className="btn-loading">
          <span className="btn-spinner" aria-hidden="true" />
          {loadingText || 'one moment…'}
        </span>
      ) : (
        children
      )}
    </button>
  )
}
