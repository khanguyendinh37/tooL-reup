import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getDubbingStatus } from '@/lib/api'
import { playNotificationSound } from '@/lib/notificationSound'
import { useAppStore } from '@/stores/appStore'
import { getWorkflowPhase, notificationForJob, type JobStatus } from '@/lib/workflow'

const POLL_INTERVAL_MS = 2000
const MAX_CONSECUTIVE_POLL_ERRORS = 5
// Stop tracking when the server has reported no new activity for this long.
// Phase transitions and download-progress writes refresh updated_at, so a
// healthy job is never cut off no matter how long the whole workflow runs.
const MAX_SERVER_IDLE_MS = 15 * 60 * 1000
// Safety net for a phase that keeps reporting activity but never finishes.
// The backend sends a heartbeat every 20 s, so the idle check above catches a
// dead job; this limit only has to exceed the longest real phase, and
// Whisper/Demucs on a multi-hour video on CPU can take several hours.
const MAX_PHASE_RUNTIME_MS = 12 * 60 * 60 * 1000
// The download phase has a shorter watchdog: yt-dlp/pytubefix can hang
// silently (bot-detection prompts, blocked IPs), so we abort after 90 s
// instead of letting the UI spin forever.
const MAX_DOWNLOAD_IDLE_MS = 90 * 1000
const TERMINAL_STATUSES: JobStatus[] = ['preview_ready', 'completed', 'error', 'cancelled']

function isJobStatus(value: string): value is JobStatus {
  return [
    'pending', 'downloading', 'preview_ready', 'processing', 'transcribing',
    'translating', 'tts', 'removing_vocals', 'merging', 'completed', 'error', 'cancelled',
  ].includes(value)
}

export default function useActiveDubbingMonitor() {
  const navigate = useNavigate()
  const activeJobId = useAppStore((state) => state.activeWorkflow?.jobId)
  const activeStatus = useAppStore((state) => state.activeWorkflow?.status)
  const patchActiveWorkflow = useAppStore((state) => state.patchActiveWorkflow)
  const addNotification = useAppStore((state) => state.addNotification)
  const announcedEventsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!activeJobId) return undefined
    // Terminal statuses have nothing to monitor. This also keeps a watchdog
    // "stopped" decision sticky: once we mark the workflow as error below, the
    // status change disarms this effect so later polls cannot overwrite the
    // local error with the server's stale non-terminal status.
    if (activeStatus && TERMINAL_STATUSES.includes(activeStatus)) return undefined

    let disposed = false
    let timer: number | undefined
    let consecutiveErrors = 0
    // Idle/runtime budgets are measured with the client clock against activity
    // observed from polls, never against job.created_at — an old job that is
    // still progressing must not be cut off.
    const phaseStartedAt = Date.now()
    let lastSeenUpdatedAt: string | null = null
    let lastServerActivityAt = Date.now()

    const notifySystem = (jobId: string, kind: 'completed' | 'error', message: string) => {
      if (localStorage.getItem('notificationsEnabled') === 'false') return
      if (!('Notification' in window) || Notification.permission !== 'granted') return
      const notification = new Notification(
        kind === 'completed' ? 'VideoDub - Hoàn thành!' : 'VideoDub - Lỗi xử lý',
        {
          body: message,
          icon: '/videodub-logo.svg',
          tag: `videodub-${jobId}-${kind}`,
          requireInteraction: false,
        },
      )
      const closeTimer = window.setTimeout(() => notification.close(), 8_000)
      notification.onclick = () => {
        window.clearTimeout(closeTimer)
        window.focus()
        navigate(`/dubbing/${jobId}`)
        notification.close()
      }
    }

    const reconcile = async () => {
      try {
        const job = await getDubbingStatus(activeJobId)
        if (disposed) return
        consecutiveErrors = 0

        // Any change in the server's updated_at counts as progress. The first
        // poll also counts, giving each tracking session a fresh idle budget.
        if (job.updated_at && job.updated_at !== lastSeenUpdatedAt) {
          lastSeenUpdatedAt = job.updated_at
          lastServerActivityAt = Date.now()
        }

        const nextStatus = isJobStatus(job.status) ? job.status : 'processing'
        const current = useAppStore.getState().activeWorkflow
        if (!current || current.jobId !== activeJobId) return

        const previousStatus = current.status
        const nextPhase = getWorkflowPhase(nextStatus)
        patchActiveWorkflow({
          status: nextStatus,
          phase: nextPhase,
          progress: job.progress ?? current.progress,
          error: job.error || null,
          previewUrl: nextStatus === 'preview_ready'
            ? `/api/dubbing/${activeJobId}/preview-url`
            : current.previewUrl,
          resultUrl: nextStatus === 'completed'
            ? `/api/dubbing/${activeJobId}/download`
            : current.resultUrl,
          updatedAt: job.updated_at,
        })

        if (previousStatus !== nextStatus && (nextStatus === 'completed' || nextStatus === 'error')) {
          const updated = {
            ...current,
            status: nextStatus,
            phase: nextPhase,
            progress: job.progress ?? current.progress,
            error: job.error || null,
            updatedAt: job.updated_at,
          }
          const kind = nextStatus === 'completed' ? 'completed' : 'error'
          const eventKey = `${activeJobId}:${kind}`
          const alreadyStored = useAppStore.getState().notifications.some((item) => item.id === eventKey)

          if (!announcedEventsRef.current.has(eventKey) && !alreadyStored) {
            announcedEventsRef.current.add(eventKey)
            addNotification(notificationForJob(updated, kind))
            if (localStorage.getItem('notificationsEnabled') !== 'false') {
              playNotificationSound(kind)
            }
            notifySystem(activeJobId, kind, kind === 'completed'
              ? 'Video lồng tiếng đã xử lý xong. Bấm để mở video.'
              : job.error || 'Quy trình lồng tiếng gặp lỗi. Bấm để mở và chạy lại.')
          } else {
            announcedEventsRef.current.add(eventKey)
          }
        }

        if (!TERMINAL_STATUSES.includes(nextStatus)) {
          const stalled = Date.now() - lastServerActivityAt >= MAX_SERVER_IDLE_MS
          const tooLong = Date.now() - phaseStartedAt >= MAX_PHASE_RUNTIME_MS
          // pytubefix / yt-dlp can hang silently while waiting for a PO
          // token prompt or a captcha. Surface a friendlier error sooner
          // than the 15-minute global idle budget.
          const downloadStuck = nextStatus === 'downloading'
            && Date.now() - lastServerActivityAt >= MAX_DOWNLOAD_IDLE_MS

          if (stalled || tooLong || downloadStuck) {
            const message = downloadStuck
              ? `Không nhận được tiến trình tải xuống trong ${MAX_DOWNLOAD_IDLE_MS / 1000} giây. Có thể máy chủ video đang chặn yêu cầu (cookie, captcha, hoặc khu vực). Vui lòng thử lại hoặc cập nhật cookies cho ${nextStatus === 'downloading' ? 'nền tảng này' : 'nền tảng này'}.`
              : stalled
                ? `Không thấy tiến trình mới trong ${MAX_SERVER_IDLE_MS / 60000} phút nên đã dừng theo dõi. Quy trình có thể bị gián đoạn — bạn hãy thử lại.`
                : 'Quy trình chạy quá lâu nên đã dừng theo dõi để tránh treo vô hạn. Bạn có thể thử lại.'
            patchActiveWorkflow({
              status: 'error',
              phase: 'error',
              error: message,
              updatedAt: new Date().toISOString(),
            })
            addNotification(notificationForJob({
              ...current,
              status: 'error',
              phase: 'error',
              error: message,
              updatedAt: new Date().toISOString(),
            }, 'error'))
            return
          }
          timer = window.setTimeout(reconcile, POLL_INTERVAL_MS)
        }
      } catch (error) {
        consecutiveErrors += 1
        if (!disposed && consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
          const message = error instanceof Error
            ? error.message
            : 'Không thể cập nhật trạng thái quy trình.'
          const current = useAppStore.getState().activeWorkflow
          if (current?.jobId === activeJobId) {
            const errorMessage = `${message} Đã dừng theo dõi để tránh trạng thái loading vô hạn.`
            patchActiveWorkflow({
              status: 'error',
              phase: 'error',
              error: errorMessage,
              updatedAt: new Date().toISOString(),
            })
            const eventKey = `${activeJobId}:error`
            if (!announcedEventsRef.current.has(eventKey)) {
              announcedEventsRef.current.add(eventKey)
              addNotification(notificationForJob({
                ...current,
                status: 'error',
                phase: 'error',
                error: errorMessage,
                updatedAt: new Date().toISOString(),
              }, 'error'))
            }
          }
          return
        }
        if (!disposed) timer = window.setTimeout(reconcile, POLL_INTERVAL_MS)
      }
    }

    void reconcile()
    return () => {
      disposed = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [activeJobId, activeStatus, addNotification, navigate, patchActiveWorkflow])
}
