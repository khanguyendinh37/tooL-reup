import { useLocation } from 'react-router-dom'
import { Bell, Search } from 'lucide-react'

const pageTitles: Record<string, { title: string; description: string }> = {
  '/': { title: 'Trang chủ', description: 'Chào mừng đến với VideoDub' },
  '/dubbing': { title: 'Lồng tiếng', description: 'Bắt đầu lồng tiếng video mới' },
  '/history': { title: 'Lịch sử', description: 'Các video đã lồng tiếng' },
  '/settings': { title: 'Cài đặt', description: 'Tùy chỉnh hệ thống' },
}

export default function Header() {
  const location = useLocation()
  const path = location.pathname.startsWith('/dubbing') ? '/dubbing' : location.pathname
  const page = pageTitles[path] || pageTitles['/']

  return (
    <header className="h-16 glass border-b border-surface-700/50 flex items-center justify-between px-6">
      <div>
        <h2 className="text-lg font-semibold text-surface-100">{page.title}</h2>
        <p className="text-sm text-surface-500">{page.description}</p>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
          <input
            type="text"
            placeholder="Tìm kiếm..."
            className="glass-input !pl-10 !py-2 !w-64 text-sm"
          />
        </div>
        <button className="relative p-2 rounded-lg hover:bg-surface-800/50 transition-colors">
          <Bell className="w-5 h-5 text-surface-400" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-primary-500 rounded-full" />
        </button>
      </div>
    </header>
  )
}
