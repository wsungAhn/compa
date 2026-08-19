import { Route, Routes } from 'react-router-dom'
import { HomePage } from './routes/HomePage'
import { AdminMatchesPage } from './routes/AdminMatchesPage'
import { DealFeedPage } from './routes/DealFeedPage'
import { CoveragePage } from './routes/CoveragePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/admin/matches" element={<AdminMatchesPage />} />
      <Route path="/deals" element={<DealFeedPage />} />
      <Route path="/admin/coverage" element={<CoveragePage />} />
    </Routes>
  )
}
