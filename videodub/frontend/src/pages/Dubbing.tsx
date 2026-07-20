import { useState, useEffect, useRef } from 'react'
import {
  Link, Download, Play, CheckCircle2, XCircle, Loader2,
  ChevronDown, Settings2, Video, RotateCcw, FileText, Bell, BellOff
} from 'lucide-react'
import { LANGUAGES, TTS_VOICES, WHISPER_MODELS, DEFAULT_SUBTITLE_CONFIG, type SubtitleConfig } from '@/lib/utils'
import { startDubbing, getDubbingStatus, getSettings } from '@/lib/api'
import { SubtitleEditor } from '@/components/SubtitleEditor'

type StepStatus = 'pending' | 'active' | 'completed' | 'error'

interface PipelineStep {
  id: string
  label: string
  icon: React.ElementType
  status: StepStatus
  progress?: number
}

const STATUS_STEP_MAP: Record<string, number> = {
  pending: -1,
  downloading: 0,
  transcribing: 1,
  translating: 2,
  tts: 3,
  removing_vocals: 4,
  merging: 5,
  completed: 6,
  error: -2,
}

export default function Dubbing() {
  const [url, setUrl] = useState('')
  const [sourceLang, setSourceLang] = useState('en')
  const [targetLang, setTargetLang] = useState('vi')
  const [selectedVoice, setSelectedVoice] = useState('vi-VN-HoaiMyNeural')
  const [whisperModel, setWhisperModel] = useState('small')
  const [ttsSpeed, setTtsSpeed] = useState(1.0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showSubtitleEditor] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [subtitleConfig, setSubtitleConfig] = useState<SubtitleConfig>(DEFAULT_SUBTITLE_CONFIG)
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const notificationRef = useRef<Notification | null>(null)

  const [steps, setSteps] = useState<PipelineStep[]>([
    { id: 'download', label: 'Tải video', icon: Download, status: 'pending' },
    { id: 'transcribe', label: 'Tạo phụ đề SRT', icon: Download, status: 'pending' },
    { id: 'translate', label: 'Dịch thuật', icon: Download, status: 'pending' },
    { id: 'tts', label: 'Tạo giọng lồng tiếng', icon: Download, status: 'pending' },
    { id: 'remove_vocal', label: 'Xóa giọng gốc', icon: Download, status: 'pending' },
    { id: 'merge', label: 'Ghép video + phụ đề', icon: Download, status: 'pending' },
  ])

  // Persist job state to localStorage for history navigation
  const saveJobState = () => {
    const state = {
      jobId,
      isProcessing,
      completed,
      videoUrl,
      error,
      steps: steps.map(s => ({ ...s })),
      url,
      sourceLang,
      targetLang,
      selectedVoice,
      whisperModel,
      ttsSpeed,
      subtitleConfig,
      timestamp: Date.now(),
    }
    localStorage.setItem('videodub_job_state', JSON.stringify(state))
  }

  const loadJobState = () => {
    const saved = localStorage.getItem('videodub_job_state')
    if (saved) {
      try {
        const state = JSON.parse(saved)
        // Only restore if recent (within 1 hour)
        if (Date.now() - state.timestamp < 3600000) {
          if (state.jobId) setJobId(state.jobId)
          if (state.isProcessing !== undefined) setIsProcessing(state.isProcessing)
          if (state.completed !== undefined) setCompleted(state.completed)
          if (state.videoUrl) setVideoUrl(state.videoUrl)
          if (state.error) setError(state.error)
          if (state.steps) setSteps(state.steps)
          if (state.url) setUrl(state.url)
          if (state.sourceLang) setSourceLang(state.sourceLang)
          if (state.targetLang) setTargetLang(state.targetLang)
          if (state.selectedVoice) setSelectedVoice(state.selectedVoice)
          if (state.whisperModel) setWhisperModel(state.whisperModel)
          if (state.ttsSpeed !== undefined) setTtsSpeed(state.ttsSpeed)
          if (state.subtitleConfig) setSubtitleConfig(state.subtitleConfig)
        }
      } catch (e) {
        console.error('Failed to load job state:', e)
      }
    }
  }

  const clearJobState = () => {
    localStorage.removeItem('videodub_job_state')
  }

  // Save state on changes
  useEffect(() => {
    if (isProcessing || completed) {
      saveJobState()
    } else {
      clearJobState()
    }
  }, [isProcessing, completed, jobId, videoUrl, error, steps])

  // Load state on mount
  useEffect(() => {
    loadJobState()
  }, [])

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
    // Load saved notification preference
    const saved = localStorage.getItem('notificationsEnabled')
    if (saved !== null) {
      setNotificationsEnabled(JSON.parse(saved))
    }
  }, [])

  const toggleNotifications = () => {
    const newValue = !notificationsEnabled
    setNotificationsEnabled(newValue)
    localStorage.setItem('notificationsEnabled', JSON.stringify(newValue))
    if (!notificationsEnabled && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }

  const showNotification = (title: string, body: string, icon?: string) => {
    if (!notificationsEnabled || !('Notification' in window) || Notification.permission !== 'granted') return
    if (notificationRef.current) {
      notificationRef.current.close()
    }
    notificationRef.current = new Notification(title, {
      body,
      icon: icon || '/favicon.ico',
      tag: 'videodub-completion',
      requireInteraction: true,
    })

    // Auto close after 10 seconds
    setTimeout(() => {
      if (notificationRef.current) {
        notificationRef.current.close()
      }
    }, 10000)

    // Focus window on click
    notificationRef.current.onclick = () => {
      window.focus()
      notificationRef.current?.close()
    }
  }

  // Load settings from backend on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const settings = await getSettings()
        setSourceLang(settings.default_target_lang || 'vi') // Using target_lang as source default
        setTargetLang(settings.default_target_lang || 'vi')
        setSelectedVoice(settings.default_voice || 'vi-VN-HoaiMyNeural')
        setWhisperModel(settings.whisper_model || 'small')
        setTtsSpeed(parseFloat(settings.tts_speed || '1.0'))
      } catch (err) {
        console.error('Failed to load settings:', err)
      } finally {
        setSettingsLoaded(true)
      }
    }
    loadSettings()
  }, [])

  // Update voice when target language changes, but keep user's manual selection
  const filteredVoices = TTS_VOICES.filter(v => v.lang === targetLang)

  useEffect(() => {
    if (filteredVoices.length > 0 && settingsLoaded) {
      // Check if current voice is valid for new language
      const currentVoiceValid = filteredVoices.some(v => v.id === selectedVoice)
      if (!currentVoiceValid) {
        // Set to first available voice for the new language
        setSelectedVoice(filteredVoices[0].id)
      }
    }
  }, [targetLang, filteredVoices, settingsLoaded, selectedVoice])

  const updateStepsFromStatus = (status: string, progress: number) => {
    const activeIdx = STATUS_STEP_MAP[status] ?? -1
    setSteps(prev =>
      prev.map((s, idx) => ({
        ...s,
        status: idx < activeIdx ? 'completed'
          : idx === activeIdx ? (status === 'error' ? 'error' : 'active')
          : 'pending',
        progress: idx === activeIdx ? progress : (idx < activeIdx ? 100 : undefined),
      }))
    )
  }

  const handleStart = async () => {
    if (!url.trim()) return
    // Clear previous job state when starting new job
    clearJobState()
    setIsProcessing(true)
    setError(null)
    setCompleted(false)
    setVideoUrl(null)

    try {
      const result = await startDubbing({
        url,
        source_lang: sourceLang,
        target_lang: targetLang,
        voice: selectedVoice,
        whisper_model: whisperModel,
        tts_speed: ttsSpeed,
        subtitle_config: subtitleConfig,
      })
      setJobId(result.id)

      const pollInterval = setInterval(async () => {
        try {
          const status = await getDubbingStatus(result.id)
          updateStepsFromStatus(status.status, status.progress)

          if (status.status === 'completed') {
            clearInterval(pollInterval)
            setIsProcessing(false)
            setCompleted(true)
            // Create video URL for preview
            setVideoUrl(`/api/dubbing/${result.id}/download`)
            // Show completion notification
            showNotification(
              'VideoDub - Hoàn thành!',
              'Video lồng tiếng đã xử lý xong. Nhấn để xem kết quả.',
              '/favicon.ico'
            )
          } else if (status.status === 'error') {
            clearInterval(pollInterval)
            setIsProcessing(false)
            const errorMsg = status.error || 'Đã xảy ra lỗi khi xử lý video'
            setError(errorMsg)
            // Show error notification
            showNotification(
              'VideoDub - Lỗi!',
              `Xử lý thất bại: ${errorMsg}`,
              '/favicon.ico'
            )
          }
        } catch {
          clearInterval(pollInterval)
          setIsProcessing(false)
          setError('Không thể kết nối đến server')
        }
      }, 2000)
    } catch (err) {
      setIsProcessing(false)
      const errorMsg = err instanceof Error ? err.message : 'Không thể bắt đầu xử lý'
      setError(errorMsg)
      showNotification('VideoDub - Lỗi!', errorMsg, '/favicon.ico')
    }
  }

  const handleDownload = () => {
    if (jobId) {
      window.open(`/api/dubbing/${jobId}/download`, '_blank')
    }
  }

  const handleReprocess = () => {
    // Clear job state before reprocessing
    clearJobState()
    setCompleted(false)
    setVideoUrl(null)
    handleStart()
  }

  const handleResetSubtitle = () => {
    setSubtitleConfig(DEFAULT_SUBTITLE_CONFIG)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* URL Input */}
      <div className="glass-card">
        <h3 className="text-lg font-semibold text-surface-100 mb-4 flex items-center gap-2">
          <Link className="w-5 h-5 text-primary-400" />
          Nhập link video
        </h3>
        <div className="flex gap-3">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=... hoặc link từ bất kỳ nền tảng nào"
            className="glass-input flex-1"
          />
          <button
            onClick={handleStart}
            disabled={!url.trim() || isProcessing}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Đang xử lý...
              </>
            ) : (
              <>
                <Play className="w-5 h-5" />
                Bắt đầu
              </>
            )}
          </button>
        </div>
      </div>

      {/* Language Selection */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card">
          <label className="text-sm text-surface-400 mb-2 block">Ngôn ngữ gốc</label>
          <select
            value={sourceLang}
            onChange={(e) => setSourceLang(e.target.value)}
            className="glass-input w-full appearance-none cursor-pointer"
          >
            {LANGUAGES.map(lang => (
              <option key={lang.code} value={lang.code}>
                {lang.flag} {lang.name}
              </option>
            ))}
          </select>
        </div>

        <div className="glass-card">
          <label className="text-sm text-surface-400 mb-2 block">Ngôn ngữ đích</label>
          <select
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
            className="glass-input w-full appearance-none cursor-pointer"
          >
            {LANGUAGES.map(lang => (
              <option key={lang.code} value={lang.code}>
                {lang.flag} {lang.name}
              </option>
            ))}
          </select>
        </div>

        <div className="glass-card">
          <label className="text-sm text-surface-400 mb-2 block">Giọng lồng tiếng</label>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="glass-input w-full appearance-none cursor-pointer"
          >
            {filteredVoices.map(voice => (
              <option key={voice.id} value={voice.id}>
                {voice.name} ({voice.gender === 'female' ? 'Nữ' : 'Nam'})
              </option>
            ))}
            {filteredVoices.length === 0 && (
              <option value="">Không có giọng cho ngôn ngữ này</option>
            )}
          </select>
        </div>
      </div>

      {/* Subtitle Editor Toggle */}
      <div className="glass-card">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-3 flex-1">
            <FileText className="w-5 h-5 text-primary-400" />
            <span className="text-surface-300">Cài đặt phụ đề</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={subtitleConfig.enabled}
                onChange={(e) => setSubtitleConfig({ ...subtitleConfig, enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-surface-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-500/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
            </label>
            <span className="text-sm text-surface-500">({subtitleConfig.enabled ? 'Bật' : 'Tắt'})</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleNotifications}
              className="btn-ghost !p-2 text-surface-400 hover:text-surface-200"
              title={notificationsEnabled ? 'Tắt thông báo hoàn thành' : 'Bật thông báo hoàn thành'}
            >
              {notificationsEnabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
            </button>
            <ChevronDown
              className={`w-5 h-5 text-surface-500 transition-transform ${showSubtitleEditor ? 'rotate-180' : ''}`}
            />
          </div>
        </div>

        {showSubtitleEditor && (
          <div className="mt-4 pt-4 border-t border-surface-700/50">
            <SubtitleEditor
              config={subtitleConfig}
              onChange={setSubtitleConfig}
              onReset={handleResetSubtitle}
            />
          </div>
        )}
      </div>

      {/* Advanced Settings */}
      <div className="glass-card">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center justify-between w-full"
        >
          <span className="flex items-center gap-2 text-surface-300">
            <Settings2 className="w-5 h-5" />
            Cài đặt nâng cao
          </span>
          <ChevronDown
            className={`w-5 h-5 text-surface-500 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
          />
        </button>

        {showAdvanced && (
          <div className="mt-4 pt-4 border-t border-surface-700/50 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-surface-400 mb-2 block">Whisper Model</label>
              <select
                value={whisperModel}
                onChange={(e) => setWhisperModel(e.target.value)}
                className="glass-input w-full appearance-none cursor-pointer"
              >
                {WHISPER_MODELS.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} - {model.size} ({model.speed})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-surface-400 mb-2 block">Tốc độ giọng nói: {ttsSpeed}x</label>
              <input
                type="range"
                min="0.5"
                max="2"
                step="0.1"
                value={ttsSpeed}
                onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
                className="w-full accent-primary-500"
              />
              <div className="flex justify-between text-xs text-surface-500 mt-1">
                <span>Chậm (0.5x)</span>
                <span>Bình thường (1x)</span>
                <span>Nhanh (2x)</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="glass-card border-red-500/30 bg-red-500/10 animate-slide-up">
          <div className="flex items-center gap-3">
            <XCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
            <div>
              <p className="text-red-400 font-medium">Lỗi</p>
              <p className="text-surface-400 text-sm">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Progress */}
      {isProcessing && (
        <div className="glass-card animate-slide-up">
          <h3 className="text-lg font-semibold text-surface-100 mb-6">Tiến trình xử lý</h3>
          <div className="space-y-4">
            {steps.map((step) => {
              const Icon = step.icon
              return (
                <div key={step.id} className="flex items-center gap-4">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                      step.status === 'completed'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : step.status === 'active'
                        ? 'bg-primary-500/20 text-primary-400 animate-pulse'
                        : step.status === 'error'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-surface-800 text-surface-500'
                    }`}
                  >
                    {step.status === 'completed' ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : step.status === 'active' ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : step.status === 'error' ? (
                      <XCircle className="w-5 h-5" />
                    ) : (
                      <Icon className="w-5 h-5" />
                    )}
                  </div>

                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-sm font-medium ${
                        step.status === 'active' ? 'text-surface-100' : 'text-surface-400'
                      }`}>
                        {step.label}
                      </span>
                      {step.status === 'active' && step.progress !== undefined && (
                        <span className="text-xs text-primary-400">{step.progress}%</span>
                      )}
                    </div>
                    {step.status === 'active' && (
                      <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-primary-500 to-accent-cyan rounded-full transition-all duration-300"
                          style={{ width: `${step.progress || 0}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Completed Result with Video Preview */}
      {completed && (
        <div className="glass-card animate-slide-up border-emerald-500/30">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-xl bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-surface-100">Hoàn thành!</h3>
              <p className="text-surface-400 text-sm">Video đã được lồng tiếng thành công</p>
            </div>
          </div>

          {/* Video Preview */}
          {videoUrl && (
            <div className="mb-6 rounded-xl overflow-hidden bg-surface-900 border border-surface-700">
              <div className="relative" style={{ paddingTop: '56.25%' }}>
                <video
                  src={videoUrl}
                  controls
                  className="absolute top-0 left-0 w-full h-full"
                  style={{ objectFit: 'contain' }}
                />
              </div>
              <div className="p-3 bg-surface-900/50 border-t border-surface-700 flex items-center justify-between">
                <span className="text-sm text-surface-300 flex items-center gap-2">
                  <Video className="w-4 h-4" />
                  Xem trước kết quả
                </span>
                <button
                  onClick={handleDownload}
                  className="btn-primary inline-flex items-center gap-2 text-sm px-4 py-2"
                >
                  <Download className="w-4 h-4" />
                  Tải video
                </button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button onClick={handleDownload} className="btn-primary inline-flex items-center gap-2">
              <Download className="w-4 h-4" />
              Tải video
            </button>
            <button onClick={handleReprocess} className="btn-secondary inline-flex items-center gap-2">
              <RotateCcw className="w-4 h-4" />
              Làm lại
            </button>
          </div>
        </div>
      )}
    </div>
  )
}