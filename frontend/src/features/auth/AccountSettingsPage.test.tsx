import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { AccountSettingsPage } from './pages/AccountSettingsPage'

function renderAccountSettingsPage(): ReturnType<typeof render> {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AccountSettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AccountSettingsPage', () => {
  it('renders change password form fields', () => {
    renderAccountSettingsPage()
    expect(screen.getByLabelText('Current Password')).toBeInTheDocument()
    expect(screen.getByLabelText('New Password')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm New Password')).toBeInTheDocument()
  })

  it('renders Log out everywhere button', () => {
    renderAccountSettingsPage()
    expect(
      screen.getByRole('button', { name: /log out everywhere/i }),
    ).toBeInTheDocument()
  })
})
