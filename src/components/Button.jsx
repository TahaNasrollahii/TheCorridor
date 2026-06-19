import { haptic } from '../lib/telegram.js'

// The corridor's action button. `variant`: 'primary' (ember) or 'ghost'.
export default function Button({
  children,
  onClick,
  disabled = false,
  loading = false,
  variant = 'primary',
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant}`}
      disabled={disabled || loading}
      onClick={(e) => {
        haptic('medium')
        onClick?.(e)
      }}
    >
      {loading ? '…' : children}
    </button>
  )
}
