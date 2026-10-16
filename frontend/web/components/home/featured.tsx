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
      <h2 id="featured-heading" className="text-display-3">
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
      className="group flex h-full min-h-90 flex-col justify-between gap-10 rounded-2xl bg-accent p-6 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:min-h-115 md:p-8"
    >
      <Icon aria-hidden className="size-12 text-primary" strokeWidth={1.5} />
      <div className="flex flex-col gap-4">
        <p className="eyebrow">{item.eyebrow}</p>
        <h3 className="line-clamp-2 text-display-3 text-foreground group-hover:text-primary">
          {item.title}
        </h3>
        <p className="line-clamp-3 text-base leading-6.5 text-muted-foreground">
          {item.description}
        </p>
      </div>
    </Link>
  )
}
