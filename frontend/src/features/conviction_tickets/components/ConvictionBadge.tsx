import { cn } from '../../../shared/utils/cn'

interface ConvictionBadgeProps {
  readonly score: number
  readonly size?: 'sm' | 'md' | 'lg'
}

function convictionColor(score: number): string {
  if (score >= 70) return 'bg-green-100 text-green-800'
  if (score >= 56) return 'bg-lime-100 text-lime-800'
  if (score >= 45) return 'bg-yellow-100 text-yellow-800'
  return 'bg-red-100 text-red-800'
}

function sizeClasses(size: 'sm' | 'md' | 'lg'): string {
  switch (size) {
    case 'sm':
      return 'px-2 py-0.5 text-xs'
    case 'lg':
      return 'px-4 py-2 text-lg'
    default:
      return 'px-2.5 py-1 text-sm'
  }
}

export function ConvictionBadge({ score, size = 'md' }: ConvictionBadgeProps): JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        convictionColor(score),
        sizeClasses(size),
      )}
    >
      {score}
    </span>
  )
}
