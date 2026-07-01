import { useParams, Link } from 'react-router-dom'
import { useTicket } from '../api/useTicket'
import { useReviewTicket, useActionTicket } from '../api/useTicketActions'
import { ConvictionBadge } from '../components/ConvictionBadge'
import { ConformalIntervalBar } from '../components/ConformalIntervalBar'
import { BacktestPassTable } from '../components/BacktestPassTable'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'
import { useState } from 'react'

export function DetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>()
  const ticketId = id ?? ''
  const { data: ticket, isLoading, isError, error } = useTicket(ticketId)
  const reviewMutation = useReviewTicket(ticketId)
  const actionMutation = useActionTicket(ticketId)
  const [notes, setNotes] = useState('')

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading ticket...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-600" role="alert">
            {error instanceof Error ? error.message : 'Failed to load ticket'}
          </p>
          <Link to="/tickets">
            <Button type="button" variant="outline" className="mt-4">
              Back to Inbox
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  if (!ticket) return <></>

  const canReview = ticket.status === 'TRADABLE'
  const canAction = ticket.status === 'TRADABLE' || ticket.status === 'REVIEWED'
  const isResolved = ticket.status === 'RESOLVED'

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Link to="/tickets">
          <Button type="button" variant="outline">
            Back to Inbox
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <CardTitle className="font-mono text-xl">{ticket.ticker_id}</CardTitle>
              <span className="text-muted-foreground">{ticket.universe_id}</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium">
                {ticket.horizon}
              </span>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  ticket.direction === 'LONG'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                }`}
              >
                {ticket.direction}
              </span>
              <StatusBadge status={ticket.status} />
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Conviction</p>
            <ConvictionBadge score={ticket.conviction_score} size="lg" />
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">
              Predicted Return with Conformal Interval
            </h3>
            <ConformalIntervalBar
              lower={ticket.conformal_lower}
              predicted={ticket.predicted_return}
              upper={ticket.conformal_upper}
            />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Inference Date: </span>
              <span>{new Date(ticket.inference_date).toLocaleDateString()}</span>
            </div>
            {ticket.resolution_date && (
              <div>
                <span className="text-muted-foreground">Resolution Date: </span>
                <span>{new Date(ticket.resolution_date).toLocaleDateString()}</span>
              </div>
            )}
            <div>
              <span className="text-muted-foreground">Passes: </span>
              <span className="font-medium">{ticket.backtest_passes} / 4</span>
            </div>
            {isResolved && ticket.actual_return !== null && (
              <div>
                <span className="text-muted-foreground">Actual Return: </span>
                <span
                  className={`font-medium ${
                    ticket.actual_return > 0
                      ? 'text-green-600'
                      : ticket.actual_return < 0
                        ? 'text-red-600'
                        : 'text-gray-600'
                  }`}
                >
                  {ticket.actual_return > 0 ? '+' : ''}
                  {ticket.actual_return.toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Backtest Validation</CardTitle>
        </CardHeader>
        <CardContent>
          <BacktestPassTable
            backtestPasses={ticket.backtest_passes}
            passStrategies={ticket.backtest_pass_strategies}
          />
          {ticket.backtest_pass_strategies.length > 0 && (
            <div className="mt-3 text-sm">
              <span className="text-muted-foreground">Passed strategies: </span>
              <span className="font-medium">
                {ticket.backtest_pass_strategies
                  .map((s) =>
                    s
                      .replace(/_/g, ' ')
                      .replace(/\b\w/g, (c) => c.toUpperCase()),
                  )
                  .join(', ')}
              </span>
            </div>
          )}
          <div className="mt-3">
            <Link
              to={`/backtests/${ticket.universe_id}/${ticket.ticker_id}`}
              className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
            >
              View detailed backtest results
            </Link>
          </div>
        </CardContent>
      </Card>

      {isResolved && ticket.outcome && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Outcome</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <OutcomeBadge outcome={ticket.outcome} />
            {ticket.actual_return !== null && (
              <p className="text-sm">
                <span className="text-muted-foreground">Actual Return: </span>
                <span
                  className={`font-medium ${
                    ticket.actual_return > 0
                      ? 'text-green-600'
                      : ticket.actual_return < 0
                        ? 'text-red-600'
                        : 'text-gray-600'
                  }`}
                >
                  {ticket.actual_return > 0 ? '+' : ''}
                  {ticket.actual_return.toFixed(2)}%
                </span>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {!isResolved && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-3">
              {canReview && (
                <Button
                  type="button"
                  onClick={() => reviewMutation.mutate()}
                  disabled={reviewMutation.isPending}
                >
                  {reviewMutation.isPending ? 'Marking...' : 'Mark Reviewed'}
                </Button>
              )}
              {canAction && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => actionMutation.mutate({ notes: notes || undefined })}
                  disabled={actionMutation.isPending}
                >
                  {actionMutation.isPending ? 'Marking...' : 'Mark Actioned'}
                </Button>
              )}
            </div>
            {canAction && (
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Notes (optional)
                </label>
                <textarea
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
                  placeholder="Add notes about this action..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            )}

            {reviewMutation.isError && (
              <p className="text-sm text-red-600" role="alert">
                {reviewMutation.error instanceof Error
                  ? reviewMutation.error.message
                  : 'Review failed'}
              </p>
            )}
            {actionMutation.isError && (
              <p className="text-sm text-red-600" role="alert">
                {actionMutation.error instanceof Error
                  ? actionMutation.error.message
                  : 'Action failed'}
              </p>
            )}
            {reviewMutation.isSuccess && (
              <p className="text-sm text-green-600" role="status">
                Ticket marked as reviewed.
              </p>
            )}
            {actionMutation.isSuccess && (
              <p className="text-sm text-green-600" role="status">
                Ticket marked as actioned.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {ticket.user_notes && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">User Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{ticket.user_notes}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function StatusBadge({ status }: { readonly status: string }): JSX.Element {
  const colors: Record<string, string> = {
    TRADABLE: 'bg-blue-100 text-blue-800',
    REVIEWED: 'bg-purple-100 text-purple-800',
    ACTIONED: 'bg-amber-100 text-amber-800',
    RESOLVED: 'bg-green-100 text-green-800',
    EXPIRED: 'bg-gray-100 text-gray-800',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-800'}`}
    >
      {status}
    </span>
  )
}

function OutcomeBadge({ outcome }: { readonly outcome: string }): JSX.Element {
  const colors: Record<string, string> = {
    WIN: 'bg-green-100 text-green-800',
    LOSS: 'bg-red-100 text-red-800',
    FLAT: 'bg-gray-100 text-gray-800',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${colors[outcome] ?? 'bg-gray-100 text-gray-800'}`}
    >
      {outcome}
    </span>
  )
}
