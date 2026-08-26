import { NavLink } from 'react-router-dom'
import { Home, Mic2, History, Settings } from 'lucide-react'
import BrandMark from '@/components/brand/BrandMark'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: Home, label: 'Trang chủ' },
  { to: '/dubbing', icon: Mic2, label: 'Lồng tiếng' },
  { to: '/history', icon: History, label: 'Lịch sử' },
  { to: '/settings', icon: Settings, label: 'Cài đặt' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 h-screen glass flex flex-col">
      <div className="p-6 border-b border-surface-700/50">
        <div className="flex items-center gap-3">
          <BrandMark size="sm" />
          <div>
            <h1 className="text-lg font-bold gradient-text">VideoDub</h1>
            <p className="text-xs text-surface-500">Lồng tiếng AI</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200',
                isActive
                  ? 'bg-primary-600/20 text-primary-400 border border-primary-500/30'
                  : 'text-surface-400 hover:bg-surface-800/50 hover:text-surface-200'
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span className="font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-surface-700/50">
        <div className="glass-card !p-4 !rounded-xl">
          <p className="text-xs text-surface-500 mb-2">Trạng thái hệ thống</p>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm text-surface-300">Sẵn sàng</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
