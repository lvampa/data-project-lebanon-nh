import { HeroCarousel, Featured, AboutData } from '@/components/home'
import { ABOUT_DATA, FEATURED_ITEMS, HERO_SLIDES } from '@/lib/home-content'

export default function HomePage() {
  return (
    <div className="flex flex-col gap-16 pb-10 md:gap-24 md:pb-20">
      <HeroCarousel slides={HERO_SLIDES} />
      <Featured items={FEATURED_ITEMS} />
      <AboutData {...ABOUT_DATA} />
    </div>
  )
}
