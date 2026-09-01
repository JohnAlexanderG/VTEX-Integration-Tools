import type { JobStatus } from '../types'
import { Badge } from './ui'
import type { BadgeTone } from './ui'

const TONES: Record<JobStatus, BadgeTone> = {
  pending: 'neutral',
  running: 'info',
  completed: 'success',
  failed: 'danger',
}

const LABELS: Record<JobStatus, string> = {
  pending: 'Pendiente',
  running: 'Ejecutando…',
  completed: 'Completado',
  failed: 'Error',
}

export default function StatusBadge({ status }: { status: JobStatus | null }) {
  if (!status) return null
  // Un estado desconocido cae en neutral en vez de renderizar class="undefined".
  return (
    <Badge tone={TONES[status] ?? 'neutral'} pulse={status === 'running'}>
      {LABELS[status] ?? status}
    </Badge>
  )
}
