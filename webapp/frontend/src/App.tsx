import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './components/ui'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import ToolsCatalog from './pages/ToolsCatalog'
import ToolDetail from './pages/ToolDetail'
import JobHistory from './pages/JobHistory'
import Config from './pages/Config'
import Users from './pages/Users'
import AccessManagement from './pages/AccessManagement'

export default function App() {
  return (
    <AuthProvider>
      {/* Fuera del router: un toast disparado antes de navegar debe sobrevivir
          al cambio de ruta. */}
      <ToastProvider>
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
              <Route index element={<Navigate to="/tools" replace />} />
              <Route path="pipeline" element={<Navigate to="/tools" replace />} />
              <Route path="tools"          element={<ToolsCatalog />} />
              <Route path="tools/:toolId"  element={<ToolDetail />} />
              <Route path="jobs"     element={<JobHistory />} />

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
              <Route
                path="access"
                element={
                  <ProtectedRoute roles={['superadmin']}>
                    <AccessManagement />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/tools" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}
