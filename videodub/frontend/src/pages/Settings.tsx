import { useState, useEffect } from 'react'
import { Settings2, Mic2, Globe, Volume2, Save, RotateCcw, CheckCircle2, Cookie, Upload, Trash2, Bell } from 'lucide-react'
import { WHISPER_MODELS, TTS_VOICES, LANGUAGES } from '@/lib/utils'
import { getAllCookiesStatus, uploadCookies, deleteCookies, getSettings, testTranslationConnection, updateSettings } from '@/lib/api'
import TranslationAiRoute from '@/components/settings/TranslationAiRoute'
import { getTranslationProvider, type TranslationConnectionStatus, type TranslationModelOption, type TranslationProviderId } from '@/lib/translation'

interface PlatformCookies {
  platform: string
  name: string
  domains: string[]
  has_cookies: boolean
}

interface AppSettings {
  whisper_model: string
  default_source_lang: string
  default_target_lang: string
  default_voice: string
  tts_speed: string
  notifications_enabled: boolean
  default_dubbing_volume: number
  default_background_volume: number
  default_original_volume: number
  translation_provider?: TranslationProviderId
  translation_model?: string
  translation_endpoint?: string
  translation_api_key_set?: boolean
  translation_api_key_hint?: string
  translation_key_verified?: boolean
  translation_models?: TranslationModelOption[]
}

export default function Settings() {
  const [whisperModel, setWhisperModel] = useState('small')
  const [defaultSourceLang, setDefaultSourceLang] = useState('en')
  const [defaultTargetLang, setDefaultTargetLang] = useState('vi')
  const [ttsSpeed, setTtsSpeed] = useState(1)
  const [selectedVoice, setSelectedVoice] = useState('vi-VN-HoaiMyNeural')
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [platforms, setPlatforms] = useState<PlatformCookies[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState('youtube')
  const [cookiesText, setCookiesText] = useState('')
  const [cookiesMessage, setCookiesMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [dubbingVolume, setDubbingVolume] = useState(2.0)
  const [backgroundVolume, setBackgroundVolume] = useState(1.0)
  const [originalVocalsVolume, setOriginalVocalsVolume] = useState(0.1)
  const [translationProvider, setTranslationProvider] = useState<TranslationProviderId>('google')
  const [translationModel, setTranslationModel] = useState('google-free')
  const [translationEndpoint, setTranslationEndpoint] = useState('')
  const [translationApiKeySet, setTranslationApiKeySet] = useState(false)
  const [translationApiKeyHint, setTranslationApiKeyHint] = useState('')
  const [translationApiKeyDraft, setTranslationApiKeyDraft] = useState('')
  const [translationClearApiKey, setTranslationClearApiKey] = useState(false)
  const [translationModels, setTranslationModels] = useState<TranslationModelOption[]>([])
  const [translationModelsUnlocked, setTranslationModelsUnlocked] = useState(true)
  const [translationConnectionStatus, setTranslationConnectionStatus] = useState<TranslationConnectionStatus>('idle')
  const [translationConnectionMessage, setTranslationConnectionMessage] = useState('')
  const [settingsError, setSettingsError] = useState('')

  // Load settings on mount
  useEffect(() => {
    loadSettings()
    loadCookiesStatus()
  }, [])

  const loadSettings = async () => {
    try {
      const settings = await getSettings() as AppSettings
      setWhisperModel(settings.whisper_model || 'small')
      setDefaultSourceLang(settings.default_source_lang || 'en')
      setDefaultTargetLang(settings.default_target_lang || 'vi')
      setSelectedVoice(settings.default_voice || 'vi-VN-HoaiMyNeural')
      setTtsSpeed(parseFloat(settings.tts_speed || '1.0'))
      setNotificationsEnabled(String(settings.notifications_enabled) === 'true')
      setDubbingVolume(parseFloat(String(settings.default_dubbing_volume ?? 2.0)))
      setBackgroundVolume(parseFloat(String(settings.default_background_volume ?? 1.0)))
      setOriginalVocalsVolume(parseFloat(String(settings.default_original_volume ?? 0.1)))
      setTranslationProvider((settings.translation_provider as TranslationProviderId) || 'google')
      setTranslationModel(settings.translation_model || getTranslationProvider(settings.translation_provider).defaultModel)
      setTranslationEndpoint(settings.translation_endpoint || '')
      const hasSavedTranslationKey = Boolean(settings.translation_api_key_set)
      const savedTranslationModels = Array.isArray(settings.translation_models)
        ? settings.translation_models as TranslationModelOption[]
        : []
      const savedTranslationVerified = Boolean(settings.translation_key_verified)
      const savedTranslationProvider = (settings.translation_provider as TranslationProviderId) || 'google'
      setTranslationProvider(savedTranslationProvider)
      setTranslationModel(settings.translation_model || getTranslationProvider(savedTranslationProvider).defaultModel)
      setTranslationEndpoint(settings.translation_endpoint || '')
      setTranslationApiKeySet(hasSavedTranslationKey)
      setTranslationApiKeyHint(settings.translation_api_key_hint || '')
      setTranslationModels(savedTranslationModels)
      setTranslationModelsUnlocked(savedTranslationProvider === 'google' || (hasSavedTranslationKey && savedTranslationVerified && savedTranslationModels.length > 0))
      setTranslationConnectionStatus(savedTranslationProvider !== 'google' && hasSavedTranslationKey && savedTranslationVerified && savedTranslationModels.length > 0 ? 'connected' : 'idle')
      setTranslationConnectionMessage(savedTranslationProvider !== 'google' && hasSavedTranslationKey && savedTranslationVerified
        ? `Đã tải ${savedTranslationModels.length} model đã xác thực.`
        : '')
      setTranslationApiKeyDraft('')
      setTranslationClearApiKey(false)
    } catch (err) {
      console.error('Failed to load settings:', err)
      setSettingsError('Không tải được cấu hình đã lưu. Thử lại sau.')
    }
  }

  const loadCookiesStatus = async () => {
    try {
      const status = await getAllCookiesStatus()
      setPlatforms(status)
    } catch {}
  }

  const handleSave = async () => {
    setSaving(true)
    setSettingsError('')
    try {
      await updateSettings({
        whisper_model: whisperModel,
        default_source_lang: defaultSourceLang,
        default_target_lang: defaultTargetLang,
        default_voice: selectedVoice,
        tts_speed: ttsSpeed.toString(),
        notifications_enabled: notificationsEnabled,
        default_dubbing_volume: dubbingVolume,
        default_background_volume: backgroundVolume,
        default_original_volume: originalVocalsVolume,
        translation_provider: translationProvider,
        translation_model: translationModel,
        translation_endpoint: translationEndpoint,
        translation_key_verified: translationProvider === 'google'
          ? false
          : translationConnectionStatus === 'connected' && translationModelsUnlocked,
        translation_models: translationProvider === 'google' ? [] : translationModels,
        ...(translationApiKeyDraft.trim() ? { translation_api_key: translationApiKeyDraft.trim() } : {}),
        ...(translationClearApiKey ? { translation_clear_api_key: true } : {}),
      })
      if (translationApiKeyDraft.trim()) {
        setTranslationApiKeySet(true)
        setTranslationApiKeyHint(`••••${translationApiKeyDraft.trim().slice(-4)}`)
      }
      if (translationClearApiKey) {
        setTranslationApiKeySet(false)
        setTranslationApiKeyHint('')
      }
      setTranslationApiKeyDraft('')
      setTranslationClearApiKey(false)
      setTranslationConnectionStatus(translationProvider === 'google' ? 'idle' : translationConnectionStatus)
      setTranslationConnectionMessage(translationProvider === 'google' ? '' : translationConnectionMessage)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save settings:', err)
      setSettingsError(err instanceof Error ? err.message : 'Không thể lưu cài đặt. Thử lại.')
    } finally {
      setSaving(false)
    }
  }

  const handleConnectTranslation = async () => {
    setTranslationConnectionStatus('connecting')
    setTranslationModelsUnlocked(false)
    setTranslationConnectionMessage('')
    try {
      const result = await testTranslationConnection({
        translation_provider: translationProvider,
        translation_model: translationModel || undefined,
        translation_endpoint: translationEndpoint,
        ...(translationApiKeyDraft.trim() ? { translation_api_key: translationApiKeyDraft.trim() } : {}),
      })
      if (result.ok && !result.used_fallback && result.models.length > 0) {
        const selectedModel = result.model || result.models[0].id
        setTranslationModels(result.models)
        setTranslationModelsUnlocked(true)
        setTranslationModel(selectedModel)
        setTranslationApiKeySet(true)
        setTranslationApiKeyHint(
          translationApiKeyDraft.trim()
            ? `••••${translationApiKeyDraft.trim().slice(-4)}`
            : translationApiKeyHint,
        )
        setTranslationConnectionStatus('connected')
        setTranslationConnectionMessage(`Đã tải ${result.models.length} model phù hợp và đã lưu route.`)
      } else {
        setTranslationModels([])
        setTranslationModelsUnlocked(false)
        setTranslationConnectionStatus('error')
        setTranslationConnectionMessage(result.message || 'Không thể xác thực API key. Google Translate vẫn được dùng làm dự phòng.')
      }
    } catch (err) {
      setTranslationModels([])
      setTranslationModelsUnlocked(false)
      setTranslationConnectionStatus('error')
      setTranslationConnectionMessage(err instanceof Error ? err.message : 'Không thể xác thực API key. Google Translate vẫn được dùng làm dự phòng.')
    }
  }

  const handleReset = async () => {
    setSettingsError('')
    // Reset to defaults
    setWhisperModel('small')
    setDefaultSourceLang('en')
    setDefaultTargetLang('vi')
    setSelectedVoice('vi-VN-HoaiMyNeural')
    setTtsSpeed(1)
    setNotificationsEnabled(true)
    localStorage.setItem('notificationsEnabled', JSON.stringify(true))
    setDubbingVolume(1.0)
    setBackgroundVolume(1.0)
    setOriginalVocalsVolume(0.3)
    setTranslationProvider('google')
    setTranslationModel('google-free')
    setTranslationEndpoint('')
    setTranslationApiKeyDraft('')
    setTranslationApiKeySet(false)
    setTranslationApiKeyHint('')
    setTranslationClearApiKey(true)
    setTranslationModels([])
    setTranslationModelsUnlocked(true)
    setTranslationConnectionStatus('idle')
    setTranslationConnectionMessage('')

    // Also persist to backend
    try {
      await updateSettings({
        whisper_model: 'small',
        default_source_lang: 'en',
        default_target_lang: 'vi',
        default_voice: 'vi-VN-HoaiMyNeural',
        tts_speed: '1.0',
        notifications_enabled: true,
        default_dubbing_volume: 1.0,
        default_background_volume: 1.0,
        default_original_volume: 0.3,
        translation_provider: 'google',
        translation_model: 'google-free',
        translation_endpoint: '',
        translation_key_verified: false,
        translation_models: [],
        translation_clear_api_key: true,
      })
      setTranslationClearApiKey(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to reset settings:', err)
      setSettingsError(err instanceof Error ? err.message : 'Không thể đặt lại cài đặt. Thử lại.')
    }
  }

  const handleUploadCookies = async () => {
    if (!cookiesText.trim()) return
    setLoading(true)
    try {
      await uploadCookies(selectedPlatform, cookiesText)
      setCookiesMessage(`Đã lưu cookies cho ${platforms.find(p => p.platform === selectedPlatform)?.name || selectedPlatform}!`)
      setCookiesText('')
      loadCookiesStatus()
      setTimeout(() => setCookiesMessage(''), 3000)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Lỗi khi lưu cookies'
      setCookiesMessage(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteCookies = async (platform: string) => {
    try {
      await deleteCookies(platform)
      setCookiesMessage(`Đã xóa cookies cho ${platforms.find(p => p.platform === platform)?.name || platform}`)
      loadCookiesStatus()
      setTimeout(() => setCookiesMessage(''), 3000)
    } catch {
      setCookiesMessage('Lỗi khi xóa cookies')
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xl sm:text-2xl font-bold text-surface-100">Cài đặt</h2>
        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <button onClick={handleReset} className="btn-secondary inline-flex items-center gap-2 text-sm sm:text-base">
            <RotateCcw className="w-4 h-4" />
            <span className="hidden sm:inline">Đặt lại</span>
          </button>
          <button onClick={handleSave} disabled={saving} className="btn-primary inline-flex items-center gap-2 disabled:opacity-50 text-sm sm:text-base">
            {saved ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span className="hidden sm:inline">Đã lưu!</span>
              </>
            ) : saving ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                <span className="hidden sm:inline">Đang lưu...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span className="hidden sm:inline">Lưu cài đặt</span>
              </>
            )}
          </button>
        </div>
      </div>
      {settingsError && (
        <p role="alert" className="-mt-3 text-sm text-red-300">{settingsError}</p>
      )}

      {/* Whisper Settings */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <Mic2 className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Speech-to-Text (Whisper)</h3>
            <p className="text-sm text-surface-500">Chọn model nhận dạng giọng nói</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {WHISPER_MODELS.map(model => (
            <button
              key={model.id}
              onClick={() => setWhisperModel(model.id)}
              className={`p-4 rounded-xl border text-left transition-all ${
                whisperModel === model.id
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-surface-700/50 hover:border-surface-600'
              }`}
            >
              <div className="font-medium text-surface-100">{model.name}</div>
              <div className="text-xs text-surface-500 mt-1">
                {model.size} • {model.speed}
              </div>
              <div className="text-xs text-surface-400 mt-1">{model.quality}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Audio Mix Controls */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center">
            <Volume2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Audio Mix Controls</h3>
            <p className="text-sm text-surface-500">Điều chỉnh âm lượng khi ghép video</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Dubbing Volume - Controls dubbed_audio_boosted.wav */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-surface-400">Dubbing Volume (dubbed_audio_boosted.wav)</label>
              <span className="text-sm text-surface-500">{dubbingVolume.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={dubbingVolume}
              onChange={(e) => setDubbingVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Background Volume - Controls no_vocals_normalized.wav */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-surface-400">Background Volume (no_vocals_normalized.wav)</label>
              <span className="text-sm text-surface-500">{backgroundVolume.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={backgroundVolume}
              onChange={(e) => setBackgroundVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Original Volume - Controls vocals in final_audio.wav */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-surface-400">Original Volume (vocals in final_audio.wav)</label>
              <span className="text-sm text-surface-500">{originalVocalsVolume.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1.0"
              step="0.05"
              value={originalVocalsVolume}
              onChange={(e) => setOriginalVocalsVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </div>

      {/* TTS Settings */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-accent-cyan/20 flex items-center justify-center">
            <Volume2 className="w-5 h-5 text-accent-cyan" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Text-to-Speech (Edge TTS)</h3>
            <p className="text-sm text-surface-500">Cài đặt giọng nói lồng tiếng</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-sm text-surface-400 mb-2 block">Giọng nói mặc định</label>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="glass-input w-full appearance-none cursor-pointer"
            >
              {TTS_VOICES.map(voice => (
                <option key={voice.id} value={voice.id}>
                  {voice.name} ({voice.lang.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm text-surface-400 mb-2 block">
              Tốc độ nói: {ttsSpeed}x
            </label>
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
              <span>Chậm</span>
              <span>Bình thường</span>
              <span>Nhanh</span>
            </div>
          </div>
        </div>
      </div>

      {/* Translation Settings */}
      <div className="glass-card">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-purple/20">
            <Globe className="h-5 w-5 text-accent-purple" aria-hidden="true" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Dịch thuật</h3>
            <p className="text-sm text-surface-500">Chọn ngôn ngữ và cách dịch mặc định</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:gap-4 rounded-xl bg-surface-800/35 p-3 sm:p-4 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:items-end md:gap-3">
          <div>
            <label htmlFor="default-source-language" className="mb-2 block text-sm text-surface-400">Ngôn ngữ nguồn mặc định</label>
            <select
              id="default-source-language"
              value={defaultSourceLang}
              onChange={(e) => setDefaultSourceLang(e.target.value)}
              className="glass-input w-full appearance-none cursor-pointer"
            >
              {LANGUAGES.map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-center text-surface-600 md:pb-3" aria-hidden="true">→</div>
          <div>
            <label htmlFor="default-target-language" className="mb-2 block text-sm text-surface-400">Ngôn ngữ đích mặc định</label>
            <select
              id="default-target-language"
              value={defaultTargetLang}
              onChange={(e) => setDefaultTargetLang(e.target.value)}
              className="glass-input w-full appearance-none cursor-pointer"
            >
              {LANGUAGES.map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <TranslationAiRoute
          provider={translationProvider}
          model={translationModel}
          endpoint={translationEndpoint}
          hasSavedKey={translationApiKeySet}
          apiKeyDraft={translationApiKeyDraft}
          apiKeyHint={translationApiKeyHint}
          clearApiKey={translationClearApiKey}
          models={translationModels}
          modelsUnlocked={translationModelsUnlocked}
          connectionStatus={translationConnectionStatus}
          connectionMessage={translationConnectionMessage}
          onProviderChange={(nextProvider) => {
            setTranslationProvider(nextProvider)
            setTranslationModel(getTranslationProvider(nextProvider).defaultModel)
            setTranslationModels([])
            setTranslationModelsUnlocked(nextProvider === 'google')
            setTranslationConnectionStatus('idle')
            setTranslationConnectionMessage('')
          }}
          onModelChange={(nextModel) => {
            setTranslationModel(nextModel)
          }}
          onEndpointChange={(nextEndpoint) => {
            setTranslationEndpoint(nextEndpoint)
            setTranslationModels([])
            setTranslationModelsUnlocked(false)
            setTranslationConnectionStatus('idle')
            setTranslationConnectionMessage('')
          }}
          onApiKeyChange={(nextKey) => {
            setTranslationApiKeyDraft(nextKey)
            setTranslationModels([])
            setTranslationModelsUnlocked(false)
            setTranslationConnectionStatus('idle')
            setTranslationConnectionMessage('')
          }}
          onClearKeyChange={(clear) => {
            setTranslationClearApiKey(clear)
            if (clear) {
              setTranslationModels([])
              setTranslationModelsUnlocked(false)
              setTranslationConnectionStatus('idle')
              setTranslationConnectionMessage('')
            }
          }}
          onConnect={() => void handleConnectTranslation()}
        />
      </div>

      {/* Notification Settings */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
            <Bell className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Thông báo</h3>
            <p className="text-sm text-surface-500">Cài đặt thông báo hoàn thành xử lý video</p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-surface-100">Thông báo trình duyệt</p>
            <p className="text-sm text-surface-500">Nhận thông báo và âm thanh khi video xử lý xong</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={notificationsEnabled}
              onChange={(e) => {
                const enabled = e.target.checked
                setNotificationsEnabled(enabled)
                localStorage.setItem('notificationsEnabled', JSON.stringify(enabled))
              }}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-surface-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-500/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
          </label>
        </div>
      </div>

      {/* System Info */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-surface-700 flex items-center justify-center">
            <Settings2 className="w-5 h-5 text-surface-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Thông tin hệ thống</h3>
            <p className="text-sm text-surface-500">Trạng thái các thành phần</p>
          </div>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[
            { name: 'faster-whisper', status: 'installed', version: 'v3.1.0' },
            { name: 'edge-tts', status: 'installed', version: 'v6.1.9' },
            { name: 'deep-translator', status: 'installed', version: 'v1.11.4' },
            { name: 'demucs', status: 'installed', version: 'v4.0.1' },
          ].map(comp => (
            <div key={comp.name} className="p-3 rounded-xl bg-surface-800/50">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-sm font-medium text-surface-200">{comp.name}</span>
              </div>
              <span className="text-xs text-surface-500">{comp.version}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Cookies Management */}
      <div className="glass-card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
            <Cookie className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Cookies cho nền tảng video</h3>
            <p className="text-sm text-surface-500">Thêm cookies để bypass restrictions khi tải video</p>
          </div>
        </div>

        {/* Platform Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4 sm:mb-6">
          {platforms.map((p) => (
            <div
              key={p.platform}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                selectedPlatform === p.platform
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-surface-700/50 hover:border-surface-600'
              }`}
              onClick={() => setSelectedPlatform(p.platform)}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-surface-100">{p.name}</span>
                {p.has_cookies ? (
                  <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400">
                    Đã có
                  </span>
                ) : (
                  <span className="text-xs px-2 py-1 rounded-full bg-surface-700 text-surface-400">
                    Chưa có
                  </span>
                )}
              </div>
              <p className="text-xs text-surface-500 mt-1">{p.domains.join(', ')}</p>
            </div>
          ))}
        </div>

        {/* Upload Section */}
        <div className="space-y-4">
          <div>
            <label className="text-sm text-surface-400 mb-2 block">
              Dán cookies.txt cho <strong>{platforms.find(p => p.platform === selectedPlatform)?.name || selectedPlatform}</strong>
            </label>
            <textarea
              value={cookiesText}
              onChange={(e) => setCookiesText(e.target.value)}
              placeholder={`# Netscape HTTP Cookie File\n.${platforms.find(p => p.platform === selectedPlatform)?.domains[0] || 'example.com'}\tTRUE\t/\tFALSE\t0\tcookie_name\tcookie_value\n...`}
              className="glass-input w-full h-32 font-mono text-xs"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleUploadCookies}
              disabled={!cookiesText.trim() || loading}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
            >
              <Upload className="w-4 h-4" />
              {loading ? 'Đang lưu...' : 'Lưu cookies'}
            </button>
            {platforms.find(p => p.platform === selectedPlatform)?.has_cookies && (
              <button
                onClick={() => handleDeleteCookies(selectedPlatform)}
                className="btn-secondary inline-flex items-center gap-2 text-red-400 hover:text-red-300"
              >
                <Trash2 className="w-4 h-4" />
                Xóa cookies
              </button>
            )}
          </div>

          {cookiesMessage && (
            <p className={`text-sm ${cookiesMessage.includes('Lỗi') || cookiesMessage.includes('error') ? 'text-red-400' : 'text-emerald-400'}`}>{cookiesMessage}</p>
          )}

          <div className="text-xs text-surface-500 space-y-2 mt-4">
            <p><strong>Hướng dẫn lấy cookies:</strong></p>
            <ol className="list-decimal list-inside space-y-1">
              <li>Cài extension <strong>"Get cookies.txt LOCALLY"</strong> trên Chrome/Firefox</li>
              <li>Đăng nhập vào nền tảng bạn muốn tải video</li>
              <li>Mở extension, chọn <strong>"Export"</strong> để tải file cookies.txt</li>
              <li>Chọn nền tảng phù hợp ở trên, dán nội dung file và bấm <strong>"Lưu cookies"</strong></li>
            </ol>
            <p className="mt-2 text-surface-400">
              <strong>Lưu ý:</strong> Cookies sẽ hết hạn sau một thời gian. Nếu download bị lỗi, hãy export cookies mới.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
