import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

const HomePage = lazy(() => import('./routes/HomePage').then((m) => ({ default: m.HomePage })))
const AdminMatchesPage = lazy(() =>
  import('./routes/AdminMatchesPage').then((m) => ({ default: m.AdminMatchesPage })),
)
const DealFeedPage = lazy(() =>
  import('./routes/DealFeedPage').then((m) => ({ default: m.DealFeedPage })),
)
const CoveragePage = lazy(() =>
  import('./routes/CoveragePage').then((m) => ({ default: m.CoveragePage })),
)

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/admin/matches" element={<AdminMatchesPage />} />
        <Route path="/deals" element={<DealFeedPage />} />
        <Route path="/admin/coverage" element={<CoveragePage />} />
      </Routes>
    </Suspense>
  )
}
