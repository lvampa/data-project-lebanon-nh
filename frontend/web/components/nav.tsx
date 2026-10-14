'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { buttonVariants } from '@project/ui/components/ui/button'
import { cn } from '@project/ui/lib/utils'

const SECTION_LINKS = [
  { href: '/voter-pamphlet', label: 'Voter Pamphlet' },
  { href: '/incidents', label: 'Crime' },
  { href: '/government', label: 'Government' },
]

export function Nav() {
  return <NavBar pathname={usePathname()} />
}

export function NavBar({ pathname }: { pathname: string }) {
  return (
    <header className="border-b bg-background sticky top-0 z-40">
      <nav
        aria-label="Main navigation"
        className="max-w-7xl mx-auto px-4 py-2 flex flex-wrap items-center gap-x-6 gap-y-1 min-h-14"
      >
        <Link href="/" className="font-semibold text-sm tracking-tight py-2">
          Lebanon Data Project
        </Link>
        <ul className="flex flex-wrap gap-1">
          {SECTION_LINKS.map(({ href, label }) => (
            <li key={href}>
              <NavLink href={href} label={label} pathname={pathname} />
            </li>
          ))}
        </ul>
        <ul className="ml-auto flex items-center gap-1">
          <li>
            <NavLink href="/about" label="About" pathname={pathname} />
          </li>
          <li>
            <Link
              href="/donate"
              aria-current={isActive(pathname, '/donate') ? 'page' : undefined}
              className={buttonVariants({ size: 'lg', className: 'px-4' })}
            >
              Donate
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  )
}

function NavLink({ href, label, pathname }: { href: string; label: string; pathname: string }) {
  const active = isActive(pathname, href)
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'block px-3 py-1.5 rounded-md text-sm transition-colors',
        active
          ? 'bg-muted text-foreground font-medium'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
      )}
    >
      {label}
    </Link>
  )
}

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`)
}
