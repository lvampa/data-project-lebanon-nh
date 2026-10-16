import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { HeroCarousel, type HeroSlide } from '@/components/home/hero-carousel'

const slides: HeroSlide[] = [
  {
    eyebrow: 'One',
    title: 'First slide',
    body: 'Body one',
    cta: { label: 'Go one', href: '/one' },
  },
  {
    eyebrow: 'Two',
    title: 'Second slide',
    body: 'Body two',
    cta: { label: 'Go two', href: '/two' },
  },
  {
    eyebrow: 'Three',
    title: 'Third slide',
    body: 'Body three',
    cta: { label: 'Go three', href: '/three' },
  },
]

function currentTitle() {
  return screen.getByRole('heading', { level: 2 }).textContent
}

function mockReducedMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion'),
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

describe('HeroCarousel', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the first slide with its call to action', () => {
    render(<HeroCarousel slides={slides} />)
    expect(currentTitle()).toBe('First slide')
    expect(screen.getByRole('link', { name: 'Go one' })).toHaveAttribute('href', '/one')
    expect(screen.getByRole('group', { name: '1 of 3' })).toBeInTheDocument()
  })

  it('moves forward and back, wrapping at both ends', () => {
    render(<HeroCarousel slides={slides} />)
    fireEvent.click(screen.getByRole('button', { name: 'Previous slide' }))
    expect(currentTitle()).toBe('Third slide')
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }))
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }))
    expect(currentTitle()).toBe('Second slide')
  })

  it('advances on its own', () => {
    vi.useFakeTimers()
    render(<HeroCarousel slides={slides} interval={5000} />)
    act(() => vi.advanceTimersByTime(5000))
    expect(currentTitle()).toBe('Second slide')
  })

  it('stops advancing when paused', () => {
    vi.useFakeTimers()
    render(<HeroCarousel slides={slides} interval={5000} />)
    fireEvent.click(screen.getByRole('button', { name: 'Pause rotation' }))
    act(() => vi.advanceTimersByTime(20000))
    expect(currentTitle()).toBe('First slide')
    expect(screen.getByRole('button', { name: 'Start rotation' })).toBeInTheDocument()
  })

  it('stops advancing while the pointer is over it', () => {
    vi.useFakeTimers()
    render(<HeroCarousel slides={slides} interval={5000} />)
    fireEvent.mouseEnter(screen.getByRole('region', { name: 'Highlights' }))
    act(() => vi.advanceTimersByTime(20000))
    expect(currentTitle()).toBe('First slide')
  })

  it('does not advance when the reader prefers reduced motion', () => {
    mockReducedMotion(true)
    vi.useFakeTimers()
    render(<HeroCarousel slides={slides} interval={5000} />)
    act(() => vi.advanceTimersByTime(20000))
    expect(currentTitle()).toBe('First slide')
    expect(screen.getByRole('button', { name: 'Start rotation' })).toBeInTheDocument()
  })

  it('announces slide changes only while not rotating', () => {
    render(<HeroCarousel slides={slides} />)
    const live = screen.getByRole('group', { name: '1 of 3' }).parentElement!
    expect(live).toHaveAttribute('aria-live', 'off')
    fireEvent.click(screen.getByRole('button', { name: 'Pause rotation' }))
    expect(live).toHaveAttribute('aria-live', 'polite')
  })
})
