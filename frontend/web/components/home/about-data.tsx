import Link from 'next/link'
import { buttonVariants } from '@project/ui/components/ui/button'
import { cn } from '@project/ui/lib/utils'

interface Props {
  title: string
  body: string
  links: { label: string; href: string }[]
  facts: { label: string; text: string }[]
}

export function AboutData({ title, body, links, facts }: Props) {
  return (
    <section
      aria-labelledby="about-data-heading"
      className="relative left-1/2 w-screen -translate-x-1/2 bg-primary text-primary-foreground"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-12 px-5 py-16 md:gap-16 md:px-8 md:py-24">
        <div className="flex max-w-4xl flex-col gap-6">
          <h2 id="about-data-heading" className="text-display-1">
            {title}
          </h2>
          <p className="max-w-2xl text-base leading-6.5 text-primary-foreground/85 md:text-lg md:leading-7">
            {body}
          </p>
          <div className="flex flex-wrap gap-3">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(buttonVariants({ variant: 'inverse', size: 'pill' }))}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>

        <ul className="grid list-none gap-4 p-0 md:auto-rows-fr md:grid-cols-2 md:gap-6 lg:grid-cols-3">
          {facts.map((fact) => (
            <li
              key={fact.label}
              className="flex min-h-55 flex-col justify-between gap-10 rounded-2xl bg-background p-6 text-foreground md:min-h-80 md:p-8"
            >
              <p className="eyebrow text-sm">{fact.label}</p>
              <p className="text-lg leading-7 md:text-xl md:leading-8">{fact.text}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
