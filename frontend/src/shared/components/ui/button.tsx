import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../utils/cn'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: 'default' | 'outline' | 'ghost'
}

export function Button({ className, variant = 'default', ...props }: ButtonProps): JSX.Element {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        variant === 'default' &&
          'bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-600',
        variant === 'outline' &&
          'border border-input bg-background hover:bg-gray-100 focus-visible:ring-gray-400',
        variant === 'ghost' && 'hover:bg-gray-100 focus-visible:ring-gray-400',
        'h-10 px-4 py-2',
        className,
      )}
      {...props}
    />
  )
}
