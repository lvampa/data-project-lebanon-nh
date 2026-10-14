import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { usePathname } from 'next/navigation'
import { Nav } from '@/components/nav'

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/'),
}))

const mockedUsePathname = vi.mocked(usePathname)

describe('Nav', () => {
  beforeEach(() => {
    mockedUsePathname.mockReturnValue('/')
  })

  it('links the brand to the home page', () => {
    render(<Nav />)
    expect(screen.getByRole('link', { name: 'Lebanon Data Project' })).toHaveAttribute('href', '/')
  })

  it('lists the section links in order', () => {
    render(<Nav />)
    const [sections] = screen.getAllByRole('list')
    const links = within(sections).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['Voter Pamphlet', '/voter-pamphlet'],
      ['Crime', '/incidents'],
      ['Government', '/government'],
    ])
  })

  it('puts About and Donate in a separate group after the sections', () => {
    render(<Nav />)
    const [, secondary] = screen.getAllByRole('list')
    const links = within(secondary).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['About', '/about'],
      ['Donate', '/donate'],
    ])
  })

  it('marks the active section, including nested pages', () => {
    mockedUsePathname.mockReturnValue('/incidents/26-14680')
    render(<Nav />)
    expect(screen.getByRole('link', { name: 'Crime' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Government' })).not.toHaveAttribute('aria-current')
  })

  it('marks nothing active on the home page', () => {
    render(<Nav />)
    const current = screen.getAllByRole('link').filter((link) => link.hasAttribute('aria-current'))
    expect(current).toEqual([])
  })
})
