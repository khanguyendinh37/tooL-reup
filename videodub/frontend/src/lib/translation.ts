export type TranslationProviderId =
  | 'google'
  | 'openai'
  | 'openrouter'
  | 'nvidia'
  | 'openai_compatible'
  | 'gemini'
  | 'anthropic'

export type TranslationProviderFamily = 'google' | 'openai_compatible' | 'gemini' | 'anthropic'
export type TranslationModelSource = 'discovered' | 'curated'
export type TranslationRouteStatus = 'fallback' | 'ready' | 'invalid'
export type TranslationTestStatus = 'idle' | 'testing' | 'success' | 'error'
export type TranslationConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error'

export interface TranslationModelOption {
  id: string
  name: string
  source?: TranslationModelSource
}

export interface TranslationProviderMeta {
  id: TranslationProviderId
  name: string
  family: TranslationProviderFamily
  defaultModel: string
  defaultEndpoint?: string
  endpointRequired: boolean
  models: TranslationModelOption[]
}

export const TRANSLATION_PROVIDERS: TranslationProviderMeta[] = [
  {
    id: 'google',
    name: 'Google Translate miễn phí',
    family: 'google',
    defaultModel: 'google-free',
    endpointRequired: false,
    models: [{ id: 'google-free', name: 'Google Translate miễn phí' }],
  },
  {
    id: 'openai',
    name: 'OpenAI',
    family: 'openai_compatible',
    defaultModel: 'gpt-4o-mini',
    defaultEndpoint: 'https://api.openai.com/v1',
    endpointRequired: false,
    models: [
      { id: 'gpt-4o-mini', name: 'GPT-4o mini' },
      { id: 'gpt-4.1-mini', name: 'GPT-4.1 mini' },
    ],
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    family: 'openai_compatible',
    defaultModel: 'openai/gpt-4o-mini',
    defaultEndpoint: 'https://openrouter.ai/api/v1',
    endpointRequired: false,
    models: [
      { id: 'openai/gpt-4o-mini', name: 'OpenAI GPT-4o mini' },
      { id: 'google/gemini-2.0-flash-001', name: 'Google Gemini 2.0 Flash' },
      { id: 'anthropic/claude-3.5-haiku', name: 'Anthropic Claude 3.5 Haiku' },
    ],
  },
  {
    id: 'nvidia',
    name: 'NVIDIA NIM',
    family: 'openai_compatible',
    defaultModel: 'meta/llama-3.1-8b-instruct',
    defaultEndpoint: 'https://integrate.api.nvidia.com/v1',
    endpointRequired: false,
    models: [
      { id: 'meta/llama-3.1-8b-instruct', name: 'Llama 3.1 8B Instruct' },
      { id: 'nvidia/llama-3.1-nemotron-ultra-253b-v1', name: 'NVIDIA Nemotron Ultra' },
    ],
  },
  {
    id: 'openai_compatible',
    name: 'Endpoint tương thích OpenAI',
    family: 'openai_compatible',
    defaultModel: '',
    endpointRequired: true,
    models: [{ id: 'custom', name: 'Model tùy chỉnh' }],
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    family: 'gemini',
    defaultModel: 'gemini-2.0-flash',
    defaultEndpoint: 'https://generativelanguage.googleapis.com/v1beta',
    endpointRequired: false,
    models: [
      { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
      { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash' },
    ],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    family: 'anthropic',
    defaultModel: 'claude-3-5-haiku-latest',
    defaultEndpoint: 'https://api.anthropic.com',
    endpointRequired: false,
    models: [
      { id: 'claude-3-5-haiku-latest', name: 'Claude 3.5 Haiku' },
      { id: 'claude-3-7-sonnet-latest', name: 'Claude 3.7 Sonnet' },
    ],
  },
]

export function getTranslationProvider(provider: string | undefined): TranslationProviderMeta {
  return TRANSLATION_PROVIDERS.find((item) => item.id === provider) || TRANSLATION_PROVIDERS[0]
}

export function getTranslationModel(provider: string | undefined, model: string | undefined): string {
  const meta = getTranslationProvider(provider)
  return model ?? meta.defaultModel
}

export function maskApiKeyHint(value: string | null | undefined): string {
  if (!value) return ''
  return `••••${value.slice(-4)}`
}

export interface TranslationRouteInput {
  provider: TranslationProviderId
  model: string
  endpoint: string
  hasApiKey: boolean
  modelsUnlocked?: boolean
  connectionStatus?: TranslationConnectionStatus
  connectionMessage?: string
}

export interface TranslationRouteState {
  status: TranslationRouteStatus
  title: string
  detail: string
}

export function getTranslationRouteState(input: TranslationRouteInput): TranslationRouteState {
  const meta = getTranslationProvider(input.provider)
  if (input.provider === 'google') {
    return {
      status: 'fallback',
      title: 'Đang sử dụng Google Translate',
      detail: 'Bạn có thể thêm API key bất cứ lúc nào để dùng nhà cung cấp AI.',
    }
  }

  if (!input.hasApiKey) {
    return {
      status: 'fallback',
      title: 'Đang sử dụng Google Translate',
      detail: 'Chưa có API key cho nhà cung cấp này.',
    }
  }

  if (input.connectionStatus === 'error') {
    return {
      status: 'invalid',
      title: 'Google Translate vẫn đang được sử dụng',
      detail: input.connectionMessage || 'Không thể kết nối nhà cung cấp AI. Hệ thống sẽ tự động dùng Google Translate.',
    }
  }

  if (!input.modelsUnlocked) {
    return {
      status: 'invalid',
      title: 'Google Translate vẫn đang được sử dụng',
      detail: 'Kết nối API key để tải model phù hợp trước khi dùng dịch AI.',
    }
  }

  if (!input.model.trim()) {
    return {
      status: 'invalid',
      title: 'Google Translate vẫn đang được sử dụng',
      detail: 'Chưa chọn mô hình AI nên hệ thống chưa thể dùng nhà cung cấp này.',
    }
  }

  if (meta.endpointRequired && !input.endpoint.trim()) {
    return {
      status: 'invalid',
      title: 'Google Translate vẫn đang được sử dụng',
      detail: 'Endpoint tùy chỉnh là bắt buộc với nhà cung cấp này.',
    }
  }

  if (input.endpoint.trim() && !/^https?:\/\/[^\s]+$/i.test(input.endpoint.trim())) {
    return {
      status: 'invalid',
      title: 'Google Translate vẫn đang được sử dụng',
      detail: 'Không thể dùng endpoint này. Kiểm tra URL hoặc thử lại sau.',
    }
  }

  return {
    status: 'ready',
    title: `Lần dịch tiếp theo sẽ dùng ${meta.name} · ${input.model}`,
    detail: 'Nếu nhà cung cấp không phản hồi, hệ thống dùng Google Translate.',
  }
}
