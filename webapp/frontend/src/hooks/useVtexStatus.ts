import { useEffect, useState } from 'react'
import { fetchVtexStatus } from '../api/client'

/**
 * `configured === null` significa "no lo pudimos determinar" y NO debe
 * bloquear la ejecución: el backend rechaza con un 400 claro si faltan
 * credenciales. Así un fallo de este endpoint nunca deja a un operador sin
 * poder ejecutar nada.
 */
export function useVtexStatus(): { configured: boolean | null; loading: boolean } {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchVtexStatus()
      .then((s) => {
        if (!cancelled) setConfigured(s.configured)
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

  return { configured, loading }
}
