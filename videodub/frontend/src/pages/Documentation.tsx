import { useEffect } from 'react'
import { BookOpen, Cpu, Mic2, Languages, Palette, Layers, HelpCircle, Workflow, Settings, Volume2 } from 'lucide-react'

declare global {
  interface Window {
    mermaid?: any
  }
}

const features = [
  {
    icon: Languages,
    title: 'AI Translation',
    description: 'Dịch phụ đề bằng OpenAI, Gemini, Anthropic hoặc Google Translate. Prompt 8 rules đảm bảo bản dịch ngắn gọn, đầy đủ ý.',
    color: 'from-blue-500 to-cyan-500'
  },
  {
    icon: Mic2,
    title: 'Voice Gender Matching',
    description: 'Chọn giọng nam hoặc nữ. Hệ thống đảm bảo không bao giờ đảo ngược giới khi fallback.',
    color: 'from-purple-500 to-pink-500'
  },
  {
    icon: Layers,
    title: 'Vocal Separation',
    description: 'Tách giọng hát khỏi nhạc nền bằng Demucs. Người dùng chọn mức âm lượng cho từng track.',
    color: 'from-green-500 to-emerald-500'
  },
  {
    icon: Palette,
    title: 'Subtitle Customization',
    description: 'Tùy chỉnh kích thước phụ đề (10-40px), vị trí, màu sắc. Blur phụ đề cũ bằng vùng kéo thả.',
    color: 'from-orange-500 to-amber-500'
  },
  {
    icon: Cpu,
    title: 'Whisper Transcription',
    description: 'Nhận dạng lời thoại chính xác bằng Faster-Whisper. Xuất SRT với timestamp chính xác.',
    color: 'from-red-500 to-rose-500'
  },
  {
    icon: Settings,
    title: 'Edge TTS + gTTS',
    description: '76+ giọng Edge TTS cho 20 ngôn ngữ, kèm nút "Nghe thử" trên UI. Tự động fallback sang gTTS nếu Edge TTS lỗi.',
    color: 'from-indigo-500 to-violet-500'
  }
]

const pipelineSteps = [
  { step: 1, title: 'Download', desc: 'Tải video từ URL (10 nền tảng)', icon: '📥' },
  { step: 2, title: 'Transcribe', desc: 'Whisper nhận dạng lời thoại → SRT', icon: '🎤' },
  { step: 3, title: 'Translate', desc: 'AI dịch phụ đề (full-context hoặc grouped)', icon: '🌐' },
  { step: 4, title: 'TTS', desc: 'Edge TTS tạo audio, 3-pass atempo giữ cue khớp SRT', icon: '🔊' },
  { step: 5, title: 'Separate', desc: 'Demucs tách giọng gốc', icon: '🎵' },
  { step: 6, title: 'Merge', desc: 'FFmpeg burn phụ đề + ghép audio + blur phụ đề cũ', icon: '🎬' }
]

// A representative slice of the Edge TTS voice table (the full table
// lives in the backend ``EDGE_TTS_VOICES`` dict and the frontend
// ``TTS_VOICES`` array). We keep the docs short: showing every voice
// here would bloat the page; the dropdowns in Dubbing/Settings are the
// canonical reference. One entry per language/gender pair is enough to
// illustrate the id format.
const voices = [
  { id: 'vi-VN-HoaiMyNeural', gender: 'Nữ', lang: 'Tiếng Việt' },
  { id: 'vi-VN-NamMinhNeural', gender: 'Nam', lang: 'Tiếng Việt' },
  { id: 'en-US-JennyNeural', gender: 'Nữ', lang: 'Tiếng Anh' },
  { id: 'en-US-AriaNeural', gender: 'Nữ', lang: 'Tiếng Anh' },
  { id: 'en-US-GuyNeural', gender: 'Nam', lang: 'Tiếng Anh' },
  { id: 'en-US-AndrewNeural', gender: 'Nam', lang: 'Tiếng Anh' },
  { id: 'en-GB-SoniaNeural', gender: 'Nữ', lang: 'Tiếng Anh (UK)' },
  { id: 'ja-JP-NanamiNeural', gender: 'Nữ', lang: 'Tiếng Nhật' },
  { id: 'ja-JP-KeitaNeural', gender: 'Nam', lang: 'Tiếng Nhật' },
  { id: 'ko-KR-SunHiNeural', gender: 'Nữ', lang: 'Tiếng Hàn' },
  { id: 'ko-KR-InJoonNeural', gender: 'Nam', lang: 'Tiếng Hàn' },
  { id: 'zh-CN-XiaoxiaoNeural', gender: 'Nữ', lang: 'Tiếng Trung (CN)' },
  { id: 'zh-CN-YunxiNeural', gender: 'Nam', lang: 'Tiếng Trung (CN)' },
  { id: 'zh-HK-HiuMaanNeural', gender: 'Nữ', lang: 'Tiếng Trung (HK)' },
  { id: 'th-TH-PremwadeeNeural', gender: 'Nữ', lang: 'Tiếng Thái' },
  { id: 'fr-FR-DeniseNeural', gender: 'Nữ', lang: 'Tiếng Pháp' },
  { id: 'fr-FR-HenriNeural', gender: 'Nam', lang: 'Tiếng Pháp' },
  { id: 'de-DE-KatjaNeural', gender: 'Nữ', lang: 'Tiếng Đức' },
  { id: 'es-ES-ElviraNeural', gender: 'Nữ', lang: 'Tiếng Tây Ban Nha' },
  { id: 'es-MX-DaliaNeural', gender: 'Nữ', lang: 'Tiếng Tây Ban Nha (MX)' },
  { id: 'pt-BR-FranciscaNeural', gender: 'Nữ', lang: 'Tiếng Bồ Đào Nha (BR)' },
  { id: 'ar-SA-ZariyahNeural', gender: 'Nữ', lang: 'Tiếng Ả Rập' },
  { id: 'ar-EG-SalmaNeural', gender: 'Nữ', lang: 'Tiếng Ả Rập (Ai Cập)' },
  { id: 'ru-RU-SvetlanaNeural', gender: 'Nữ', lang: 'Tiếng Nga' },
  { id: 'hi-IN-SwaraNeural', gender: 'Nữ', lang: 'Tiếng Hindi' },
  { id: 'it-IT-IsabellaNeural', gender: 'Nữ', lang: 'Tiếng Ý' },
  { id: 'tr-TR-EmelNeural', gender: 'Nữ', lang: 'Tiếng Thổ Nhĩ Kỳ' },
]

const faqs = [
  {
    q: 'Video quá dài bị timeout?',
    a: 'Timeout dịch: 600s (10 phút). TTS mỗi đoạn: 90s. Tăng trong translator.py nếu cần.'
  },
  {
    q: 'Tại sao phụ đề lúc nhiều lúc ít?',
    a: 'Prompt AI yêu cầu 18-32 chars/cue nhưng AI có thể không tuân thủ hoàn toàn. Hàm _compress_too_long_cue() post-processing cắt các cue quá dài tại clause boundary.'
  },
  {
    q: 'Giọng TTS bị sai (nam nghe nữ)?',
    a: 'Đã fix: get_fallback_voices() lọc fallback theo cùng giới tính với voice chính. Khi không có fallback cùng giới, trả về [] để caller giữ voice chính thay vì đổi sang giới khác.'
  },
  {
    q: 'Làm sao nghe thử giọng trước khi lồng tiếng?',
    a: 'Trong trang Dubbing hoặc Settings, bấm nút "Nghe thử" bên cạnh dropdown giọng. Backend gọi POST /api/tts/preview với voice id và trả về MP3 mẫu (câu tiếng Việt/Anh/... tùy theo target language). Có thể dùng để so sánh 76+ giọng trước khi chọn.'
  },
  {
    q: 'Subtitle lệch so với audio lồng tiếng?',
    a: 'Đã fix bằng 3-pass logic trong tts_engine.merge_tts_segments: (1) build audio thô ở tốc độ tự nhiên, (2) phát hiện overlap giữa các cue và áp dụng atempo để cue kết thúc đúng SRT start_seconds của cue kế tiếp, (3) ghép silence prefix cuối cùng. actual_start luôn khớp với SRT start_seconds nên subtitle SRT (build lại từ actual_segments) hiển thị cùng lúc với giọng.'
  },
  {
    q: 'Làm sao tùy chỉnh kích thước phụ đề?',
    a: 'Trong trang Dubbing, slider "Cỡ chữ phụ đề" cho phép chọn 10-40px.'
  },
  {
    q: 'Có bao nhiêu giọng và ngôn ngữ được hỗ trợ?',
    a: '20 ngôn ngữ (vi/en/ja/ko/zh/th/fr/de/es/pt/ru/ar/hi/id/ms/it/nl/pl/tr/uk) với 76+ giọng Edge TTS, có cả nam và nữ cho hầu hết ngôn ngữ. Bảng đầy đủ ở backend (tts_engine.py EDGE_TTS_VOICES) và frontend (lib/utils.ts TTS_VOICES).'
  },
  {
    q: 'Backend API chạy ở port nào?',
    a: 'Desktop app tự động khởi động FastAPI trên http://127.0.0.1:{port}/ (port ngẫu nhiên free).'
  }
]

export default function Documentation() {
  // Initialize Mermaid. We load the library only on first visit
  // (cached in localStorage) to keep the docs page lightweight, and
  // re-init on theme changes so colors track dark/light mode.
  useEffect(() => {
    const initMermaid = async () => {
      if (typeof window !== 'undefined' && !window.localStorage.getItem('mermaid_loaded')) {
        const script = document.createElement('script')
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.0/mermaid.min.js'
        script.onload = () => {
          if (window.mermaid) {
            window.mermaid.initialize({
              startOnLoad: true,
              theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
              flowchart: { curve: 'basis', htmlLabels: true },
              sequence: { useMaxWidth: true }
            })
            window.mermaid.init()
          }
          window.localStorage.setItem('mermaid_loaded', 'true')
        }
        document.head.appendChild(script)
      } else if (window.mermaid) {
        setTimeout(() => window.mermaid.init(), 100)
      }
    }
    initMermaid()
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-950 via-surface-900 to-surface-950 pb-16">
      {/* Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary-600/20 via-purple-600/20 to-blue-600/20" />
        <div className="absolute inset-0 backdrop-blur-3xl" />
        <div className="relative px-6 py-12">
          <div className="flex items-center gap-4 mb-4">
            <div className="p-3 rounded-2xl bg-primary-500/20 border border-primary-500/30">
              <BookOpen className="w-8 h-8 text-primary-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold gradient-text">VideoDub Documentation</h1>
              <p className="text-surface-400">Hướng dẫn sử dụng chi tiết ứng dụng lồng tiếng video AI</p>
            </div>
          </div>
          <div className="flex gap-3 mt-6">
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">Windows</span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-gray-500/20 text-gray-400 border border-gray-500/30">macOS</span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">AI Translation</span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30">Edge TTS</span>
          </div>
        </div>
      </div>

      <div className="px-6 space-y-8">
        {/* Tổng quan */}
        <section className="glass-card mt-8">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-primary-400" />
            Tổng quan
          </h2>
          <p className="text-surface-300 mb-4">
            VideoDub là ứng dụng desktop cho phép bạn tự động lồng tiếng video bằng cách:
          </p>
          <ul className="space-y-2 text-surface-400">
            <li className="flex items-center gap-2">✓ Tải video từ URL (YouTube, TikTok, Facebook, Instagram, Twitter, Bilibili, Douyin, Xiaohongshu, Vimeo, Twitch — 10 nền tảng)</li>
            <li className="flex items-center gap-2">✓ Nhận dạng lời thoại (Faster-Whisper AI)</li>
            <li className="flex items-center gap-2">✓ Dịch phụ đề bằng AI (OpenAI / Gemini / Anthropic / Google Translate)</li>
            <li className="flex items-center gap-2">✓ Tạo giọng lồng tiếng với 76+ giọng Edge TTS cho 20 ngôn ngữ (kèm nút "Nghe thử" trên UI)</li>
            <li className="flex items-center gap-2">✓ Tách giọng gốc (Demucs) và ghép audio mới vào video</li>
            <li className="flex items-center gap-2">✓ Tùy chỉnh phụ đề: cỡ chữ 10-40px, vị trí, màu sắc, blur vùng phụ đề cũ</li>
          </ul>
        </section>

        {/* Kiến trúc */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Workflow className="w-5 h-5 text-primary-400" />
            Kiến trúc hệ thống
          </h2>
          <div className="mermaid mb-6">
{`
graph TB
    subgraph Frontend["🖥️ Frontend (React + TypeScript)"]
        F1["Dubbing.tsx<br/>Trang chính, nhập URL, chọn ngôn ngữ"]
        F2["Settings.tsx<br/>Cài đặt phụ đề, giọng nói, âm lượng"]
        F3["Preview<br/>Xem trước video và vùng blur"]
    end

    subgraph Backend["⚙️ Backend (FastAPI + SQLAlchemy)"]
        B1["downloader.py<br/>Tải video (yt-dlp)"]
        B2["transcriber.py<br/>Transcribe (Whisper)"]
        B3["translator.py<br/>Dịch phụ đề (AI / Google)"]
        B4["tts_engine.py<br/>Tạo audio (Edge TTS 78 voice + gTTS)<br/>merge 3-pass atempo"]
        B5["vocal_remover.py<br/>Tách giọng (Demucs)"]
        B6["pipeline.py<br/>Điều phối toàn bộ luồng"]
        B7["api/tts_preview.py<br/>POST /api/tts/preview<br/>(Nghe thử giọng)"]
    end

    F1 --> B1
    B2 --> B3
    B3 --> B4
    B4 --> B6
    B5 --> B6
    B6 --> F3
    F2 --> B7
    B4 --> B7

    style Backend fill:#1e3a5f,color:#fff,stroke:#0d6efd
    style Frontend fill:#2d1f4e,color:#fff,stroke:#6f42c1
`}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-surface-800/50 border border-surface-700">
              <h3 className="font-semibold text-primary-400 mb-2">Frontend</h3>
              <p className="text-sm text-surface-400">React + TypeScript + Tailwind CSS</p>
              <p className="text-sm text-surface-500 mt-1">videodub/frontend/src/pages/</p>
            </div>
            <div className="p-4 rounded-lg bg-surface-800/50 border border-surface-700">
              <h3 className="font-semibold text-primary-400 mb-2">Backend</h3>
              <p className="text-sm text-surface-400">FastAPI + SQLAlchemy (aiosqlite)</p>
              <p className="text-sm text-surface-500 mt-1">videodub/backend/app/</p>
            </div>
          </div>
        </section>

        {/* Luồng xử lý */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Workflow className="w-5 h-5 text-primary-400" />
            Luồng xử lý chi tiết (Pipeline)
          </h2>
          <div className="mermaid mb-6">
{`
sequenceDiagram
    participant User as Người dùng
    participant FE as Frontend
    participant API as FastAPI
    participant Pipe as Pipeline
    participant DL as Downloader
    participant WH as Whisper
    participant TR as Translator
    participant TT as TTS Engine
    participant DM as Demucs
    participant FF as FFmpeg

    User->>FE: Nhập URL video
    FE->>API: POST /api/dubbing/start
    API->>Pipe: run_pipeline()
    Pipe->>DL: download_video()
    DL-->>Pipe: video_path
    Pipe->>WH: transcribe_with_whisper()
    WH-->>Pipe: segments (SRT)
    Pipe->>TR: translate_srt_deep_translator()
    Note over TR: AI (OpenAI/Gemini)<br/>hoặc Google Translate
    TR-->>Pipe: translated.srt
    Pipe->>TT: generate_dubbing_audio()
    Note over TT: Edge TTS từng cue<br/>3-pass atempo: build / overlap-fix / re-pad<br/>Voice gender matching fallback
    TT-->>Pipe: audio_files[] + actual_segments
    Pipe->>TT: build_subtitle_srt_from_actual_timing()
    Note over TT: Subtitle SRT rebuild<br/>từ actual_start/actual_end
    TT-->>Pipe: final_subtitle.srt
    Pipe->>DM: separate_vocals()
    DM-->>Pipe: vocals.wav, no_vocals.wav
    Pipe->>FF: burn_subtitles_with_blur_mask()
    FF-->>Pipe: final_video.mp4
    Pipe-->>User: Job completed
`}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {pipelineSteps.map((s) => (
              <div key={s.step} className="p-3 rounded-lg bg-surface-800/50 border border-surface-700 text-center">
                <div className="text-2xl mb-1">{s.icon}</div>
                <div className="text-xs font-semibold text-primary-400">{s.step}. {s.title}</div>
                <div className="text-xs text-surface-500 mt-1 hidden md:block">{s.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Tính năng */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4">✨ Tính năng chính</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {features.map((f) => (
              <div key={f.title} className="p-5 rounded-xl bg-gradient-to-br from-surface-800/80 to-surface-800/40 border border-surface-700/50 hover:border-surface-600 transition-all">
                <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${f.color} flex items-center justify-center mb-3`}>
                  <f.icon className="w-5 h-5 text-white" />
                </div>
                <h3 className="font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-surface-400">{f.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Voice Gender Matching */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Mic2 className="w-5 h-5 text-primary-400" />
            Voice Gender Matching (TTS)
          </h2>
          <div className="mermaid mb-6">
{`
graph TD
    A["Chọn giọng: Nam"] --> B["get_fallback_voices('vi-VN-NamMinhNeural')"]
    B --> C{"Có fallback cùng giới?"}
    C -->|"Có"| D["Dùng fallback nam<br/>en-US-GuyNeural"]
    C -->|"Không"| E["Trả về []<br/>Dùng voice chính"]
    F --> G["✅ Luôn là giọng nam"]
    E --> G

    H["Chọn giọng: Nữ"] --> I["get_fallback_voices('vi-VN-HoaiMyNeural')"]
    I --> J{"Có fallback cùng giới?"}
    J -->|"Có"| K["Dùng fallback nữ<br/>vi-VN-HoaiMyNeural"]
    J -->|"Không"| L["Trả về []<br/>Dùng voice chính"]
    K --> M["✅ Luôn là giọng nữ"]
    L --> M

    style G fill:#198754,color:#fff
    style M fill:#198754,color:#fff
`}
          </div>
          <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20 mb-4">
            <p className="text-sm text-green-400">
              <strong>Nguyên tắc:</strong> Khi user chọn giọng nam, hệ thống <em>không bao giờ</em> tự động chuyển sang giọng nữ nếu primary voice fails. Thay vào đó, nó giữ voice chính hoặc dùng fallback cùng giới.
            </p>
          </div>
          <h3 className="font-semibold mb-3">Bảng voice (một số giọng tiêu biểu — đầy đủ 76+ giọng ở dropdown Dubbing/Settings):</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left py-2 px-3">Voice ID</th>
                  <th className="text-left py-2 px-3">Giới</th>
                  <th className="text-left py-2 px-3">Ngôn ngữ</th>
                </tr>
              </thead>
              <tbody>
                {voices.map((v) => (
                  <tr key={v.id} className="border-b border-surface-800">
                    <td className="py-2 px-3 text-surface-400 font-mono text-xs">{v.id}</td>
                    <td className="py-2 px-3">{v.gender === 'Nam' ? '👨 Nam' : '👩 Nữ'}</td>
                    <td className="py-2 px-3 text-surface-400">{v.lang}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* TTS Voice Preview */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-primary-400" />
            Nghe thử giọng (Voice Preview)
          </h2>
          <p className="text-surface-400 mb-4">
            Mỗi dropdown chọn giọng ở trang Dubbing và Settings có một nút <strong>Nghe thử</strong> bên cạnh. Khi bấm, frontend gọi <code className="px-1 rounded bg-surface-700">POST /api/tts/preview</code> với voice id và target language, backend synthesize một câu ngắn bằng Edge TTS rồi trả về MP3. Frontend dùng <code className="px-1 rounded bg-surface-700">URL.createObjectURL</code> để phát trực tiếp blob audio.
          </p>
          <div className="mermaid mb-6">
{`
sequenceDiagram
    participant User as Người dùng
    participant FE as VoicePreviewButton
    participant API as /api/tts/preview
    participant TTS as Edge TTS

    User->>FE: Bấm "Nghe thử"
    FE->>API: POST {voice, lang}
    API->>API: Chọn câu mẫu theo lang
    API->>TTS: edge_tts.Communicate(text, voice)
    TTS-->>API: MP3 bytes
    API-->>FE: 200 audio/mpeg
    FE->>User: Phát audio
    Note over FE: Auto-stop khi đổi voice
`}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left py-2 px-3">Tham số</th>
                  <th className="text-left py-2 px-3">Kiểu</th>
                  <th className="text-left py-2 px-3">Mô tả</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3"><code>voice</code></td>
                  <td className="py-2 px-3 text-surface-400">string</td>
                  <td className="py-2 px-3 text-surface-400">Edge TTS voice id (vd: <code>vi-VN-HoaiMyNeural</code>)</td>
                </tr>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3"><code>text</code></td>
                  <td className="py-2 px-3 text-surface-400">string?</td>
                  <td className="py-2 px-3 text-surface-400">Optional custom text. Mặc định dùng câu mẫu theo <code>lang</code> (20 câu có sẵn cho 20 ngôn ngữ)</td>
                </tr>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3"><code>lang</code></td>
                  <td className="py-2 px-3 text-surface-400">string?</td>
                  <td className="py-2 px-3 text-surface-400">Lang code (vi/en/ja/...) để chọn câu mẫu. Mặc định lấy từ voice prefix.</td>
                </tr>
                <tr>
                  <td className="py-2 px-3"><code>rate</code></td>
                  <td className="py-2 px-3 text-surface-400">string?</td>
                  <td className="py-2 px-3 text-surface-400">Edge TTS rate (vd: <code>+10%</code>, <code>-5%</code>). Mặc định <code>+0%</code>.</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 mt-4">
            <p className="text-sm text-blue-400">
              <strong>Bảo mật:</strong> Endpoint sanitize control chars + bidi overrides, giới hạn 200 ký tự để chặn misuse. Cache header <code>Cache-Control: private, max-age=300</code> để không gọi Edge TTS lặp lại khi user click nhiều lần cùng voice.
            </p>
          </div>
        </section>

        {/* Kích thước phụ đề */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Palette className="w-5 h-5 text-primary-400" />
            Kích thước phụ đề (Font Size)
          </h2>
          <div className="mermaid mb-6">
{`
graph LR
    A["Frontend Slider<br/>10px - 40px"] --> B["Dubbing.tsx<br/>subtitlesize: number"]
    B --> C["API: /api/dubbing/start<br/>subtitle_size: number"]
    C --> D["settings.py<br/>_build_subtitle_config()"]
    D --> E["pipeline.py<br/>font_size (pixel)"]
    E --> F["Burn ASS subtitle<br/>với font_size đã chọn"]
`}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left py-2 px-3">Vị trí</th>
                  <th className="text-left py-2 px-3">Code</th>
                  <th className="text-left py-2 px-3">Mô tả</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3">Frontend</td>
                  <td className="py-2 px-3 text-surface-400 font-mono text-xs">Dubbing.tsx</td>
                  <td className="py-2 px-3 text-surface-400">Slider range input (10-40px)</td>
                </tr>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3">Type</td>
                  <td className="py-2 px-3 text-surface-400 font-mono text-xs">workflow.ts</td>
                  <td className="py-2 px-3 text-surface-400">subtitleSize: number (trước là "small")</td>
                </tr>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3">Settings</td>
                  <td className="py-2 px-3 text-surface-400 font-mono text-xs">settings.py</td>
                  <td className="py-2 px-3 text-surface-400">SUBTITLE_SIZE_PRESETS: {"{small: 13, medium: 18, large: 24}"}</td>
                </tr>
                <tr className="border-b border-surface-800">
                  <td className="py-2 px-3">Limits</td>
                  <td className="py-2 px-3 text-surface-400 font-mono text-xs">settings.py</td>
                  <td className="py-2 px-3 text-surface-400">MIN=10, MAX=40</td>
                </tr>
                <tr>
                  <td className="py-2 px-3">Pipeline</td>
                  <td className="py-2 px-3 text-surface-400 font-mono text-xs">pipeline.py</td>
                  <td className="py-2 px-3 text-surface-400">Tính scale theo video resolution</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Prompt dịch */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Languages className="w-5 h-5 text-primary-400" />
            Prompt dịch thuật (Translation Prompt)
          </h2>
          <div className="mermaid mb-6">
{`
graph TD
    A["SRT Input<br/><<<index>>> cue text"] --> B["Build contextual block<br/>8 cues mỗi block"]
    B --> C["AI Translation<br/>TRANSLATION_SYSTEM_PROMPT"]
    C --> D{"8 RULES"}
    D --> D1["1. Giữ ngắn 18-32 chars"]
    D --> D2["2. Giữ nguyên markers"]
    D --> D3["3. Dịch ý, không dịch từ"]
    D --> D4["4. Chinese idioms có điều kiện"]
    D --> D5["5. Không thêm metadata"]
    D --> D6["6. Không dịch proper nouns"]
    D --> D7["7. Không censor"]
    D --> D8["8. Marker rỗng giữ timing"]
    D1 --> E["_compress_too_long_cue()"]
    E --> F["Output: translated.srt"]
`}
          </div>
          <div className="p-4 rounded-lg bg-surface-800/50 border border-surface-700">
            <h3 className="font-semibold mb-2">8 Rules trong TRANSLATION_SYSTEM_PROMPT:</h3>
            <ol className="text-sm text-surface-400 space-y-1">
              <li><strong>1.</strong> Giữ ngắn 18-32 chars/cue, max 40 chars</li>
              <li><strong>2.</strong> Giữ nguyên markers &lt;&lt;&lt;index&gt;&gt;&gt; chính xác</li>
              <li><strong>3.</strong> Dịch ý, không dịch từng từ</li>
              <li><strong>4.</strong> Chinese idioms có điều kiện</li>
              <li><strong>5.</strong> Không thêm metadata, giải thích</li>
              <li><strong>6.</strong> Không dịch proper nouns</li>
              <li><strong>7.</strong> Không censor content</li>
              <li><strong>8.</strong> Marker rỗng vẫn giữ timing</li>
            </ol>
          </div>
          <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 mt-4">
            <p className="text-sm text-blue-400">
              <strong>Lưu ý:</strong> Nếu AI vẫn trả về bản dịch quá dài, <code className="px-1 rounded bg-surface-700">_compress_too_long_cue()</code> trong translator.py sẽ tự động cắt tại clause boundary gần nhất.
            </p>
          </div>
        </section>

        {/* File cấu hình */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary-400" />
            File cấu hình quan trọng
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-700">
                  <th className="text-left py-2 px-3">File</th>
                  <th className="text-left py-2 px-3">Chức năng</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/api/settings.py</td><td className="py-2 px-3 text-surface-400">DEFAULT_SETTINGS, SUBTITLE_SIZE_PRESETS, _parse_subtitle_config, _build_subtitle_config</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/api/dubbing.py</td><td className="py-2 px-3 text-surface-400">API endpoint, _map_subtitle_config chuyển config frontend → pipeline</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/api/tts_preview.py</td><td className="py-2 px-3 text-surface-400">POST /api/tts/preview — synthesize câu mẫu ngắn để nghe thử giọng</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/core/tts_engine.py</td><td className="py-2 px-3 text-surface-400">EDGE_TTS_VOICES (78), VOICE_GENDERS, VOICE_FALLBACKS, get_fallback_voices(), merge_tts_segments() 3-pass atempo</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/core/translation_providers.py</td><td className="py-2 px-3 text-surface-400">TRANSLATION_SYSTEM_PROMPT (8 rules), translate_marked_block()</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/core/translator.py</td><td className="py-2 px-3 text-surface-400">_compress_too_long_cue(), translate_srt_deep_translator(), _context_groups()</td></tr>
                <tr className="border-b border-surface-800"><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/core/pipeline.py</td><td className="py-2 px-3 text-surface-400">run_pipeline() điều phối toàn bộ luồng, burn_subtitles_with_blur_mask()</td></tr>
                <tr><td className="py-2 px-3 text-surface-400 font-mono text-xs">app/core/transcriber.py</td><td className="py-2 px-3 text-surface-400">Whisper transcription, extract_audio()</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* FAQ */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-primary-400" />
            FAQ - Câu hỏi thường gặp
          </h2>
          <div className="space-y-4">
            {faqs.map((faq, idx) => (
              <details key={idx} className="group p-4 rounded-lg bg-surface-800/50 border border-surface-700 cursor-pointer">
                <summary className="font-semibold list-none flex items-center justify-between">
                  <span>{faq.q}</span>
                  <span className="text-surface-500 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <p className="mt-2 text-surface-400 text-sm">{faq.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Footer */}
        <div className="text-center py-8 text-surface-500 text-sm">
          VideoDub Documentation · Built with Claude Code · 2026
        </div>
      </div>
    </div>
  )
}
