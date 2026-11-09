import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { AlertTriangle, KeyRound, Loader2, Monitor, RefreshCw, ShieldCheck } from 'lucide-react'
import BrandMark from '@/components/brand/BrandMark'
import {
  activateLicense,
  getLicenseStatus,
  LICENSE_REQUIRED_EVENT,
  refreshLicense,
  type LicenseStatus,
} from '@/lib/license'

const POLL_INTERVAL_MS = 5 * 60 * 1000

/** Blocks the app behind an activation screen until the backend reports a valid license. */
export default function LicenseGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(async () => {
    try {
      setStatus(await getLicenseStatus())
      setLoadError('')
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : String(error))
    }
  }, [])

  useEffect(() => {
    void load()
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS)
    const onRequired = () => void load()
    window.addEventListener(LICENSE_REQUIRED_EVENT, onRequired)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener(LICENSE_REQUIRED_EVENT, onRequired)
    }
  }, [load])

  if (!status) {
    return (
      <FullScreen>
        {loadError ? (
          <div className="text-center space-y-4">
            <p className="text-red-300">{loadError}</p>
            <button className="btn-secondary" onClick={() => void load()}>Thử lại</button>
          </div>
        ) : (
          <Loader2 className="w-8 h-8 animate-spin text-primary-400" aria-label="Đang kiểm tra license" />
        )}
      </FullScreen>
    )
  }

  if (!status.enforced || status.allowed) return <>{children}</>
  return <ActivationScreen status={status} onChange={setStatus} />
}

function FullScreen({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-4">
      {children}
    </div>
  )
}

function ActivationScreen({ status, onChange }: { status: LicenseStatus; onChange: (s: LicenseStatus) => void }) {
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState<'activate' | 'refresh' | null>(null)
  const [error, setError] = useState('')
  const hasStoredKey = Boolean(status.key_hint)
  const canRetryOnline = hasStoredKey && ['offline_expired', 'clock_rollback'].includes(status.state)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!key.trim() || busy) return
    setBusy('activate')
    setError('')
    try {
      onChange(await activateLicense(key))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const retryOnline = async () => {
    setBusy('refresh')
    setError('')
    try {
      const next = await refreshLicense()
      onChange(next)
      if (!next.allowed) setError(next.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const showStatusNotice = status.state !== 'unlicensed' || hasStoredKey

  return (
    <FullScreen>
      <div className="glass-card w-full max-w-md space-y-6">
        <div className="flex flex-col items-center text-center gap-3">
          <BrandMark size="md" />
          <div>
            <h1 className="text-2xl font-bold text-surface-100">Kích hoạt VideoDub</h1>
            <p className="text-sm text-surface-400 mt-1">
              Nhập mã license bạn nhận được khi mua để sử dụng ứng dụng trên máy này.
            </p>
          </div>
        </div>

        {showStatusNotice && (
          <div className="flex gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p>{status.message}</p>
              {status.key_hint && <p className="text-amber-200/70">Mã đã lưu: {status.key_hint}</p>}
            </div>
          </div>
        )}

        {canRetryOnline && (
          <button
            type="button"
            onClick={() => void retryOnline()}
            disabled={busy !== null}
            className="btn-secondary w-full inline-flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {busy === 'refresh' ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Xác thực lại qua mạng
          </button>
        )}

        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="license-key" className="block text-sm font-medium text-surface-300">Mã license</label>
          <div className="relative">
            <KeyRound className="w-4 h-4 text-surface-500 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              id="license-key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="XXXX-XXXX-XXXX-XXXX"
              autoComplete="off"
              spellCheck={false}
              autoFocus
              disabled={busy !== null}
              className="glass-input w-full pl-11 font-mono"
            />
          </div>
          {error && <p className="text-sm text-red-300" role="alert">{error}</p>}
          <button
            type="submit"
            disabled={!key.trim() || busy !== null}
            className="btn-primary w-full inline-flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {busy === 'activate' ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
            {busy === 'activate' ? 'Đang kích hoạt…' : 'Kích hoạt'}
          </button>
        </form>

        <div className="space-y-2 border-t border-surface-700/50 pt-4 text-xs text-surface-400">
          <p className="flex items-center gap-2">
            <Monitor className="w-4 h-4" /> Thiết bị: <span className="text-surface-200">{status.device_name}</span>
          </p>
          <p>Mỗi license dùng trên một thiết bị. Cần kết nối mạng khi kích hoạt; sau đó có thể dùng ngoại tuyến tối đa 72 giờ giữa các lần xác thực.</p>
          <p>{status.contact}</p>
        </div>
      </div>
    </FullScreen>
  )
}
