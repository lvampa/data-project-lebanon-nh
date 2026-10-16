'use client'
import { useEffect, useState, type FocusEvent } from 'react'
import Link from 'next/link'
import { buttonVariants } from '@project/ui/components/ui/button'
import { cn } from '@project/ui/lib/utils'
import { usePrefersReducedMotion } from '@/lib/use-prefers-reduced-motion'
import { IconButton } from '@project/ui/components/ui/icon-button'
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
      className="relative flex flex-col justify-between gap-10 rounded-3xl bg-muted px-6 py-10 md:min-h-110 md:px-14 md:py-16"
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
          <p className="eyebrow">{slide.eyebrow}</p>
          <h2 className="text-display-1 text-foreground">{slide.title}</h2>
          <p className="max-w-2xl text-base leading-6.5 text-muted-foreground md:text-lg md:leading-7">
            {slide.body}
          </p>
          <Link
            href={slide.cta.href}
            className={cn(buttonVariants({ size: 'pill' }), 'mt-2 w-fit')}
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
        <IconButton
          variant="outline"
          size="xl"
          className="rounded-full bg-background hover:bg-accent"
          label={isPlaying ? 'Pause rotation' : 'Start rotation'}
          onClick={() => setPreference(isPlaying ? 'paused' : 'playing')}
        >
          {isPlaying ? <Pause aria-hidden /> : <Play aria-hidden />}
        </IconButton>
        <IconButton
          variant="outline"
          size="xl"
          className="rounded-full bg-background hover:bg-accent"
          label="Previous slide"
          onClick={showPrevious}
        >
          <ChevronLeft aria-hidden />
        </IconButton>
        <IconButton
          variant="outline"
          size="xl"
          className="rounded-full bg-background hover:bg-accent"
          label="Next slide"
          onClick={showNext}
        >
          <ChevronRight aria-hidden />
        </IconButton>
      </div>
    </section>
  )
}
