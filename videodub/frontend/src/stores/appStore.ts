import { create } from 'zustand'

interface DubbingJob {
  id: string
  url: string
  sourceLang: string
  targetLang: string
  voice: string
  whisperModel: string
  status: 'pending' | 'downloading' | 'transcribing' | 'translating' | 'tts' | 'removing_vocals' | 'merging' | 'completed' | 'error'
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

interface AppState {
  // Current job
  currentJob: DubbingJob | null
  setCurrentJob: (job: DubbingJob | null) => void
  updateJobStatus: (status: DubbingJob['status'], progress?: number) => void

  // History
  history: DubbingJob[]
  addToHistory: (job: DubbingJob) => void
  removeFromHistory: (id: string) => void
  clearHistory: () => void

  // Settings
  settings: Settings
  updateSettings: (settings: Partial<Settings>) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentJob: null,
  setCurrentJob: (job) => set({ currentJob: job }),
  updateJobStatus: (status, progress) =>
    set((state) => ({
      currentJob: state.currentJob
        ? { ...state.currentJob, status, progress: progress ?? state.currentJob.progress }
        : null,
    })),

  history: [],
  addToHistory: (job) =>
    set((state) => ({ history: [job, ...state.history] })),
  removeFromHistory: (id) =>
    set((state) => ({ history: state.history.filter((j) => j.id !== id) })),
  clearHistory: () => set({ history: [] }),

  settings: {
    whisperModel: 'small',
    defaultTargetLang: 'vi',
    defaultVoice: 'vi-VN-HoaiMyNeural',
    ttsSpeed: 1,
  },
  updateSettings: (newSettings) =>
    set((state) => ({
      settings: { ...state.settings, ...newSettings },
    })),
}))
