'use client'
import { useEffect, useState, useSyncExternalStore, type FocusEvent } from 'react'
import Link from 'next/link'
import { ArrowRight, ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'

export interface HeroSlide {
  eyebrow: string
  title: string
  body: string
  cta: { label: string; href: string }
}

interface Props {
  slides: HeroSlide[]
  interval?: number
}

type PlayPreference = 'auto' | 'playing' | 'paused'

export function HeroCarousel({ slides, interval = 7000 }: Props) {
  const [index, setIndex] = useState(0)
  const [preference, setPreference] = useState<PlayPreference>('auto')
  const [isInteracting, setIsInteracting] = useState(false)
  const prefersReducedMotion = usePrefersReducedMotion()

  const isPlaying = preference === 'playing' || (preference === 'auto' && !prefersReducedMotion)
  const isRotating = isPlaying && !isInteracting
  const slide = slides[index]

  const showNext = () => setIndex((i) => (i + 1) % slides.length)
  const showPrevious = () => setIndex((i) => (i - 1 + slides.length) % slides.length)

  // index is a dependency so a manual change restarts the timer with a full interval.
  useEffect(() => {
    if (!isRotating) return
    const timer = setTimeout(() => setIndex((i) => (i + 1) % slides.length), interval)
    return () => clearTimeout(timer)
  }, [isRotating, index, interval, slides.length])

  const stopInteractingOnFocusLeave = (event: FocusEvent<HTMLElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setIsInteracting(false)
  }

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Highlights"
      className="relative flex flex-col justify-between gap-10 rounded-3xl bg-muted px-6 py-10 md:min-h-[440px] md:px-14 md:py-16"
      onMouseEnter={() => setIsInteracting(true)}
      onMouseLeave={() => setIsInteracting(false)}
      onFocus={() => setIsInteracting(true)}
      onBlur={stopInteractingOnFocusLeave}
    >
      <h1 className="sr-only">Lebanon Data Project</h1>

      <div aria-live={isPlaying ? 'off' : 'polite'}>
        <div
          key={index}
          role="group"
          aria-roledescription="slide"
          aria-label={`${index + 1} of ${slides.length}`}
          className="flex max-w-4xl flex-col gap-5 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-500"
        >
          <p className="font-mono text-xs uppercase tracking-[0.08em] text-highlight">
            {slide.eyebrow}
          </p>
          <h2 className="text-[34px] font-semibold leading-[1.2] tracking-[-0.01em] text-foreground md:text-[64px] md:leading-[1.1]">
            {slide.title}
          </h2>
          <p className="max-w-2xl text-base leading-[26px] text-muted-foreground md:text-lg md:leading-7">
            {slide.body}
          </p>
          <Link
            href={slide.cta.href}
            className="mt-2 inline-flex h-[54px] w-fit items-center gap-2 rounded-full bg-primary px-7 font-medium text-primary-foreground transition-colors hover:bg-primary/85 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {slide.cta.label}
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-3 md:justify-end">
        <span className="mr-auto font-mono text-sm tabular-nums text-muted-foreground md:mr-2">
          {String(index + 1).padStart(2, '0')} / {String(slides.length).padStart(2, '0')}
        </span>
        <ControlButton
          label={isPlaying ? 'Pause rotation' : 'Start rotation'}
          onClick={() => setPreference(isPlaying ? 'paused' : 'playing')}
        >
          {isPlaying ? (
            <Pause aria-hidden className="size-5" />
          ) : (
            <Play aria-hidden className="size-5" />
          )}
        </ControlButton>
        <ControlButton label="Previous slide" onClick={showPrevious}>
          <ChevronLeft aria-hidden className="size-5" />
        </ControlButton>
        <ControlButton label="Next slide" onClick={showNext}>
          <ChevronRight aria-hidden className="size-5" />
        </ControlButton>
      </div>
    </section>
  )
}

function ControlButton({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="flex size-[50px] items-center justify-center rounded-full border border-border bg-background text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      {children}
    </button>
  )
}

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function usePrefersReducedMotion() {
  return useSyncExternalStore(subscribeToReducedMotion, readReducedMotion, () => false)
}

function subscribeToReducedMotion(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {}
  const query = window.matchMedia(REDUCED_MOTION_QUERY)
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}

function readReducedMotion() {
  return typeof window.matchMedia === 'function' && window.matchMedia(REDUCED_MOTION_QUERY).matches
}
