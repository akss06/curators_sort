export interface LogEntry {
  track: string
  artist: string
  genre: string
  vibe: string
  confidence: number
  reasoning: string
  destination: string
  resolution: 'EXISTING' | 'NEW' | 'REVIEW' | 'ERROR'
  status: string
  image_url?: string | null
}

export interface TrackInfo {
  id: string
  name: string
  artist: string
  album: string
  uri: string
  image_url?: string | null
}

export interface TrackAnalysis {
  reasoning: string
  suggested_existing: string   // exact playlist display name, or "NONE"
  suggested_new: string
}

export interface ReviewLabData {
  session_id: string
  tracks: TrackInfo[]
  analyses: Record<string, TrackAnalysis>
  review_pid: string
}

export interface ResolveResponse {
  success: boolean
  dest_display_name: string
  created_new: boolean
  message: string
}

export interface BatchResolveResponse {
  moved: number
  failed: number
  dest_display_name: string
  created_new: boolean
}

export interface SortProgress {
  current: number
  total: number
  track: string
}

export type SortStatus = 'idle' | 'starting' | 'running' | 'complete' | 'error'
export type ReviewStatus = 'idle' | 'loading' | 'loaded' | 'error'

export interface PlaylistItem {
  id: string
  name: string
  track_count: number
  external_url: string
}

export interface RunStats {
  total: number
  sorted: number
  duplicates: number
  review: number
  new_playlists: number
}

export interface RunEntry {
  id: string
  timestamp: string
  priorities: string[]
  limit: number
  remove_from_liked: boolean
  allow_new_playlists: boolean
  dry_run: boolean
  confidence_threshold: number
  stats: RunStats
  logs: LogEntry[]
}

export interface LocalTrackInfo {
  id: string
  name: string
  artist: string
  album: string
  uri: string      // absolute file path
  format: string
  duration_ms?: number | null
}

export interface LocalReviewLabData {
  session_id: string
  tracks: LocalTrackInfo[]
  analyses: Record<string, TrackAnalysis>
  review_folder: string
  base_path: string
}

export interface BrowseEntry {
  name: string
  path: string
  audio_count: number
}

export interface BrowseResponse {
  current: string
  parent: string | null
  dirs: BrowseEntry[]
  audio_count: number
}
