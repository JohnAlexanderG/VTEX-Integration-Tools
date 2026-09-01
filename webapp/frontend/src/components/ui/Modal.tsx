import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from './cn'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  size?: 'sm' | 'md' | 'lg'
  footer?: ReactNode
  closeOnBackdrop?: boolean
  children: ReactNode
}

const SIZES = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

/**
 * Nota de alcance: hay Escape, click en el backdrop, foco inicial y foco
 * restaurado al cerrar, pero no un focus trap completo (Tab puede salir del
 * diálogo). Son confirmaciones de una sola acción; un trap real requiere
 * recorrer nodos tabbables y no vale la complejidad todavía.
 */
export default function Modal({
  open,
  onClose,
  title,
  size = 'md',
  footer,
  closeOnBackdrop = true,
  children,
}: Props) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<Element | null>(null)

  useEffect(() => {
    if (!open) return

    previouslyFocused.current = document.activeElement
    panelRef.current?.focus()

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      if (previouslyFocused.current instanceof HTMLElement) previouslyFocused.current.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 px-4"
      onClick={closeOnBackdrop ? onClose : undefined}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          'w-full rounded-card border border-line-2 bg-surface-1 shadow-2xl outline-none',
          SIZES[size],
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line-1 px-5 py-4">
          <h2 id={titleId} className="text-base font-semibold text-ink-1">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="-mr-1 rounded-control p-1 text-ink-4 hover:bg-surface-2 hover:text-ink-1"
          >
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-4 text-sm leading-6 text-ink-2">{children}</div>

        {footer && (
          <div className="flex justify-end gap-2 border-t border-line-1 px-5 py-4">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  )
}
