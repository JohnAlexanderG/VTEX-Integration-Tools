import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Pipeline from './pages/Pipeline'
import Tools from './pages/Tools'
import Config from './pages/Config'
import Users from './pages/Users'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Ruta pública */}
          <Route path="/login" element={<Login />} />

          {/* Rutas protegidas (cualquier usuario autenticado) */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/pipeline" replace />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="tools"    element={<Tools />} />

            {/* Solo admin y superadmin */}
            <Route
              path="config"
              element={
                <ProtectedRoute roles={['admin', 'superadmin']}>
                  <Config />
                </ProtectedRoute>
              }
            />
            <Route
              path="users"
              element={
                <ProtectedRoute roles={['admin', 'superadmin']}>
                  <Users />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/pipeline" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
