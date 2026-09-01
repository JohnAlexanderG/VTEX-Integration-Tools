import { Check, Circle, RefreshCw, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
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

const ICONS: Record<JobStatus, LucideIcon> = {
  pending: Circle,
  running: RefreshCw,
  completed: Check,
  failed: X,
}

export default function StatusBadge({ status }: { status: JobStatus | null }) {
  if (!status) return null
  const Icon = ICONS[status]
  // Un estado desconocido cae en neutral en vez de renderizar class="undefined".
  return (
    <Badge tone={TONES[status] ?? 'neutral'} pulse={status === 'running'}>
      {Icon && <Icon size={11} className={status === 'running' ? 'animate-spin' : undefined} />}
      {LABELS[status] ?? status}
    </Badge>
  )
}
