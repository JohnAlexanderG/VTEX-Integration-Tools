import { cn } from './cn'

interface Props {
  className?: string
  count?: number
}

export default function Skeleton({ className = 'h-14', count = 1 }: Props) {
  const block = (key?: number) => (
    <div key={key} className={cn('animate-pulse rounded-control bg-surface-2', className)} />
  )
  if (count === 1) return block()
  return <div className="space-y-2">{Array.from({ length: count }, (_, i) => block(i))}</div>
}
