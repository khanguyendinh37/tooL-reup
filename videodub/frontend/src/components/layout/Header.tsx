import { useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import NotificationPopover from '@/components/notifications/NotificationPopover'

const pageTitles: Record<string, { title: string; description: string }> = {
  '/': { title: 'Trang chủ', description: 'Chào mừng đến với VideoDub' },
  '/dubbing': { title: 'Lồng tiếng', description: 'Bắt đầu lồng tiếng video mới' },
  '/history': { title: 'Lịch sử', description: 'Các video đã lồng tiếng' },
  '/settings': { title: 'Cài đặt', description: 'Tùy chỉnh hệ thống' },
}

interface HeaderProps {
  onMenuClick: () => void
  showMenuButton: boolean
}

export default function Header({ onMenuClick, showMenuButton }: HeaderProps) {
  const location = useLocation()
  const path = location.pathname.startsWith('/dubbing') ? '/dubbing' : location.pathname
  const page = pageTitles[path] || pageTitles['/']

  return (
    <header className="h-16 glass border-b border-surface-700/50 flex items-center justify-between px-4 sm:px-6 flex-shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        {showMenuButton && (
          <button
            type="button"
            onClick={onMenuClick}
            aria-label="Mở menu"
            className="btn-ghost !p-2 -ml-1 flex-shrink-0"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="min-w-0">
          <h2 className="text-base sm:text-lg font-semibold text-surface-100 truncate">
            {page.title}
          </h2>
          <p className="text-xs sm:text-sm text-surface-500 truncate hidden xs:block sm:block">
            {page.description}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
        <NotificationPopover />
      </div>
    </header>
  )
}
