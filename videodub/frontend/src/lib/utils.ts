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

// Font presets for CapCut-style subtitles
export interface FontPreset {
  id: string
  name: string
  description: string
  font_family: string
  font_size: number
  font_color: string
  outline_color: string
  outline_width: number
  shadow_enabled: boolean
  shadow_color: string
  shadow_offset_x: number
  shadow_offset_y: number
  animation?: string
  animation_speed: number
  preview_url?: string
}

export const FONT_PRESETS: FontPreset[] = [
  {
    id: 'default',
    name: 'Mặc định',
    description: 'Phụ đề tiêu chuẩn',
    font_family: 'Arial',
    font_size: 24,
    font_color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 2,
    shadow_enabled: true,
    shadow_color: '#000000',
    shadow_offset_x: 2,
    shadow_offset_y: 2,
    animation: undefined,
    animation_speed: 1.0,
  },
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: 'Màu vàng viền đỏ, kiểu karaoke',
    font_family: 'Arial',
    font_size: 32,
    font_color: '#FFFF00',
    outline_color: '#FF0000',
    outline_width: 3,
    shadow_enabled: true,
    shadow_color: '#000000',
    shadow_offset_x: 3,
    shadow_offset_y: 3,
    animation: 'karaoke',
    animation_speed: 1.0,
  },
  {
    id: 'tiktok_viral',
    name: 'TikTok Viral',
    description: 'Font to, bo tròn, màu trắng viền đen',
    font_family: 'Montserrat',
    font_size: 40,
    font_color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 4,
    shadow_enabled: false,
    shadow_color: '#000000',
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    animation: 'pop',
    animation_speed: 1.0,
  },
  {
    id: 'cinematic',
    name: 'Sinematic',
    description: 'Font mỏng, chữ trắng, viền đen mịn',
    font_family: 'Cinzel',
    font_size: 28,
    font_color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 1,
    shadow_enabled: true,
    shadow_color: '#000000',
    shadow_offset_x: 2,
    shadow_offset_y: 2,
    animation: 'fade',
    animation_speed: 1.0,
  },
  {
    id: 'neon',
    name: 'Neon',
    description: 'Màu neon sáng, viền phát sáng',
    font_family: 'Orbitron',
    font_size: 30,
    font_color: '#00FFFF',
    outline_color: '#FF00FF',
    outline_width: 2,
    shadow_enabled: true,
    shadow_color: '#FF00FF',
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    animation: 'wave',
    animation_speed: 1.0,
  },
  {
    id: 'typewriter',
    name: 'Máy đánh chữ',
    description: 'Font monospace, hiệu ứng gõ chữ',
    font_family: 'Courier New',
    font_size: 26,
    font_color: '#00FF00',
    outline_color: '#000000',
    outline_width: 1,
    shadow_enabled: true,
    shadow_color: '#003300',
    shadow_offset_x: 1,
    shadow_offset_y: 1,
    animation: 'typewriter',
    animation_speed: 1.0,
  },
  {
    id: 'bold_impact',
    name: 'Impact Bold',
    description: 'Font đậm, to, dùng cho meme/video ngắn',
    font_family: 'Impact',
    font_size: 48,
    font_color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 5,
    shadow_enabled: false,
    shadow_color: '#000000',
    shadow_offset_x: 0,
    shadow_offset_y: 0,
    animation: 'pop',
    animation_speed: 1.0,
  },
  {
    id: 'elegant',
    name: 'Sang trọng',
    description: 'Font serif, vàng nhạt, viền nâu',
    font_family: 'Georgia',
    font_size: 30,
    font_color: '#FFD700',
    outline_color: '#8B4513',
    outline_width: 2,
    shadow_enabled: true,
    shadow_color: '#4A2C00',
    shadow_offset_x: 2,
    shadow_offset_y: 2,
    animation: 'fade',
    animation_speed: 1.0,
  },
]

export const ASPECT_RATIOS = [
  { id: '16:9', name: '16:9 - Ngáng (YouTube, Facebook)', width: 1920, height: 1080 },
  { id: '9:16', name: '9:16 - Dọc (TikTok, Reels, Shorts)', width: 1080, height: 1920 },
  { id: '1:1', name: '1:1 - Vuông (Instagram Post)', width: 1080, height: 1080 },
  { id: '4:5', name: '4:5 - Dọc cao (Instagram Portrait)', width: 1080, height: 1350 },
  { id: '4:3', name: '4:3 - Truyền thống', width: 1440, height: 1080 },
]

export interface TextOverlay {
  id: string
  text: string
  font_family: string
  font_size: number
  font_color: string
  outline_color: string
  outline_width: number
  shadow_enabled: boolean
  shadow_color: string
  shadow_offset_x: number
  shadow_offset_y: number
  x: number
  y: number
  animation?: string
  animation_speed: number
  start_time?: number
  end_time?: number
}

export interface ImageOverlay {
  id: string
  image_data?: string
  image_url?: string
  x: number
  y: number
  scale: number
  opacity: number
  rotation: number
  start_time?: number
  end_time?: number
}

export interface SubtitleConfig {
  enabled: boolean
  font_family: string
  font_size: number
  font_color: string
  outline_color: string
  outline_width: number
  shadow_enabled: boolean
  shadow_color: string
  shadow_offset_x: number
  shadow_offset_y: number
  position: 'top' | 'center' | 'bottom'
  margin_v: number
  margin_l: number
  margin_r: number
  alignment: number
  custom_x: number | null
  custom_y: number | null
  use_custom_position: boolean
  animation?: string
  animation_speed: number
  font_preset_id?: string
  text_overlays: TextOverlay[]
  image_overlays: ImageOverlay[]
  aspect_ratio: string
}

export const DEFAULT_SUBTITLE_CONFIG: SubtitleConfig = {
  enabled: true,
  font_family: 'Arial',
  font_size: 24,
  font_color: '#FFFFFF',
  outline_color: '#000000',
  outline_width: 2,
  shadow_enabled: true,
  shadow_color: '#000000',
  shadow_offset_x: 2,
  shadow_offset_y: 2,
  position: 'bottom',
  margin_v: 40,
  margin_l: 20,
  margin_r: 20,
  alignment: 2,
  custom_x: null,
  custom_y: null,
  use_custom_position: false,
  animation: undefined,
  animation_speed: 1.0,
  font_preset_id: undefined,
  text_overlays: [],
  image_overlays: [],
  aspect_ratio: '16:9',
}