// `soon` marks a topic that is not ready yet. It shows as plain text with a "Coming soon"
// chip, not a link, so nobody lands on a page that is not there.
export type NavItem = { label: string; href: string; soon?: boolean }

// Four topics, no dropdowns. Government holds budgets and meetings.
export const NAV_ITEMS: NavItem[] = [
  { label: 'Voter Info', href: '/elections', soon: true },
  { label: 'Public safety', href: '/public-safety' },
  { label: 'Properties', href: '/properties', soon: true },
  { label: 'Government', href: '/government', soon: true },
]

export const ABOUT_ITEMS: NavItem[] = [
  { label: 'About the data', href: '/about' },
  { label: 'Support the project', href: '/support' },
  { label: 'Contact', href: '/contact' },
]

// TODO: point at the real support destination (page or donation service).
export const SUPPORT_HREF = '/support'

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(href + '/')
}
