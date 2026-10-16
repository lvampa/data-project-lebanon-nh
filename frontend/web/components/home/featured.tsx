import Link from 'next/link'
import type { LucideIcon } from 'lucide-react'

export interface FeaturedItem {
  eyebrow: string
  title: string
  description: string
  href: string
  icon: LucideIcon
}

export function Featured({ items }: { items: FeaturedItem[] }) {
  return (
    <section aria-labelledby="featured-heading" className="flex flex-col gap-6 md:gap-8">
      <h2
        id="featured-heading"
        className="text-[22px] font-semibold leading-[1.2] tracking-[-0.01em] md:text-[30px]"
      >
        Featured
      </h2>
      <ul className="grid list-none gap-8 p-0 md:grid-cols-3 md:gap-6">
        {items.map((item) => (
          <li key={item.href}>
            <FeaturedCard item={item} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function FeaturedCard({ item }: { item: FeaturedItem }) {
  const Icon = item.icon
  return (
    <Link
      href={item.href}
      className="group flex h-full min-h-[360px] flex-col justify-between gap-10 rounded-2xl bg-accent p-6 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:min-h-[460px] md:p-8"
    >
      <Icon aria-hidden className="size-12 text-primary" strokeWidth={1.5} />
      <div className="flex flex-col gap-4">
        <p className="font-mono text-xs uppercase tracking-[0.08em] text-highlight">
          {item.eyebrow}
        </p>
        <h3 className="line-clamp-2 text-[22px] font-semibold leading-[1.2] tracking-[-0.01em] text-foreground group-hover:text-primary md:text-[26px]">
          {item.title}
        </h3>
        <p className="line-clamp-3 text-base leading-[26px] text-muted-foreground">
          {item.description}
        </p>
      </div>
    </Link>
  )
}
