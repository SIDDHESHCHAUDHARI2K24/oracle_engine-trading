import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { UniverseFormPage } from './pages/UniverseFormPage'

vi.mock('./api/useCreateUniverse', () => ({
  useCreateUniverse: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
  }),
}))

vi.mock('./api/useUpdateUniverse', () => ({
  useUpdateUniverse: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
  }),
}))

vi.mock('./api/useUniverse', () => ({
  useUniverse: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
  }),
}))

function renderUniverseFormPage(mode: 'create' | 'edit'): ReturnType<typeof render> {
  const client = new QueryClient()
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[mode === 'create' ? '/universes/new' : '/universes/u1/edit']}>
        <UniverseFormPage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('UniverseFormPage', () => {
  it('renders create form with title', () => {
    renderUniverseFormPage('create')
    expect(screen.getByText('Create Universe')).toBeInTheDocument()
  })

  it('renders slug input', () => {
    renderUniverseFormPage('create')
    expect(screen.getByLabelText('Slug')).toBeInTheDocument()
  })

  it('renders display name input', () => {
    renderUniverseFormPage('create')
    expect(screen.getByLabelText('Display Name')).toBeInTheDocument()
  })

  it('renders description textarea', () => {
    renderUniverseFormPage('create')
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
  })

  it('renders create button', () => {
    renderUniverseFormPage('create')
    expect(screen.getByText('Create')).toBeInTheDocument()
  })

  it('renders cancel button that links to universes list', () => {
    renderUniverseFormPage('create')
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })
})
