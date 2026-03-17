import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types'

interface Props {
  logs: LogEntry[]
  className?: string
}

function colorizeText(text: string, stream?: string): string {
  return text // raw text; we apply color via stream below
}

export default function LogPanel({ logs, className = '' }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  if (logs.length === 0) {
    return (
      <div className={`log-panel bg-gray-950 rounded-lg p-4 font-mono text-xs text-gray-600 ${className}`}>
        Sin logs aún…
      </div>
    )
  }

  return (
    <div className={`log-panel bg-gray-950 rounded-lg p-4 font-mono text-xs overflow-y-auto ${className}`}>
      {logs.map((entry, i) => {
        if (entry.type !== 'log' || !entry.text) return null
        const color =
          entry.stream === 'stderr'
            ? 'text-red-400'
            : entry.stream === 'system'
            ? 'text-yellow-400'
            : 'text-green-300'
        return (
          <pre key={i} className={`whitespace-pre-wrap break-words ${color}`}>
            {colorizeText(entry.text, entry.stream)}
          </pre>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
