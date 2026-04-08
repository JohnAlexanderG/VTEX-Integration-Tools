import { useState, useEffect, FormEvent } from 'react'
import { UserPlus, RefreshCw, Shield, ShieldCheck, User as UserIcon, ToggleLeft, ToggleRight } from 'lucide-react'
import { fetchUsers, createUser, updateUser, type ApiUser } from '../api/client'
import { useAuth } from '../context/AuthContext'
import AccessDeniedModal from '../components/AccessDeniedModal'

type RoleFilter = 'all' | 'admin' | 'operator'

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  admin:      'Admin',
  operator:   'Operador',
}

const ROLE_COLORS: Record<string, string> = {
  superadmin: 'bg-purple-900 text-purple-300 border-purple-700',
  admin:      'bg-blue-900  text-blue-300  border-blue-700',
  operator:   'bg-gray-800  text-gray-300  border-gray-700',
}

export default function Users() {
  const { user: me, isSuperAdmin, hasSectionAccess } = useAuth()
  const usersAllowed = hasSectionAccess('users')

  const [users,       setUsers]       = useState<ApiUser[]>([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [filter,      setFilter]      = useState<RoleFilter>('all')
  const [showCreate,  setShowCreate]  = useState(false)
  const [saving,      setSaving]      = useState(false)
  const [showDeniedModal, setShowDeniedModal] = useState(false)

  // Formulario de nuevo usuario
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newEmail,    setNewEmail]    = useState('')
  const [newRole,     setNewRole]     = useState('operator')
  const [createError, setCreateError] = useState('')

  async function load() {
    if (!usersAllowed) {
      setLoading(false)
      setShowDeniedModal(true)
      return
    }
    setLoading(true)
    setError('')
    try {
      setUsers(await fetchUsers())
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [usersAllowed])
  useEffect(() => {
    if (!usersAllowed) setShowDeniedModal(true)
  }, [usersAllowed])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setCreateError('')
    setSaving(true)
    try {
      await createUser({ username: newUsername, password: newPassword, email: newEmail || undefined, role: newRole })
      setNewUsername(''); setNewPassword(''); setNewEmail(''); setNewRole('operator')
      setShowCreate(false)
      await load()
    } catch (e: any) {
      setCreateError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(u: ApiUser) {
    try {
      await updateUser(u.id, { is_active: !u.is_active })
      await load()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const filtered = users.filter(u => filter === 'all' || u.role === filter)

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Usuarios</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {isSuperAdmin ? 'Todos los tenants' : me?.tenant_name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="p-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800 rounded-lg transition-colors"
            title="Recargar"
          >
            <RefreshCw size={16} />
          </button>
          <button
            onClick={() => setShowCreate(v => !v)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                       text-white text-sm font-medium rounded-lg transition-colors"
          >
            <UserPlus size={15} />
            Nuevo usuario
          </button>
        </div>
      </div>

      {/* Formulario de creación */}
      {showCreate && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-200 mb-4">Crear usuario</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Usuario *</label>
              <input
                value={newUsername} onChange={e => setNewUsername(e.target.value)} required
                placeholder="nombre_usuario"
                className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg
                           px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Contraseña * (mín. 8 caracteres)</label>
              <input
                type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required
                placeholder="••••••••"
                className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg
                           px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Email</label>
              <input
                type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                placeholder="correo@ejemplo.com"
                className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg
                           px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Rol</label>
              <select
                value={newRole} onChange={e => setNewRole(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white text-sm rounded-lg
                           px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="operator">Operador</option>
                <option value="admin">Admin</option>
                {isSuperAdmin && <option value="superadmin">Super Admin</option>}
              </select>
            </div>

            {createError && (
              <div className="col-span-2 bg-red-950 border border-red-800 text-red-300 rounded-lg px-3 py-2 text-sm">
                {createError}
              </div>
            )}

            <div className="col-span-2 flex justify-end gap-2">
              <button
                type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-gray-100 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit" disabled={saving}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50
                           text-white text-sm font-medium rounded-lg transition-colors"
              >
                {saving ? 'Creando...' : 'Crear usuario'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-2 mb-4">
        {(['all', 'admin', 'operator'] as RoleFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              filter === f
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-gray-100'
            }`}
          >
            {f === 'all' ? 'Todos' : ROLE_LABELS[f]}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Tabla */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-14 bg-gray-900 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500 text-sm">
          No hay usuarios para mostrar
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(u => {
            const isMe = u.id === me?.id
            return (
              <div
                key={u.id}
                className={`flex items-center gap-4 bg-gray-900 border rounded-xl px-4 py-3 transition-opacity ${
                  u.is_active ? 'border-gray-800' : 'border-gray-800 opacity-50'
                }`}
              >
                {/* Avatar */}
                <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center flex-shrink-0">
                  {u.role === 'superadmin' ? (
                    <ShieldCheck size={16} className="text-purple-400" />
                  ) : u.role === 'admin' ? (
                    <Shield size={16} className="text-blue-400" />
                  ) : (
                    <UserIcon size={16} className="text-gray-400" />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-100">{u.username}</span>
                    {isMe && (
                      <span className="text-[10px] bg-indigo-900 text-indigo-300 border border-indigo-700
                                       rounded px-1.5 py-0.5">Tú</span>
                    )}
                    <span className={`text-[11px] border rounded px-1.5 py-0.5 ${ROLE_COLORS[u.role]}`}>
                      {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    {u.email && <span className="text-xs text-gray-500">{u.email}</span>}
                    {isSuperAdmin && (
                      <span className="text-xs text-gray-600">{u.tenant_name}</span>
                    )}
                  </div>
                </div>

                {/* Toggle activo (no se puede desactivar a sí mismo) */}
                {!isMe && (
                  <button
                    onClick={() => toggleActive(u)}
                    title={u.is_active ? 'Desactivar usuario' : 'Activar usuario'}
                    className="flex-shrink-0 text-gray-500 hover:text-gray-100 transition-colors"
                  >
                    {u.is_active
                      ? <ToggleRight size={22} className="text-green-500" />
                      : <ToggleLeft  size={22} />
                    }
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}

      <AccessDeniedModal
        open={showDeniedModal}
        title="Usuarios bloqueados"
        message="Tu cuenta no tiene permisos para administrar usuarios en este tenant. Solicita la habilitación desde Laburu Agencia."
        onClose={() => setShowDeniedModal(false)}
      />
    </div>
  )
}
