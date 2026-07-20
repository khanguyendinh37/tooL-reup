import { useState, useEffect } from 'react'
import { Settings2, Mic2, Globe, Volume2, Save, RotateCcw, CheckCircle2, Cookie, Upload, Trash2 } from 'lucide-react'
import { WHISPER_MODELS, TTS_VOICES, LANGUAGES } from '@/lib/utils'
import { getAllCookiesStatus, uploadCookies, deleteCookies, getSettings, updateSettings } from '@/lib/api'

interface PlatformCookies {
  platform: string
  name: string
  domains: string[]
  has_cookies: boolean
}

interface AppSettings {
  whisper_model: string
  default_target_lang: string
  default_voice: string
  tts_speed: string
}

export default function Settings() {
  const [whisperModel, setWhisperModel] = useState('small')
  const [defaultTargetLang, setDefaultTargetLang] = useState('vi')
  const [ttsSpeed, setTtsSpeed] = useState(1)
  const [selectedVoice, setSelectedVoice] = useState('vi-VN-HoaiMyNeural')
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [platforms, setPlatforms] = useState<PlatformCookies[]>([])
  const [selectedPlatform, setSelectedPlatform] = useState('youtube')
  const [cookiesText, setCookiesText] = useState('')
  const [cookiesMessage, setCookiesMessage] = useState('')
  const [loading, setLoading] = useState(false)

  // Load settings on mount
  useEffect(() => {
    loadSettings()
    loadCookiesStatus()
  }, [])

  const loadSettings = async () => {
    try {
      const settings = await getSettings() as AppSettings
      setWhisperModel(settings.whisper_model || 'small')
      setDefaultTargetLang(settings.default_target_lang || 'vi')
      setSelectedVoice(settings.default_voice || 'vi-VN-HoaiMyNeural')
      setTtsSpeed(parseFloat(settings.tts_speed || '1.0'))
    } catch (err) {
      console.error('Failed to load settings:', err)
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
    try {
      await updateSettings({
        whisper_model: whisperModel,
        default_target_lang: defaultTargetLang,
        default_voice: selectedVoice,
        tts_speed: ttsSpeed.toString(),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save settings:', err)
      setCookiesMessage('Lỗi khi lưu cài đặt')
      setTimeout(() => setCookiesMessage(''), 3000)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    // Reset to defaults
    setWhisperModel('small')
    setDefaultTargetLang('vi')
    setSelectedVoice('vi-VN-HoaiMyNeural')
    setTtsSpeed(1)

    // Also persist to backend
    try {
      await updateSettings({
        whisper_model: 'small',
        default_target_lang: 'vi',
        default_voice: 'vi-VN-HoaiMyNeural',
        tts_speed: '1.0',
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to reset settings:', err)
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
    } catch {
      setCookiesMessage('Lỗi khi lưu cookies')
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
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-surface-100">Cài đặt</h2>
        <div className="flex items-center gap-3">
          <button onClick={handleReset} className="btn-secondary inline-flex items-center gap-2">
            <RotateCcw className="w-4 h-4" />
            Đặt lại
          </button>
          <button onClick={handleSave} disabled={saving} className="btn-primary inline-flex items-center gap-2 disabled:opacity-50">
            {saved ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                Đã lưu!
              </>
            ) : saving ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                Đang lưu...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                Lưu cài đặt
              </>
            )}
          </button>
        </div>
      </div>

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

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
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
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-accent-purple/20 flex items-center justify-center">
            <Globe className="w-5 h-5 text-accent-purple" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">Dịch thuật (Google Translate)</h3>
            <p className="text-sm text-surface-500">Cài đặt ngôn ngữ mặc định</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-sm text-surface-400 mb-2 block">Ngôn ngữ đích mặc định</label>
            <select
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

          <div>
            <label className="text-sm text-surface-400 mb-2 block">Engine dịch thuật</label>
            <div className="glass-input !bg-emerald-500/10 !border-emerald-500/30 !text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              Google Translate (Miễn phí, không cần API key)
            </div>
          </div>
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

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
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
            <p className="text-sm text-emerald-400">{cookiesMessage}</p>
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
