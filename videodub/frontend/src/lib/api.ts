const API_BASE = '/api'

import type { TranslationModelOption, TranslationProviderId } from '@/lib/translation'
import type { BlurRegion } from '@/lib/workflow'

export interface DubbingResponse {
  id: string
  url: string
  title?: string | null
  source_lang: string
  target_lang: string
  voice: string
  whisper_model: string
  status: string
  progress: number
  error?: string | null
  result_path?: string | null
  thumbnail_path?: string | null
  subtitle_config?: string | null
  processing_config?: string | null
  duration?: string | null
  file_size?: string | null
  created_at: string
  updated_at: string
}

export interface TranslationSettingsUpdate {
  translation_provider?: TranslationProviderId
  translation_model?: string
  translation_endpoint?: string
  translation_api_key?: string
  translation_clear_api_key?: boolean
  translation_key_verified?: boolean
  translation_models?: TranslationModelOption[]
}

export interface TranslationTestResponse {
  ok: boolean
  provider: TranslationProviderId
  model: string
  models: TranslationModelOption[]
  model_source?: 'discovered' | 'curated' | ''
  message: string
  used_fallback: boolean
}

type DesktopDownloadResult = {
  status: 'ok' | 'cancelled' | 'error'
  path?: string
  message?: string
}

type DesktopApi = {
  save_file: (url: string, filename: string) => Promise<DesktopDownloadResult>
}

const DEFAULT_API_TIMEOUT_MS = 30_000
const STATUS_API_TIMEOUT_MS = 10_000

async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_API_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Yêu cầu tới VideoDub quá thời gian. Kiểm tra backend rồi thử lại.')
    }
    throw new Error('Không thể kết nối tới backend VideoDub. Kiểm tra server rồi thử lại.')
  } finally {
    window.clearTimeout(timeoutId)
  }
}

async function throwApiError(response: Response, fallback: string): Promise<never> {
  const data = await response.json().catch(() => null) as { detail?: string; message?: string } | null
  throw new Error(data?.detail || data?.message || fallback)
}

declare global {
  interface Window {
    pywebview?: {
      api?: DesktopApi
    }
  }
}

/** Use the native Save As dialog in the desktop shell and a browser fallback in dev. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const absoluteUrl = new URL(path, window.location.href).href
  const desktopApi = window.pywebview?.api

  if (desktopApi) {
    const result = await desktopApi.save_file(absoluteUrl, filename)
    if (result.status === 'cancelled') return
    if (result.status !== 'ok') {
      throw new Error(result.message || 'Không thể lưu file')
    }
    return
  }

  const link = document.createElement('a')
  link.href = path
  link.download = filename
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

export async function startPreview(params: {
  url: string
  source_lang?: string
  target_lang?: string
  voice?: string
  whisper_model?: string
}): Promise<DubbingResponse> {
  const res = await apiFetch(`${API_BASE}/dubbing/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) await throwApiError(res, 'Không thể bắt đầu tải video xem trước')
  return res.json() as Promise<DubbingResponse>
}

export async function startDubbing(params: {
  url: string
  source_lang: string
  target_lang: string
  voice: string
  whisper_model: string
  tts_speed: number
  job_id?: string
  subtitle_enabled?: boolean
  subtitle_position?: string
  subtitle_position_y?: number
  subtitle_size?: number
  subtitle_color?: string
  blur_existing_subtitles?: boolean
  blur_region?: BlurRegion
  dubbing_volume?: number
  background_volume?: number
  original_vocals_volume?: number
}): Promise<DubbingResponse> {
  const res = await apiFetch(`${API_BASE}/dubbing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: params.url,
      source_lang: params.source_lang,
      target_lang: params.target_lang,
      voice: params.voice,
      whisper_model: params.whisper_model,
      tts_speed: params.tts_speed,
      job_id: params.job_id,
      subtitle_config: params.subtitle_enabled ? {
        enabled: true,
        position: params.subtitle_position || 'bottom',
        position_y: params.subtitle_position_y,
        size: params.subtitle_size || 'small',
        color: params.subtitle_color || 'white',
        blur_existing_subtitles: params.blur_existing_subtitles ?? false,
        blur_region: params.blur_region,
      } : undefined,
      dubbing_volume: params.dubbing_volume,
      background_volume: params.background_volume,
      original_vocals_volume: params.original_vocals_volume,
    }),
  })
  if (!res.ok) await throwApiError(res, 'Không thể bắt đầu quy trình lồng tiếng')
  return res.json() as Promise<DubbingResponse>
}

export async function retryDubbing(id: string): Promise<DubbingResponse> {
  const res = await apiFetch(`${API_BASE}/dubbing/${id}/retry`, { method: 'POST' })
  if (!res.ok) {
    await throwApiError(res, 'Không thể chạy lại quy trình')
  }
  return res.json() as Promise<DubbingResponse>
}

export async function getDubbingStatus(id: string): Promise<DubbingResponse> {
  const res = await apiFetch(`${API_BASE}/dubbing/${id}/status`, {}, STATUS_API_TIMEOUT_MS)
  if (!res.ok) await throwApiError(res, 'Không thể cập nhật trạng thái quy trình')
  return res.json() as Promise<DubbingResponse>
}

export async function downloadResult(id: string) {
  const res = await apiFetch(`${API_BASE}/dubbing/${id}/download`)
  if (!res.ok) await throwApiError(res, 'Không thể tải video lồng tiếng')
  return res.blob()
}

export async function downloadOriginal(id: string) {
  const res = await apiFetch(`${API_BASE}/dubbing/${id}/download-original`)
  if (!res.ok) await throwApiError(res, 'Không thể tải video gốc')
  return res.blob()
}

export async function cancelDubbing(id: string) {
  const res = await apiFetch(`${API_BASE}/dubbing/${id}/cancel`, { method: 'POST' })
  if (!res.ok) await throwApiError(res, 'Không thể hủy quy trình')
  return res.json()
}

export async function getHistory() {
  const res = await apiFetch(`${API_BASE}/history`)
  if (!res.ok) await throwApiError(res, 'Không thể tải lịch sử')
  return res.json()
}

export async function deleteHistoryItem(id: string) {
  const res = await apiFetch(`${API_BASE}/history/${id}`, { method: 'DELETE' })
  if (!res.ok) await throwApiError(res, 'Không thể xóa mục lịch sử')
  return res.json()
}

export async function deleteHistoryItems(ids: string[]) {
  const res = await apiFetch(`${API_BASE}/history/batch`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  })
  if (!res.ok) await throwApiError(res, 'Không thể xóa các mục lịch sử')
  return res.json()
}

export async function getSettings() {
  const res = await apiFetch(`${API_BASE}/settings`)
  if (!res.ok) await throwApiError(res, 'Không thể tải cài đặt')
  return res.json()
}

export async function updateSettings(settings: Record<string, unknown>) {
  const res = await apiFetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) {
    await throwApiError(res, 'Không thể lưu cài đặt')
  }
  return res.json()
}

export async function testTranslationConnection(
  settings: TranslationSettingsUpdate,
): Promise<TranslationTestResponse> {
  const res = await apiFetch(`${API_BASE}/settings/translation/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  const data = await res.json().catch(() => null) as Partial<TranslationTestResponse> & { detail?: string } | null
  if (!res.ok) await throwApiError(res, 'Không thể kiểm tra kết nối AI')
  return {
    ok: Boolean(data?.ok),
    provider: data?.provider as TranslationTestResponse['provider'],
    model: String(data?.model || ''),
    models: Array.isArray(data?.models) ? data.models as TranslationModelOption[] : [],
    model_source: data?.model_source as TranslationTestResponse['model_source'],
    message: String(data?.message || ''),
    used_fallback: Boolean(data?.used_fallback),
  }
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
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Failed to upload cookies')
  return data
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

/** Ask the backend to synthesize a short sample for a TTS voice.

The backend calls Edge TTS with a demo sentence in the target language
and returns the MP3 bytes. We use ``URL.createObjectURL`` to turn the
blob into a URL the ``<audio>`` element can play without a second
network round-trip. The caller is responsible for ``revokeObjectURL``
when the audio element is done.
*/
export async function previewTtsVoice(params: {
  voice: string
  text?: string
  lang?: string
  rate?: string
}): Promise<string> {
  const res = await fetch(`${API_BASE}/tts/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    // Surface the backend's friendly detail when available so the UI
    // can show "Edge TTS is busy" rather than a generic "fetch failed".
    let message = `TTS preview failed (${res.status})`
    try {
      const payload = await res.json()
      if (payload?.detail) message = String(payload.detail)
    } catch {
      // Body wasn't JSON; keep the default message.
    }
    throw new Error(message)
  }
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
