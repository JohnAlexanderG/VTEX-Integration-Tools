import type { ToolExtraProps } from './index'

/** Progreso de la carga de catálogo Seller Portal (step_79). */
export default function SellerPortalProgress({ progress, isRunning, jobId }: ToolExtraProps) {
  if (!jobId || (!progress && !isRunning)) return null

  const rawPercent = typeof progress?.percent === 'number' ? progress.percent : null
  const percent = rawPercent === null ? null : Math.max(0, Math.min(100, rawPercent))
  const isDone = progress?.phase === 'done'
  const accent = isDone ? 'bg-green-400' : 'bg-blue-400'
  const border = isDone ? 'border-green-800/50 bg-green-900/15' : 'border-blue-800/50 bg-blue-900/15'
  const title = progress?.phase_label ?? 'Preparando carga'

  return (
    <div className={`rounded-control border px-3 py-3 space-y-3 ${border}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-ink-1 truncate">{title}</div>
          {progress?.message && <div className="mt-0.5 text-[11px] text-ink-3">{progress.message}</div>}
        </div>
        {percent !== null && (
          <span className="text-xs font-medium text-ink-2 tabular-nums">{Math.round(percent)}%</span>
        )}
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
        {percent === null ? (
          <div className={`h-full w-1/3 rounded-full ${accent} animate-pulse`} />
        ) : (
          <div
            className={`h-full rounded-full ${accent} transition-all duration-500`}
            style={{ width: `${percent}%` }}
          />
        )}
      </div>
    </div>
  )
}
