import type { ReactNode } from 'react'
import { cn } from './cn'

interface Props {
  as?: 'div' | 'section' | 'article'
  padded?: boolean
  interactive?: boolean
  className?: string
  children: ReactNode
}

export default function Card({
  as: Tag = 'div',
  padded = true,
  interactive = false,
  className,
  children,
}: Props) {
  return (
    <Tag
      className={cn(
        'bg-surface-1 border border-line-1 rounded-card',
        padded && 'p-4 md:p-5',
        interactive && 'hover:border-line-3 transition-colors',
        className,
      )}
    >
      {children}
    </Tag>
  )
}

export function CardHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start justify-between gap-3 mb-4', className)}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-ink-1">{title}</h3>
        {subtitle && <p className="text-xs text-ink-4 mt-0.5 leading-relaxed">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={className}>{children}</div>
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-center justify-end gap-2 mt-4 pt-4 border-t border-line-1', className)}>
      {children}
    </div>
  )
}
