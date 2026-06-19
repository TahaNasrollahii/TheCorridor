// Thin wrapper around the Telegram Mini App SDK (window.Telegram.WebApp).
//
// Outside Telegram (e.g. `npm run dev` in a normal browser) the SDK is absent,
// so every accessor degrades gracefully and `isDev` is true — the app then
// runs against mocked data so the UI can be built without a phone.

const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined

export const isDev = !tg || !tg.initData

export function initTelegram() {
  if (!tg) return
  try {
    tg.ready()
    tg.expand()
    // Lock the chrome to the corridor's palette.
    tg.setBackgroundColor?.('#08080b')
    tg.setHeaderColor?.('#08080b')
    tg.enableClosingConfirmation?.()
  } catch {
    /* never let SDK quirks crash the app */
  }
}

export function getInitData() {
  return tg?.initData || ''
}

export function getUser() {
  return tg?.initDataUnsafe?.user || null
}

export function haptic(kind = 'light') {
  try {
    tg?.HapticFeedback?.impactOccurred?.(kind)
  } catch {
    /* ignore */
  }
}

export function notify(kind = 'success') {
  try {
    tg?.HapticFeedback?.notificationOccurred?.(kind)
  } catch {
    /* ignore */
  }
}

// Telegram's native back button (top-left). We keep a single handler bound and
// swap it as navigation changes. In dev (no SDK) this is a no-op and the app's
// own on-screen back affordance is used instead.
let _backHandler = null

export function setBackButton(visible, handler) {
  const bb = tg?.BackButton
  if (!bb) return
  try {
    if (_backHandler) bb.offClick(_backHandler)
    _backHandler = handler || null
    if (visible && handler) {
      bb.onClick(handler)
      bb.show()
    } else {
      bb.hide()
    }
  } catch {
    /* older clients may lack BackButton; the in-app control covers dev */
  }
}
