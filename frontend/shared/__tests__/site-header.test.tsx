import '@testing-library/jest-dom/vitest'
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
    const text = desktopNav().textContent ?? ''
    const order = ['Voter Info', 'Public safety', 'Properties', 'Government'].map((label) =>
      text.indexOf(label),
    )
    expect(order.every((at) => at >= 0)).toBe(true)
    expect(order).toEqual([...order].sort((a, b) => a - b))
  })

  it('links only the topics that are ready', () => {
    render(<SiteHeader />)
    const links = within(desktopNav()).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['Public safety', '/public-safety'],
    ])
  })

  // The chip shows from xl up and the screen-reader text below it, so each topic has both.
  it('says each topic that is not ready is coming soon', () => {
    render(<SiteHeader />)
    for (const label of ['Voter Info', 'Properties', 'Government']) {
      const topic = within(desktopNav()).getByText(
        (_, element) => element?.tagName === 'SPAN' && element.firstChild?.textContent === label,
      )
      expect(topic.textContent).toBe(`${label}Coming soonComing soon`)
      expect(within(topic).getByText('Coming soon', { selector: '.sr-only' })).toHaveClass(
        'xl:hidden',
      )
    }
  })

  it('marks coming-soon topics in the phone menu too', async () => {
    const user = userEvent.setup()
    render(<SiteHeader />)
    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = within(screen.getByRole('dialog', { name: 'Menu' }))
    expect(menu.getAllByText('Coming soon')).toHaveLength(3)
    expect(menu.getAllByRole('link').map((link) => link.textContent)).not.toContain('Government')
  })

  it('links Support to the support page', () => {
    render(<SiteHeader />)
    for (const support of screen.getAllByRole('link', { name: 'Support' })) {
      expect(support).toHaveAttribute('href', '/support')
    }
  })

  it('marks the active topic, including nested pages', () => {
    mockedUsePathname.mockReturnValue('/public-safety/map')
    render(<SiteHeader />)
    const nav = desktopNav()
    expect(within(nav).getByRole('link', { name: 'Public safety' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('opens the phone menu and closes it with Escape', async () => {
    const user = userEvent.setup()
    render(<SiteHeader />)

    await user.click(screen.getByRole('button', { name: 'Open menu' }))
    const menu = screen.getByRole('dialog', { name: 'Menu' })
    expect(within(menu).getByRole('link', { name: 'Support the project' })).toHaveAttribute(
      'href',
      '/support',
    )
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
