'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, BarChart2, MapPin, Tag, Building2, Search } from 'lucide-react'
import { cn } from '@project/ui/lib/utils'

const SECTIONS = [
  {
    heading: 'Operations',
    items: [
      { href: '/search', label: 'Search', icon: Search },
      { href: '/incidents', label: 'Incidents', icon: Activity },
      { href: '/stats', label: 'Stats', icon: BarChart2 },
    ],
  },
  {
    heading: 'Data',
    items: [
      { href: '/addresses', label: 'Addresses', icon: MapPin },
      { href: '/categories', label: 'Categories', icon: Tag },
      { href: '/llcs', label: 'LLCs', icon: Building2 },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col gap-4 border-r border-border bg-card px-3 py-4 sticky top-0">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-2 pb-3 border-b border-border">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-foreground text-background text-xs font-bold select-none">
          LN
        </div>
        <div>
          <div
            className="text-[15px] font-medium leading-tight tracking-tight text-foreground"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Lebanon NH
          </div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Admin
          </div>
        </div>
      </div>

      {/* Nav sections */}
      {SECTIONS.map((section) => (
        <div key={section.heading} className="flex flex-col gap-0.5">
          <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {section.heading}
          </div>
          {section.items.map(({ href, label, icon: Icon }) => {
            const isActive = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors',
                  isActive
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )}
              >
                <Icon size={15} className="shrink-0" />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>
      ))}

      {/* Footer */}
      <div className="mt-auto rounded-md border border-border bg-muted/50 p-3">
        <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          Methodology
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          v3.2 · Lebanon, NH Data Project
        </div>
      </div>
    </aside>
  )
}
