import { useState, useRef, useCallback, useEffect } from 'react'
import type { LogEntry, SortProgress, SortStatus } from '../types'

const STREAM_TIMEOUT_MS = 10 * 60 * 1000

export interface SortParams {
  priorities: string[]
  limit: number
  removeFromLiked: boolean
  allowNewPlaylists: boolean
  dryRun: boolean
  confidenceThreshold: number
}

interface UseSortStreamReturn {
  status: SortStatus
  progress: SortProgress | null
  logs: LogEntry[]
  error: string | null
  startSort: (params: SortParams) => void
  reset: () => void
}

export function useSortStream(): UseSortStreamReturn {
  const [status, setStatus] = useState<SortStatus>('idle')
  const [progress, setProgress] = useState<SortProgress | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const resetStreamTimeout = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      esRef.current?.close()
      setError('Sort timed out — no response from server for 10 minutes.')
      setStatus('error')
    }, STREAM_TIMEOUT_MS)
  }, [])

  useEffect(() => () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
  }, [])

  const startSort = useCallback(async (params: SortParams) => {
    esRef.current?.close()
    setStatus('starting')
    setProgress(null)
    setLogs([])
    setError(null)

    try {
      const res = await fetch('/api/sort/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          priorities: params.priorities,
          limit: params.limit,
          remove_from_liked: params.removeFromLiked,
          allow_new_playlists: params.allowNewPlaylists,
          dry_run: params.dryRun,
          confidence_threshold: params.confidenceThreshold,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }

      const { job_id } = await res.json()

      setStatus('running')
      const es = new EventSource(`/api/sort/stream/${job_id}`)
      esRef.current = es
      resetStreamTimeout()

      es.addEventListener('progress', (e: MessageEvent) => {
        resetStreamTimeout()
        setProgress(JSON.parse(e.data) as SortProgress)
      })

      es.addEventListener('complete', (e: MessageEvent) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        const { logs: resultLogs } = JSON.parse(e.data)
        setLogs(resultLogs as LogEntry[])
        setStatus('complete')
        es.close()
      })

      es.addEventListener('error', (e: Event) => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        let errorMessage = 'An unexpected error occurred'
        try {
          const data = (e as MessageEvent).data
          if (data) {
            const parsed = JSON.parse(data)
            errorMessage = parsed.message || errorMessage
          }
        } catch {
          errorMessage = 'Connection error'
        }
        setError(errorMessage)
        setStatus('error')
        es.close()
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }, [resetStreamTimeout])

  const reset = useCallback(() => {
    esRef.current?.close()
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    setStatus('idle')
    setProgress(null)
    setLogs([])
    setError(null)
  }, [])

  return { status, progress, logs, error, startSort, reset }
}
