export type NavItem = { label: string; href: string }

// Four topics, no dropdowns. Government holds budgets and meetings.
export const NAV_ITEMS: NavItem[] = [
  { label: "Voter Info", href: "/elections" },
  { label: "Public safety", href: "/public-safety" },
  { label: "Properties", href: "/properties" },
  { label: "Government", href: "/government" },
]

export const ABOUT_ITEMS: NavItem[] = [
  { label: "About the data", href: "/about" },
  { label: "Support the project", href: "/support" },
  { label: "Contact", href: "/contact" },
]

// TODO: point at the real support destination (page or donation service).
export const SUPPORT_HREF = "/support"

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(href + "/")
}
