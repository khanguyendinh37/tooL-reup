const API_BASE = '/api'

export interface SubtitleConfig {
  enabled: boolean
  font_family: string
  font_size: number
  font_color: string
  outline_color: string
  outline_width: number
  shadow_enabled: boolean
  shadow_color: string
  shadow_offset_x: number
  shadow_offset_y: number
  position: 'top' | 'center' | 'bottom'
  margin_v: number
  margin_l: number
  margin_r: number
  alignment: number
  custom_x: number | null
  custom_y: number | null
  use_custom_position: boolean
}

export async function startDubbing(params: {
  url: string
  source_lang: string
  target_lang: string
  voice: string
  whisper_model: string
  tts_speed: number
  subtitle_config?: SubtitleConfig
}) {
  const res = await fetch(`${API_BASE}/dubbing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error('Failed to start dubbing')
  return res.json()
}

export async function getDubbingStatus(id: string) {
  const res = await fetch(`${API_BASE}/dubbing/${id}/status`)
  if (!res.ok) throw new Error('Failed to get status')
  return res.json()
}

export async function downloadResult(id: string) {
  const res = await fetch(`${API_BASE}/dubbing/${id}/download`)
  if (!res.ok) throw new Error('Failed to download')
  return res.blob()
}

export async function cancelDubbing(id: string) {
  const res = await fetch(`${API_BASE}/dubbing/${id}/cancel`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to cancel')
  return res.json()
}

export async function getHistory() {
  const res = await fetch(`${API_BASE}/history`)
  if (!res.ok) throw new Error('Failed to get history')
  return res.json()
}

export async function deleteHistoryItem(id: string) {
  const res = await fetch(`${API_BASE}/history/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete')
  return res.json()
}

export async function getSettings() {
  const res = await fetch(`${API_BASE}/settings`)
  if (!res.ok) throw new Error('Failed to get settings')
  return res.json()
}

export async function updateSettings(settings: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error('Failed to update settings')
  return res.json()
}

export async function getAllCookiesStatus() {
  const res = await fetch(`${API_BASE}/cookies/status`)
  if (!res.ok) throw new Error('Failed to get cookies status')
  return res.json()
}

export async function uploadCookies(platform: string, cookies: string) {
  const res = await fetch(`${API_BASE}/cookies/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform, cookies }),
  })
  if (!res.ok) throw new Error('Failed to upload cookies')
  return res.json()
}

export async function uploadCookiesFile(platform: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/cookies/upload-file/${platform}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error('Failed to upload cookies file')
  return res.json()
}

export async function deleteCookies(platform: string) {
  const res = await fetch(`${API_BASE}/cookies/${platform}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete cookies')
  return res.json()
}