import { useEffect, useRef, useState } from 'react'
import { previewTtsVoice } from '@/lib/api'

interface VoicePreviewButtonProps {
  voice: string
  lang?: string
  /** Optional fixed text. When provided, the backend skips its demo-sentence lookup. */
  text?: string
  /** Disable interaction (e.g. while a job is running). */
  disabled?: boolean
}

/**
 * A compact "listen" button placed next to a TTS voice selector.
 *
 * Clicking it asks the backend to synthesize a short MP3 sample for the
 * currently-selected voice, then plays it in a hidden ``<audio>`` element.
 * The same button becomes a stop button while audio is playing. We cache
 * one object URL per ``voice|lang|text`` so flipping between voices
 * doesn't make a fresh request every render - the blob URL is revoked
 * when the component unmounts or the key changes.
 */
export function VoicePreviewButton({ voice, lang, text, disabled }: VoicePreviewButtonProps) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'playing' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState<string>('')
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const objectUrlRef = useRef<string | null>(null)

  // Tear down on unmount so we don't leak object URLs across page changes.
  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
      }
    }
  }, [])

  // Stop playback when the selected voice changes - the URL the audio
  // element is playing is now stale, so we drop it cleanly rather than
  // letting it finish a sentence for a voice the user just deselected.
  useEffect(() => {
    if (status === 'playing' || status === 'loading') {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      setStatus('idle')
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
    setErrorMessage('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voice, lang, text])

  const handleClick = async () => {
    if (disabled) return
    // If currently playing or loading, treat the click as "stop".
    if (status === 'playing' || status === 'loading') {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      setStatus('idle')
      return
    }

    setStatus('loading')
    setErrorMessage('')
    try {
      const url = await previewTtsVoice({ voice, lang, text })
      // Revoke any previous URL before swapping to a new one.
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
      }
      objectUrlRef.current = url
      const audio = audioRef.current ?? new Audio()
      audioRef.current = audio
      audio.src = url
      audio.onended = () => setStatus('idle')
      audio.onerror = () => {
        setStatus('error')
        setErrorMessage('Trình duyệt không phát được audio này')
      }
      await audio.play()
      setStatus('playing')
    } catch (err) {
      setStatus('error')
      setErrorMessage(err instanceof Error ? err.message : 'Lỗi không xác định')
    }
  }

  const label =
    status === 'loading' ? 'Đang tải…' :
    status === 'playing' ? 'Dừng' :
    'Nghe thử'

  const title =
    status === 'error' && errorMessage ? errorMessage :
    'Nghe thử giọng này'

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled && status === 'idle'}
      title={title}
      className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
        status === 'playing'
          ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30'
          : status === 'error'
          ? 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30'
          : 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30'
      }`}
    >
      {status === 'playing' ? (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>
      ) : status === 'loading' ? (
        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
      ) : (
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
      )}
      <span>{label}</span>
    </button>
  )
}
