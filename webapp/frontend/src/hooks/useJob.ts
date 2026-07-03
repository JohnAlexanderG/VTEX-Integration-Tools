import { useEffect, useRef, useState } from 'react'
import type { LogEntry, JobProgress, JobStatus } from '../types'
import { buildWsUrl } from '../api/client'

interface UseJobResult {
  logs: LogEntry[]
  status: JobStatus | null
  progress: JobProgress | null
  outputFiles: string[]
  exitCode: number | null
  isConnected: boolean
}

export function useJob(jobId: string | null): UseJobResult {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [outputFiles, setOutputFiles] = useState<string[]>([])
  const [exitCode, setExitCode] = useState<number | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Reset state for new job
    setLogs([])
    setStatus('pending')
    setProgress(null)
    setOutputFiles([])
    setExitCode(null)
    setIsConnected(false)

    if (!jobId) {
      setStatus(null)
      return
    }

    const url = buildWsUrl(jobId)

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setIsConnected(true)
    ws.onclose = () => setIsConnected(false)

    ws.onmessage = (event) => {
      try {
        const msg: LogEntry = JSON.parse(event.data)
        if (msg.type === 'ping') return

        if (msg.type === 'log') {
          setLogs((prev) => [...prev, msg])
        } else if (msg.type === 'status') {
          if (msg.status) setStatus(msg.status)
          if (msg.exit_code !== undefined) setExitCode(msg.exit_code ?? null)
        } else if (msg.type === 'outputs') {
          setOutputFiles(msg.files ?? [])
        } else if (msg.type === 'progress') {
          setProgress(msg.progress ?? null)
        }
      } catch {
        // ignore malformed messages
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [jobId])

  return { logs, status, progress, outputFiles, exitCode, isConnected }
}
