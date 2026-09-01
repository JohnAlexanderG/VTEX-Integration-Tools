import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from './cn'

interface Props {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
  size?: 'sm' | 'md'
  className?: string
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  size = 'md',
  className,
}: Props) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-card border border-dashed border-line-1 text-center',
        size === 'sm' ? 'px-4 py-8' : 'px-4 py-12',
        className,
      )}
    >
      {Icon && <Icon size={size === 'sm' ? 20 : 26} className="mb-3 text-ink-4" />}
      <p className={cn('font-medium text-ink-2', size === 'sm' ? 'text-sm' : 'text-base')}>{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-ink-4">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
