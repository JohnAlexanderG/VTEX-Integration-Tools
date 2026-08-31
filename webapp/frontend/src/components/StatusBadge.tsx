import type { JobStatus } from '../types'

export default function StatusBadge({ status }: { status: JobStatus | null }) {
  if (!status) return null
  const map: Record<string, string> = {
    pending: 'bg-gray-700 text-gray-300',
    running: 'bg-blue-900 text-blue-300 animate-pulse',
    completed: 'bg-green-900 text-green-300',
    failed: 'bg-red-900 text-red-300',
  }
  const labels: Record<string, string> = {
    pending: 'Pendiente',
    running: 'Ejecutando…',
    completed: 'Completado',
    failed: 'Error',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${map[status]}`}>
      {labels[status]}
    </span>
  )
}
