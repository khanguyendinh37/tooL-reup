import { useNavigate } from 'react-router-dom'
import { Mic2, Zap, Globe, Clock, ArrowRight, Video, Languages, Volume2 } from 'lucide-react'
import BrandMark from '@/components/brand/BrandMark'
import { PIPELINE_STEPS } from '@/lib/workflow'

const features = [
  {
    icon: Video,
    title: 'Tải video',
    description: 'Hỗ trợ YouTube, TikTok, Facebook, Instagram, Twitter, Bilibili, Douyin, Xiaohongshu, Vimeo, Twitch',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    icon: Languages,
    title: 'Dịch tự động',
    description: 'Dịch đúng ngữ cảnh với AI, giữ nguyên thời gian',
    color: 'from-purple-500 to-pink-500',
  },
  {
    icon: Volume2,
    title: 'Lồng tiếng',
    description: 'Tạo giọng nói tự nhiên với 20+ giọng đa ngôn ngữ qua Edge TTS',
    color: 'from-emerald-500 to-teal-500',
  },
  {
    icon: Mic2,
    title: 'Xóa giọng gốc',
    description: 'Tự động tách và xóa giọng nói gốc bằng AI (Demucs)',
    color: 'from-orange-500 to-red-500',
  },
]

const stats = [
  { label: 'Nền tảng hỗ trợ', value: '10', icon: Globe },
  { label: 'Ngôn ngữ', value: '16', icon: Languages },
  { label: 'Giọng TTS', value: '20+', icon: Volume2 },
  { label: 'Hoàn toàn miễn phí', value: '100%', icon: Zap },
]

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="glass-card !p-6 sm:!p-8 md:!p-12 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary-600/10 via-accent-cyan/10 to-accent-purple/10" />
        <div className="relative z-10">
          <BrandMark size="md" className="mx-auto mb-4 sm:mb-6 animate-float" />
          <h1 className="text-3xl sm:text-4xl font-bold mb-3 sm:mb-4">
            <span className="gradient-text">VideoDub</span>
          </h1>
          <p className="text-surface-400 text-base sm:text-lg mb-6 sm:mb-8 max-w-2xl mx-auto px-2">
            Lồng tiếng video tự động bằng AI - hoàn toàn miễn phí.
            Hỗ trợ đa nền tảng, đa ngôn ngữ, giữ nguyên ngữ cảnh.
          </p>
          <button
            onClick={() => navigate('/dubbing')}
            className="btn-primary text-base sm:text-lg px-6 sm:px-8 py-3 sm:py-4 inline-flex items-center gap-2 sm:gap-3 group"
          >
            <Zap className="w-5 h-5" />
            Bắt đầu lồng tiếng
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className="glass-card !p-3 sm:!p-4 text-center hover:scale-[1.02] transition-transform">
            <Icon className="w-5 h-5 sm:w-6 sm:h-6 text-primary-400 mx-auto mb-1.5 sm:mb-2" />
            <div className="text-xl sm:text-2xl font-bold gradient-text">{value}</div>
            <div className="text-xs sm:text-sm text-surface-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
        {features.map(({ icon: Icon, title, description, color }, index) => (
          <div
            key={title}
            className="glass-card hover:scale-[1.02] transition-all duration-300 animate-slide-up"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center mb-3 sm:mb-4`}>
              <Icon className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
            </div>
            <h3 className="text-base sm:text-lg font-semibold text-surface-100 mb-1.5 sm:mb-2">{title}</h3>
            <p className="text-surface-400 text-xs sm:text-sm">{description}</p>
          </div>
        ))}
      </div>

      {/* Pipeline Preview */}
      <div className="glass-card">
        <h3 className="text-base sm:text-lg font-semibold text-surface-100 mb-4 sm:mb-6 flex items-center gap-2">
          <Clock className="w-5 h-5 text-primary-400" />
          Quy trình tự động
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:flex lg:items-center lg:justify-between gap-3">
          {PIPELINE_STEPS.map(
            (step, i) => (
              <div key={step.id} className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-sm font-medium text-primary-400 flex-shrink-0">
                  {i + 1}
                </div>
                <span className="text-sm text-surface-300">{step.label}</span>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}
