import { useEffect, useMemo, useState } from 'react'
import { KeyRound, RefreshCw, Search, Users as UsersIcon } from 'lucide-react'
import { fetchAccessOverview, updateTenantAccess } from '../api/client'
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

export default function AccessManagement() {
  const [tenants, setTenants] = useState<TenantAccess[]>([])
  const [catalog, setCatalog] = useState<AccessCatalog>({ sections: [], tools: [] })
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [savingKey, setSavingKey] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await fetchAccessOverview()
      setTenants(data.tenants)
      setCatalog(data.catalog)
      setSelectedTenantId((current) => current ?? data.tenants[0]?.id ?? null)
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

  return (
    <div className="p-4 md:p-6">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-100">Accesos por tenant</h1>
          <p className="mt-1 text-sm text-gray-500">
            Desde aquí `Laburu Agencia` puede habilitar secciones y herramientas por cuenta.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-2 self-start rounded-lg border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-800"
        >
          <RefreshCw size={15} />
          Recargar
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
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
                            {tool.category === 'pipeline' && tool.step ? `#${tool.step} ` : ''}
                            {tool.shortName}
                          </p>
                          <p className="text-xs text-gray-500">{tool.category === 'pipeline' ? 'Pipeline' : 'Herramienta'}</p>
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
