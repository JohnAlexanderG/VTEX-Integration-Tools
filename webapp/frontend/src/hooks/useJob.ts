import { useEffect, useRef, useState } from 'react'
import type { LogEntry, JobProgress, JobStatus } from '../types'
import { buildWsUrl, fetchJob } from '../api/client'

/**
 * - 'connecting':   todavía no se ha logrado la primera conexión (arranque del job).
 * - 'connected':    WebSocket abierto, recibiendo logs en tiempo real.
 * - 'reconnecting': se perdió una conexión ya establecida, reintentando con backoff.
 * - 'stale':        sin WebSocket, pero un poll REST confirmó que el job sigue vivo.
 */
export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'stale'

interface UseJobResult {
  logs: LogEntry[]
  status: JobStatus | null
  progress: JobProgress | null
  outputFiles: string[]
  exitCode: number | null
  isConnected: boolean
  connectionState: ConnectionState
}

const BASE_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 20000
const POLL_INTERVAL_MS = 8000

function isTerminal(status: JobStatus | null): boolean {
  return status === 'completed' || status === 'failed'
}

export function useJob(jobId: string | null): UseJobResult {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [outputFiles, setOutputFiles] = useState<string[]>([])
  const [exitCode, setExitCode] = useState<number | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')

  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Reset state for new job
    setLogs([])
    setStatus('pending')
    setProgress(null)
    setOutputFiles([])
    setExitCode(null)
    setIsConnected(false)
    setConnectionState('connecting')

    if (!jobId) {
      setStatus(null)
      return
    }

    let stopped = false
    let hasConnectedOnce = false
    let statusNow: JobStatus | null = 'pending'
    let reconnectAttempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    const clearPollTimer = () => {
      if (pollTimer !== null) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const startPolling = () => {
      if (pollTimer !== null) return
      pollTimer = setInterval(() => {
        fetchJob(jobId)
          .then((job) => {
            statusNow = job.status
            setStatus(job.status)
            setExitCode(job.exit_code)
            setOutputFiles(job.output_files ?? [])
            if (isTerminal(job.status)) {
              clearPollTimer()
              clearReconnectTimer()
            } else if (hasConnectedOnce) {
              // El WS sigue caído, pero el servidor confirma que el job sigue vivo.
              setConnectionState('stale')
            }
          })
          .catch(() => {
            // El job pudo haber sido borrado o hubo un error transitorio de red;
            // seguimos confiando en los reintentos del WebSocket.
          })
      }, POLL_INTERVAL_MS)
    }

    const connect = () => {
      if (stopped) return

      const ws = new WebSocket(buildWsUrl(jobId))
      wsRef.current = ws

      ws.onopen = () => {
        hasConnectedOnce = true
        reconnectAttempts = 0
        clearPollTimer()
        setIsConnected(true)
        setConnectionState('connected')
        // El servidor reenvía el buffer completo de logs desde el inicio en
        // cada conexión nueva (main.py: replay en /ws/{job_id}), así que
        // limpiamos para no duplicar entradas ya mostradas.
        setLogs([])
        setProgress(null)
        setOutputFiles([])
        setExitCode(null)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null

        if (stopped || isTerminal(statusNow)) {
          return
        }

        setConnectionState(hasConnectedOnce ? 'reconnecting' : 'connecting')
        startPolling()

        const delay = Math.min(MAX_RECONNECT_DELAY_MS, BASE_RECONNECT_DELAY_MS * 2 ** reconnectAttempts)
        reconnectAttempts += 1
        clearReconnectTimer()
        reconnectTimer = setTimeout(connect, delay)
      }

      ws.onmessage = (event) => {
        try {
          const msg: LogEntry = JSON.parse(event.data)
          if (msg.type === 'ping') return

          if (msg.type === 'log') {
            setLogs((prev) => [...prev, msg])
          } else if (msg.type === 'status') {
            if (msg.status) {
              statusNow = msg.status
              setStatus(msg.status)
              if (isTerminal(msg.status)) {
                clearPollTimer()
                clearReconnectTimer()
              }
            }
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
    }

    connect()

    return () => {
      stopped = true
      clearReconnectTimer()
      clearPollTimer()
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [jobId])

  return { logs, status, progress, outputFiles, exitCode, isConnected, connectionState }
}
