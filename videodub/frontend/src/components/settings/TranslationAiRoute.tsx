import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  Cpu,
  Eye,
  EyeOff,
  GitBranch,
  KeyRound,
  RefreshCw,
  SlidersHorizontal,
  Waypoints,
  X,
} from 'lucide-react'
import {
  getTranslationProvider,
  getTranslationRouteState,
  maskApiKeyHint,
  TRANSLATION_PROVIDERS,
  type TranslationConnectionStatus,
  type TranslationModelOption,
  type TranslationProviderId,
  type TranslationRouteInput,
} from '@/lib/translation'

interface TranslationAiRouteProps {
  provider: TranslationProviderId
  model: string
  endpoint: string
  hasSavedKey: boolean
  apiKeyDraft: string
  apiKeyHint: string
  clearApiKey: boolean
  models: TranslationModelOption[]
  modelsUnlocked: boolean
  connectionStatus: TranslationConnectionStatus
  connectionMessage: string
  onProviderChange: (provider: TranslationProviderId) => void
  onModelChange: (model: string) => void
  onEndpointChange: (endpoint: string) => void
  onApiKeyChange: (apiKey: string) => void
  onClearKeyChange: (clear: boolean) => void
  onConnect: () => void
}

interface RouteMarkerProps {
  index: string
  label: string
  icon: typeof KeyRound
  active: boolean
  warning?: boolean
  last?: boolean
}

function RouteMarker({ index, label, icon: Icon, active, warning = false, last = false }: RouteMarkerProps) {
  const tone = warning
    ? 'text-amber-400 border-amber-400/50'
    : active
      ? 'text-accent-cyan border-accent-cyan/50'
      : 'text-surface-600 border-surface-700'

  return (
    <div className="relative flex min-h-[82px] w-12 shrink-0 flex-col items-center gap-1 text-center">
      {!last && <span className={`absolute left-1/2 top-10 h-[calc(100%-1.25rem)] w-px -translate-x-1/2 ${active ? 'bg-accent-cyan/60' : 'bg-surface-700'}`} aria-hidden="true" />}
      <span className="font-mono text-[10px] leading-none text-surface-500">{index}</span>
      <span className={`relative z-10 flex h-7 w-7 items-center justify-center rounded-full border bg-surface-900 ${tone}`}>
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
      <span className="text-[10px] leading-3 text-surface-600">{label}</span>
    </div>
  )
}

interface SecretKeyInputProps {
  value: string
  hasSavedKey: boolean
  hint: string
  clearApiKey: boolean
  onChange: (value: string) => void
  onClearChange: (clear: boolean) => void
}

function SecretKeyInput({
  value,
  hasSavedKey,
  hint,
  clearApiKey,
  onChange,
  onClearChange,
}: SecretKeyInputProps) {
  const [revealed, setRevealed] = useState(false)
  const keyIsPresent = Boolean(value.trim()) || (hasSavedKey && !clearApiKey)
  const savedHint = hint || (hasSavedKey ? '••••' : '')

  return (
    <div>
      <label htmlFor="translation-api-key" className="mb-2 block text-sm text-surface-400">API key</label>
      <div className="relative">
        <input
          id="translation-api-key"
          type={revealed ? 'text' : 'password'}
          value={value}
          onChange={(event) => {
            onClearChange(false)
            onChange(event.target.value)
          }}
          placeholder={hasSavedKey && !clearApiKey ? 'Để trống để giữ key đã lưu' : 'Dán API key của nhà cung cấp'}
          autoComplete="new-password"
          spellCheck={false}
          className="glass-input w-full pr-20 font-mono text-[13px]"
          aria-describedby="translation-api-key-help"
        />
        <div className="absolute inset-y-0 right-2 flex items-center gap-1">
          <button
            type="button"
            onClick={() => setRevealed((current) => !current)}
            className="rounded-md p-2 text-surface-500 transition-colors hover:bg-surface-700/70 hover:text-surface-200"
            aria-label={revealed ? 'Ẩn API key' : 'Hiện API key'}
            title={revealed ? 'Ẩn API key' : 'Hiện API key'}
          >
            {revealed ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
          </button>
          {keyIsPresent && (
            <button
              type="button"
              onClick={() => {
                onChange('')
                onClearChange(true)
              }}
              className="rounded-md p-2 text-surface-500 transition-colors hover:bg-red-500/10 hover:text-red-300"
              aria-label="Xóa API key khi lưu"
              title="Xóa API key khi lưu"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
      <p id="translation-api-key-help" className="mt-2 min-h-4 text-xs text-surface-500">
        {clearApiKey
          ? 'API key sẽ bị xóa khi bạn bấm Lưu cài đặt.'
          : value.trim()
            ? 'Đã nhập API key. Bấm “Kết nối key & tải model” để xác thực.'
            : hasSavedKey
              ? <>Đã lưu khóa kết thúc bằng <span className="font-mono text-surface-400">{savedHint}</span></>
              : 'Key chỉ được lưu cục bộ và không bao giờ hiển thị đầy đủ.'}
      </p>
    </div>
  )
}

interface TranslationRouteStatusProps {
  input: TranslationRouteInput
}

function TranslationRouteStatus({ input }: TranslationRouteStatusProps) {
  const route = getTranslationRouteState(input)
  const dotTone = route.status === 'ready'
    ? 'bg-accent-emerald'
    : route.status === 'invalid'
      ? 'bg-amber-400'
      : 'bg-surface-500'

  return (
    <div
      className="mt-8 border-t border-surface-700/50 bg-surface-800/50 px-4 py-3 transition-opacity duration-150"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotTone}`} aria-hidden="true" />
        <GitBranch className="mt-0.5 h-4 w-4 shrink-0 text-surface-400" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-surface-200">{route.title}</p>
          <p className="mt-1 text-xs leading-5 text-surface-500">{route.detail}</p>
        </div>
      </div>
    </div>
  )
}

export default function TranslationAiRoute({
  provider,
  model,
  endpoint,
  hasSavedKey,
  apiKeyDraft,
  apiKeyHint,
  clearApiKey,
  models,
  modelsUnlocked,
  connectionStatus,
  connectionMessage,
  onProviderChange,
  onModelChange,
  onEndpointChange,
  onApiKeyChange,
  onClearKeyChange,
  onConnect,
}: TranslationAiRouteProps) {
  const providerMeta = getTranslationProvider(provider)
  const [endpointOpen, setEndpointOpen] = useState(Boolean(endpoint) || providerMeta.endpointRequired)
  const hasApiKey = (hasSavedKey || Boolean(apiKeyDraft.trim())) && !clearApiKey
  const routeInput: TranslationRouteInput = {
    provider,
    model,
    endpoint,
    hasApiKey,
    modelsUnlocked,
    connectionStatus,
    connectionMessage,
  }
  const routeState = getTranslationRouteState(routeInput)
  const modelStepActive = provider !== 'google' && hasApiKey && modelsUnlocked
  const endpointStepActive = Boolean(endpoint.trim()) || providerMeta.endpointRequired
  const canConnect = provider !== 'google'
    && hasApiKey
    && connectionStatus !== 'connecting'
    && (!providerMeta.endpointRequired || Boolean(endpoint.trim()))
  const connectLabel = connectionStatus === 'connecting'
    ? 'Đang kết nối và tải model...'
    : connectionStatus === 'error'
      ? 'Kết nối lại & tải model'
      : 'Kết nối key & tải model'
  const modelOptions = models.length > 0 ? models : providerMeta.models

  useEffect(() => {
    if (providerMeta.endpointRequired || endpoint) setEndpointOpen(true)
  }, [endpoint, providerMeta.endpointRequired])

  const handleProviderChange = (nextProvider: TranslationProviderId) => {
    const nextMeta = getTranslationProvider(nextProvider)
    setEndpointOpen(nextMeta.endpointRequired || (nextProvider !== 'google' && Boolean(endpoint)))
    if (nextProvider === 'google' && endpoint) onEndpointChange('')
    onProviderChange(nextProvider)
  }

  return (
    <div className="mt-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h4 className="font-medium text-surface-100">Nhà cung cấp dịch AI</h4>
          <p className="mt-1 text-sm text-surface-500">Kết nối API key trước để tải đúng model; nếu không khả dụng, hệ thống vẫn dịch bằng Google Translate.</p>
        </div>
        {connectionStatus === 'connected' && (
          <span className="hidden items-center gap-1 text-xs text-accent-emerald sm:inline-flex">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Đã kết nối
          </span>
        )}
      </div>

      <div className="flex gap-4">
        <div className="hidden pt-1 md:block" aria-hidden="true">
          <RouteMarker index="01" label="Key" icon={KeyRound} active={hasApiKey} warning={provider !== 'google' && !hasApiKey} />
          <RouteMarker index="02" label="Model" icon={Cpu} active={modelStepActive} warning={provider !== 'google' && hasApiKey && !modelsUnlocked} />
          <RouteMarker index="03" label="URL" icon={Waypoints} active={endpointStepActive} warning={providerMeta.endpointRequired && !endpoint.trim()} last />
        </div>

        <div className="min-w-0 flex-1">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,0.35fr)_minmax(0,0.65fr)]">
            <div>
              <label htmlFor="translation-provider" className="mb-2 block text-sm text-surface-400">Nhà cung cấp</label>
              <div className="relative">
                <select
                  id="translation-provider"
                  value={provider}
                  onChange={(event) => handleProviderChange(event.target.value as TranslationProviderId)}
                  className="glass-input w-full appearance-none cursor-pointer pr-10"
                >
                  {TRANSLATION_PROVIDERS.map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" aria-hidden="true" />
              </div>
            </div>
            <SecretKeyInput
              value={apiKeyDraft}
              hasSavedKey={hasSavedKey}
              hint={apiKeyHint || maskApiKeyHint(apiKeyDraft)}
              clearApiKey={clearApiKey}
              onChange={onApiKeyChange}
              onClearChange={onClearKeyChange}
            />
          </div>

          <div className="mt-8">
            <label htmlFor="translation-model" className="mb-2 block text-sm text-surface-400">Mô hình</label>
            <div className="relative">
              <select
                id="translation-model"
                value={modelsUnlocked && model ? model : ''}
                onChange={(event) => onModelChange(event.target.value)}
                disabled={!modelsUnlocked || connectionStatus === 'connecting'}
                className="glass-input w-full appearance-none cursor-pointer pr-10 disabled:cursor-not-allowed disabled:opacity-50"
                aria-describedby="translation-model-help"
              >
                {!modelsUnlocked && <option value="">Kết nối API key để tải model phù hợp</option>}
                {modelsUnlocked && modelOptions.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} — {item.id}</option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" aria-hidden="true" />
            </div>
            <p id="translation-model-help" className="mt-2 text-xs text-surface-600">
              {provider === 'google'
                ? 'Google Translate không cần API key.'
                : modelsUnlocked
                  ? `Đã tải ${models.length || modelOptions.length} model tương thích từ ${providerMeta.name}.`
                  : 'Model chỉ được mở sau khi API key kết nối thành công.'}
            </p>
          </div>

          {provider !== 'google' && (
            <div className="mt-6">
              <button
                type="button"
                onClick={() => setEndpointOpen((current) => !current)}
                className="inline-flex min-h-10 items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-surface-400 transition-colors hover:bg-surface-800/70 hover:text-surface-200"
                aria-expanded={endpointOpen}
                aria-controls="translation-custom-endpoint"
              >
                {endpointOpen ? <ChevronDown className="h-4 w-4" aria-hidden="true" /> : <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />}
                {endpointOpen ? 'Ẩn endpoint tùy chỉnh' : 'Dùng endpoint tùy chỉnh'}
              </button>
              <div
                id="translation-custom-endpoint"
                className={`grid transition-[grid-template-rows,opacity] duration-150 ${endpointOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
              >
                <div className="min-h-0 overflow-hidden">
                  <div className="mt-3 border-l border-accent-cyan/40 pl-4">
                    <label htmlFor="translation-endpoint" className="mb-2 block text-sm text-surface-400">Endpoint tùy chỉnh</label>
                    <input
                      id="translation-endpoint"
                      value={endpoint}
                      onChange={(event) => onEndpointChange(event.target.value)}
                      placeholder="https://api.example.com/v1"
                      inputMode="url"
                      className="glass-input w-full font-mono text-[13px]"
                      aria-describedby="translation-endpoint-help"
                    />
                    <p id="translation-endpoint-help" className="mt-2 text-xs leading-5 text-surface-600">Chỉ thay đổi nếu nhà cung cấp hoặc máy chủ của bạn yêu cầu URL riêng.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {provider !== 'google' && (
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={onConnect}
                disabled={!canConnect}
                className="btn-secondary inline-flex min-h-10 items-center gap-2 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RefreshCw className={`h-4 w-4 ${connectionStatus === 'connecting' ? 'animate-spin' : ''}`} aria-hidden="true" />
                {connectLabel}
              </button>
              {connectionStatus === 'error' && <span className="text-xs text-amber-300">{connectionMessage}</span>}
              {connectionStatus === 'connected' && <span className="text-xs text-accent-emerald">{connectionMessage}</span>}
            </div>
          )}

          <TranslationRouteStatus input={routeInput} />
          {routeState.status === 'invalid' && connectionStatus !== 'error' && connectionStatus !== 'connecting' && (
            <p className="mt-2 text-xs text-amber-300">Cấu hình chưa đủ; bản dịch vẫn dùng Google Translate.</p>
          )}
        </div>
      </div>
    </div>
  )
}
