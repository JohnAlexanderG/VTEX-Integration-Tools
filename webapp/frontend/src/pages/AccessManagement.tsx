import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { KeyRound, Plus, RefreshCw, Search, Users as UsersIcon, X } from 'lucide-react'
import { createTenant, fetchAccessOverview, updateTenantAccess } from '../api/client'
import type { AccessCatalog, TenantAccess } from '../types'
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Skeleton,
  Toggle,
  cn,
} from '../components/ui'

function slugifyTenant(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export default function AccessManagement() {
  const [tenants, setTenants] = useState<TenantAccess[]>([])
  const [catalog, setCatalog] = useState<AccessCatalog>({ sections: [], tools: [] })
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [showCreateTenant, setShowCreateTenant] = useState(false)
  const [tenantName, setTenantName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [creatingTenant, setCreatingTenant] = useState(false)
  const [createTenantError, setCreateTenantError] = useState('')

  async function load(nextSelectedTenantId?: number) {
    setLoading(true)
    setError('')
    try {
      const data = await fetchAccessOverview()
      setTenants(data.tenants)
      setCatalog(data.catalog)
      setSelectedTenantId((current) => nextSelectedTenantId ?? current ?? data.tenants[0]?.id ?? null)
    } catch (e: any) {
      setError(e.message || 'No fue posible cargar los accesos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filteredTenants = useMemo(() => {
    return tenants.filter((tenant) => {
      const term = search.trim().toLowerCase()
      if (!term) return true
      return tenant.name.toLowerCase().includes(term) || tenant.slug.toLowerCase().includes(term)
    })
  }, [search, tenants])

  const selectedTenant = filteredTenants.find((tenant) => tenant.id === selectedTenantId)
    ?? tenants.find((tenant) => tenant.id === selectedTenantId)
    ?? null

  async function handlePermissionChange(permissionKey: string, enabled: boolean) {
    if (!selectedTenant) return
    setSavingKey(permissionKey)
    try {
      const permissions = await updateTenantAccess(selectedTenant.id, { [permissionKey]: enabled })
      setTenants((prev) => prev.map((tenant) => (
        tenant.id === selectedTenant.id ? { ...tenant, permissions } : tenant
      )))
    } catch (e: any) {
      setError(e.message || 'No se pudo actualizar el acceso')
    } finally {
      setSavingKey(null)
    }
  }

  function handleTenantNameChange(value: string) {
    setTenantName(value)
    if (!slugEdited) {
      setTenantSlug(slugifyTenant(value))
    }
  }

  function handleTenantSlugChange(value: string) {
    setSlugEdited(true)
    setTenantSlug(slugifyTenant(value))
  }

  async function handleCreateTenant(e: FormEvent) {
    e.preventDefault()
    setCreateTenantError('')
    setCreatingTenant(true)
    try {
      const created = await createTenant({
        name: tenantName.trim(),
        slug: slugifyTenant(tenantSlug),
      })
      setTenantName('')
      setTenantSlug('')
      setSlugEdited(false)
      setShowCreateTenant(false)
      setSearch('')
      await load(created.id)
    } catch (e: any) {
      setCreateTenantError(e.message || 'No se pudo crear el tenant')
    } finally {
      setCreatingTenant(false)
    }
  }

  return (
    <div className="p-4 md:p-6">
      <PageHeader
        title="Accesos por tenant"
        description="Desde aquí `Laburu Agencia` puede habilitar secciones y herramientas por cuenta."
        actions={
          <>
            <Button
              icon={showCreateTenant ? X : Plus}
              onClick={() => setShowCreateTenant((value) => !value)}
            >
              {showCreateTenant ? 'Cancelar' : 'Nuevo tenant'}
            </Button>
            <Button variant="secondary" icon={RefreshCw} onClick={() => load()}>
              Recargar
            </Button>
          </>
        }
      />

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      {showCreateTenant && (
        <Card as="section" className="mb-4">
          <form onSubmit={handleCreateTenant}>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,320px)_auto] md:items-end">
            <Field label="Nombre del tenant" htmlFor="tenant-name">
              <Input
                id="tenant-name"
                type="text"
                value={tenantName}
                onChange={(e) => handleTenantNameChange(e.target.value)}
                required
                placeholder="Nuevo Cliente"
              />
            </Field>
            <Field label="Slug" htmlFor="tenant-slug">
              <Input
                id="tenant-slug"
                type="text"
                value={tenantSlug}
                onChange={(e) => handleTenantSlugChange(e.target.value)}
                required
                placeholder="nuevo-cliente"
              />
            </Field>
            <Button type="submit" icon={Plus} loading={creatingTenant}>
              {creatingTenant ? 'Creando…' : 'Crear tenant'}
            </Button>
          </div>
          {createTenantError && (
            <Alert tone="error" className="mt-3">{createTenantError}</Alert>
          )}
          </form>
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card as="section">
          <div className="mb-4">
            <Input
              type="text"
              leftIcon={Search}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar tenant…"
              aria-label="Buscar tenant"
            />
          </div>

          <div className="space-y-2">
            {loading && <Skeleton className="h-16" count={4} />}
            {!loading && filteredTenants.map((tenant) => (
              <button
                key={tenant.id}
                type="button"
                onClick={() => setSelectedTenantId(tenant.id)}
                className={cn(
                  'w-full rounded-card border px-4 py-3 text-left transition-colors',
                  tenant.id === selectedTenantId
                    ? 'border-accent bg-accent-soft'
                    : 'border-line-1 bg-surface-0 hover:bg-surface-2/70',
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink-1">{tenant.name}</p>
                    <p className="text-xs text-ink-4">{tenant.slug}</p>
                  </div>
                  <Badge tone={tenant.is_active ? 'success' : 'neutral'}>
                    {tenant.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </div>
              </button>
            ))}
          </div>
        </Card>

        <Card as="section" className="min-w-0">
          {!selectedTenant ? (
            <EmptyState
              icon={KeyRound}
              title="Ningún tenant seleccionado"
              description="Selecciona un tenant para administrar sus accesos."
            />
          ) : (
            <div className="space-y-6">
              <div className="flex flex-col gap-2 border-b border-line-1 pb-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-ink-1">{selectedTenant.name}</h2>
                  <p className="text-sm text-ink-4">{selectedTenant.slug}</p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-control border border-line-1 bg-surface-0 px-3 py-2 text-xs text-ink-3">
                  <UsersIcon size={14} />
                  {selectedTenant.users.length} usuario{selectedTenant.users.length === 1 ? '' : 's'}
                </div>
              </div>

              <div>
                <div className="mb-3 flex items-center gap-2">
                  <KeyRound size={15} className="text-accent" />
                  <h3 className="text-sm font-semibold text-ink-1">Secciones</h3>
                </div>
                <div className="space-y-3">
                  {catalog.sections.map((section) => {
                    const enabled = selectedTenant.permissions.sections[section.id] ?? true
                    return (
                      <div key={section.id} className="flex items-center justify-between gap-4 rounded-card border border-line-1 bg-surface-0 px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-ink-1">{section.label}</p>
                          <p className="text-xs text-ink-4">{section.description}</p>
                        </div>
                        <Toggle
                          checked={enabled}
                          disabled={savingKey === section.permission_key}
                          onChange={(next) => handlePermissionChange(section.permission_key, next)}
                          label={`Acceso a ${section.label}`}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink-1">Herramientas</h3>
                <div className="grid gap-3 lg:grid-cols-2">
                  {catalog.tools.map((tool) => {
                    const enabled = selectedTenant.permissions.tools[tool.id] ?? true
                    return (
                      <div key={tool.id} className="flex items-center justify-between gap-4 rounded-card border border-line-1 bg-surface-0 px-4 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink-1">
                            {tool.shortName}
                          </p>
                          <p className="text-xs text-ink-4">Herramienta</p>
                        </div>
                        <Toggle
                          checked={enabled}
                          disabled={savingKey === tool.permission_key}
                          onChange={(next) => handlePermissionChange(tool.permission_key, next)}
                          label={`Acceso a ${tool.shortName}`}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink-1">Usuarios del tenant</h3>
                <div className="space-y-2">
                  {selectedTenant.users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between rounded-card border border-line-1 bg-surface-0 px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink-1">{user.username}</p>
                        <p className="text-xs text-ink-4">
                          {user.role} {user.email ? `• ${user.email}` : ''}
                        </p>
                      </div>
                      <Badge tone={user.is_active ? 'success' : 'neutral'}>
                        {user.is_active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
