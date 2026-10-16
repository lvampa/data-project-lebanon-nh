import { House, ShieldCheck, Vote } from 'lucide-react'
import type { HeroSlide } from '@/components/home/hero-carousel'
import type { FeaturedItem } from '@/components/home/featured'

// Placeholder copy until the real homepage text is written.

export const HERO_SLIDES: HeroSlide[] = [
  {
    eyebrow: 'Voter Info',
    title: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
    body: 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation.',
    cta: { label: 'Lorem ipsum', href: '/elections' },
  },
  {
    eyebrow: 'Public safety',
    title: 'Duis aute irure dolor in reprehenderit in voluptate',
    body: 'Velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident.',
    cta: { label: 'Dolor sit', href: '/public-safety' },
  },
  {
    eyebrow: 'Properties',
    title: 'Sunt in culpa qui officia deserunt mollit anim',
    body: 'Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores.',
    cta: { label: 'Amet elit', href: '/properties' },
  },
]

export const FEATURED_ITEMS: FeaturedItem[] = [
  {
    eyebrow: 'Voter Info',
    title: 'Lorem ipsum dolor sit amet consectetur',
    description:
      'Adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
    href: '/elections',
    icon: Vote,
  },
  {
    eyebrow: 'Public safety',
    title: 'Ut enim ad minim veniam quis nostrud',
    description:
      'Exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat duis aute irure.',
    href: '/public-safety',
    icon: ShieldCheck,
  },
  {
    eyebrow: 'Properties',
    title: 'Excepteur sint occaecat cupidatat non proident',
    description:
      'Sunt in culpa qui officia deserunt mollit anim id est laborum sed ut perspiciatis.',
    href: '/properties',
    icon: House,
  },
]

export const ABOUT_DATA = {
  title: 'Lorem ipsum dolor sit amet, consectetur adipiscing',
  body: 'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco.',
  links: [
    { label: 'About the data', href: '/about' },
    { label: 'Support the project', href: '/support' },
  ],
  facts: [
    {
      label: '00,000 lorem',
      text: 'Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore.',
    },
    {
      label: '00+ ipsum',
      text: 'Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia.',
    },
    {
      label: '0,000+ dolor',
      text: 'Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit.',
    },
  ],
}
