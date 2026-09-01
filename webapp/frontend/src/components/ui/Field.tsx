import type { ReactNode } from 'react'
import { cn } from './cn'

export function Label({
  htmlFor,
  required,
  children,
  className,
}: {
  htmlFor?: string
  required?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <label htmlFor={htmlFor} className={cn('block text-xs font-medium text-ink-3 mb-1.5', className)}>
      {children}
      {required && <span className="text-accent ml-1">*</span>}
    </label>
  )
}

interface Props {
  label?: string
  htmlFor?: string
  required?: boolean
  help?: string
  error?: string
  children: ReactNode
  className?: string
}

export default function Field({ label, htmlFor, required, help, error, children, className }: Props) {
  return (
    <div className={className}>
      {label && (
        <Label htmlFor={htmlFor} required={required}>
          {label}
        </Label>
      )}
      {children}
      {help && !error && <p className="mt-1 text-xs text-ink-4">{help}</p>}
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
    </div>
  )
}
