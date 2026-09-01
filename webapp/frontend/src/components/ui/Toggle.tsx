import { cn } from './cn'

interface Props {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  /** Se usa como aria-label cuando no hay un label visible asociado. */
  label?: string
  size?: 'sm' | 'md'
}

export default function Toggle({ checked, onChange, disabled, label, size = 'md' }: Props) {
  const track = size === 'sm' ? 'h-5 w-9' : 'h-7 w-12'
  const knob = size === 'sm' ? 'h-3.5 w-3.5' : 'h-5 w-5'
  const offset = size === 'sm' ? (checked ? 'translate-x-4' : 'translate-x-0') : checked ? 'translate-x-5' : 'translate-x-0'

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative flex-shrink-0 rounded-full',
        track,
        checked ? 'bg-accent' : 'bg-line-2',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <span
        className={cn(
          'absolute left-1 top-1 rounded-full bg-white transition-transform',
          knob,
          offset,
        )}
      />
    </button>
  )
}
