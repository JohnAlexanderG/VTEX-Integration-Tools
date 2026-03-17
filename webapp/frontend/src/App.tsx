import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Pipeline from './pages/Pipeline'
import Tools from './pages/Tools'
import Config from './pages/Config'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/pipeline" replace />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="tools" element={<Tools />} />
          <Route path="config" element={<Config />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
