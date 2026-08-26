export type NotificationSoundKind = 'completed' | 'error'

type AudioContextConstructor = new () => AudioContext

let audioContext: AudioContext | null = null
let audioUnlocked = false

function getAudioContext(): AudioContext | null {
  if (audioContext) return audioContext
  if (typeof window === 'undefined') return null

  const AudioContextCtor = window.AudioContext
    || (window as typeof window & { webkitAudioContext?: AudioContextConstructor }).webkitAudioContext
  if (!AudioContextCtor) return null

  try {
    audioContext = new AudioContextCtor()
    return audioContext
  } catch {
    return null
  }
}

/** Unlock audio from a real user gesture so later background events can play a cue. */
export async function unlockNotificationSound(): Promise<void> {
  const context = getAudioContext()
  if (!context) return

  try {
    if (context.state === 'suspended') await context.resume()
    audioUnlocked = context.state === 'running'
  } catch {
    audioUnlocked = false
  }
}

/** Play a quiet, short cue without ever blocking the job monitor. */
export function playNotificationSound(kind: NotificationSoundKind): void {
  const context = audioContext
  if (!context || !audioUnlocked || context.state !== 'running') return

  try {
    const now = context.currentTime
    const gain = context.createGain()
    const frequencies = kind === 'completed' ? [880, 1320] : [440, 220]
    const duration = 0.16

    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(0.055, now + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.5)
    gain.connect(context.destination)

    frequencies.forEach((frequency, index) => {
      const oscillator = context.createOscillator()
      const startAt = now + index * 0.14
      oscillator.type = kind === 'completed' ? 'sine' : 'triangle'
      oscillator.frequency.setValueAtTime(frequency, startAt)
      oscillator.connect(gain)
      oscillator.start(startAt)
      oscillator.stop(startAt + duration)
    })

    window.setTimeout(() => {
      try {
        gain.disconnect()
      } catch {
        // The context may have been closed while the cue was playing.
      }
    }, 650)
  } catch {
    // Audio is optional feedback. Unsupported/suspended audio must not affect jobs.
  }
}
