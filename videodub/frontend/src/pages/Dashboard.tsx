import { useNavigate } from 'react-router-dom'
import { Mic2, Zap, Globe, Clock, ArrowRight, Video, Languages, Volume2 } from 'lucide-react'

const features = [
  {
    icon: Video,
    title: 'Tải video',
    description: 'Hỗ trợ YouTube, TikTok, Facebook và 1000+ trang web',
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
    description: 'Tạo giọng nói tự nhiên với 300+ giọng đa ngôn ngữ',
    color: 'from-emerald-500 to-teal-500',
  },
  {
    icon: Mic2,
    title: 'Xóa giọng gốc',
    description: 'Tự động tách và xóa giọng nói gốc bằng AI',
    color: 'from-orange-500 to-red-500',
  },
]

const stats = [
  { label: 'Nền tảng hỗ trợ', value: '1000+', icon: Globe },
  { label: 'Ngôn ngữ', value: '16+', icon: Languages },
  { label: 'Giọng TTS', value: '300+', icon: Volume2 },
  { label: 'Hoàn toàn miễn phí', value: '100%', icon: Zap },
]

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-fade-in">
      {/* Hero */}
      <div className="glass-card !p-12 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary-600/10 via-accent-cyan/10 to-accent-purple/10" />
        <div className="relative z-10">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-cyan flex items-center justify-center animate-float">
            <Mic2 className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold mb-4">
            <span className="gradient-text">VideoDub</span>
          </h1>
          <p className="text-surface-400 text-lg mb-8 max-w-2xl mx-auto">
            Lồng tiếng video tự động bằng AI - hoàn toàn miễn phí.
            Hỗ trợ đa nền tảng, đa ngôn ngữ, giữ nguyên ngữ cảnh.
          </p>
          <button
            onClick={() => navigate('/dubbing')}
            className="btn-primary text-lg px-8 py-4 inline-flex items-center gap-3 group"
          >
            <Zap className="w-5 h-5" />
            Bắt đầu lồng tiếng
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className="glass-card !p-4 text-center hover:scale-[1.02] transition-transform">
            <Icon className="w-6 h-6 text-primary-400 mx-auto mb-2" />
            <div className="text-2xl font-bold gradient-text">{value}</div>
            <div className="text-sm text-surface-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {features.map(({ icon: Icon, title, description, color }, index) => (
          <div
            key={title}
            className="glass-card hover:scale-[1.02] transition-all duration-300 animate-slide-up"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center mb-4`}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-lg font-semibold text-surface-100 mb-2">{title}</h3>
            <p className="text-surface-400 text-sm">{description}</p>
          </div>
        ))}
      </div>

      {/* Pipeline Preview */}
      <div className="glass-card">
        <h3 className="text-lg font-semibold text-surface-100 mb-6 flex items-center gap-2">
          <Clock className="w-5 h-5 text-primary-400" />
          Quy trình tự động
        </h3>
        <div className="flex items-center justify-between flex-wrap gap-4">
          {['Tải video', 'Tạo SRT', 'Dịch thuật', 'Tạo giọng', 'Xóa giọng gốc', 'Ghép video'].map(
            (step, i) => (
              <div key={step} className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-primary-600/20 border border-primary-500/30 flex items-center justify-center text-sm font-medium text-primary-400">
                  {i + 1}
                </div>
                <span className="text-sm text-surface-300">{step}</span>
                {i < 5 && <ArrowRight className="w-4 h-4 text-surface-600 hidden md:block" />}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}
