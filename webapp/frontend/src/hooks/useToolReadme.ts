import { useEffect, useState } from 'react'
import { fetchToolReadme } from '../api/client'

/**
 * `markdown === null` (sin error) = la herramienta no tiene README: es un
 * estado vacío legítimo, no un fallo. El backend responde 200 con readme=null
 * justamente para que se distinga de un 404 por permisos.
 */
export function useToolReadme(toolId: string | undefined): {
  markdown: string | null
  loading: boolean
  error: string | null
} {
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(toolId))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!toolId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchToolReadme(toolId)
      .then((md) => {
        if (!cancelled) setMarkdown(md)
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setMarkdown(null)
          setError(e instanceof Error ? e.message : 'No se pudo cargar la documentación')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [toolId])

  return { markdown, loading, error }
}
