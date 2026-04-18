import { useState, useCallback } from 'react'
import type { LocalReviewLabData, ReviewStatus, ResolveResponse, BatchResolveResponse } from '../types'

interface UseLocalReviewLabReturn {
  status: ReviewStatus
  data: LocalReviewLabData | null
  error: string | null
  load: (folderPath: string) => Promise<void>
  resolve: (trackUri: string, targetFolderName: string) => Promise<ResolveResponse>
  resolveBatch: (trackUris: string[], targetFolderName: string) => Promise<BatchResolveResponse>
  keepInReview: (trackUri: string) => void
}

export function useLocalReviewLab(): UseLocalReviewLabReturn {
  const [status, setStatus] = useState<ReviewStatus>('idle')
  const [data, setData] = useState<LocalReviewLabData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (folderPath: string) => {
    setStatus('loading')
    setError(null)
    try {
      const res = await fetch(`/api/local-review-lab?folder_path=${encodeURIComponent(folderPath)}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }
      const json: LocalReviewLabData = await res.json()
      setData(json)
      setStatus('loaded')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }, [])

  const resolve = useCallback(async (
    trackUri: string,
    targetFolderName: string,
  ): Promise<ResolveResponse> => {
    if (!data) throw new Error('No session loaded')

    const res = await fetch('/api/local-review-lab/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_uri: trackUri,
        target_folder_name: targetFolderName,
        session_id: data.session_id,
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }

    const result: ResolveResponse = await res.json()

    setData(prev =>
      prev ? { ...prev, tracks: prev.tracks.filter(t => t.uri !== trackUri) } : null
    )

    return result
  }, [data])

  const resolveBatch = useCallback(async (
    trackUris: string[],
    targetFolderName: string,
  ): Promise<BatchResolveResponse> => {
    if (!data) throw new Error('No session loaded')

    const res = await fetch('/api/local-review-lab/resolve-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_uris: trackUris,
        target_folder_name: targetFolderName,
        session_id: data.session_id,
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }

    const result: BatchResolveResponse = await res.json()

    // Remove all successfully dispatched URIs from local state
    const uriSet = new Set(trackUris)
    setData(prev =>
      prev ? { ...prev, tracks: prev.tracks.filter(t => !uriSet.has(t.uri)) } : null
    )

    return result
  }, [data])

  const keepInReview = useCallback((trackUri: string) => {
    setData(prev =>
      prev ? { ...prev, tracks: prev.tracks.filter(t => t.uri !== trackUri) } : null
    )
  }, [])

  return { status, data, error, load, resolve, resolveBatch, keepInReview }
}
