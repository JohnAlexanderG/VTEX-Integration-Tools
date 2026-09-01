import type { ButtonHTMLAttributes } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Loader2 } from 'lucide-react'
import { cn } from './cn'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
export type ButtonSize = 'sm' | 'md'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
  loading?: boolean
  fullWidth?: boolean
}

// Class strings literales completos: el purge de Tailwind es un regex sobre el
// código fuente y nunca emitiría algo como `bg-${variant}-600`.
const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover border border-transparent',
  secondary: 'bg-surface-2 text-ink-1 border border-line-2 hover:bg-surface-3',
  danger: 'bg-red-600 text-white border border-transparent hover:bg-red-500',
  ghost: 'bg-transparent text-ink-3 border border-transparent hover:text-ink-1 hover:bg-surface-2',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  icon: Icon,
  loading = false,
  fullWidth = false,
  className,
  disabled,
  children,
  type = 'button',
  ...rest
}: Props) {
  const iconSize = size === 'sm' ? 13 : 15
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-control font-medium',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        fullWidth && 'w-full',
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 size={iconSize} className="animate-spin" />
      ) : (
        Icon && <Icon size={iconSize} />
      )}
      {children}
    </button>
  )
}
