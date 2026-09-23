import { Link } from 'react-router-dom'

export function SiteFooter() {
  return (
    <footer className="text-center text-xs text-gray-400 py-6 space-y-2">
      <nav className="flex justify-center gap-4">
        <Link to="/about" className="hover:text-gray-600">About</Link>
        <Link to="/privacy" className="hover:text-gray-600">Privacy</Link>
        <Link to="/terms" className="hover:text-gray-600">Terms</Link>
      </nav>
      <p>As an Amazon Associate, compa earns from qualifying purchases.</p>
    </footer>
  )
}
