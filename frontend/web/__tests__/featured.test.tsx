import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { Vote } from 'lucide-react'
import { Featured, type FeaturedItem } from '@/components/home/featured'

const items: FeaturedItem[] = [
  {
    eyebrow: 'Elections',
    title: 'Voter guide',
    description: 'Who is on the ballot.',
    href: '/elections',
    icon: Vote,
  },
  {
    eyebrow: 'Safety',
    title: 'Police log',
    description: 'Recent calls.',
    href: '/public-safety',
    icon: Vote,
  },
]

describe('Featured', () => {
  it('renders a heading and one link per item', () => {
    render(<Featured items={items} />)
    const section = screen.getByRole('region', { name: 'Featured' })
    const links = within(section).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['/elections', '/public-safety'])
  })

  it('shows the eyebrow, title and description inside each card', () => {
    render(<Featured items={items} />)
    const card = screen.getByRole('link', { name: /Voter guide/ })
    expect(card).toHaveTextContent('Elections')
    expect(card).toHaveTextContent('Who is on the ballot.')
    expect(within(card).getByRole('heading', { level: 3 })).toHaveTextContent('Voter guide')
  })
})
