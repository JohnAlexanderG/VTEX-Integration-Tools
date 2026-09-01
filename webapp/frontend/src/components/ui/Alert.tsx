import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle, Info, X, XCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from './cn'

export type AlertTone = 'error' | 'success' | 'warning' | 'info'

interface Props {
  tone: AlertTone
  title?: string
  children?: ReactNode
  icon?: boolean
  onDismiss?: () => void
  className?: string
}

const TONES: Record<AlertTone, { box: string; icon: string; Icon: LucideIcon }> = {
  error: {
    box: 'bg-red-900/20 border-red-800/50 text-red-300',
    icon: 'text-red-400',
    Icon: XCircle,
  },
  success: {
    box: 'bg-green-900/20 border-green-800/50 text-green-300',
    icon: 'text-green-400',
    Icon: CheckCircle,
  },
  warning: {
    box: 'bg-yellow-900/20 border-yellow-700/50 text-yellow-300',
    icon: 'text-yellow-400',
    Icon: AlertTriangle,
  },
  info: {
    box: 'bg-blue-900/20 border-blue-800/50 text-blue-300',
    icon: 'text-blue-400',
    Icon: Info,
  },
}

export default function Alert({ tone, title, children, icon = true, onDismiss, className }: Props) {
  const { box, icon: iconClass, Icon } = TONES[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-control border px-3 py-2.5 text-xs', box, className)}
    >
      {icon && <Icon size={15} className={cn('flex-shrink-0 mt-px', iconClass)} />}
      <div className="min-w-0 flex-1 leading-relaxed">
        {title && <p className="font-semibold mb-0.5">{title}</p>}
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Cerrar aviso"
          className="flex-shrink-0 opacity-60 hover:opacity-100"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
