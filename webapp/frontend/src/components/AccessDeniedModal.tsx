interface Props {
  open: boolean
  title?: string
  message: string
  onClose?: () => void
}

export default function AccessDeniedModal({
  open,
  title = 'Acceso restringido',
  message,
  onClose,
}: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-md rounded-2xl border border-red-900 bg-gray-900 shadow-2xl">
        <div className="border-b border-gray-800 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm leading-6 text-gray-300">{message}</p>
        </div>
        <div className="flex justify-end border-t border-gray-800 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  )
}
