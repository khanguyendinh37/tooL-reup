import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import useActiveDubbingMonitor from '@/hooks/useActiveDubbingMonitor'
import { unlockNotificationSound } from '@/lib/notificationSound'

export default function Layout() {
  useActiveDubbingMonitor()

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

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
