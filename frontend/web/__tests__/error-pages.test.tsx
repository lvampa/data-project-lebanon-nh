import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AppError from '@/app/error'
import IncidentsError from '@/app/incidents/error'

describe.each([
  ['app', AppError],
  ['incidents', IncidentsError],
])('%s error page', (_name, ErrorPage) => {
  it('retries with the retry prop Next passes', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const retry = vi.fn()
    render(<ErrorPage error={new Error('boom')} retry={retry} />)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(retry).toHaveBeenCalledOnce()
  })
})
