"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import { Menu, X } from "lucide-react"
import { LogoMark } from "./logo-mark"
import { NAV_ITEMS, SUPPORT_HREF, isActive } from "./nav-items"
import { useHideOnScroll } from "./use-hide-on-scroll"

const supportClass =
  "inline-flex items-center justify-center rounded-full bg-highlight text-highlight-foreground font-semibold " +
  "transition-colors hover:bg-highlight/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" aria-label="Lebanon Data Project home" className="flex items-center gap-3 text-foreground">
      <LogoMark size={compact ? 36 : 44} strokeWidth={compact ? 6 : 5.2} />
      <span className="flex flex-col">
        <span className={compact ? "text-base font-semibold" : "text-lg leading-[22px] font-semibold"}>
          Lebanon Data Project
        </span>
        {!compact && (
          <span className="font-mono text-[11px] leading-[14px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Lebanon, NH · public records
          </span>
        )}
      </span>
    </Link>
  )
}

export function SiteHeader() {
  const pathname = usePathname() ?? "/"
  const hidden = useHideOnScroll()
  // The menu belongs to the page it was opened on, so navigating closes it.
  const [menuPath, setMenuPath] = useState<string | null>(null)
  const menuOpen = menuPath === pathname
  const setMenuOpen = (open: boolean) => setMenuPath(open ? pathname : null)

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuPath(null)
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [menuOpen])

  return (
    <>
      <header
        className={
          "sticky top-0 z-40 bg-background motion-safe:transition-transform motion-safe:duration-300 " +
          (hidden && !menuOpen ? "-translate-y-full" : "translate-y-0")
        }
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-8 px-5 md:h-[76px] md:px-8">
          <div className="md:hidden">
            <Brand compact />
          </div>
          <div className="hidden md:block">
            <Brand />
          </div>

          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => {
              const active = isActive(pathname, item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  data-label={item.label}
                  className={
                    // after: reserves bold width so links don't shift when one becomes active
                    "inline-flex h-11 flex-col items-center justify-center px-3 text-[15px] transition-colors " +
                    "after:invisible after:h-0 after:overflow-hidden after:font-bold after:content-[attr(data-label)] " +
                    "rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring " +
                    (active
                      ? "font-bold text-foreground underline decoration-2 underline-offset-8"
                      : "font-medium text-foreground hover:text-primary")
                  }
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>

          <div className="flex-1" />

          <Link href={SUPPORT_HREF} className={supportClass + " hidden h-10 px-5 text-[15px] md:inline-flex"}>
            Support
          </Link>
          <Link href={SUPPORT_HREF} className={supportClass + " h-9 px-3.5 text-sm md:hidden"}>
            Support
          </Link>
          <button
            type="button"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="site-menu"
            onClick={() => setMenuOpen(true)}
            className="-mr-2 inline-flex size-11 items-center justify-center rounded-full text-foreground hover:bg-accent hover:text-primary md:hidden"
          >
            <Menu className="size-[22px]" />
          </button>
        </div>
      </header>

      {menuOpen && (
        <div
          id="site-menu"
          role="dialog"
          aria-modal="true"
          aria-label="Menu"
          className="fixed inset-0 z-50 flex flex-col bg-background md:hidden"
        >
          <div className="flex h-16 items-center gap-2.5 px-5">
            <Brand compact />
            <div className="flex-1" />
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMenuOpen(false)}
              className="-mr-2 inline-flex size-11 items-center justify-center rounded-full text-foreground hover:bg-accent"
            >
              <X className="size-[22px]" />
            </button>
          </div>
          <nav aria-label="Main" className="flex flex-col pt-2">
            {NAV_ITEMS.map((item) => {
              const active = isActive(pathname, item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    "flex h-13 items-center px-5 text-lg " +
                    (active ? "font-bold underline decoration-2 underline-offset-8" : "font-medium hover:text-primary")
                  }
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
          <div className="p-5">
            <Link href={SUPPORT_HREF} className={supportClass + " h-12 w-full text-base"}>
              Support the project
            </Link>
          </div>
        </div>
      )}
    </>
  )
}
