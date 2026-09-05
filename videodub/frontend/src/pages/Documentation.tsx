import { useState } from 'react'
import {
  BookOpen,
  Mic2,
  Languages,
  Volume2,
  Settings as SettingsIcon,
  History as HistoryIcon,
  Home,
  HelpCircle,
  Play,
  Gauge,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const stats = [
  { value: '10+', label: 'Nền tảng hỗ trợ', icon: Home },
  { value: '20', label: 'Ngôn ngữ', icon: Languages },
  { value: '76+', label: 'Giọng TTS', icon: Volume2 },
  { value: 'Miễn phí', label: 'Chi phí', icon: Sparkles },
]

interface GuideStep {
  text: string
}

interface GuidePage {
  id: string
  icon: typeof Home
  title: string
  summary: string
  whatYouSee: string[]
  steps: GuideStep[]
  tip?: string
}

const guidePages: GuidePage[] = [
  {
    id: 'dashboard',
    icon: Home,
    title: 'Trang chủ (Dashboard)',
    summary:
      'Trang giới thiệu tổng quan, điểm khởi đầu mỗi lần mở app. Không có input ở đây — chỉ để bạn nắm nhanh tính năng và bấm nút bắt đầu.',
    whatYouSee: [
      'Hero card: tiêu đề, tagline, nút Bắt đầu lồng tiếng → mở trang Lồng tiếng',
      'Stats 4 ô: nền tảng, ngôn ngữ, giọng TTS, chi phí',
      'Features grid 4 thẻ: Tải video / Dịch tự động / Lồng tiếng / Xóa giọng gốc',
      'Pipeline preview: 6 bước từ tải đến xuất video',
    ],
    steps: [
      { text: 'Mở app → mặc định vào Trang chủ.' },
      { text: 'Đọc nhanh 4 stats để biết app hỗ trợ gì.' },
      { text: 'Bấm "Bắt đầu lồng tiếng" để chuyển sang trang Lồng tiếng.' },
    ],
    tip: 'Nếu bạn đã có job trước, mở trang Lịch sử để tải lại video đã render.',
  },
  {
    id: 'dubbing',
    icon: Mic2,
    title: 'Lồng tiếng',
    summary:
      'Trang chính — nơi bạn dán URL, chọn ngôn ngữ và giọng, rồi bấm chạy pipeline. Có 3 pha: input → preview video gốc → chạy lồng tiếng.',
    whatYouSee: [
      'URL input + chọn ngôn ngữ nguồn/đích',
      'Chọn giọng TTS (76+ giọng, có nút Nghe thử) và tốc độ nói',
      'Cài đặt phụ đề: cỡ chữ 10-40px, vị trí, màu, blur phụ đề cũ',
      'Âm lượng: lồng tiếng / nhạc nền / giọng gốc còn lại',
      'Cài đặt nâng cao: model Whisper, vocal separation, gợi ý prompt',
    ],
    steps: [
      { text: 'Dán URL video (YouTube, TikTok, Facebook, Instagram, ...).' },
      { text: 'Chọn ngôn ngữ gốc (Whisper sẽ nghe) và ngôn ngữ đích (TTS sẽ đọc).' },
      { text: 'Bấm nút ▶ bên cạnh dropdown giọng để nghe thử, rồi chọn giọng bạn thích.' },
      { text: 'Tùy chỉnh phụ đề (cỡ chữ, vị trí) và âm lượng nếu cần.' },
      { text: 'Bấm "Tải video" để sang pha preview — xem lại video gốc trước khi xử lý.' },
      { text: 'Bấm "Bắt đầu lồng tiếng" để chạy pipeline. Theo dõi tiến trình ở thanh bên phải.' },
      { text: 'Khi xong, bấm "Tải xuống" để lấy video đã lồng tiếng.' },
    ],
    tip: 'Nếu video dài (>10 phút) mà AI dịch chậm, tăng timeout dịch trong Settings.',
  },
  {
    id: 'history',
    icon: HistoryIcon,
    title: 'Lịch sử',
    summary:
      'Danh sách tất cả video đã lồng tiếng. Tìm kiếm, lọc theo trạng thái, mở lại để tải về hoặc chạy lại với cài đặt khác.',
    whatYouSee: [
      'Thanh tìm kiếm theo tiêu đề',
      'Bộ lọc trạng thái: tất cả / đang xử lý / hoàn thành / lỗi',
      'Mỗi job là 1 card: thumbnail, tiêu đề, ngôn ngữ, thời lượng, ngày tạo',
      'Mỗi card có nút: tải video / tải video gốc / retry / xóa',
    ],
    steps: [
      { text: 'Mở trang Lịch sử từ sidebar.' },
      { text: 'Gõ tên vào ô tìm kiếm nếu danh sách dài.' },
      { text: 'Bấm lọc trạng thái để chỉ thấy job đang lỗi hoặc đang chạy.' },
      { text: 'Bấm nút "Retry" trên job lỗi để chạy lại với đúng cài đặt cũ.' },
      { text: 'Bấm nút "Xóa" để dọn job không cần — có thể chọn nhiều job để xóa hàng loạt.' },
    ],
    tip: 'Job đang chạy có nút "Hủy" — bấm để dừng pipeline ngay lập tức.',
  },
  {
    id: 'settings',
    icon: SettingsIcon,
    title: 'Cài đặt',
    summary:
      'Mọi thứ mặc định: ngôn ngữ nguồn/đích, giọng TTS, tốc độ, model Whisper, cỡ chữ phụ đề, màu phụ đề, âm lượng. Đặt 1 lần, áp dụng cho job mới.',
    whatYouSee: [
      'AI Translation: chọn provider (Google / OpenAI / Gemini / Anthropic), nhập API key, test kết nối',
      'Text-to-Speech: dropdown giọng + nút Nghe thử, tốc độ nói 0.5x-2x',
      'Speech-to-Text: chọn model Whisper (tiny → large-v3)',
      'Audio Mix: 3 slider âm lượng (lồng tiếng / nhạc nền / giọng gốc)',
      'Thông báo: bật/tắt thông báo khi job xong',
      'Cookies: upload cookies cho từng nền tảng nếu bị chặn',
    ],
    steps: [
      { text: 'Mở trang Cài đặt từ sidebar.' },
      { text: 'Chọn nhà cung cấp dịch AI: Google miễn phí hoặc OpenAI/Gemini/Anthropic nếu có key.' },
      { text: 'Chọn giọng TTS mặc định — bấm ▶ Nghe thử trước khi lưu.' },
      { text: 'Chọn model Whisper: small là cân bằng, large-v3 chậm nhưng chính xác nhất.' },
      { text: 'Bấm "Lưu cài đặt" để áp dụng cho job tiếp theo.' },
    ],
    tip: 'Nếu Google Translate trả bản dịch chưa tốt, dùng OpenAI/Gemini với API key — chất lượng nhảy rõ rệt.',
  },
]

export default function Documentation() {
  const [activePage, setActivePage] = useState<string>(guidePages[0].id)
  const current = guidePages.find((p) => p.id === activePage) ?? guidePages[0]

  return (
    <div className="min-h-screen pb-16">
      {/* Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary-600/20 via-purple-600/20 to-blue-600/20" />
        <div className="absolute inset-0 backdrop-blur-3xl" />
        <div className="relative px-6 py-10">
          <div className="flex items-center gap-4 mb-3">
            <div className="p-3 rounded-2xl bg-primary-500/20 border border-primary-500/30">
              <BookOpen className="w-8 h-8 text-primary-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold gradient-text">Hướng dẫn sử dụng</h1>
              <p className="text-surface-400">Cách dùng từng màn hình trong VideoDub</p>
            </div>
          </div>
          <div className="flex gap-2 mt-5 flex-wrap">
            {guidePages.map((p) => {
              const Icon = p.icon
              const isActive = p.id === activePage
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setActivePage(p.id)}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                    isActive
                      ? 'bg-primary-500/20 text-primary-300 border-primary-500/40'
                      : 'bg-surface-800/50 text-surface-300 border-surface-700 hover:bg-surface-800 hover:text-surface-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {p.title.split(' (')[0]}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="px-6 space-y-6 mt-6">
        {/* Tổng quan */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-3 flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-primary-400" />
            VideoDub có gì?
          </h2>
          <p className="text-surface-300 mb-5">
            VideoDub là ứng dụng desktop giúp bạn tự động lồng tiếng video bằng AI: tải video từ URL → nhận dạng
            lời thoại → dịch sang ngôn ngữ khác → tạo giọng mới → ghép lại vào video. Tài liệu này hướng dẫn bạn
            dùng từng màn hình trong app.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {stats.map((s) => {
              const Icon = s.icon
              return (
                <div
                  key={s.label}
                  className="p-4 rounded-xl bg-surface-800/40 border border-surface-700/60 text-center"
                >
                  <Icon className="w-5 h-5 text-primary-400 mx-auto mb-2" />
                  <div className="text-2xl font-bold gradient-text">{s.value}</div>
                  <div className="text-xs text-surface-400 mt-1">{s.label}</div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Trang đang chọn */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
            <current.icon className="w-5 h-5 text-primary-400" />
            {current.title}
          </h2>
          <p className="text-surface-300 mb-5">{current.summary}</p>

          <h3 className="font-semibold mb-2 text-surface-100">Có gì trên trang</h3>
          <ul className="space-y-1.5 text-sm text-surface-400 mb-5">
            {current.whatYouSee.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="text-primary-400 mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <h3 className="font-semibold mb-2 text-surface-100">Cách dùng</h3>
          <ol className="space-y-2 text-sm text-surface-300 mb-5">
            {current.steps.map((step, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-500/20 text-primary-300 text-xs font-semibold flex items-center justify-center">
                  {idx + 1}
                </span>
                <span>{step.text}</span>
              </li>
            ))}
          </ol>

          {current.tip && (
            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <p className="text-sm text-blue-300">
                <span className="font-semibold">Mẹo:</span> {current.tip}
              </p>
            </div>
          )}
        </section>

        {/* Đường tắt nhanh */}
        <section className="glass-card">
          <h2 className="text-xl font-bold mb-3 flex items-center gap-2">
            <Gauge className="w-5 h-5 text-primary-400" />
            Đi nhanh đến từng màn hình
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {guidePages.map((p) => {
              const Icon = p.icon
              return (
                <Link
                  key={p.id}
                  to={p.id === 'dashboard' ? '/' : `/${p.id}`}
                  className="flex items-center gap-3 p-3 rounded-lg bg-surface-800/40 border border-surface-700/60 hover:border-primary-500/40 hover:bg-surface-800 transition-colors"
                >
                  <div className="p-2 rounded-lg bg-primary-500/20">
                    <Icon className="w-5 h-5 text-primary-300" />
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-surface-100">{p.title}</div>
                    <div className="text-xs text-surface-400 line-clamp-1">{p.summary}</div>
                  </div>
                  <Play className="w-4 h-4 text-surface-500" />
                </Link>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}
