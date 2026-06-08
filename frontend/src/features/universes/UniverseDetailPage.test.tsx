import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { UniverseDetailPage } from './pages/UniverseDetailPage'

vi.mock('./api/useUniverse', () => ({
  useUniverse: () => ({
    data: {
      id: 'u1',
      name: 'sp500',
      display_name: 'S&P 500',
      is_system_managed: true,
      created_at: '2024-01-01T00:00:00Z',
      ticker_count: 3,
      public_id: 'pub-sp500',
      last_retrain_at: '2024-05-01T00:00:00Z',
      description: 'Standard & Poor\u2019s 500',
    },
    isLoading: false,
    isError: false,
    error: null,
  }),
}))

vi.mock('./api/useMembership', () => ({
  useMembership: () => ({
    data: [
      {
        id: 't1',
        symbol: 'AAPL',
        name: 'Apple Inc.',
        exchange: 'NASDAQ',
        asset_type: 'stock',
        active: true,
        added_at: '2024-03-15T00:00:00Z',
      },
      {
        id: 't2',
        symbol: 'MSFT',
        name: 'Microsoft Corp.',
        exchange: 'NASDAQ',
        asset_type: 'stock',
        active: true,
        added_at: '2024-03-16T00:00:00Z',
      },
    ],
    isLoading: false,
    isError: false,
    error: null,
  }),
}))

vi.mock('./api/useAddMembers', () => ({
  useAddMembers: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
  }),
}))

vi.mock('./api/useRemoveMember', () => ({
  useRemoveMember: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
  }),
}))

vi.mock('./api/useImportCsv', () => ({
  useImportCsv: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
  }),
}))

vi.mock('react-dropzone', () => ({
  useDropzone: () => ({
    getRootProps: () => ({}),
    getInputProps: () => ({}),
    isDragActive: false,
  }),
}))

function renderUniverseDetailPage(): ReturnType<typeof render> {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/universes/u1']}>
        <UniverseDetailPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('UniverseDetailPage', () => {
  it('renders universe detail with display name', () => {
    renderUniverseDetailPage()
    expect(screen.getByText('S&P 500')).toBeInTheDocument()
  })

  it('shows Model Health placeholder', () => {
    renderUniverseDetailPage()
    expect(screen.getByText(/Model Health/)).toBeInTheDocument()
    expect(screen.getByText(/Coming in S4/)).toBeInTheDocument()
  })

  it('renders membership table with tickers', () => {
    renderUniverseDetailPage()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
  })

  it('renders status badge for system-managed universe', () => {
    renderUniverseDetailPage()
    expect(screen.getByText('System Managed')).toBeInTheDocument()
  })

  it('does not show edit button for system-managed universe', () => {
    renderUniverseDetailPage()
    expect(screen.queryByText('Edit')).not.toBeInTheDocument()
  })
})
