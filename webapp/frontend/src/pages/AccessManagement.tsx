import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { KeyRound, Plus, RefreshCw, Search, Users as UsersIcon, X } from 'lucide-react'
import { createTenant, fetchAccessOverview, updateTenantAccess } from '../api/client'
import type { AccessCatalog, TenantAccess } from '../types'

function Toggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean
  disabled?: boolean
  onChange: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onChange}
      className={`relative h-7 w-12 rounded-full transition-colors ${
        checked ? 'bg-green-600' : 'bg-gray-700'
      } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      <span
        className={`absolute left-1 top-1 h-5 w-5 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

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
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Accesos por tenant</h1>
          <p className="mt-1 text-sm text-gray-500">
            Desde aquí `Laburu Agencia` puede habilitar secciones y herramientas por cuenta.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 self-start">
          <button
            type="button"
            onClick={() => setShowCreateTenant((value) => !value)}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
          >
            {showCreateTenant ? <X size={15} /> : <Plus size={15} />}
            {showCreateTenant ? 'Cancelar' : 'Nuevo tenant'}
          </button>
          <button
            type="button"
            onClick={() => load()}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-800"
          >
            <RefreshCw size={15} />
            Recargar
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {showCreateTenant && (
        <form
          onSubmit={handleCreateTenant}
          className="mb-4 rounded-2xl border border-gray-800 bg-gray-900 p-4"
        >
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,320px)_auto] md:items-end">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">Nombre del tenant</label>
              <input
                type="text"
                value={tenantName}
                onChange={(e) => handleTenantNameChange(e.target.value)}
                required
                placeholder="Nuevo Cliente"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">Slug</label>
              <input
                type="text"
                value={tenantSlug}
                onChange={(e) => handleTenantSlugChange(e.target.value)}
                required
                placeholder="nuevo-cliente"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={creatingTenant}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus size={15} />
              {creatingTenant ? 'Creando...' : 'Crear tenant'}
            </button>
          </div>
          {createTenantError && (
            <div className="mt-3 rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">
              {createTenantError}
            </div>
          )}
        </form>
      )}

      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <section className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
          <div className="relative mb-4">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar tenant..."
              className="w-full rounded-lg border border-gray-700 bg-gray-800 py-2 pl-9 pr-3 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="space-y-2">
            {loading && [...Array(4)].map((_, index) => (
              <div key={index} className="h-16 animate-pulse rounded-xl bg-gray-800" />
            ))}
            {!loading && filteredTenants.map((tenant) => (
              <button
                key={tenant.id}
                type="button"
                onClick={() => setSelectedTenantId(tenant.id)}
                className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                  tenant.id === selectedTenantId
                    ? 'border-indigo-500 bg-indigo-950/40'
                    : 'border-gray-800 bg-gray-950 hover:bg-gray-800/70'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-gray-100">{tenant.name}</p>
                    <p className="text-xs text-gray-500">{tenant.slug}</p>
                  </div>
                  <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                    tenant.is_active ? 'bg-green-900/50 text-green-300' : 'bg-gray-800 text-gray-400'
                  }`}>
                    {tenant.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="min-w-0 rounded-2xl border border-gray-800 bg-gray-900 p-4 md:p-5">
          {!selectedTenant ? (
            <div className="rounded-xl border border-dashed border-gray-800 px-4 py-10 text-center text-sm text-gray-500">
              Selecciona un tenant para administrar sus accesos.
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex flex-col gap-2 border-b border-gray-800 pb-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-100">{selectedTenant.name}</h2>
                  <p className="text-sm text-gray-500">{selectedTenant.slug}</p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-gray-400">
                  <UsersIcon size={14} />
                  {selectedTenant.users.length} usuario{selectedTenant.users.length === 1 ? '' : 's'}
                </div>
              </div>

              <div>
                <div className="mb-3 flex items-center gap-2">
                  <KeyRound size={15} className="text-indigo-300" />
                  <h3 className="text-sm font-semibold text-gray-100">Secciones</h3>
                </div>
                <div className="space-y-3">
                  {catalog.sections.map((section) => {
                    const enabled = selectedTenant.permissions.sections[section.id] ?? true
                    return (
                      <div key={section.id} className="flex items-center justify-between gap-4 rounded-xl border border-gray-800 bg-gray-950 px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-gray-100">{section.label}</p>
                          <p className="text-xs text-gray-500">{section.description}</p>
                        </div>
                        <Toggle
                          checked={enabled}
                          disabled={savingKey === section.permission_key}
                          onChange={() => handlePermissionChange(section.permission_key, !enabled)}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-100">Herramientas</h3>
                <div className="grid gap-3 lg:grid-cols-2">
                  {catalog.tools.map((tool) => {
                    const enabled = selectedTenant.permissions.tools[tool.id] ?? true
                    return (
                      <div key={tool.id} className="flex items-center justify-between gap-4 rounded-xl border border-gray-800 bg-gray-950 px-4 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-100">
                            {tool.shortName}
                          </p>
                          <p className="text-xs text-gray-500">Herramienta</p>
                        </div>
                        <Toggle
                          checked={enabled}
                          disabled={savingKey === tool.permission_key}
                          onChange={() => handlePermissionChange(tool.permission_key, !enabled)}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-100">Usuarios del tenant</h3>
                <div className="space-y-2">
                  {selectedTenant.users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between rounded-xl border border-gray-800 bg-gray-950 px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-gray-100">{user.username}</p>
                        <p className="text-xs text-gray-500">
                          {user.role} {user.email ? `• ${user.email}` : ''}
                        </p>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${
                        user.is_active ? 'bg-green-900/50 text-green-300' : 'bg-gray-800 text-gray-400'
                      }`}>
                        {user.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
