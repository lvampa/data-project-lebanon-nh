import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { AboutData } from '@/components/home'

const props = {
  title: 'We read the PDFs',
  body: 'So you do not have to.',
  links: [
    { label: 'About the data', href: '/about' },
    { label: 'Support the project', href: '/support' },
  ],
  facts: [
    { label: '12 sources', text: 'Every record links back to its source.' },
    { label: 'Daily', text: 'The police log updates every morning.' },
  ],
}

describe('AboutData', () => {
  it('renders the heading, copy and links', () => {
    render(<AboutData {...props} />)
    const section = screen.getByRole('region', { name: 'We read the PDFs' })
    expect(section).toHaveTextContent('So you do not have to.')
    expect(
      within(section)
        .getAllByRole('link')
        .map((link) => [link.textContent, link.getAttribute('href')]),
    ).toEqual([
      ['About the data', '/about'],
      ['Support the project', '/support'],
    ])
  })

  it('renders one card per fact with its label and text', () => {
    render(<AboutData {...props} />)
    const cards = screen.getAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(cards[0]).toHaveTextContent('12 sources')
    expect(cards[0]).toHaveTextContent('Every record links back to its source.')
  })
})
