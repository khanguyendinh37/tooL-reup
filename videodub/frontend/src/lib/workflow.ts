import type { LucideIcon } from 'lucide-react'
import { AudioLines, Download, FileText, Mic2, Video } from 'lucide-react'

export type JobStatus =
  | 'pending'
  | 'downloading'
  | 'preview_ready'
  | 'processing'
  | 'transcribing'
  | 'translating'
  | 'tts'
  | 'removing_vocals'
  | 'merging'
  | 'completed'
  | 'error'
  | 'cancelled'

export type WorkflowPhase = 'idle' | 'downloading' | 'preview' | 'processing' | 'completed' | 'error'
export type PipelineStepStatus = 'pending' | 'active' | 'completed' | 'error'
export type NotificationKind = 'completed' | 'error'

export interface BlurRegion {
  x: number
  y: number
  width: number
  height: number
}

export const DEFAULT_BLUR_REGION: BlurRegion = {
  x: 0,
  y: 0.76,
  width: 1,
  height: 0.24,
}

export function clampUnit(value: number): number {
  return Math.min(Math.max(Number.isFinite(value) ? value : 0, 0), 1)
}

export function clampBlurRegion(region: BlurRegion): BlurRegion {
  const rawWidth = Number(region.width)
  const rawHeight = Number(region.height)
  const width = Math.min(Math.max(Number.isFinite(rawWidth) ? rawWidth : 1, 0.02), 1)
  const height = Math.min(Math.max(Number.isFinite(rawHeight) ? rawHeight : 0.24, 0.02), 1)
  const x = Math.min(clampUnit(Number(region.x)), 1 - width)
  const y = Math.min(clampUnit(Number(region.y)), 1 - height)
  return { x, y, width, height }
}

export function subtitleYForPreset(position: string): number {
  return position === 'top' ? 0.1 : position === 'center' ? 0.5 : 0.94
}

export function subtitlePresetForY(value: number): string {
  if (Math.abs(value - subtitleYForPreset('top')) < 0.035) return 'top'
  if (Math.abs(value - subtitleYForPreset('center')) < 0.035) return 'center'
  if (Math.abs(value - subtitleYForPreset('bottom')) < 0.035) return 'bottom'
  return 'custom'
}

export interface WorkflowFormValues {
  url: string
  sourceLang: string
  targetLang: string
  voice: string
  whisperModel: string
  ttsSpeed: number
  subtitleEnabled: boolean
  subtitlePosition: string
  subtitlePositionY: number
  subtitleSize: number
  subtitleColor: string
  blurRegion: BlurRegion
  blurExistingSubtitles: boolean
  dubbingVolume: number
  backgroundVolume: number
  originalVocalsVolume: number
}

export interface ActiveWorkflow extends WorkflowFormValues {
  jobId: string
  phase: WorkflowPhase
  status: JobStatus
  progress: number
  error: string | null
  previewUrl: string | null
  resultUrl: string | null
  startedAt: string
  updatedAt: string
}

export interface AppNotification {
  id: string
  jobId: string
  kind: NotificationKind
  title: string
  message: string
  createdAt: string
  read: boolean
}

export interface WorkflowJobLike {
  id: string
  url: string
  source_lang: string
  target_lang: string
  voice: string
  whisper_model: string
  status: string
  progress: number
  error?: string | null
  subtitle_config?: string | null
  processing_config?: string | null
  created_at: string
  updated_at: string
}

export const DEFAULT_WORKFLOW_FORM: WorkflowFormValues = {
  url: '',
  sourceLang: 'en',
  targetLang: 'vi',
  voice: 'vi-VN-HoaiMyNeural',
  whisperModel: 'small',
  ttsSpeed: 1,
  subtitleEnabled: false,
  subtitlePosition: 'bottom',
  subtitlePositionY: subtitleYForPreset('bottom'),
  subtitleSize: 13,
  subtitleColor: 'white',
  blurExistingSubtitles: false,
  blurRegion: DEFAULT_BLUR_REGION,
  dubbingVolume: 2,
  backgroundVolume: 1,
  originalVocalsVolume: 0.1,
}

export const PIPELINE_STEPS: ReadonlyArray<{
  id: string
  backendStatus: JobStatus
  label: string
  icon: LucideIcon
}> = [
  { id: 'download', backendStatus: 'downloading', label: 'Tải video', icon: Download },
  { id: 'transcribe', backendStatus: 'transcribing', label: 'Nhận dạng lời thoại', icon: FileText },
  { id: 'translate', backendStatus: 'translating', label: 'Dịch phụ đề theo ngữ cảnh', icon: AudioLines },
  { id: 'tts', backendStatus: 'tts', label: 'Tạo giọng lồng tiếng', icon: Mic2 },
  { id: 'remove_vocal', backendStatus: 'removing_vocals', label: 'Tách giọng gốc', icon: AudioLines },
  { id: 'merge', backendStatus: 'merging', label: 'Hoàn thiện video', icon: Video },
]

export const STATUS_STEP_MAP: Record<string, number> = {
  pending: -1,
  downloading: 0,
  preview_ready: -1,
  processing: 1,
  transcribing: 1,
  translating: 2,
  tts: 3,
  removing_vocals: 4,
  merging: 5,
  completed: 6,
  error: -2,
  cancelled: -2,
}

export function normalizeJobStatus(status: string): JobStatus {
  const knownStatuses: JobStatus[] = [
    'pending', 'downloading', 'preview_ready', 'processing', 'transcribing',
    'translating', 'tts', 'removing_vocals', 'merging', 'completed', 'error', 'cancelled',
  ]
  return knownStatuses.includes(status as JobStatus) ? status as JobStatus : 'pending'
}

export function getWorkflowPhase(status: JobStatus): WorkflowPhase {
  if (status === 'preview_ready') return 'preview'
  if (status === 'completed') return 'completed'
  if (status === 'error' || status === 'cancelled') return 'error'
  if (status === 'pending' || status === 'downloading') return 'downloading'
  return 'processing'
}

export function getPipelineSteps(status: JobStatus, progress: number) {
  const activeIndex = STATUS_STEP_MAP[status] ?? -1
  return PIPELINE_STEPS.map((step, index) => ({
    ...step,
    status: index < activeIndex
      ? 'completed' as PipelineStepStatus
      : index === activeIndex
        ? 'active' as PipelineStepStatus
        : 'pending' as PipelineStepStatus,
    progress: index === activeIndex ? progress : index < activeIndex ? 100 : undefined,
  }))
}

export function workflowFromJob(
  job: WorkflowJobLike,
  form: Partial<WorkflowFormValues> = {},
  urls: Partial<Pick<ActiveWorkflow, 'previewUrl' | 'resultUrl'>> = {},
): ActiveWorkflow {
  const status = normalizeJobStatus(job.status)
  let savedForm: Partial<WorkflowFormValues> = {}

  let processingConfig: {
    tts_speed?: number
    subtitle_config?: {
      enabled?: boolean
      position?: string
      position_y?: number
      custom_y?: number
      font_color?: string
      blur_existing_subtitles?: boolean
      blur_region?: BlurRegion
    } | null
    audio_config?: {
      dubbing_volume?: number
      background_volume?: number
      original_vocals_volume?: number
    } | null
  } | null = null

  if (job.processing_config) {
    try {
      processingConfig = JSON.parse(job.processing_config)
    } catch {
      // Older jobs may not have a valid processing snapshot.
    }
  }

  let subtitleConfig = processingConfig?.subtitle_config || null
  if (!subtitleConfig && job.subtitle_config) {
    try {
      subtitleConfig = JSON.parse(job.subtitle_config)
    } catch {
      // Fall back to the local form/defaults when the saved subtitle JSON is invalid.
    }
  }

  if (subtitleConfig || processingConfig) {
    const savedPosition = subtitleConfig?.position || 'bottom'
    const rawPositionY = subtitleConfig?.position_y ?? subtitleConfig?.custom_y
    const positionY = typeof rawPositionY === 'number'
      ? clampUnit(rawPositionY)
      : subtitleYForPreset(savedPosition)
    const position = subtitleConfig?.position === 'custom'
      ? 'custom'
      : subtitlePresetForY(positionY)
    const savedBlurRegion = subtitleConfig?.blur_region && typeof subtitleConfig.blur_region === 'object'
      ? clampBlurRegion(subtitleConfig.blur_region as BlurRegion)
      : DEFAULT_BLUR_REGION
    const fontColor = subtitleConfig?.font_color?.toUpperCase()
    const color = fontColor === '#FFD700'
      ? 'yellow'
      : fontColor === '#00FFFF'
        ? 'cyan'
        : fontColor === '#FF4444'
          ? 'red'
          : 'white'
    savedForm = {
      ttsSpeed: processingConfig?.tts_speed,
      subtitleEnabled: subtitleConfig?.enabled,
      subtitlePosition: position,
      subtitlePositionY: positionY,
      subtitleColor: color,
      subtitleSize: subtitleConfig?.font_size ? parseInt(subtitleConfig?.font_size, 10) : 13,
      blurExistingSubtitles: subtitleConfig?.blur_existing_subtitles,
      blurRegion: savedBlurRegion,
      dubbingVolume: processingConfig?.audio_config?.dubbing_volume,
      backgroundVolume: processingConfig?.audio_config?.background_volume,
      originalVocalsVolume: processingConfig?.audio_config?.original_vocals_volume,
    }
  }

  return {
    ...DEFAULT_WORKFLOW_FORM,
    ...savedForm,
    ...form,
    url: job.url,
    sourceLang: job.source_lang,
    targetLang: job.target_lang,
    voice: job.voice,
    whisperModel: job.whisper_model,
    jobId: job.id,
    phase: getWorkflowPhase(status),
    status,
    progress: job.progress ?? 0,
    error: job.error || null,
    previewUrl: status === 'preview_ready' ? `/api/dubbing/${job.id}/preview-url` : urls.previewUrl || null,
    resultUrl: status === 'completed' ? `/api/dubbing/${job.id}/download` : urls.resultUrl || null,
    startedAt: job.created_at,
    updatedAt: job.updated_at,
  }
}

export function notificationForJob(job: ActiveWorkflow, kind: NotificationKind): AppNotification {
  const isComplete = kind === 'completed'
  return {
    id: `${job.jobId}:${kind}`,
    jobId: job.jobId,
    kind,
    title: isComplete ? 'Video đã hoàn thành' : 'Video xử lý thất bại',
    message: isComplete
      ? 'Video lồng tiếng đã xử lý xong. Bấm để mở video.'
      : job.error || 'Quy trình lồng tiếng gặp lỗi. Bấm để mở và chạy lại.',
    createdAt: new Date().toISOString(),
    read: false,
  }
}

export function formatNotificationTime(value: string): string {
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

