import { createPortal } from 'react-dom'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { ArrowRight, Bell, CheckCircle2, X, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { formatNotificationTime } from '@/lib/workflow'
import { useAppStore } from '@/stores/appStore'

const POPOVER_ID = 'header-notification-popover'
const POPOVER_TITLE_ID = 'header-notification-popover-title'
const POPOVER_GUTTER = 16
const READ_NOTIFICATION_RETENTION_MS = 45_000

const initialPanelStyle: CSSProperties = {
  position: 'fixed',
  top: 80,
  right: POPOVER_GUTTER,
  width: 'min(22rem, calc(100vw - 2rem))',
  zIndex: 100,
}

export default function NotificationPopover() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [panelStyle, setPanelStyle] = useState<CSSProperties | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const notifications = useAppStore((state) => state.notifications)
  const markAllNotificationsRead = useAppStore((state) => state.markAllNotificationsRead)
  const removeNotification = useAppStore((state) => state.removeNotification)
  const clearReadNotifications = useAppStore((state) => state.clearReadNotifications)
  const clearAllNotifications = useAppStore((state) => state.clearAllNotifications)
  const unreadCount = notifications.filter((item) => !item.read).length
  const readCount = notifications.length - unreadCount

  const updatePanelPosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return

    const triggerRect = trigger.getBoundingClientRect()
    const panelHeight = panelRef.current?.getBoundingClientRect().height ?? 460
    const preferredTop = triggerRect.bottom + 12
    const maxTop = window.innerHeight - panelHeight - POPOVER_GUTTER
    const top = Math.max(POPOVER_GUTTER, Math.min(preferredTop, maxTop))
    const right = Math.max(POPOVER_GUTTER, window.innerWidth - triggerRect.right)

    setPanelStyle({
      ...initialPanelStyle,
      top,
      right,
    })
  }, [])

  useLayoutEffect(() => {
    if (!open) {
      setPanelStyle(null)
      return undefined
    }

    updatePanelPosition()
    const frame = window.requestAnimationFrame(updatePanelPosition)
    const handleViewportChange = () => updatePanelPosition()
    window.addEventListener('resize', handleViewportChange)
    // The main content scrolls inside Layout, so listen in capture phase.
    window.addEventListener('scroll', handleViewportChange, true)

    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('resize', handleViewportChange)
      window.removeEventListener('scroll', handleViewportChange, true)
    }
  }, [open, updatePanelPosition])

  useEffect(() => {
    const timers = notifications
      .filter((item) => item.read)
      .map((item) => {
        const createdAt = new Date(item.createdAt).getTime()
        const elapsed = Number.isFinite(createdAt) ? Date.now() - createdAt : 0
        const remaining = Math.max(0, READ_NOTIFICATION_RETENTION_MS - elapsed)
        return window.setTimeout(() => removeNotification(item.id), remaining)
      })

    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [notifications, removeNotification])

  useEffect(() => {
    if (!open) return undefined

    const focusFrame = window.requestAnimationFrame(() => panelRef.current?.focus())
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      const clickedTrigger = containerRef.current?.contains(target)
      const clickedPanel = panelRef.current?.contains(target)
      if (!clickedTrigger && !clickedPanel) setOpen(false)
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      window.cancelAnimationFrame(focusFrame)
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const openNotification = (id: string, jobId: string) => {
    removeNotification(id)
    setOpen(false)
    navigate(`/dubbing/${jobId}`)
  }

  const panel = open ? (
    <div
      ref={panelRef}
      id={POPOVER_ID}
      role="dialog"
      aria-modal="false"
      aria-labelledby={POPOVER_TITLE_ID}
      tabIndex={-1}
      style={panelStyle || initialPanelStyle}
      className="overflow-hidden rounded-2xl border border-surface-700/70 bg-surface-900/95 shadow-2xl shadow-black/30 backdrop-blur-xl focus:outline-none"
    >
      <div className="flex items-center justify-between border-b border-surface-700/60 px-4 py-3">
        <div>
          <h3 id={POPOVER_TITLE_ID} className="text-sm font-semibold text-surface-100">Thông báo</h3>
          <p className="text-xs text-surface-500">
            {unreadCount ? `${unreadCount} thông báo chưa đọc` : 'Bạn đã xem hết thông báo'}
          </p>
        </div>
        <div className="flex items-center gap-1">
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={markAllNotificationsRead}
              className="rounded-lg px-2 py-1 text-xs font-medium text-primary-400 transition-colors hover:bg-primary-500/10 hover:text-primary-300"
            >
              Đánh dấu đã đọc
            </button>
          )}
          {readCount > 0 && (
            <button
              type="button"
              onClick={clearReadNotifications}
              className="rounded-lg px-2 py-1 text-xs font-medium text-surface-500 transition-colors hover:bg-surface-800 hover:text-surface-200"
            >
              Xóa đã đọc
            </button>
          )}
          {notifications.length > 0 && (
            <button
              type="button"
              onClick={clearAllNotifications}
              className="rounded-lg p-1.5 text-surface-500 transition-colors hover:bg-red-500/10 hover:text-red-300"
              aria-label="Xóa tất cả thông báo"
              title="Xóa tất cả thông báo"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <div className="max-h-[min(28rem,calc(100vh-10rem))] overflow-y-auto p-2">
        {notifications.length === 0 ? (
          <div className="px-4 py-10 text-center">
            <Bell className="mx-auto mb-3 h-8 w-8 text-surface-600" aria-hidden="true" />
            <p className="text-sm text-surface-400">Không có thông báo mới</p>
            <p className="mt-1 text-xs text-surface-600">Kết quả video sẽ xuất hiện ở đây.</p>
          </div>
        ) : (
          notifications.map((item) => {
            const isComplete = item.kind === 'completed'
            return (
              <div
                key={item.id}
                className={`group mb-1 rounded-xl p-3 transition-colors hover:bg-surface-800/70 ${item.read ? 'opacity-75' : 'bg-surface-800/40'}`}
              >
                <div className="flex items-start gap-3">
                  {isComplete ? (
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden="true" />
                  ) : (
                    <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" aria-hidden="true" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-surface-100">{item.title}</p>
                      {!item.read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary-400" aria-label="Chưa đọc" />}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-surface-400">{item.message}</p>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="text-[11px] text-surface-600">{formatNotificationTime(item.createdAt)}</span>
                      <button
                        type="button"
                        onClick={() => openNotification(item.id, item.jobId)}
                        className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors ${isComplete ? 'text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300' : 'text-primary-400 hover:bg-primary-500/10 hover:text-primary-300'}`}
                      >
                        {isComplete ? 'Mở video' : 'Mở quy trình'}
                        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeNotification(item.id)}
                    className="rounded-md p-1 text-surface-600 opacity-0 transition-opacity hover:bg-red-500/10 hover:text-red-300 group-hover:opacity-100 focus:opacity-100"
                    aria-label="Xóa thông báo"
                    title="Xóa thông báo"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  ) : null

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        className="relative rounded-lg p-2 text-surface-400 transition-colors hover:bg-surface-800/50 hover:text-surface-200 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
        aria-label={unreadCount > 0 ? `Thông báo, ${unreadCount} chưa đọc` : 'Thông báo'}
        aria-expanded={open}
        aria-controls={POPOVER_ID}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary-500 px-1 text-[10px] font-bold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {typeof document !== 'undefined' && panel ? createPortal(panel, document.body) : null}
    </div>
  )
}
