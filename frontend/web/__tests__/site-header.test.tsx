import '@testing-library/jest-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { usePathname } from 'next/navigation'
import { SiteHeader } from '@project/ui/components/site/site-header'

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/'),
}))

const mockedUsePathname = vi.mocked(usePathname)

function desktopNav() {
  return screen.getByRole('navigation', { name: 'Main' })
}

describe('SiteHeader', () => {
  beforeEach(() => {
    mockedUsePathname.mockReturnValue('/')
  })

  it('links the brand to the home page', () => {
    render(<SiteHeader />)
    for (const brand of screen.getAllByRole('link', { name: 'Lebanon Data Project home' })) {
      expect(brand).toHaveAttribute('href', '/')
    }
  })

  it('lists the four topics in order', () => {
    render(<SiteHeader />)
    const links = within(desktopNav()).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['Public safety', '/public-safety'],
      ['Properties', '/properties'],
      ['Government', '/government'],
      ['Voter info', '/elections'],
    ])
  })

  it('links Support to the support page', () => {
    render(<SiteHeader />)
    for (const support of screen.getAllByRole('link', { name: 'Support' })) {
      expect(support).toHaveAttribute('href', '/support')
    }
  })

  it('marks the active topic, including nested pages', () => {
    mockedUsePathname.mockReturnValue('/government/budgets')
    render(<SiteHeader />)
    const nav = desktopNav()
    expect(within(nav).getByRole('link', { name: 'Government' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Properties' })).not.toHaveAttribute('aria-current')
  })

  it('opens the phone menu and closes it with Escape', async () => {
    const user = userEvent.setup()
    render(<SiteHeader />)

    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = screen.getByRole('dialog', { name: 'Menu' })
    expect(within(menu).getByRole('link', { name: 'Support the project' })).toHaveAttribute('href', '/support')
    expect(document.body.style.overflow).toBe('hidden')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
  })

  it('closes the phone menu after navigating', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<SiteHeader />)
    await user.click(screen.getByRole('button', { name: 'Open menu' }))

    mockedUsePathname.mockReturnValue('/properties')
    rerender(<SiteHeader />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
