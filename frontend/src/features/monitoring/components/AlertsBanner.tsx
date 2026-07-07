import { useNavigate } from 'react-router-dom'
import { useSystemAlerts } from '../api/useSystemAlerts'

export function AlertsBanner(): JSX.Element | null {
  const navigate = useNavigate()
  const { data, isLoading } = useSystemAlerts({ severity: 'critical' })

  if (isLoading || !data) return null

  const unresolved = data.alerts.filter(
    (a) => !a.resolved && a.severity === 'critical',
  )
  if (unresolved.length === 0) return null

  return (
    <button
      type="button"
      onClick={() => navigate('/monitoring/alerts')}
      className="flex w-full items-center justify-center gap-2 bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span>
        {unresolved.length} unresolved critical alert
        {unresolved.length !== 1 ? 's' : ''} — click to review
      </span>
    </button>
  )
}
