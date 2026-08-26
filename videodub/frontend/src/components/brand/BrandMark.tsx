import { Sparkles } from 'lucide-react'
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

const iconClasses = {
  sm: 'h-5 w-5',
  md: 'h-8 w-8',
  lg: 'h-10 w-10',
} as const

export default function BrandMark({ size = 'sm', className }: BrandMarkProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        'flex shrink-0 items-center justify-center bg-gradient-to-br from-primary-500 to-accent-cyan',
        sizeClasses[size],
        className,
      )}
    >
      <Sparkles className={cn('text-white', iconClasses[size])} />
    </div>
  )
}
