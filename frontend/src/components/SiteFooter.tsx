import { Link } from 'react-router-dom'

export function SiteFooter() {
  return (
    <footer className="text-center text-xs text-ink/70 py-6 space-y-2">
      <nav className="flex justify-center gap-4">
        <Link to="/about" className="hover:text-ink">About</Link>
        <Link to="/privacy" className="hover:text-ink">Privacy</Link>
        <Link to="/terms" className="hover:text-ink">Terms</Link>
      </nav>
      <p>As an Amazon Associate, compa earns from qualifying purchases.</p>
    </footer>
  )
}
