// Implemented feature screens, keyed by door. Anything absent here falls back
// to a Placeholder.

import Alias from '../screens/Alias.jsx'
import Archive from '../screens/Archive.jsx'
import Countdown from '../screens/Countdown.jsx'
import Dark from '../screens/Dark.jsx'
import Fortune from '../screens/Fortune.jsx'
import Inbox from '../screens/Inbox.jsx'
import Letter from '../screens/Letter.jsx'
import Mirror from '../screens/Mirror.jsx'
import Mood from '../screens/Mood.jsx'
import Ritual from '../screens/Ritual.jsx'
import Speak from '../screens/Speak.jsx'
import Vow from '../screens/Vow.jsx'

export const SCREENS = {
  speak: Speak,
  inbox: Inbox,
  mood: Mood,
  mirror: Mirror,
  dark: Dark,
  fortune: Fortune,
  ritual: Ritual,
  letter: Letter,
  vow: Vow,
  countdown: Countdown,
  alias: Alias,
  archive: Archive,
}
