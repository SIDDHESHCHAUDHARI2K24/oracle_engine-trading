import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { UniverseListPage } from './pages/UniverseListPage'

vi.mock('./api/useUniverses', () => ({
  useUniverses: () => ({
    data: {
      universes: [
        {
          id: 'u1',
          name: 'sp500',
          display_name: 'S&P 500',
          is_system_managed: true,
          created_at: '2024-01-01T00:00:00Z',
          ticker_count: 3,
        },
      ],
      total: 1,
    },
    isLoading: false,
    isError: false,
    error: null,
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
  it('displays universe display name', () => {
    renderUniverseListPage()
    expect(screen.getByText('S&P 500')).toBeInTheDocument()
  })

  it('displays universe ticker count', () => {
    renderUniverseListPage()
    expect(screen.getByText('3 tickers')).toBeInTheDocument()
  })
})
