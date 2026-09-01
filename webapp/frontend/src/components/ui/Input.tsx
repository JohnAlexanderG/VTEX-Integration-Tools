import { forwardRef } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from './cn'

export const inputBaseClass =
  'w-full bg-surface-2 border border-line-2 rounded-control px-3 py-2 text-sm text-ink-1 ' +
  'placeholder-ink-4 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent ' +
  'disabled:opacity-60 disabled:cursor-not-allowed'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: LucideIcon
  rightSlot?: ReactNode
  invalid?: boolean
}

const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { leftIcon: Icon, rightSlot, invalid, className, ...rest },
  ref,
) {
  const field = (
    <input
      ref={ref}
      className={cn(
        inputBaseClass,
        Icon ? 'pl-9' : undefined,
        rightSlot ? 'pr-10' : undefined,
        invalid && 'border-red-500 focus:border-red-500 focus:ring-red-500',
        className,
      )}
      {...rest}
    />
  )

  if (!Icon && !rightSlot) return field

  return (
    <div className="relative">
      {Icon && (
        <Icon
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-4"
        />
      )}
      {field}
      {rightSlot && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-4">{rightSlot}</span>
      )}
    </div>
  )
})

export default Input
