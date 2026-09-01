import { useEffect, useState } from 'react'
import type { Job } from '../types'
import { fetchJobs } from '../api/client'

/**
 * Último job por herramienta, para reenganchar una corrida que sigue viva en
 * el servidor (o recuperar los archivos de una que terminó mientras el
 * usuario no miraba). `fetchJobs` ya viene ordenado por fecha descendente, así
 * que el primero que vemos por tool_id es el más reciente.
 *
 * Con `toolId` el filtro va al backend: el LIMIT de /api/jobs es global, así
 * que sin filtrar una herramienta poco usada no encuentra su última corrida.
 */
export function useActiveJobs(toolId?: string): {
  jobsByTool: Record<string, Job>
  loading: boolean
} {
  const [jobsByTool, setJobsByTool] = useState<Record<string, Job>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchJobs(toolId)
      .then((jobs) => {
        if (cancelled) return
        const byTool: Record<string, Job> = {}
        for (const job of jobs) {
          if (!byTool[job.tool_id]) byTool[job.tool_id] = job
        }
        setJobsByTool(byTool)
      })
      .catch(() => {
        if (!cancelled) setJobsByTool({})
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [toolId])

  return { jobsByTool, loading }
}
