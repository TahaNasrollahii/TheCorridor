import { memo } from 'react'
import '../styles.css' // Ensures styles apply

// A pure aesthetic layer that sits behind the entire app.
// Renders the moving fog, floating particles (dust/embers), and a soft radial glow.
const Atmosphere = memo(function Atmosphere() {
  return (
    <div className="atmosphere" aria-hidden="true">
      {/* Deep gradient background */}
      <div className="void-bg" />
      
      {/* Slow moving CSS fog layers */}
      <div className="fog fog-1" />
      <div className="fog fog-2" />
      
      {/* Floating particles */}
      <div className="particles">
        {/* We use multiple CSS-animated particles */}
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className={`particle p-${i + 1}`} />
        ))}
      </div>
      
      {/* Central ominous glow (the candle/ember light) */}
      <div className="ambient-glow" />
    </div>
  )
})

export default Atmosphere
