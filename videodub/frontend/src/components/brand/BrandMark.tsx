import { cn } from '@/lib/utils'

interface BrandMarkProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'h-10 w-10 rounded-xl',
  md: 'h-16 w-16 rounded-2xl',
  lg: 'h-20 w-20 rounded-2xl',
} as const

const iconSize = {
  sm: 22,
  md: 36,
  lg: 46,
} as const

/**
 * Brand logo: a friendly robot holding a microphone — represents
 * AI-powered voice / dubbing. Rendered as inline SVG so it picks up
 * the surrounding gradient and stays crisp at every size.
 */
export default function BrandMark({ size = 'sm', className }: BrandMarkProps) {
  const s = iconSize[size]
  return (
    <div
      aria-hidden="true"
      className={cn(
        'flex shrink-0 items-center justify-center bg-gradient-to-br from-primary-500 to-accent-cyan',
        sizeClasses[size],
        className,
      )}
    >
      <svg
        width={s}
        height={s}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Robot head */}
        <rect
          x="6"
          y="14"
          width="36"
          height="28"
          rx="8"
          fill="white"
          fillOpacity="0.95"
        />
        {/* Robot antenna */}
        <line
          x1="24"
          y1="14"
          x2="24"
          y2="8"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <circle cx="24" cy="6" r="2.5" fill="white" />

        {/* Eyes */}
        <circle cx="17" cy="26" r="3" fill="#0ea5e9" />
        <circle cx="31" cy="26" r="3" fill="#0ea5e9" />
        {/* Eye highlights */}
        <circle cx="18" cy="25" r="1" fill="white" />
        <circle cx="32" cy="25" r="1" fill="white" />

        {/* Smile (mouth grille) */}
        <rect x="15" y="34" width="18" height="2.5" rx="1.25" fill="#0ea5e9" fillOpacity="0.55" />
        <rect x="16" y="37.5" width="3" height="2" rx="1" fill="#0ea5e9" fillOpacity="0.55" />
        <rect x="20.5" y="37.5" width="3" height="2" rx="1" fill="#0ea5e9" fillOpacity="0.55" />
        <rect x="25" y="37.5" width="3" height="2" rx="1" fill="#0ea5e9" fillOpacity="0.55" />
        <rect x="29.5" y="37.5" width="3" height="2" rx="1" fill="#0ea5e9" fillOpacity="0.55" />

        {/* Robot body / base */}
        <rect x="10" y="42" width="28" height="10" rx="3" fill="white" fillOpacity="0.9" />
        <circle cx="16" cy="47" r="1.5" fill="#0ea5e9" />
        <circle cx="22" cy="47" r="1.5" fill="#22c55e" />
        <circle cx="28" cy="47" r="1.5" fill="#f59e0b" />

        {/* Microphone (held by robot) */}
        {/* Mic body */}
        <rect
          x="44"
          y="22"
          width="12"
          height="20"
          rx="6"
          fill="white"
          stroke="#0ea5e9"
          strokeWidth="2"
        />
        {/* Mic grille lines */}
        <line x1="47" y1="27" x2="53" y2="27" stroke="#0ea5e9" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="47" y1="30" x2="53" y2="30" stroke="#0ea5e9" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="47" y1="33" x2="53" y2="33" stroke="#0ea5e9" strokeWidth="1.2" strokeLinecap="round" />
        <line x1="47" y1="36" x2="53" y2="36" stroke="#0ea5e9" strokeWidth="1.2" strokeLinecap="round" />
        {/* Mic stand arc */}
        <path
          d="M40 32 Q40 44 50 44 Q60 44 60 32"
          stroke="white"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
        {/* Mic stand stem */}
        <line x1="50" y1="44" x2="50" y2="52" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        {/* Mic stand base */}
        <line x1="44" y1="54" x2="56" y2="54" stroke="white" strokeWidth="2.5" strokeLinecap="round" />

        {/* Sound waves (showing robot is "broadcasting") */}
        <path
          d="M38 28 Q41 32 38 36"
          stroke="white"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
          strokeOpacity="0.6"
        />
      </svg>
    </div>
  )
}
