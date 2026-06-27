import { memo } from 'react'
import '../styles.css'

export default memo(function GothicCard({ children, className = '', as: Component = 'div', ...props }) {
  return (
    <Component className={`gothic-card ${className}`} {...props}>
      <div className="gothic-card-border" aria-hidden="true" />
      <div className="gothic-card-content">{children}</div>
    </Component>
  )
})
