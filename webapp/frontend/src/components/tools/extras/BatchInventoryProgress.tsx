import type { ToolExtraProps } from './index'

/** Progreso de batch inventory (step_67). */
export default function BatchInventoryProgress({ progress, isRunning, jobId }: ToolExtraProps) {
  if (!jobId || (!progress && !isRunning)) return null

  const rawPercent = typeof progress?.percent === 'number' ? progress.percent : null
  const percent = rawPercent === null ? null : Math.max(0, Math.min(100, rawPercent))
  const phase = progress?.phase ?? (isRunning ? 'running' : '')
  const isDone = phase === 'done'
  const isFailed = phase === 'failed'
  const accent = isFailed ? 'bg-red-400' : isDone ? 'bg-green-400' : 'bg-blue-400'
  const border = isFailed
    ? 'border-red-800/50 bg-red-900/15'
    : isDone
    ? 'border-green-800/50 bg-green-900/15'
    : 'border-blue-800/50 bg-blue-900/15'
  const title = progress?.phase_label ?? (isRunning ? 'Procesando batch inventory' : 'Batch inventory')
  const elapsed =
    typeof progress?.elapsed_seconds === 'number' ? `${progress.elapsed_seconds.toFixed(1)}s` : null

  return (
    <div className={`rounded-control border px-3 py-3 space-y-3 ${border}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-ink-1 truncate">{title}</div>
          <div className="mt-0.5 text-[11px] text-ink-3">
            {progress?.part_number ? `Parte ${progress.part_number}` : 'Preparando partes'}
          </div>
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

      <div className="grid gap-2 text-[11px] text-ink-3 sm:grid-cols-2">
        {progress?.batch_id && (
          <div className="min-w-0">
            <span className="text-ink-4">Batch: </span>
            <span className="break-all text-ink-2">{progress.batch_id}</span>
          </div>
        )}
        {progress?.status_name && (
          <div>
            <span className="text-ink-4">Status VTEX: </span>
            <span className={isFailed ? 'text-red-300' : isDone ? 'text-green-300' : 'text-blue-300'}>
              {progress.status_name}
            </span>
          </div>
        )}
        {(progress?.completed_parts !== undefined || progress?.failed_parts !== undefined) && (
          <div>
            <span className="text-ink-4">Partes: </span>
            <span className="text-ink-2">
              {progress.completed_parts ?? 0} OK / {progress.failed_parts ?? 0} error
            </span>
          </div>
        )}
        {elapsed && (
          <div>
            <span className="text-ink-4">Polling: </span>
            <span className="text-ink-2">{elapsed}</span>
          </div>
        )}
      </div>
    </div>
  )
}
