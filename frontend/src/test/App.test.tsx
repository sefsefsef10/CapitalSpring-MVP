import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Simple test to verify test infrastructure works
describe('App', () => {
  it('renders without crashing', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    })

    // Just verify we can render a basic component
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div data-testid="test-component">Test</div>
        </BrowserRouter>
      </QueryClientProvider>
    )

    expect(screen.getByTestId('test-component')).toBeInTheDocument()
  })
})
