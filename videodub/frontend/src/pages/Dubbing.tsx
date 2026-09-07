import { useState, useEffect, useRef, type ReactNode, type RefObject } from 'react'
import { useParams } from 'react-router-dom'
import {
  Link, Download, Play, CheckCircle2, XCircle, Loader2,
  ChevronDown, Settings2, Video, RotateCcw, FileText, Bell, BellOff,
  Save, AlertCircle, RefreshCw
} from 'lucide-react'
import { LANGUAGES, TTS_VOICES, WHISPER_MODELS } from '@/lib/utils'
import { downloadFile, startPreview, startDubbing, getDubbingStatus, getSettings, updateSettings, cancelDubbing } from '@/lib/api'
import { VoicePreviewButton } from '@/components/VoicePreviewButton'
import {
  DEFAULT_BLUR_REGION,
  DEFAULT_WORKFLOW_FORM,
  clampBlurRegion,
  getPipelineSteps,
  subtitlePresetForY,
  subtitleYForPreset,
  workflowFromJob,
  type ActiveWorkflow,
  type BlurRegion,
  type WorkflowFormValues,
} from '@/lib/workflow'
import { useAppStore } from '@/stores/appStore'
import BlurRegionEditor from '@/components/dubbing/BlurRegionEditor'

// Video Preview Component
interface VideoPreviewProps {
  videoUrl: string
  controls?: boolean
  stageRef?: RefObject<HTMLDivElement>
  overlay?: ReactNode
}

function VideoPreview({ videoUrl, controls = true, stageRef, overlay }: VideoPreviewProps) {
  const [videoError, setVideoError] = useState(false)
  const [videoLoading, setVideoLoading] = useState(true)
  const [videoReady, setVideoReady] = useState(false)
  const [aspectRatio, setAspectRatio] = useState('16 / 9')
  const [aspectRatioValue, setAspectRatioValue] = useState(16 / 9)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    setCurrentTime(0)
    setDuration(0)
    setVideoReady(false)
    setVideoLoading(true)
    setVideoError(false)
  }, [videoUrl])

  const updateDuration = () => {
    const value = videoRef.current?.duration
    setDuration(value && Number.isFinite(value) ? value : 0)
  }
  const formatTime = (value: number) => `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2, '0')}`

  const handleVideoError = () => {
    setVideoError(true)
    setVideoLoading(false)
  }

  const handleVideoLoadedMetadata = () => {
    updateDuration()
    const video = videoRef.current
    if (!video?.videoWidth || !video.videoHeight) return
    setAspectRatio(`${video.videoWidth} / ${video.videoHeight}`)
    setAspectRatioValue(video.videoWidth / video.videoHeight)
  }

  const handleVideoLoadedData = () => {
    setVideoLoading(false)
    setVideoReady(true)
  }

  const handleVideoCanPlay = () => {
    setVideoLoading(false)
    setVideoReady(true)
  }

  const handleRetry = () => {
    setVideoError(false)
    setVideoLoading(true)
    setVideoReady(false)
    if (videoRef.current) {
      videoRef.current.src = videoUrl + '?t=' + Date.now()
      videoRef.current.load()
    }
  }

  return (
    <div className="rounded-xl overflow-hidden bg-surface-900 border border-surface-700">
      <div
        ref={stageRef}
        className="relative mx-auto bg-black"
        style={{
          aspectRatio,
          width: `min(100%, ${Math.max(aspectRatioValue * 70, 1)}vh)`,
          maxHeight: '70vh',
        }}
      >
        {!videoReady && videoLoading && !videoError && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-900 z-10">
            <div className="flex flex-col items-center gap-3 text-surface-400">
              <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
              <span className="text-sm">Đang tải video...</span>
            </div>
          </div>
        )}
        <video
          ref={videoRef}
          src={videoUrl}
          controls={controls}
          preload="auto"
          className={`absolute top-0 left-0 w-full h-full transition-opacity duration-300 ${
            videoReady ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ objectFit: 'contain' }}
          onError={handleVideoError}
          onLoadedMetadata={handleVideoLoadedMetadata}
          onLoadedData={handleVideoLoadedData}
          onCanPlay={handleVideoCanPlay}
          onDurationChange={updateDuration}
          onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime || 0)}
        />
        {overlay}
        {videoError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface-900 z-20 p-4">
            <div className="flex flex-col items-center gap-4 text-center">
              <AlertCircle className="w-16 h-16 text-red-400" />
              <div>
                <p className="text-lg font-medium text-surface-100">Không thể tải video</p>
                <p className="text-sm text-surface-400 mt-1">Video có thể đã bị xóa hoặc đường link không hợp lệ</p>
              </div>
              <button onClick={handleRetry} className="btn-primary inline-flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Thử lại
              </button>
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="text-xs text-surface-300 tabular-nums">{formatTime(currentTime)}</span>
        <input
          type="range"
          aria-label="Tua video"
          aria-valuetext={`${formatTime(currentTime)} / ${formatTime(duration)}`}
          min={0}
          max={duration || 1}
          step={0.1}
          value={Math.min(currentTime, duration)}
          disabled={!duration || videoError}
          onChange={(event) => {
            const time = Number(event.target.value)
            if (videoRef.current) videoRef.current.currentTime = time
            setCurrentTime(time)
          }}
          className="h-6 min-w-0 flex-1 accent-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-400"
        />
        <span className="text-xs text-surface-300 tabular-nums">{formatTime(duration)}</span>
      </div>
    </div>
  )
}

export default function Dubbing() {
  const { projectId } = useParams<{ projectId?: string }>()
  const activeWorkflow = useAppStore((state) => state.activeWorkflow)
  const dubbingPreferences = useAppStore((state) => state.dubbingPreferences)
  const updateDubbingPreferences = useAppStore((state) => state.updateDubbingPreferences)
  const setActiveWorkflow = useAppStore((state) => state.setActiveWorkflow)
  const patchActiveWorkflow = useAppStore((state) => state.patchActiveWorkflow)
  const clearActiveWorkflow = useAppStore((state) => state.clearActiveWorkflow)
  const selectedWorkflow = projectId && activeWorkflow?.jobId !== projectId ? null : activeWorkflow
  const jobId = projectId || selectedWorkflow?.jobId || null
  const workflowPhase = selectedWorkflow?.phase ?? 'idle'
  const videoUrl = selectedWorkflow?.phase === 'completed'
    ? selectedWorkflow.resultUrl
    : selectedWorkflow?.phase === 'preview'
      ? selectedWorkflow.previewUrl
      : null
  const steps = selectedWorkflow
    ? getPipelineSteps(selectedWorkflow.status, selectedWorkflow.progress)
    : getPipelineSteps('pending', 0)
  const workflowHydratedRef = useRef<string | null>(null)
  const [url, setUrl] = useState(() => activeWorkflow?.url || '')
  const [sourceLang, setSourceLang] = useState(() => activeWorkflow?.sourceLang ?? dubbingPreferences.sourceLang ?? DEFAULT_WORKFLOW_FORM.sourceLang)
  const [targetLang, setTargetLang] = useState(() => activeWorkflow?.targetLang ?? dubbingPreferences.targetLang ?? DEFAULT_WORKFLOW_FORM.targetLang)
  const [selectedVoice, setSelectedVoice] = useState(() => activeWorkflow?.voice ?? dubbingPreferences.voice ?? DEFAULT_WORKFLOW_FORM.voice)
  const [whisperModel, setWhisperModel] = useState(() => activeWorkflow?.whisperModel ?? dubbingPreferences.whisperModel ?? DEFAULT_WORKFLOW_FORM.whisperModel)
  const [ttsSpeed, setTtsSpeed] = useState(() => activeWorkflow?.ttsSpeed ?? dubbingPreferences.ttsSpeed ?? DEFAULT_WORKFLOW_FORM.ttsSpeed)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const error = activeWorkflow?.error || localError
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [subtitleEnabled, setSubtitleEnabled] = useState(() => activeWorkflow?.subtitleEnabled ?? dubbingPreferences.subtitleEnabled ?? DEFAULT_WORKFLOW_FORM.subtitleEnabled)
  const [subtitlePosition, setSubtitlePosition] = useState(() => activeWorkflow?.subtitlePosition ?? dubbingPreferences.subtitlePosition ?? DEFAULT_WORKFLOW_FORM.subtitlePosition)
  const [subtitlePositionY, setSubtitlePositionY] = useState(() => activeWorkflow?.subtitlePositionY ?? dubbingPreferences.subtitlePositionY ?? DEFAULT_WORKFLOW_FORM.subtitlePositionY)
  const [subtitleSize, setSubtitleSize] = useState(() => activeWorkflow?.subtitleSize ?? dubbingPreferences.subtitleSize ?? DEFAULT_WORKFLOW_FORM.subtitleSize)
  const [subtitleColor, setSubtitleColor] = useState(() => activeWorkflow?.subtitleColor ?? dubbingPreferences.subtitleColor ?? DEFAULT_WORKFLOW_FORM.subtitleColor)
  const [blurExistingSubtitles, setBlurExistingSubtitles] = useState(() => activeWorkflow?.blurExistingSubtitles ?? dubbingPreferences.blurExistingSubtitles ?? DEFAULT_WORKFLOW_FORM.blurExistingSubtitles)
  const [blurRegion, setBlurRegion] = useState<BlurRegion>(() => activeWorkflow?.blurRegion ?? dubbingPreferences.blurRegion ?? DEFAULT_BLUR_REGION)
  const [editingBlurRegion, setEditingBlurRegion] = useState(false)
  const previewStageRef = useRef<HTMLDivElement>(null)
  const [dubbingVolume, setDubbingVolume] = useState(() => activeWorkflow?.dubbingVolume ?? dubbingPreferences.dubbingVolume ?? DEFAULT_WORKFLOW_FORM.dubbingVolume)
  const [backgroundVolume, setBackgroundVolume] = useState(() => activeWorkflow?.backgroundVolume ?? dubbingPreferences.backgroundVolume ?? DEFAULT_WORKFLOW_FORM.backgroundVolume)
  const [originalVocalsVolume, setOriginalVocalsVolume] = useState(() => activeWorkflow?.originalVocalsVolume ?? dubbingPreferences.originalVocalsVolume ?? DEFAULT_WORKFLOW_FORM.originalVocalsVolume)
  const [settingsSaved, setSettingsSaved] = useState(false)
  const [cancelPending, setCancelPending] = useState(false)

  const applyWorkflowToForm = (workflow: ActiveWorkflow) => {
    setUrl(workflow.url)
    setSourceLang(workflow.sourceLang)
    setTargetLang(workflow.targetLang)
    setSelectedVoice(workflow.voice)
    setWhisperModel(workflow.whisperModel)
    setTtsSpeed(workflow.ttsSpeed)
    setSubtitleEnabled(workflow.subtitleEnabled)
    setSubtitlePosition(workflow.subtitlePosition)
    setSubtitlePositionY(workflow.subtitlePositionY ?? subtitleYForPreset(workflow.subtitlePosition))
    setSubtitleSize(workflow.subtitleSize)
    setSubtitleColor(workflow.subtitleColor)
    setBlurExistingSubtitles(workflow.blurExistingSubtitles)
    setBlurRegion(workflow.blurRegion ? clampBlurRegion(workflow.blurRegion) : DEFAULT_BLUR_REGION)
    setEditingBlurRegion(false)
    setDubbingVolume(workflow.dubbingVolume)
    setBackgroundVolume(workflow.backgroundVolume)
    setOriginalVocalsVolume(workflow.originalVocalsVolume)
  }

  const getFormValues = (): WorkflowFormValues => ({
    url,
    sourceLang,
    targetLang,
    voice: selectedVoice,
    whisperModel,
    ttsSpeed,
    subtitleEnabled,
    subtitlePosition,
    subtitlePositionY,
    subtitleSize,
    subtitleColor,
    blurExistingSubtitles,
    blurRegion,
    dubbingVolume,
    backgroundVolume,
    originalVocalsVolume,
  })

  // Restore the canonical job after a notification click, retry, reload, or route change.
  useEffect(() => {
    const targetJobId = projectId || useAppStore.getState().activeWorkflow?.jobId
    if (!targetJobId || workflowHydratedRef.current === targetJobId) return undefined
    workflowHydratedRef.current = targetJobId
    let cancelled = false

    const restoreWorkflow = async () => {
      try {
        const job = await getDubbingStatus(targetJobId)
        if (cancelled) return
        const existing = useAppStore.getState().activeWorkflow
        const form = existing?.jobId === targetJobId ? existing : undefined
        const restored = workflowFromJob(job, form || {}, {
          previewUrl: existing?.previewUrl,
          resultUrl: existing?.resultUrl,
        })
        setActiveWorkflow(restored)
        applyWorkflowToForm(restored)
        setLocalError(null)
      } catch (restoreError) {
        if (!cancelled) {
          const message = restoreError instanceof Error
            ? restoreError.message
            : 'Không thể khôi phục trạng thái video'
          setLocalError(message)
          const current = useAppStore.getState().activeWorkflow
          if (current?.jobId === targetJobId) {
            patchActiveWorkflow({
              status: 'error',
              phase: 'error',
              error: `${message}. Đã dừng trạng thái loading để bạn có thể thử lại.`,
              updatedAt: new Date().toISOString(),
            })
          }
        }
      }
    }

    void restoreWorkflow()
    return () => {
      cancelled = true
    }
  }, [patchActiveWorkflow, projectId, activeWorkflow?.jobId, setActiveWorkflow])

  // Keep form edits in the persisted snapshot while a preview or pipeline is active.
  useEffect(() => {
    if (!activeWorkflow || activeWorkflow.jobId !== jobId) return
    if (workflowPhase !== 'preview' && workflowPhase !== 'processing') return
    patchActiveWorkflow({
      url,
      sourceLang,
      targetLang,
      voice: selectedVoice,
      whisperModel,
      ttsSpeed,
      subtitleEnabled,
      subtitlePosition,
      subtitlePositionY,
      subtitleSize,
      subtitleColor,
      blurExistingSubtitles,
      blurRegion,
      dubbingVolume,
      backgroundVolume,
      originalVocalsVolume,
      updatedAt: new Date().toISOString(),
    })
  }, [
    activeWorkflow?.jobId,
    backgroundVolume,
    blurExistingSubtitles,
    blurRegion,
    dubbingVolume,
    jobId,
    originalVocalsVolume,
    patchActiveWorkflow,
    selectedVoice,
    sourceLang,
    subtitleColor,
    subtitleEnabled,
    subtitlePosition,
    subtitlePositionY,
    subtitleSize,
    targetLang,
    ttsSpeed,
    url,
    whisperModel,
    workflowPhase,
  ])

  // Persist the editable draft even before a job is created. This keeps the
  // subtitle and blur choices available after route changes or desktop restarts.
  useEffect(() => {
    if (!settingsLoaded) return
    updateDubbingPreferences({
      sourceLang,
      targetLang,
      voice: selectedVoice,
      whisperModel,
      ttsSpeed,
      subtitleEnabled,
      subtitlePosition,
      subtitlePositionY,
      subtitleSize,
      subtitleColor,
      blurExistingSubtitles,
      blurRegion,
      dubbingVolume,
      backgroundVolume,
      originalVocalsVolume,
    })
  }, [
    backgroundVolume,
    blurExistingSubtitles,
    blurRegion,
    dubbingVolume,
    originalVocalsVolume,
    selectedVoice,
    settingsLoaded,
    sourceLang,
    subtitleColor,
    subtitleEnabled,
    subtitlePosition,
    subtitlePositionY,
    subtitleSize,
    targetLang,
    ttsSpeed,
    updateDubbingPreferences,
    whisperModel,
  ])

  // Load settings from backend on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const settings = await getSettings()
        setNotificationsEnabled(settings.notifications_enabled === 'true' || settings.notifications_enabled === true)
        const hasRestoredWorkflow = Boolean(useAppStore.getState().activeWorkflow || projectId)
        const hasSavedDubbingPreferences = useAppStore.getState().dubbingPreferencesSaved
        if (!hasRestoredWorkflow && !hasSavedDubbingPreferences) {
          setSourceLang(settings.default_source_lang || 'en')
          setTargetLang(settings.default_target_lang || 'vi')
          setSelectedVoice(settings.default_voice || 'vi-VN-HoaiMyNeural')
          setWhisperModel(settings.whisper_model || 'small')
          setTtsSpeed(parseFloat(settings.tts_speed || '1.0'))
          setSubtitleEnabled(settings.subtitle_enabled === 'true' || settings.subtitle_enabled === true)
          const savedPosition = settings.subtitle_position || 'bottom'
          const savedPositionY = Number(settings.subtitle_position_y)
          setSubtitlePosition(savedPosition)
          setSubtitlePositionY(Number.isFinite(savedPositionY)
            ? Math.min(Math.max(savedPositionY, 0), 1)
            : subtitleYForPreset(savedPosition))
          setSubtitleSize(settings.subtitle_size ? parseInt(String(settings.subtitle_size), 10) : 13)
          setSubtitleColor(settings.subtitle_color || 'white')
          setBlurExistingSubtitles(
            settings.blur_existing_subtitles === 'true' || settings.blur_existing_subtitles === true
          )
          if (settings.blur_region && typeof settings.blur_region === 'object') {
            setBlurRegion(clampBlurRegion(settings.blur_region))
          }
          setDubbingVolume(parseFloat(String(settings.default_dubbing_volume ?? 2.0)))
          setBackgroundVolume(parseFloat(String(settings.default_background_volume ?? 1.0)))
          setOriginalVocalsVolume(parseFloat(String(settings.default_original_volume ?? 0.1)))
        }
      } catch (err) {
        console.error('Failed to load settings:', err)
      } finally {
        setSettingsLoaded(true)
      }
    }
    loadSettings()
  }, [])

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
    const saved = localStorage.getItem('notificationsEnabled')
    if (saved !== null) {
      setNotificationsEnabled(JSON.parse(saved))
    }
  }, [])

  // Update voice when target language changes
  const filteredVoices = TTS_VOICES.filter(v => v.lang === targetLang)
  useEffect(() => {
    if (filteredVoices.length > 0 && settingsLoaded) {
      const currentVoiceValid = filteredVoices.some(v => v.id === selectedVoice)
      if (!currentVoiceValid) {
        setSelectedVoice(filteredVoices[0].id)
      }
    }
  }, [targetLang, filteredVoices, settingsLoaded, selectedVoice])

  const toggleNotifications = () => {
    const newValue = !notificationsEnabled
    setNotificationsEnabled(newValue)
    localStorage.setItem('notificationsEnabled', JSON.stringify(newValue))
    if (!notificationsEnabled && 'Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission()
    }
  }

  const handleSaveSettings = async () => {
    try {
      await updateSettings({
        default_source_lang: sourceLang, default_target_lang: targetLang,
        default_voice: selectedVoice, whisper_model: whisperModel,
        tts_speed: ttsSpeed.toString(), notifications_enabled: notificationsEnabled,
        subtitle_enabled: subtitleEnabled,
        subtitle_position: subtitlePosition,
        subtitle_position_y: subtitlePositionY,
        subtitle_size: subtitleSize,
        subtitle_color: subtitleColor,
        blur_existing_subtitles: blurExistingSubtitles,
        blur_region: blurRegion,
        default_dubbing_volume: dubbingVolume,
        default_background_volume: backgroundVolume,
        default_original_volume: originalVocalsVolume,
      })
      setSettingsSaved(true)
      setTimeout(() => setSettingsSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save settings:', err)
    }
  }


  // Phase 1: Download video for preview. The global monitor owns polling.
  const handleDownloadPreview = async () => {
    if (!url.trim()) return
    setLocalError(null)

    try {
      const result = await startPreview({ url, source_lang: sourceLang, target_lang: targetLang, voice: selectedVoice, whisper_model: whisperModel })
      const workflow = workflowFromJob(result, getFormValues(), {
        previewUrl: `/api/dubbing/${result.id}/preview-url`,
      })
      setActiveWorkflow(workflow)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Không thể tải video')
    }
  }

  // Phase 2: Start full dubbing pipeline with user's edits.
  const handleStartDubbing = async () => {
    if (!jobId || !url.trim()) return
    setLocalError(null)
    patchActiveWorkflow({
      ...getFormValues(),
      phase: 'processing',
      status: 'processing',
      progress: 0,
      error: null,
      resultUrl: null,
      // A new run gets its own tracking window; the job's original created_at
      // must not count against it.
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })

    try {
      const result = await startDubbing({
        url, source_lang: sourceLang, target_lang: targetLang,
        voice: selectedVoice, whisper_model: whisperModel,
        tts_speed: ttsSpeed,
        job_id: jobId,
        subtitle_enabled: subtitleEnabled,
        subtitle_position: subtitlePosition,
        subtitle_position_y: subtitlePositionY,
        subtitle_size: subtitleSize,
        subtitle_color: subtitleColor,
        blur_existing_subtitles: blurExistingSubtitles,
        blur_region: blurRegion,
        dubbing_volume: dubbingVolume,
        background_volume: backgroundVolume,
        original_vocals_volume: originalVocalsVolume,
      })
      setActiveWorkflow(workflowFromJob(result, getFormValues(), {
        previewUrl: activeWorkflow?.previewUrl,
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không thể bắt đầu xử lý'
      setLocalError(message)
      patchActiveWorkflow({ phase: 'error', status: 'error', error: message, updatedAt: new Date().toISOString() })
    }
  }

  const handleDownload = async () => {
    if (!jobId) return
    try {
      await downloadFile(`/api/dubbing/${jobId}/download`, 'VideoDub_dubbed.mp4')
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Không thể lưu video')
    }
  }

  const handleDownloadOriginal = async () => {
    if (!jobId) return
    try {
      await downloadFile(`/api/dubbing/${jobId}/download-original`, 'VideoDub_original.mp4')
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Không thể lưu video gốc')
    }
  }

  const handleReset = () => {
    clearActiveWorkflow()
    workflowHydratedRef.current = null
    setLocalError(null)
    setEditingBlurRegion(false)
    setBlurRegion({ ...dubbingPreferences.blurRegion })
    setSubtitlePosition(dubbingPreferences.subtitlePosition)
    setSubtitlePositionY(dubbingPreferences.subtitlePositionY)
    setUrl('')
  }

  // Start a new download without canceling the current one (allows parallel downloads)
  const handleStartNewDownload = () => {
    setLocalError(null)
    setUrl('')
    // Reset workflow phase to idle so a new download can be started
    // without needing to fully reset the workflow
    patchActiveWorkflow({
      phase: 'idle',
      status: 'pending',
      progress: 0,
      error: null,
      updatedAt: new Date().toISOString(),
    })
  }

  const handleCancel = async () => {
    if (!jobId) return
    setCancelPending(true)
    try {
      await cancelDubbing(jobId)
      setLocalError('Đã hủy quy trình lồng tiếng')
      patchActiveWorkflow({ phase: 'error', status: 'cancelled', error: 'Đã hủy quy trình lồng tiếng', updatedAt: new Date().toISOString() })
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Không thể hủy quy trình')
    } finally {
      setCancelPending(false)
    }
  }

  const handleSubtitlePositionChange = (position: string) => {
    setSubtitlePosition(position)
    setSubtitlePositionY(subtitleYForPreset(position))
  }

  const handleBlurRegionChange = (nextRegion: BlurRegion) => {
    setBlurRegion(clampBlurRegion(nextRegion))
  }

  const handleSubtitleYChange = (nextY: number) => {
    setSubtitlePositionY(nextY)
    setSubtitlePosition(subtitlePresetForY(nextY))
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4 sm:space-y-6 animate-fade-in">
      {/* URL Input - Always visible */}
      <div className="glass-card">
        <h3 className="text-base sm:text-lg font-semibold text-surface-100 mb-3 sm:mb-4 flex items-center gap-2">
          <Link className="w-5 h-5 text-primary-400" />
          Nhập link video
        </h3>
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=... hoặc link từ bất kỳ nền tảng nào"
            className="glass-input flex-1"
            disabled={workflowPhase === 'downloading' || workflowPhase === 'processing'}
          />
          <div className="w-full sm:w-auto sm:flex-shrink-0">
            {workflowPhase === 'idle' || workflowPhase === 'error' ? (
              <button
                onClick={handleDownloadPreview}
                disabled={!url.trim()}
                className="btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                <Download className="w-4 h-4 sm:w-5 sm:h-5" /> Tải video
              </button>
            ) : workflowPhase === 'downloading' ? (
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <button disabled className="btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-2 opacity-50 whitespace-nowrap">
                  <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" /> Đang tải...
                </button>
                <button
                  onClick={handleStartNewDownload}
                  className="btn-secondary w-full sm:w-auto inline-flex items-center justify-center gap-2 whitespace-nowrap"
                  title="Tải video khác trong khi đang tải"
                >
                  <Download className="w-4 h-4 sm:w-5 sm:h-5" /> Tải video khác
                </button>
              </div>
            ) : workflowPhase === 'processing' ? (
              <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <button disabled className="btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-2 opacity-50 whitespace-nowrap">
                  <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" /> Đang xử lý...
                </button>
                <button
                  onClick={handleStartNewDownload}
                  className="btn-secondary w-full sm:w-auto inline-flex items-center justify-center gap-2 whitespace-nowrap"
                  title="Tải video khác trong khi đang xử lý"
                >
                  <Download className="w-4 h-4 sm:w-5 sm:h-5" /> Tải video khác
                </button>
              </div>
            ) : workflowPhase === 'preview' ? (
              <button
                onClick={handleStartDubbing}
                className="btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-2 whitespace-nowrap"
              >
                <Play className="w-4 h-4 sm:w-5 sm:h-5" /> Bắt đầu lồng tiếng
              </button>
            ) : workflowPhase === 'completed' ? (
              <button onClick={handleReset} className="btn-secondary w-full sm:w-auto inline-flex items-center justify-center gap-2 whitespace-nowrap">
                <RotateCcw className="w-4 h-4 sm:w-5 sm:h-5" /> Video mới
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Language & Voice Selection - visible in idle, preview, and error phases */}
      {(workflowPhase === 'idle' || workflowPhase === 'preview' || workflowPhase === 'error') && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          <div className="glass-card">
            <label className="text-sm text-surface-400 mb-2 block">Ngôn ngữ gốc</label>
            <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} className="glass-input w-full appearance-none cursor-pointer">
              {LANGUAGES.map(lang => <option key={lang.code} value={lang.code}>{lang.flag} {lang.name}</option>)}
            </select>
          </div>
          <div className="glass-card">
            <label className="text-sm text-surface-400 mb-2 block">Ngôn ngữ đích</label>
            <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)} className="glass-input w-full appearance-none cursor-pointer">
              {LANGUAGES.map(lang => <option key={lang.code} value={lang.code}>{lang.flag} {lang.name}</option>)}
            </select>
          </div>
          <div className="glass-card">
            <label className="text-sm text-surface-400 mb-2 block">Giọng lồng tiếng</label>
            <div className="flex gap-2">
              <select value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)} className="glass-input flex-1 appearance-none cursor-pointer">
                {filteredVoices.length > 0 && (
                  <>
                    <optgroup label="Nữ">
                      {filteredVoices.filter(v => v.gender === 'female').map(voice => (
                        <option key={voice.id} value={voice.id}>{voice.name}</option>
                      ))}
                    </optgroup>
                    <optgroup label="Nam">
                      {filteredVoices.filter(v => v.gender === 'male').map(voice => (
                        <option key={voice.id} value={voice.id}>{voice.name}</option>
                      ))}
                    </optgroup>
                  </>
                )}
                {filteredVoices.length === 0 && <option value="">Không có giọng cho ngôn ngữ này</option>}
              </select>
              <VoicePreviewButton voice={selectedVoice} lang={targetLang} />
            </div>
          </div>
        </div>
      )}

      {/* Subtitle Editor - visible in preview phase */}
      {workflowPhase === 'preview' && (
        <div className="glass-card">
          <div className="flex items-center justify-between w-full gap-2 flex-wrap">
            <div className="flex items-center gap-3 flex-1 min-w-0 flex-wrap">
              <FileText className="w-5 h-5 text-primary-400" />
              <span className="text-surface-300">Cài đặt phụ đề</span>
              <label className="flex items-center gap-2 cursor-pointer ml-4">
                <input
                  type="checkbox"
                  checked={subtitleEnabled}
                  onChange={(e) => {
                    setSubtitleEnabled(e.target.checked)
                    if (!e.target.checked) setEditingBlurRegion(false)
                  }}
                  className="rounded accent-primary-500 w-4 h-4"
                />
                <span className="text-sm text-surface-400">Thêm phụ đề</span>
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={handleSaveSettings} className="btn-ghost !p-2 text-surface-400 hover:text-primary-400 hover:bg-primary-500/10 transition-all" title="Lưu cài đặt mặc định">
                {settingsSaved ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <Save className="w-5 h-5" />}
              </button>
              <button onClick={toggleNotifications} className="btn-ghost !p-2 text-surface-400 hover:text-surface-200" title={notificationsEnabled ? 'Tắt thông báo' : 'Bật thông báo'}>
                {notificationsEnabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
              </button>
            </div>
          </div>
          {subtitleEnabled && (
            <div className="mt-4 pt-4 border-t border-surface-700/50 space-y-3">
              <div className="flex items-center gap-3">
                <label htmlFor="subtitle-size" className="text-sm text-surface-400">Cỡ chữ phụ đề:</label>
                <input
                  id="subtitle-size"
                  type="range"
                  min={10}
                  max={40}
                  value={subtitleSize}
                  onChange={(e) => setSubtitleSize(parseInt(e.target.value, 10))}
                  className="w-32 accent-primary-500"
                />
                <span className="text-surface-200 font-medium">{subtitleSize} px</span>
              </div>
              <label htmlFor="blur-existing-subtitles" className="flex items-start gap-3 cursor-pointer">
                <input
                  id="blur-existing-subtitles"
                  type="checkbox"
                  checked={blurExistingSubtitles}
                  onChange={(e) => {
                    setBlurExistingSubtitles(e.target.checked)
                    if (!e.target.checked) setEditingBlurRegion(false)
                  }}
                  aria-describedby="blur-existing-subtitles-help"
                  className="mt-0.5 w-4 h-4 rounded accent-primary-500"
                />
               <span>
                   <span className="block text-sm text-surface-300">Video có phụ đề cũ đã in sẵn</span>
                   <span id="blur-existing-subtitles-help" className="block text-xs text-surface-500 mt-1">
                     Bật để chọn một vùng che phụ đề cũ bằng khung kéo thả ngay trên video preview.
                   </span>
                 </span>
               </label>
               <div className="flex flex-wrap items-center gap-2 pt-1" aria-label="Vị trí phụ đề mới">
                 <span className="mr-1 text-xs text-surface-500">Vị trí phụ đề:</span>
                 {(['top', 'center', 'bottom'] as const).map((position) => (
                   <button
                     key={position}
                     type="button"
                     onClick={() => handleSubtitlePositionChange(position)}
                     className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                       subtitlePosition === position
                         ? 'border-primary-500/50 bg-primary-500/15 text-primary-300'
                         : 'border-surface-700/60 bg-surface-800/50 text-surface-400 hover:border-surface-600 hover:text-surface-200'
                     }`}
                   >
                     {position === 'top' ? 'Trên' : position === 'center' ? 'Giữa' : 'Dưới'}
                   </button>
                 ))}
                 {subtitlePosition === 'custom' && <span className="text-xs text-accent-cyan">Tùy chỉnh</span>}
               </div>
            </div>
          )}
        </div>
      )}

      {/* Advanced Settings - visible in preview phase */}
      {workflowPhase === 'preview' && (
        <div className="glass-card">
          <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center justify-between w-full">
            <span className="flex items-center gap-2 text-surface-300">
              <Settings2 className="w-5 h-5" /> Cài đặt nâng cao
            </span>
            <ChevronDown className={`w-5 h-5 text-surface-500 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
          </button>
          {showAdvanced && (
            <div className="mt-4 pt-4 border-t border-surface-700/50 grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
              {/* Volume sliders */}
              <div className="md:col-span-2">
                <label className="text-sm text-surface-400 mb-3 block">Audio Mix Controls</label>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-surface-500">Dubbing Volume</span>
                      <span className="text-xs text-surface-500">{dubbingVolume.toFixed(1)}</span>
                    </div>
                    <input type="range" min="0.5" max="2.0" step="0.1" value={dubbingVolume} onChange={(e) => setDubbingVolume(parseFloat(e.target.value))} className="w-full accent-primary-500" />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-surface-500">Background Volume</span>
                      <span className="text-xs text-surface-500">{backgroundVolume.toFixed(1)}</span>
                    </div>
                    <input type="range" min="0.5" max="2.0" step="0.1" value={backgroundVolume} onChange={(e) => setBackgroundVolume(parseFloat(e.target.value))} className="w-full accent-primary-500" />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-surface-500">Original Vocals Volume</span>
                      <span className="text-xs text-surface-500">{originalVocalsVolume.toFixed(2)}</span>
                    </div>
                    <input type="range" min="0" max="0.5" step="0.01" value={originalVocalsVolume} onChange={(e) => setOriginalVocalsVolume(parseFloat(e.target.value))} className="w-full accent-primary-500" />
                  </div>
                </div>
              </div>
              <div>
                <label className="text-sm text-surface-400 mb-2 block">Whisper Model</label>
                <select value={whisperModel} onChange={(e) => setWhisperModel(e.target.value)} className="glass-input w-full appearance-none cursor-pointer">
                  {WHISPER_MODELS.map(model => <option key={model.id} value={model.id}>{model.name} - {model.size} ({model.speed})</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm text-surface-400 mb-2 block">Tốc độ giọng nói: {ttsSpeed}x</label>
                <input type="range" min="0.5" max="2" step="0.1" value={ttsSpeed} onChange={(e) => setTtsSpeed(parseFloat(e.target.value))} className="w-full accent-primary-500" />
                <div className="flex justify-between text-xs text-surface-500 mt-1">
                  <span>Chậm (0.5x)</span><span>Bình thường (1x)</span><span>Nhanh (2x)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="glass-card border-red-500/30 bg-red-500/10 animate-slide-up">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-red-400 font-medium">Lỗi</p>
              <p className="text-surface-400 text-sm">{error}</p>
            </div>
            {workflowPhase === 'error' && (
              <button onClick={handleReset} className="btn-ghost text-sm text-surface-400 hover:text-surface-200">
                Thử lại
              </button>
            )}
          </div>
        </div>
      )}

      {/* Video Preview - shown in preview and completed phases */}
      {(workflowPhase === 'preview' || workflowPhase === 'completed') && videoUrl && (
        <div className="space-y-3">
          <VideoPreview
            videoUrl={videoUrl}
            controls={workflowPhase === 'completed' || !editingBlurRegion}
            stageRef={workflowPhase === 'preview' ? previewStageRef : undefined}
            overlay={workflowPhase === 'preview' && subtitleEnabled && blurExistingSubtitles ? (
              <BlurRegionEditor
                stageRef={previewStageRef}
                region={blurRegion}
                subtitleY={subtitlePositionY}
                editing={editingBlurRegion}
                onRegionChange={handleBlurRegionChange}
                onSubtitleYChange={handleSubtitleYChange}
                onEditModeChange={setEditingBlurRegion}
              />
            ) : undefined}
          />
          {workflowPhase === 'completed' && (
            <div className="flex items-center justify-between flex-wrap gap-3">
              <span className="text-sm text-surface-400 flex items-center gap-2">
                <Video className="w-4 h-4" /> Xem trước kết quả
              </span>
              <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                <button onClick={handleDownloadOriginal} className="btn-primary inline-flex items-center justify-center gap-2 text-sm px-4 py-2">
                  <Download className="w-4 h-4" /> Tải video gốc
                </button>
                <button onClick={handleDownload} className="btn-primary inline-flex items-center justify-center gap-2 text-sm px-4 py-2">
                  <Download className="w-4 h-4" /> Tải video lồng tiếng
                </button>
              </div>
            </div>
          )}
          {workflowPhase === 'preview' && (
            <div className="flex items-center justify-between flex-wrap gap-3">
              <span className="text-sm text-surface-400 flex items-center gap-2">
                <Video className="w-4 h-4" /> Video gốc
              </span>
              <button onClick={handleDownloadOriginal} className="btn-primary inline-flex items-center justify-center gap-2 text-sm px-4 py-2 w-full sm:w-auto">
                <Download className="w-4 h-4" /> Tải video gốc
              </button>
            </div>
          )}
        </div>
      )}

      {/* Downloading indicator */}
      {workflowPhase === 'downloading' && (
        <div className="glass-card animate-slide-up">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
            </div>
            <div className="flex-1">
              <p className="text-surface-100 font-medium">Đang tải video...</p>
              <p className="text-sm text-surface-400">Vui lòng chờ trong giây lát</p>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Progress - shown during processing */}
      {workflowPhase === 'processing' && (
        <div className="glass-card animate-slide-up">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-12 h-12 rounded-xl bg-primary-500/20 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-surface-100">Đang lồng tiếng...</h3>
              <p className="text-surface-400 text-sm">Quá trình có thể mất vài phút</p>
            </div>
            <button
              onClick={handleCancel}
              disabled={cancelPending}
              className="btn-secondary inline-flex items-center gap-2 text-red-300 hover:text-red-200 border-red-500/30 hover:border-red-400/50 disabled:opacity-50"
            >
              {cancelPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
              {cancelPending ? 'Đang hủy...' : 'Hủy lồng tiếng'}
            </button>
          </div>
          <div className="space-y-3 sm:space-y-4">
            {steps.map((step) => {
              const Icon = step.icon
              return (
                <div key={step.id} className="flex items-center gap-3 sm:gap-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                    step.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400'
                    : step.status === 'active' ? 'bg-primary-500/20 text-primary-400 animate-pulse'
                    : step.status === 'error' ? 'bg-red-500/20 text-red-400'
                    : 'bg-surface-800 text-surface-500'
                  }`}>
                    {step.status === 'completed' ? <CheckCircle2 className="w-5 h-5" />
                    : step.status === 'active' ? <Loader2 className="w-5 h-5 animate-spin" />
                    : step.status === 'error' ? <XCircle className="w-5 h-5" />
                    : <Icon className="w-5 h-5" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium ${step.status === 'active' ? 'text-surface-100' : 'text-surface-400'}`}>{step.label}</span>
                      {step.status === 'active' && step.progress !== undefined && <span className="text-xs text-primary-400">{step.progress}%</span>}
                    </div>
                    {step.status === 'active' && (
                      <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-primary-500 to-accent-cyan rounded-full transition-all duration-300" style={{ width: `${step.progress || 0}%` }} />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Completed Result */}
      {workflowPhase === 'completed' && (
        <div className="glass-card animate-slide-up border-emerald-500/30">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-xl bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-surface-100">Hoàn thành!</h3>
              <p className="text-surface-400 text-sm">Video đã được lồng tiếng thành công</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button onClick={handleDownload} className="btn-primary inline-flex items-center gap-2">
              <Download className="w-4 h-4" /> Tải video
            </button>
            <button onClick={handleReset} className="btn-secondary inline-flex items-center gap-2">
              <RotateCcw className="w-4 h-4" /> Làm video mới
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
