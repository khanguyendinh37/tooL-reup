import { useEffect } from 'react'
import { getSettings } from '@/lib/api'
import { useAppStore } from '@/stores/appStore'
import { clampBlurRegion, DEFAULT_BLUR_REGION, subtitleYForPreset, type BlurRegion } from '@/lib/workflow'

/**
 * Hydrate Zustand `dubbingPreferences` from the backend on app start so the
 * Dubbing page shows the same values the user saved on the Settings page.
 *
 * Without this hook, the Dubbing page reads its initial slider positions from
 * the persisted Zustand store, which can stay stale (e.g. user saved 0.20 in
 * Settings but Zustand still holds 0.1). This hook is the single point that
 * reconciles that drift on every app load.
 */
export function useSyncSettings() {
  const updateDubbingPreferences = useAppStore((state) => state.updateDubbingPreferences)
  const activeWorkflow = useAppStore((state) => state.activeWorkflow)

  useEffect(() => {
    let cancelled = false
    const sync = async () => {
      try {
        const settings = await getSettings() as Record<string, unknown>
        if (cancelled) return
        // Do not overwrite an in-flight workflow: that carries the exact values
        // the user picked for the current run, which is more authoritative
        // than the global Settings default.
        if (activeWorkflow) return

        const blurRegion = settings.blur_region && typeof settings.blur_region === 'object'
          ? clampBlurRegion(settings.blur_region as BlurRegion)
          : DEFAULT_BLUR_REGION
        const savedPosition = (settings.subtitle_position as string) || 'bottom'
        const savedPositionY = Number(settings.subtitle_position_y)
        const subtitlePositionY = Number.isFinite(savedPositionY)
          ? Math.min(Math.max(savedPositionY, 0), 1)
          : subtitleYForPreset(savedPosition)

        updateDubbingPreferences({
          sourceLang: (settings.default_source_lang as string) || 'en',
          targetLang: (settings.default_target_lang as string) || 'vi',
          voice: (settings.default_voice as string) || 'vi-VN-HoaiMyNeural',
          whisperModel: (settings.whisper_model as string) || 'small',
          ttsSpeed: parseFloat((settings.tts_speed as string) || '1.0'),
          subtitleEnabled: String(settings.subtitle_enabled) === 'true',
          subtitlePosition: savedPosition,
          subtitlePositionY,
          subtitleSize: settings.subtitle_size ? parseInt(String(settings.subtitle_size), 10) : 13,
          subtitleColor: (settings.subtitle_color as string) || 'white',
          blurExistingSubtitles: String(settings.blur_existing_subtitles) === 'true',
          blurRegion,
          dubbingVolume: parseFloat(String(settings.default_dubbing_volume ?? 1.0)),
          backgroundVolume: parseFloat(String(settings.default_background_volume ?? 1.0)),
          originalVocalsVolume: parseFloat(String(settings.default_original_volume ?? 0.1)),
        })
      } catch (err) {
        // Non-fatal: Dubbing page already has its own loadSettings() call that
        // will retry on mount. Failing here just means we keep the persisted
        // Zustand values until the next page mount.
        console.error('useSyncSettings: backend fetch failed', err)
      }
    }
    sync()
    return () => {
      cancelled = true
    }
  }, [activeWorkflow, updateDubbingPreferences])
}
