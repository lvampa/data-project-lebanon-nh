'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@project/ui/lib/utils'

const LINKS = [
  { href: '/incidents', label: 'Incidents' },
  { href: '/stats', label: 'Stats' },
  { href: '/addresses', label: 'Addresses' },
  { href: '/categories', label: 'Categories' },
  { href: '/llcs', label: 'LLCs' },
]

export function Nav() {
  const pathname = usePathname()

  return (
    <header className="border-b bg-background sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-6 h-14">
        <span className="font-semibold text-sm tracking-tight">Lebanon NH — Admin</span>
        <nav className="flex gap-1" aria-label="Main navigation">
          {LINKS.map(({ href, label }) => {
            const isActive = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'px-3 py-1.5 rounded-md text-sm transition-colors',
                  isActive
                    ? 'bg-muted text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
                )}
              >
                {label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
