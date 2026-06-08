import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { UniverseListPage } from './pages/UniverseListPage'

vi.mock('./api/useUniverses', () => ({
  useUniverses: (_includeDeleted?: boolean) => ({
    data: {
      universes: [
        {
          id: 'u1',
          name: 'sp500',
          display_name: 'S&P 500',
          is_system_managed: true,
          created_at: '2024-01-01T00:00:00Z',
          ticker_count: 3,
          public_id: null,
          last_retrain_at: null,
          description: null,
        },
        {
          id: 'u2',
          name: 'my-custom',
          display_name: 'My Custom',
          is_system_managed: false,
          created_at: '2024-02-01T00:00:00Z',
          ticker_count: 5,
          public_id: 'pub-123',
          last_retrain_at: '2024-04-01T00:00:00Z',
          description: 'A custom universe',
        },
      ],
      total: 2,
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}))

function renderUniverseListPage(): ReturnType<typeof render> {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UniverseListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('UniverseListPage', () => {
  it('displays the page title', () => {
    renderUniverseListPage()
    expect(screen.getByText('Universes')).toBeInTheDocument()
  })

  it('displays universe display name as a link', () => {
    renderUniverseListPage()
    const link = screen.getByText('S&P 500')
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', '/universes/u1')
  })

  it('displays system-managed status badge', () => {
    renderUniverseListPage()
    expect(screen.getByText('System')).toBeInTheDocument()
  })

  it('displays custom status badge', () => {
    renderUniverseListPage()
    expect(screen.getByText('Custom')).toBeInTheDocument()
  })

  it('shows edit link for custom universe', () => {
    renderUniverseListPage()
    const editLink = screen.getByText('Edit')
    expect(editLink).toBeInTheDocument()
    expect(editLink.closest('a')).toHaveAttribute('href', '/universes/u2/edit')
  })

  it('does not show edit link for system-managed universe', () => {
    renderUniverseListPage()
    const editLinks = screen.getAllByText('Edit')
    expect(editLinks).toHaveLength(1)
  })

  it('shows New Universe button', () => {
    renderUniverseListPage()
    expect(screen.getByText('New Universe')).toBeInTheDocument()
  })

  it('shows Include deleted toggle', () => {
    renderUniverseListPage()
    expect(screen.getByText('Include deleted')).toBeInTheDocument()
  })
})
