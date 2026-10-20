import { useEffect, useState } from 'react'
import { fetchVtexStatus } from '../api/client'

/**
 * `configured === null` significa "no lo pudimos determinar" y NO debe
 * bloquear la ejecución: el backend rechaza con un 400 claro si faltan
 * credenciales. Así un fallo de este endpoint nunca deja a un operador sin
 * poder ejecutar nada.
 */
export function useVtexStatus(): {
  configured: boolean | null
  accountName: string | null
  environment: string | null
  loading: boolean
} {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [accountName, setAccountName] = useState<string | null>(null)
  const [environment, setEnvironment] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchVtexStatus()
      .then((s) => {
        if (cancelled) return
        setConfigured(s.configured)
        setAccountName(s.account_name ?? null)
        setEnvironment(s.environment ?? null)
      })
      .catch(() => {
        if (!cancelled) setConfigured(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { configured, accountName, environment, loading }
}
