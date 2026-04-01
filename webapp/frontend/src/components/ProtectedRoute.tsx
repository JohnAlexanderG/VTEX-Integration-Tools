import { Navigate } from 'react-router-dom'
import { useAuth, UserRole } from '../context/AuthContext'

interface Props {
  children: React.ReactNode
  /** Si se especifica, el usuario debe tener uno de estos roles. */
  roles?: UserRole[]
}

export default function ProtectedRoute({ children, roles }: Props) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/pipeline" replace />
  }

  return <>{children}</>
}
