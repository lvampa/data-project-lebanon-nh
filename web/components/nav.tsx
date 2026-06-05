import Link from 'next/link'

const LINKS = [
  { href: '/', label: 'Dashboard' },
  { href: '/incidents', label: 'Incidents' },
  { href: '/map', label: 'Map' },
  { href: '/properties', label: 'Properties' },
  { href: '/staff', label: 'Staff' },
]

export function Nav() {
  return (
    <header className="border-b bg-background sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 flex items-center gap-6 h-14">
        <span className="font-semibold text-sm tracking-tight">Lebanon NH</span>
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
