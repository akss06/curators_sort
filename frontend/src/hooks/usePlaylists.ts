import { useEffect, useState } from 'react'
import type { PlaylistItem } from '../types'

export function usePlaylists() {
  const [playlists, setPlaylists] = useState<PlaylistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/playlists')
      .then(async r => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({ detail: r.statusText }))
          throw new Error(body.detail || r.statusText)
        }
        return r.json()
      })
      .then(d => {
        setPlaylists(d.playlists || [])
        setError(null)
      })
      .catch(err => {
        setError(err.message || 'Failed to load playlists')
        setPlaylists([])
      })
      .finally(() => setLoading(false))
  }, [])

  return { playlists, loading, error }
}