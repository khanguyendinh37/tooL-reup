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
  { code: 'nl', name: 'Nederlands', flag: '🇳🇱' },
  { code: 'pl', name: 'Polski', flag: '🇵🇱' },
  { code: 'tr', name: 'Türkçe', flag: '🇹🇷' },
  { code: 'uk', name: 'Українська', flag: '🇺🇦' },
]

export const TTS_VOICES = [
  // Vietnamese
  { id: 'vi-VN-HoaiMyNeural', name: 'Hoài My (Nữ)', lang: 'vi', gender: 'female' },
  { id: 'vi-VN-NamMinhNeural', name: 'Nam Minh (Nam)', lang: 'vi', gender: 'male' },
  // English
  { id: 'en-US-JennyNeural', name: 'Jenny (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-US-GuyNeural', name: 'Guy (Nam)', lang: 'en', gender: 'male' },
  { id: 'en-US-AriaNeural', name: 'Aria (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-US-AndrewNeural', name: 'Andrew (Nam)', lang: 'en', gender: 'male' },
  { id: 'en-US-AvaNeural', name: 'Ava (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-US-BrianNeural', name: 'Brian (Nam)', lang: 'en', gender: 'male' },
  { id: 'en-US-EmmaNeural', name: 'Emma (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-US-MichelleNeural', name: 'Michelle (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-US-RogerNeural', name: 'Roger (Nam)', lang: 'en', gender: 'male' },
  { id: 'en-GB-SoniaNeural', name: 'Sonia UK (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-GB-RyanNeural', name: 'Ryan UK (Nam)', lang: 'en', gender: 'male' },
  { id: 'en-AU-NatashaNeural', name: 'Natasha AU (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-IN-NeerjaNeural', name: 'Neerja IN (Nữ)', lang: 'en', gender: 'female' },
  { id: 'en-IN-PrabhatNeural', name: 'Prabhat IN (Nam)', lang: 'en', gender: 'male' },
  // Japanese
  { id: 'ja-JP-NanamiNeural', name: 'Nanami (Nữ)', lang: 'ja', gender: 'female' },
  { id: 'ja-JP-KeitaNeural', name: 'Keita (Nam)', lang: 'ja', gender: 'male' },
  // Korean
  { id: 'ko-KR-SunHiNeural', name: 'SunHi (Nữ)', lang: 'ko', gender: 'female' },
  { id: 'ko-KR-InJoonNeural', name: 'InJoon (Nam)', lang: 'ko', gender: 'male' },
  { id: 'ko-KR-HyunsuMultilingualNeural', name: 'Hyunsu (Nam, đa ngôn ngữ)', lang: 'ko', gender: 'male' },
  // Chinese
  { id: 'zh-CN-XiaoxiaoNeural', name: 'Xiaoxiao CN (Nữ)', lang: 'zh', gender: 'female' },
  { id: 'zh-CN-YunxiNeural', name: 'Yunxi CN (Nam)', lang: 'zh', gender: 'male' },
  { id: 'zh-CN-YunjianNeural', name: 'Yunjian CN (Nam)', lang: 'zh', gender: 'male' },
  { id: 'zh-CN-XiaoyiNeural', name: 'Xiaoyi CN (Nữ)', lang: 'zh', gender: 'female' },
  { id: 'zh-CN-YunyangNeural', name: 'Yunyang CN (Nam)', lang: 'zh', gender: 'male' },
  { id: 'zh-HK-HiuMaanNeural', name: 'HiuMaan HK (Nữ)', lang: 'zh', gender: 'female' },
  { id: 'zh-HK-WanLungNeural', name: 'WanLung HK (Nam)', lang: 'zh', gender: 'male' },
  { id: 'zh-TW-HsiaoChenNeural', name: 'HsiaoChen TW (Nữ)', lang: 'zh', gender: 'female' },
  { id: 'zh-TW-YunJheNeural', name: 'YunJhe TW (Nam)', lang: 'zh', gender: 'male' },
  // Thai
  { id: 'th-TH-PremwadeeNeural', name: 'Premwadee (Nữ)', lang: 'th', gender: 'female' },
  { id: 'th-TH-NiwatNeural', name: 'Niwat (Nam)', lang: 'th', gender: 'male' },
  // French
  { id: 'fr-FR-DeniseNeural', name: 'Denise FR (Nữ)', lang: 'fr', gender: 'female' },
  { id: 'fr-FR-HenriNeural', name: 'Henri FR (Nam)', lang: 'fr', gender: 'male' },
  { id: 'fr-FR-EloiseNeural', name: 'Eloise FR (Nữ)', lang: 'fr', gender: 'female' },
  { id: 'fr-CA-SylvieNeural', name: 'Sylvie CA (Nữ)', lang: 'fr', gender: 'female' },
  { id: 'fr-CA-ThierryNeural', name: 'Thierry CA (Nam)', lang: 'fr', gender: 'male' },
  // German
  { id: 'de-DE-KatjaNeural', name: 'Katja DE (Nữ)', lang: 'de', gender: 'female' },
  { id: 'de-DE-ConradNeural', name: 'Conrad DE (Nam)', lang: 'de', gender: 'male' },
  { id: 'de-DE-AmalaNeural', name: 'Amala DE (Nữ)', lang: 'de', gender: 'female' },
  { id: 'de-AT-IngridNeural', name: 'Ingrid AT (Nữ)', lang: 'de', gender: 'female' },
  { id: 'de-AT-JonasNeural', name: 'Jonas AT (Nam)', lang: 'de', gender: 'male' },
  // Spanish
  { id: 'es-ES-ElviraNeural', name: 'Elvira ES (Nữ)', lang: 'es', gender: 'female' },
  { id: 'es-ES-AlvaroNeural', name: 'Alvaro ES (Nam)', lang: 'es', gender: 'male' },
  { id: 'es-MX-DaliaNeural', name: 'Dalia MX (Nữ)', lang: 'es', gender: 'female' },
  { id: 'es-MX-JorgeNeural', name: 'Jorge MX (Nam)', lang: 'es', gender: 'male' },
  { id: 'es-AR-ElenaNeural', name: 'Elena AR (Nữ)', lang: 'es', gender: 'female' },
  { id: 'es-AR-TomasNeural', name: 'Tomas AR (Nam)', lang: 'es', gender: 'male' },
  // Portuguese
  { id: 'pt-BR-FranciscaNeural', name: 'Francisca BR (Nữ)', lang: 'pt', gender: 'female' },
  { id: 'pt-BR-AntonioNeural', name: 'Antonio BR (Nam)', lang: 'pt', gender: 'male' },
  { id: 'pt-PT-RaquelNeural', name: 'Raquel PT (Nữ)', lang: 'pt', gender: 'female' },
  { id: 'pt-PT-DuarteNeural', name: 'Duarte PT (Nam)', lang: 'pt', gender: 'male' },
  // Russian
  { id: 'ru-RU-SvetlanaNeural', name: 'Svetlana (Nữ)', lang: 'ru', gender: 'female' },
  { id: 'ru-RU-DmitryNeural', name: 'Dmitry (Nam)', lang: 'ru', gender: 'male' },
  // Arabic
  { id: 'ar-SA-ZariyahNeural', name: 'Zariyah SA (Nữ)', lang: 'ar', gender: 'female' },
  { id: 'ar-SA-HamedNeural', name: 'Hamed SA (Nam)', lang: 'ar', gender: 'male' },
  { id: 'ar-EG-SalmaNeural', name: 'Salma EG (Nữ)', lang: 'ar', gender: 'female' },
  { id: 'ar-EG-ShakirNeural', name: 'Shakir EG (Nam)', lang: 'ar', gender: 'male' },
  { id: 'ar-AE-FatimaNeural', name: 'Fatima AE (Nữ)', lang: 'ar', gender: 'female' },
  { id: 'ar-AE-HamdanNeural', name: 'Hamdan AE (Nam)', lang: 'ar', gender: 'male' },
  // Hindi
  { id: 'hi-IN-SwaraNeural', name: 'Swara (Nữ)', lang: 'hi', gender: 'female' },
  { id: 'hi-IN-MadhurNeural', name: 'Madhur (Nam)', lang: 'hi', gender: 'male' },
  // Indonesian
  { id: 'id-ID-GadisNeural', name: 'Gadis (Nữ)', lang: 'id', gender: 'female' },
  { id: 'id-ID-ArdiNeural', name: 'Ardi (Nam)', lang: 'id', gender: 'male' },
  // Malay
  { id: 'ms-MY-YasminNeural', name: 'Yasmin (Nữ)', lang: 'ms', gender: 'female' },
  { id: 'ms-MY-OsmanNeural', name: 'Osman (Nam)', lang: 'ms', gender: 'male' },
  // Italian
  { id: 'it-IT-IsabellaNeural', name: 'Isabella (Nữ)', lang: 'it', gender: 'female' },
  { id: 'it-IT-GiuseppeMultilingualNeural', name: 'Giuseppe (Nam)', lang: 'it', gender: 'male' },
  // Dutch
  { id: 'nl-NL-ColetteNeural', name: 'Colette (Nữ)', lang: 'nl', gender: 'female' },
  { id: 'nl-NL-MaartenNeural', name: 'Maarten (Nam)', lang: 'nl', gender: 'male' },
  // Polish
  { id: 'pl-PL-AgnieszkaNeural', name: 'Agnieszka (Nữ)', lang: 'pl', gender: 'female' },
  { id: 'pl-PL-MarekNeural', name: 'Marek (Nam)', lang: 'pl', gender: 'male' },
  // Turkish
  { id: 'tr-TR-EmelNeural', name: 'Emel (Nữ)', lang: 'tr', gender: 'female' },
  { id: 'tr-TR-AhmetNeural', name: 'Ahmet (Nam)', lang: 'tr', gender: 'male' },
  // Ukrainian
  { id: 'uk-UA-PolinaNeural', name: 'Polina (Nữ)', lang: 'uk', gender: 'female' },
  { id: 'uk-UA-OstapNeural', name: 'Ostap (Nam)', lang: 'uk', gender: 'male' },
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