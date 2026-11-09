import { useEffect, useState } from 'react'
import { Loader2, RefreshCw, ShieldCheck } from 'lucide-react'
import { formatLicenseDate, getLicenseStatus, refreshLicense, type LicenseStatus } from '@/lib/license'

/** License summary for the Settings page; hidden in internal (unlicensed) runs. */
export default function LicenseCard() {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    getLicenseStatus().then(setStatus).catch(() => setStatus(null))
  }, [])

  if (!status || !status.enforced) return null

  const recheck = async () => {
    setBusy(true)
    setMessage('')
    try {
      const next = await refreshLicense()
      setStatus(next)
      setMessage(next.offline ? 'Chưa kết nối được máy chủ license, đang dùng chế độ ngoại tuyến.' : 'Đã xác thực license.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  const rows: [string, string][] = [
    ['Trạng thái', status.allowed ? (status.offline ? 'Đang hoạt động (ngoại tuyến)' : 'Đang hoạt động') : status.message],
    ['Mã license', status.key_hint || '—'],
    ['Thiết bị', status.device_name],
    ['Hạn license', formatLicenseDate(status.license_expiry)],
    ['Lần xác thực gần nhất', status.last_validated_at ? formatLicenseDate(status.last_validated_at) : '—'],
    ['Dùng ngoại tuyến đến', status.offline_until ? formatLicenseDate(status.offline_until) : '—'],
  ]

  return (
    <div className="glass-card">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-primary-400" />
          <h3 className="text-lg font-semibold text-surface-100">License</h3>
        </div>
        <button onClick={() => void recheck()} disabled={busy} className="btn-ghost inline-flex items-center gap-2 text-sm disabled:opacity-50">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Kiểm tra lại
        </button>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3 sm:block">
            <dt className="text-surface-400">{label}</dt>
            <dd className="text-surface-200 text-right sm:text-left break-words">{value}</dd>
          </div>
        ))}
      </dl>
      {message && <p className="mt-3 text-sm text-surface-300">{message}</p>}
      <p className="mt-3 text-xs text-surface-500">{status.contact}</p>
    </div>
  )
}
