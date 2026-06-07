import Link from 'next/link'

const LINKS = [
  { href: '/incidents', label: 'Incidents' },
  { href: '/stats', label: 'Stats' },
  { href: '/addresses', label: 'Addresses' },
  { href: '/categories', label: 'Categories' },
]

export function Nav() {
  return (
    <header className="border-b bg-background sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-6 h-14">
        <span className="font-semibold text-sm tracking-tight">Lebanon NH — Admin</span>
        <nav className="flex gap-4">
          {LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
