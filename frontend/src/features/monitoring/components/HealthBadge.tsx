import type { AlertState } from '../../../core/types'

const stateClasses: Record<AlertState, string> = {
  green: 'bg-green-100 text-green-800 border-green-300',
  amber: 'bg-amber-100 text-amber-800 border-amber-300',
  red: 'bg-red-100 text-red-800 border-red-300',
}

const stateLabels: Record<AlertState, string> = {
  green: 'Healthy',
  amber: 'Warning',
  red: 'Critical',
}

interface HealthBadgeProps {
  readonly state: AlertState
}

export function HealthBadge({ state }: HealthBadgeProps): JSX.Element {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${stateClasses[state]}`}
    >
      <span className={`mr-1 h-2 w-2 rounded-full ${
        state === 'green' ? 'bg-green-500' : state === 'amber' ? 'bg-amber-500' : 'bg-red-500'
      }`} />
      {stateLabels[state]}
    </span>
  )
}
