import { useLocation } from 'react-router-dom'
import NotificationPopover from '@/components/notifications/NotificationPopover'

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
        <NotificationPopover />
      </div>
    </header>
  )
}
