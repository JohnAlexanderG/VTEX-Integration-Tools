import type { ReactNode } from 'react'
import { cn } from './cn'

export type BadgeTone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'accent'

interface Props {
  tone?: BadgeTone
  pulse?: boolean
  children: ReactNode
  className?: string
}

// Class strings literales completos (ver nota en Button.tsx).
const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-2 text-ink-3',
  success: 'bg-green-900/40 text-green-300',
  danger: 'bg-red-900/40 text-red-300',
  warning: 'bg-yellow-900/40 text-yellow-300',
  info: 'bg-blue-900/40 text-blue-300',
  accent: 'bg-accent-soft text-accent',
}

export default function Badge({ tone = 'neutral', pulse = false, children, className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
        TONES[tone],
        pulse && 'animate-pulse',
        className,
      )}
    >
      {children}
    </span>
  )
}
