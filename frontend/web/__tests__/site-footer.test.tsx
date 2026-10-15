import '@testing-library/jest-dom'
import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { SiteFooter } from '@project/ui/components/site/site-footer'

function column(title: string) {
  const heading = screen.getByRole('heading', { name: title })
  return within(heading.parentElement!).getAllByRole('link')
}

describe('SiteFooter', () => {
  it('repeats the topics under Explore', () => {
    render(<SiteFooter />)
    expect(column('Explore').map((link) => link.textContent)).toEqual([
      'Public safety',
      'Properties',
      'Government',
      'Voter info',
    ])
  })

  it('links About the data, Support and Contact under About', () => {
    render(<SiteFooter />)
    expect(column('About').map((link) => [link.textContent, link.getAttribute('href')])).toEqual([
      ['About the data', '/about'],
      ['Support the project', '/support'],
      ['Contact', '/contact'],
    ])
  })

  it('shows the current year', () => {
    render(<SiteFooter />)
    expect(screen.getByText(`© ${new Date().getFullYear()} Lebanon Data Project`)).toBeInTheDocument()
  })
})
