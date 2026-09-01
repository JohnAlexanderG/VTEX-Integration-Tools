import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, CheckCircle, Info, X, XCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from './cn'

export type ToastTone = 'success' | 'error' | 'warning' | 'info'

export interface ToastOptions {
  tone?: ToastTone
  /** ms antes de auto-cerrar. 0 = queda hasta que el usuario lo cierre. */
  duration?: number
}

interface ToastItem {
  id: number
  message: string
  tone: ToastTone
}

interface ToastContextValue {
  toast: (message: string, options?: ToastOptions) => void
  success: (message: string) => void
  error: (message: string) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TONES: Record<ToastTone, { bar: string; icon: string; Icon: LucideIcon }> = {
  success: { bar: 'border-l-green-400', icon: 'text-green-400', Icon: CheckCircle },
  error: { bar: 'border-l-red-400', icon: 'text-red-400', Icon: XCircle },
  warning: { bar: 'border-l-yellow-400', icon: 'text-yellow-400', Icon: AlertTriangle },
  info: { bar: 'border-l-blue-400', icon: 'text-blue-400', Icon: Info },
}

const DEFAULT_DURATION = 4000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setItems((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (message: string, options?: ToastOptions) => {
      const id = nextId.current++
      const duration = options?.duration ?? DEFAULT_DURATION
      setItems((prev) => [...prev, { id, message, tone: options?.tone ?? 'info' }])
      if (duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), duration),
        )
      }
    },
    [dismiss],
  )

  // Limpia timers pendientes al desmontar.
  useEffect(() => {
    const pending = timers.current
    return () => {
      pending.forEach(clearTimeout)
      pending.clear()
    }
  }, [])

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      success: (message: string) => toast(message, { tone: 'success' }),
      error: (message: string) => toast(message, { tone: 'error' }),
      dismiss,
    }),
    [toast, dismiss],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col-reverse gap-2">
          {items.map((item) => {
            const { bar, icon, Icon } = TONES[item.tone]
            return (
              <div
                key={item.id}
                role="status"
                aria-live="polite"
                className={cn(
                  'pointer-events-auto flex w-80 items-start gap-2.5 rounded-card border border-line-2',
                  'border-l-2 bg-surface-1 px-4 py-3 shadow-xl animate-toast-in',
                  bar,
                )}
              >
                <Icon size={16} className={cn('mt-px flex-shrink-0', icon)} />
                <span className="min-w-0 flex-1 text-xs leading-relaxed text-ink-1">
                  {item.message}
                </span>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  aria-label="Cerrar notificación"
                  className="flex-shrink-0 text-ink-4 hover:text-ink-1"
                >
                  <X size={14} />
                </button>
              </div>
            )
          })}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast debe usarse dentro de <ToastProvider>')
  return ctx
}
