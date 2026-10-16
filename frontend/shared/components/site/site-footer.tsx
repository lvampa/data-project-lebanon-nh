import Link from "next/link"
import { LogoMark } from "./logo-mark"
import { buttonVariants } from "../ui/button"
import { cn } from "../../lib/utils"
import { ABOUT_ITEMS, NAV_ITEMS, type NavItem } from "./nav-items"

function Column({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="flex flex-col gap-2.5">
      <h2 className="font-mono text-xs font-medium uppercase tracking-[0.08em] text-brand-foreground/70">{title}</h2>
      {items.map((item) => (
        <Link
          key={item.href + item.label}
          href={item.href}
          className="text-[15px] leading-[22px] text-brand-foreground/90 underline-offset-4 hover:text-brand-foreground hover:underline"
        >
          {item.label}
        </Link>
      ))}
    </div>
  )
}

export function SiteFooter() {
  return (
    <footer className="bg-brand text-brand-foreground">
      <section
        aria-labelledby="footer-callout-heading"
        className="mx-auto flex max-w-7xl flex-col items-start gap-8 px-5 py-16 md:px-8 md:py-24"
      >
        <LogoMark size={48} strokeWidth={5.2} />
        {/* Placeholder copy until the mission statement is written. */}
        <h2
          id="footer-callout-heading"
          className="max-w-5xl text-pretty text-display-2"
        >
          Lorem ipsum dolor sit amet, consectetur adipiscing elit sed do eiusmod tempor incididunt.
        </h2>
        <Link
          href="/about"
          className={cn(buttonVariants({ variant: "highlight", size: "pill" }))}
        >
          Learn more about us
        </Link>
      </section>
      <div className="mx-auto max-w-7xl px-5 md:px-8">
        <div className="border-t border-brand-foreground/15" />
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-10 px-5 pt-10 pb-8 md:px-8 md:pt-14 md:pb-10">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-[1.4fr_1fr_1fr] md:gap-12">
          <div className="col-span-2 flex flex-col gap-3.5 md:col-span-1">
            <div className="flex items-center gap-3">
              <LogoMark size={40} strokeWidth={5.6} />
              <span className="text-[17px] font-semibold">Lebanon Data Project</span>
            </div>
            <p className="max-w-[360px] text-[15px] leading-[22px] text-brand-foreground/70">
              Public records from Lebanon, New Hampshire, gathered in one place and linked back to every original
              source.
            </p>
          </div>
          <Column title="Explore" items={NAV_ITEMS} />
          <Column title="About" items={ABOUT_ITEMS} />
        </div>
        <div className="flex flex-wrap justify-between gap-2 border-t border-brand-foreground/15 pt-6 text-[13px] leading-[18px] text-brand-foreground/70">
          {/* Confirm this disclaimer is accurate before launch. */}
          <span>An independent project. Not affiliated with the City of Lebanon.</span>
          <span>© {new Date().getFullYear()} Lebanon Data Project</span>
        </div>
      </div>
    </footer>
  )
}
