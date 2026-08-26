import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { DEFAULT_BLUR_REGION, DEFAULT_WORKFLOW_FORM, type ActiveWorkflow, type AppNotification, type WorkflowFormValues } from '@/lib/workflow'

interface LegacyDubbingJob {
  id: string
  url: string
  sourceLang: string
  targetLang: string
  voice: string
  whisperModel: string
  status: string
  progress: number
  error?: string
  resultUrl?: string
  createdAt: string
}

interface Settings {
  whisperModel: string
  defaultTargetLang: string
  defaultVoice: string
  ttsSpeed: number
}

type DubbingPreferences = Pick<WorkflowFormValues,
  | 'sourceLang'
  | 'targetLang'
  | 'voice'
  | 'whisperModel'
  | 'ttsSpeed'
  | 'subtitleEnabled'
  | 'subtitlePosition'
  | 'subtitlePositionY'
  | 'subtitleSize'
  | 'subtitleColor'
  | 'blurExistingSubtitles'
  | 'blurRegion'
  | 'dubbingVolume'
  | 'backgroundVolume'
  | 'originalVocalsVolume'
>

const DEFAULT_DUBBING_PREFERENCES: DubbingPreferences = {
  sourceLang: DEFAULT_WORKFLOW_FORM.sourceLang,
  targetLang: DEFAULT_WORKFLOW_FORM.targetLang,
  voice: DEFAULT_WORKFLOW_FORM.voice,
  whisperModel: DEFAULT_WORKFLOW_FORM.whisperModel,
  ttsSpeed: DEFAULT_WORKFLOW_FORM.ttsSpeed,
  subtitleEnabled: DEFAULT_WORKFLOW_FORM.subtitleEnabled,
  subtitlePosition: DEFAULT_WORKFLOW_FORM.subtitlePosition,
  subtitlePositionY: DEFAULT_WORKFLOW_FORM.subtitlePositionY,
  subtitleSize: DEFAULT_WORKFLOW_FORM.subtitleSize,
  subtitleColor: DEFAULT_WORKFLOW_FORM.subtitleColor,
  blurExistingSubtitles: DEFAULT_WORKFLOW_FORM.blurExistingSubtitles,
  blurRegion: { ...DEFAULT_BLUR_REGION },
  dubbingVolume: DEFAULT_WORKFLOW_FORM.dubbingVolume,
  backgroundVolume: DEFAULT_WORKFLOW_FORM.backgroundVolume,
  originalVocalsVolume: DEFAULT_WORKFLOW_FORM.originalVocalsVolume,
}

interface AppState {
  activeWorkflow: ActiveWorkflow | null
  setActiveWorkflow: (workflow: ActiveWorkflow | null) => void
  patchActiveWorkflow: (patch: Partial<ActiveWorkflow>) => void
  clearActiveWorkflow: () => void

  dubbingPreferences: DubbingPreferences
  dubbingPreferencesSaved: boolean
  updateDubbingPreferences: (preferences: Partial<DubbingPreferences>) => void

  notifications: AppNotification[]
  addNotification: (notification: AppNotification) => void
  markNotificationRead: (id: string) => void
  markAllNotificationsRead: () => void
  removeNotification: (id: string) => void
  clearReadNotifications: () => void
  clearAllNotifications: () => void

  // Keep the original store surface available for any existing consumers.
  currentJob: LegacyDubbingJob | null
  setCurrentJob: (job: LegacyDubbingJob | null) => void
  updateJobStatus: (status: string, progress?: number) => void
  history: LegacyDubbingJob[]
  addToHistory: (job: LegacyDubbingJob) => void
  removeFromHistory: (id: string) => void
  clearHistory: () => void
  settings: Settings
  updateSettings: (settings: Partial<Settings>) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activeWorkflow: null,
      setActiveWorkflow: (workflow) => set({ activeWorkflow: workflow }),
      patchActiveWorkflow: (patch) => set((state) => ({
        activeWorkflow: state.activeWorkflow
          ? { ...state.activeWorkflow, ...patch }
          : null,
      })),
      clearActiveWorkflow: () => set({ activeWorkflow: null }),

      dubbingPreferences: DEFAULT_DUBBING_PREFERENCES,
      dubbingPreferencesSaved: false,
      updateDubbingPreferences: (preferences) => set((state) => ({
        dubbingPreferences: {
          ...state.dubbingPreferences,
          ...preferences,
          blurRegion: preferences.blurRegion
            ? { ...preferences.blurRegion }
            : state.dubbingPreferences.blurRegion,
        },
        dubbingPreferencesSaved: true,
      })),

      notifications: [],
      addNotification: (notification) => set((state) => {
        const existingIndex = state.notifications.findIndex((item) => item.id === notification.id)
        if (existingIndex >= 0) {
          const next = [...state.notifications]
          next[existingIndex] = notification
          return { notifications: next }
        }
        return { notifications: [notification, ...state.notifications].slice(0, 30) }
      }),
      markNotificationRead: (id) => set((state) => ({
        notifications: state.notifications.map((item) => item.id === id ? { ...item, read: true } : item),
      })),
      markAllNotificationsRead: () => set((state) => ({
        notifications: state.notifications.map((item) => ({ ...item, read: true })),
      })),
      removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter((item) => item.id !== id),
      })),
      clearReadNotifications: () => set((state) => ({
        notifications: state.notifications.filter((item) => !item.read),
      })),
      clearAllNotifications: () => set({ notifications: [] }),

      currentJob: null,
      setCurrentJob: (job) => set({ currentJob: job }),
      updateJobStatus: (status, progress) => set((state) => ({
        currentJob: state.currentJob
          ? { ...state.currentJob, status, progress: progress ?? state.currentJob.progress }
          : null,
      })),
      history: [],
      addToHistory: (job) => set((state) => ({ history: [job, ...state.history] })),
      removeFromHistory: (id) => set((state) => ({ history: state.history.filter((job) => job.id !== id) })),
      clearHistory: () => set({ history: [] }),
      settings: {
        whisperModel: 'small',
        defaultTargetLang: 'vi',
        defaultVoice: 'vi-VN-HoaiMyNeural',
        ttsSpeed: 1,
      },
      updateSettings: (newSettings) => set((state) => ({
        settings: { ...state.settings, ...newSettings },
      })),
    }),
    {
      name: 'videodub-app-state',
      partialize: (state) => ({
        activeWorkflow: state.activeWorkflow,
        dubbingPreferences: state.dubbingPreferences,
        dubbingPreferencesSaved: state.dubbingPreferencesSaved,
        notifications: state.notifications,
      }),
    },
  ),
)
