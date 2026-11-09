export type LicenseState =
  | 'disabled'
  | 'active'
  | 'unlicensed'
  | 'revoked'
  | 'expired'
  | 'offline_expired'
  | 'clock_rollback'
  | 'misconfigured'
  | 'device_error'

export interface LicenseStatus {
  enforced: boolean
  state: LicenseState
  allowed: boolean
  message: string
  contact: string
  device_name: string
  key_hint: string | null
  last_validated_at: string | null
  license_expiry: string | null
  offline_until: string | null
  offline: boolean
}

/** Fired when a processing request is refused because the license is missing. */
export const LICENSE_REQUIRED_EVENT = 'videodub:license-required'

async function licenseRequest(path: string, init: RequestInit = {}, timeoutMs = 20_000): Promise<LicenseStatus> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  let response: Response
  try {
    response = await fetch(`/api/license${path}`, { ...init, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Máy chủ license phản hồi quá lâu. Kiểm tra mạng rồi thử lại.')
    }
    throw new Error('Không thể kết nối tới backend VideoDub. Hãy khởi động lại ứng dụng.')
  } finally {
    window.clearTimeout(timeoutId)
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error((data && (data.detail || data.message)) || 'Không thể xử lý yêu cầu license.')
  }
  return data as LicenseStatus
}

export function getLicenseStatus(): Promise<LicenseStatus> {
  return licenseRequest('/status')
}

export function activateLicense(key: string): Promise<LicenseStatus> {
  return licenseRequest('/activate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: key.trim() }),
  }, 60_000)
}

export function refreshLicense(): Promise<LicenseStatus> {
  return licenseRequest('/refresh', { method: 'POST' }, 60_000)
}

export function formatLicenseDate(value: string | null): string {
  if (!value) return 'Không giới hạn'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })
}
