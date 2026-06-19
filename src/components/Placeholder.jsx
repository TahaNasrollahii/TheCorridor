import Screen from './Screen.jsx'
import { DOOR } from '../lib/doors.js'

// Stand-in for a door whose room hasn't been carved yet. Replaced screen by
// screen in later phases.
export default function Placeholder({ screenKey, onBack }) {
  const door = DOOR[screenKey] || { glyph: '🕯️', title: 'a door', sub: '' }
  return (
    <Screen glyph={door.glyph} title={door.title} subtitle={door.sub} onBack={onBack}>
      <p className="whisper" style={{ marginTop: '2rem', textAlign: 'center' }}>
        this room is still being carved
        <br />
        from the dark.
      </p>
    </Screen>
  )
}
