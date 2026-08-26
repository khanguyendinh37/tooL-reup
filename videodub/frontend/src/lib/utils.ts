import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date))
}

export const LANGUAGES = [
  { code: 'vi', name: 'Tiếng Việt', flag: '🇻🇳' },
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
  { code: 'th', name: 'ไทย', flag: '🇹🇭' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'pt', name: 'Português', flag: '🇵🇹' },
  { code: 'it', name: 'Italiano', flag: '🇮🇹' },
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  { code: 'ar', name: 'العربية', flag: '🇸🇦' },
  { code: 'hi', name: 'हिन्दी', flag: '🇮🇳' },
  { code: 'id', name: 'Bahasa Indonesia', flag: '🇮🇩' },
  { code: 'ms', name: 'Bahasa Melayu', flag: '🇲🇾' },
]

export const TTS_VOICES = [
  { id: 'vi-VN-HoaiMyNeural', name: 'Hoài My (Nữ)', lang: 'vi', gender: 'female' },
  { id: 'vi-VN-NamMinhNeural', name: 'Nam Minh (Nam)', lang: 'vi', gender: 'male' },
  { id: 'en-US-JennyNeural', name: 'Jenny (Female)', lang: 'en', gender: 'female' },
  { id: 'en-US-GuyNeural', name: 'Guy (Male)', lang: 'en', gender: 'male' },
  { id: 'ja-JP-NanamiNeural', name: 'Nanami (Female)', lang: 'ja', gender: 'female' },
  { id: 'ja-JP-KeitaNeural', name: 'Keita (Male)', lang: 'ja', gender: 'male' },
  { id: 'ko-KR-SunHiNeural', name: 'SunHi (Female)', lang: 'ko', gender: 'female' },
  { id: 'ko-KR-InJoonNeural', name: 'InJoon (Male)', lang: 'ko', gender: 'male' },
  { id: 'zh-CN-XiaoxiaoNeural', name: 'Xiaoxiao (Female)', lang: 'zh', gender: 'female' },
  { id: 'zh-CN-YunxiNeural', name: 'Yunxi (Male)', lang: 'zh', gender: 'male' },
  { id: 'th-TH-PremwadeeNeural', name: 'Premwadee (Female)', lang: 'th', gender: 'female' },
  { id: 'fr-FR-DeniseNeural', name: 'Denise (Female)', lang: 'fr', gender: 'female' },
  { id: 'de-DE-KatjaNeural', name: 'Katja (Female)', lang: 'de', gender: 'female' },
  { id: 'es-ES-ElviraNeural', name: 'Elvira (Female)', lang: 'es', gender: 'female' },
  { id: 'pt-BR-FranciscaNeural', name: 'Francisca (Female)', lang: 'pt', gender: 'female' },
  { id: 'ru-RU-SvetlanaNeural', name: 'Svetlana (Female)', lang: 'ru', gender: 'female' },
  { id: 'ar-SA-ZariyahNeural', name: 'Zariyah (Female)', lang: 'ar', gender: 'female' },
  { id: 'hi-IN-SwaraNeural', name: 'Swara (Female)', lang: 'hi', gender: 'female' },
]

export const WHISPER_MODELS = [
  { id: 'tiny', name: 'Tiny', size: '~39 MB', speed: 'Rất nhanh', quality: 'Cơ bản' },
  { id: 'base', name: 'Base', size: '~74 MB', speed: 'Nhanh', quality: 'Tốt' },
  { id: 'small', name: 'Small', size: '~244 MB', speed: 'Trung bình', quality: 'Rất tốt' },
  { id: 'medium', name: 'Medium', size: '~769 MB', speed: 'Chậm hơn', quality: 'Xuất sắc' },
  { id: 'large-v3', name: 'Large V3', size: '~1550 MB', speed: 'Chậm', quality: 'Tối ưu' },
]

// Audio mix volume defaults (used by dubbing pipeline)
export interface AudioMixConfig {
  dubbing_volume: number      // Lồng tiếng
  background_volume: number   // Nhạc nền / giọng gốc
  original_vocals_volume: number  // Giọng gốc còn lại (khi tách vocals)
}

export const DEFAULT_AUDIO_MIX: AudioMixConfig = {
  dubbing_volume: 1.0,
  background_volume: 1.0,
  original_vocals_volume: 0.3,
}