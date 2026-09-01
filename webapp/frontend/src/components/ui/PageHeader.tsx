import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

interface Props {
  title: string
  description?: ReactNode
  actions?: ReactNode
  /** Ruta para el enlace de vuelta que se muestra encima del título. */
  backTo?: string
  backLabel?: string
  badge?: ReactNode
}

export default function PageHeader({
  title,
  description,
  actions,
  backTo,
  backLabel = 'Volver',
  badge,
}: Props) {
  return (
    <div className="mb-6">
      {backTo && (
        <Link
          to={backTo}
          className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-ink-3 hover:text-ink-1"
        >
          <ChevronLeft size={13} />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-ink-1">{title}</h1>
            {badge}
          </div>
          {description && <p className="mt-1 text-sm text-ink-4">{description}</p>}
        </div>
        {actions && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}
