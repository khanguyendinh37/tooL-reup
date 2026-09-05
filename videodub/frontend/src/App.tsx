import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Dubbing from './pages/Dubbing'
import History from './pages/History'
import Settings from './pages/Settings'
import Documentation from './pages/Documentation'
import { useSyncSettings } from './hooks/useSyncSettings'

function App() {
  // Hydrate dubbingPreferences from the backend on every app load so the
  // Dubbing page reflects whatever the user last saved on the Settings page.
  useSyncSettings()
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="dubbing" element={<Dubbing />} />
        <Route path="dubbing/:projectId" element={<Dubbing />} />
        <Route path="history" element={<History />} />
        <Route path="settings" element={<Settings />} />
        <Route path="docs" element={<Documentation />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
