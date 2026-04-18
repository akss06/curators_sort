import { useState, useCallback } from 'react'
import type { ReviewLabData, ReviewStatus, ResolveResponse } from '../types'

interface UseReviewLabReturn {
  status: ReviewStatus
  data: ReviewLabData | null
  error: string | null
  load: () => Promise<void>
  resolve: (trackUri: string, targetPlaylistName: string) => Promise<ResolveResponse>
  keepInReview: (trackUri: string) => void
}

export function useReviewLab(): UseReviewLabReturn {
  const [status, setStatus] = useState<ReviewStatus>('idle')
  const [data, setData] = useState<ReviewLabData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setStatus('loading')
    setError(null)
    try {
      const res = await fetch('/api/review-lab')
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }
      const json: ReviewLabData = await res.json()
      setData(json)
      setStatus('loaded')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }, [])

  const resolve = useCallback(async (
    trackUri: string,
    targetPlaylistName: string,
  ): Promise<ResolveResponse> => {
    if (!data) throw new Error('No session loaded')

    const res = await fetch('/api/review-lab/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_uri: trackUri,
        target_playlist_name: targetPlaylistName,
        session_id: data.session_id,
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }

    const result: ResolveResponse = await res.json()

    // Optimistically remove the track from local state
    setData(prev =>
      prev ? { ...prev, tracks: prev.tracks.filter(t => t.uri !== trackUri) } : null
    )

    return result
  }, [data])

  const keepInReview = useCallback((trackUri: string) => {
    setData(prev =>
      prev ? { ...prev, tracks: prev.tracks.filter(t => t.uri !== trackUri) } : null
    )
  }, [])

  return { status, data, error, load, resolve, keepInReview }
}
