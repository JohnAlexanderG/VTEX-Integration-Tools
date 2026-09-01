import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from './Modal'
import Button from './Button'
import { cn } from './cn'

interface Props {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'accent'
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  tone = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Modal
      open={open}
      onClose={loading ? () => {} : onCancel}
      title={title}
      size="sm"
      closeOnBackdrop={!loading}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        <span
          className={cn(
            'flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full',
            tone === 'danger' ? 'bg-red-900/30 text-red-400' : 'bg-accent-soft text-accent',
          )}
        >
          <AlertTriangle size={17} />
        </span>
        <div className="min-w-0 pt-1.5">{message}</div>
      </div>
    </Modal>
  )
}
