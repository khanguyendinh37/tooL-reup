import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import useActiveDubbingMonitor from '@/hooks/useActiveDubbingMonitor'
import { unlockNotificationSound } from '@/lib/notificationSound'
import { useMediaQuery } from '@/hooks/useMediaQuery'

export default function Layout() {
  useActiveDubbingMonitor()
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const unlockFromGesture = () => {
      void unlockNotificationSound()
      document.removeEventListener('pointerdown', unlockFromGesture)
      document.removeEventListener('keydown', unlockFromGesture)
    }
    document.addEventListener('pointerdown', unlockFromGesture, { passive: true })
    document.addEventListener('keydown', unlockFromGesture)

    return () => {
      document.removeEventListener('pointerdown', unlockFromGesture)
      document.removeEventListener('keydown', unlockFromGesture)
    }
  }, [])

  // Auto-close mobile drawer when the route changes or the viewport grows to desktop.
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])
  useEffect(() => {
    if (isDesktop) setSidebarOpen(false)
  }, [isDesktop])

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        isDesktop={isDesktop}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header onMenuClick={() => setSidebarOpen((v) => !v)} showMenuButton={!isDesktop} />
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
