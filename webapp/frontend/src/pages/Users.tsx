import { useState, useEffect, FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { UserPlus, RefreshCw, Shield, ShieldCheck, User as UserIcon, Users as UsersIcon } from 'lucide-react'
import { fetchTenants, fetchUsers, createUser, updateUser, type ApiTenant, type ApiUser } from '../api/client'
import { useAuth } from '../context/AuthContext'
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Toggle,
  cn,
  useToast,
} from '../components/ui'
import type { BadgeTone } from '../components/ui'

type RoleFilter = 'all' | 'admin' | 'operator'

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  admin:      'Admin',
  operator:   'Operador',
}

const ROLE_TONES: Record<string, BadgeTone> = {
  superadmin: 'accent',
  admin:      'info',
  operator:   'neutral',
}

export default function Users() {
  const { user: me, isSuperAdmin, hasSectionAccess } = useAuth()
  const usersAllowed = hasSectionAccess('users')
  const toast = useToast()

  const [users,       setUsers]       = useState<ApiUser[]>([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState('')
  const [filter,      setFilter]      = useState<RoleFilter>('all')
  const [showCreate,  setShowCreate]  = useState(false)
  const [saving,      setSaving]      = useState(false)
  const [tenants,     setTenants]     = useState<ApiTenant[]>([])
  const [movingUserId, setMovingUserId] = useState<number | null>(null)
  const [togglingUserId, setTogglingUserId] = useState<number | null>(null)

  // Formulario de nuevo usuario
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newEmail,    setNewEmail]    = useState('')
  const [newRole,     setNewRole]     = useState('operator')
  const [newTenantId, setNewTenantId] = useState('')
  const [createError, setCreateError] = useState('')

  async function load() {
    if (!usersAllowed) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const usersData = await fetchUsers()
      setUsers(usersData)
      if (isSuperAdmin) {
        const tenantData = await fetchTenants()
        setTenants(tenantData)
        setNewTenantId((current) => current || String(tenantData[0]?.id ?? ''))
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [usersAllowed, isSuperAdmin])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setCreateError('')
    setSaving(true)
    try {
      await createUser({
        username: newUsername,
        password: newPassword,
        email: newEmail || undefined,
        role: newRole,
        tenant_id: isSuperAdmin && newTenantId ? Number(newTenantId) : undefined,
      })
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
    // Sin este guard un doble click dispara dos updateUser.
    if (togglingUserId !== null) return
    setTogglingUserId(u.id)
    try {
      await updateUser(u.id, { is_active: !u.is_active })
      await load()
    } catch (e: any) {
      toast.error(e.message ?? 'No se pudo actualizar el usuario')
    } finally {
      setTogglingUserId(null)
    }
  }

  async function moveUserToTenant(u: ApiUser, tenantId: number) {
    if (u.tenant_id === tenantId) return
    setMovingUserId(u.id)
    try {
      await updateUser(u.id, { tenant_id: tenantId })
      await load()
    } catch (e: any) {
      toast.error(e.message ?? 'No se pudo mover el usuario')
    } finally {
      setMovingUserId(null)
    }
  }

  const filtered = users.filter(u => filter === 'all' || u.role === filter)

  if (!loading && !usersAllowed) {
    return <Navigate to="/tools" replace />
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader
        title="Usuarios"
        description={isSuperAdmin ? 'Todos los tenants' : me?.tenant_name}
        actions={
          <>
            <Button variant="ghost" onClick={load} title="Recargar" aria-label="Recargar">
              <RefreshCw size={16} />
            </Button>
            <Button icon={UserPlus} onClick={() => setShowCreate(v => !v)}>
              Nuevo usuario
            </Button>
          </>
        }
      />

      {/* Formulario de creación */}
      {showCreate && (
        <Card className="mb-6">
          <h2 className="text-sm font-semibold text-ink-2 mb-4">Crear usuario</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Usuario" htmlFor="new-username" required>
              <Input
                id="new-username"
                value={newUsername} onChange={e => setNewUsername(e.target.value)} required
                placeholder="nombre_usuario"
              />
            </Field>
            <Field label="Contraseña" htmlFor="new-password" required help="Mínimo 8 caracteres">
              <Input
                id="new-password"
                type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required
                placeholder="••••••••"
              />
            </Field>
            <Field label="Email" htmlFor="new-email">
              <Input
                id="new-email"
                type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                placeholder="correo@ejemplo.com"
              />
            </Field>
            <Field label="Rol" htmlFor="new-role">
              <Select id="new-role" value={newRole} onChange={e => setNewRole(e.target.value)}>
                <option value="operator">Operador</option>
                <option value="admin">Admin</option>
                {isSuperAdmin && <option value="superadmin">Super Admin</option>}
              </Select>
            </Field>
            {isSuperAdmin && (
              <Field label="Tenant" htmlFor="new-tenant">
                <Select
                  id="new-tenant"
                  value={newTenantId}
                  onChange={e => setNewTenantId(e.target.value)}
                  required
                >
                  {tenants.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}

            {createError && (
              <div className="col-span-2">
                <Alert tone="error">{createError}</Alert>
              </div>
            )}

            <div className="col-span-2 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancelar
              </Button>
              <Button type="submit" loading={saving}>
                {saving ? 'Creando…' : 'Crear usuario'}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Filtros */}
      <div className="flex gap-2 mb-4">
        {(['all', 'admin', 'operator'] as RoleFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'rounded-full px-3 py-1.5 text-xs font-medium',
              filter === f
                ? 'bg-accent text-accent-fg'
                : 'bg-surface-2 text-ink-3 hover:text-ink-1',
            )}
          >
            {f === 'all' ? 'Todos' : ROLE_LABELS[f]}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      {/* Tabla */}
      {loading ? (
        <Skeleton className="h-14" count={4} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={UsersIcon} title="No hay usuarios para mostrar" />
      ) : (
        <div className="space-y-2">
          {filtered.map(u => {
            const isMe = u.id === me?.id
            return (
              <div
                key={u.id}
                className={cn(
                  'flex items-center gap-4 rounded-card border border-line-1 bg-surface-1 px-4 py-3',
                  !u.is_active && 'opacity-50',
                )}
              >
                {/* Avatar */}
                <div className="w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center flex-shrink-0">
                  {u.role === 'superadmin' ? (
                    <ShieldCheck size={16} className="text-accent" />
                  ) : u.role === 'admin' ? (
                    <Shield size={16} className="text-blue-400" />
                  ) : (
                    <UserIcon size={16} className="text-ink-3" />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-ink-1">{u.username}</span>
                    {isMe && <Badge tone="accent">Tú</Badge>}
                    <Badge tone={ROLE_TONES[u.role] ?? 'neutral'}>
                      {ROLE_LABELS[u.role] ?? u.role}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    {u.email && <span className="text-xs text-ink-4">{u.email}</span>}
                    {isSuperAdmin && (
                      <span className="text-xs text-ink-4">{u.tenant_name}</span>
                    )}
                  </div>
                </div>

                {isSuperAdmin && !isMe && (
                  <div className="w-44 flex-shrink-0">
                    <Select
                      value={u.tenant_id}
                      disabled={movingUserId === u.id}
                      onChange={(e) => moveUserToTenant(u, Number(e.target.value))}
                      className="text-xs"
                      title="Mover usuario a otro tenant"
                    >
                      {tenants.map((tenant) => (
                        <option key={tenant.id} value={tenant.id}>
                          {tenant.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                )}

                {/* Toggle activo (no se puede desactivar a sí mismo) */}
                {!isMe && (
                  <Toggle
                    size="sm"
                    checked={u.is_active}
                    disabled={togglingUserId === u.id}
                    onChange={() => toggleActive(u)}
                    label={u.is_active ? `Desactivar ${u.username}` : `Activar ${u.username}`}
                  />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
