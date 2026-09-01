import { forwardRef } from 'react'
import type { SelectHTMLAttributes } from 'react'
import { cn } from './cn'
import { inputBaseClass } from './Input'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  options?: Array<{ value: string; label: string }>
  invalid?: boolean
}

const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { options, invalid, className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        inputBaseClass,
        invalid && 'border-red-500 focus:border-red-500 focus:ring-red-500',
        className,
      )}
      {...rest}
    >
      {options
        ? options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))
        : children}
    </select>
  )
})

export default Select
