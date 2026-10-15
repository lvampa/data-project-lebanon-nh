# Lebanon Data Project brand kit

Source of truth for the site's look.
Claude Code: read this before touching styles, the header, the footer, or charts.
Use these tokens and components; don't invent new colors or restyle shadcn components ad hoc.

## What's in the kit

| Path | What it is |
|---|---|
| `frontend/shared/globals.css` | Color tokens (light + `.dark`, OKLCH, shadcn names), `@theme inline` additions, loader keyframes |
| `frontend/shared/brand/logo/mark-clean.svg` | Primary mark. Clean-line Lebanon Opera House. `currentColor` |
| `frontend/shared/brand/logo/mark-simple.svg` | Reduced mark for 24–48px |
| `frontend/shared/brand/logo/mark-favicon.svg` | Heaviest strokes, for 24px and below |
| `frontend/shared/brand/logo/mark-sketch.svg` | Hand-drawn version, about page / editorial only |
| `frontend/shared/components/site/site-header.tsx` | Header + phone menu |
| `frontend/shared/components/site/site-footer.tsx` | Footer |
| `frontend/shared/components/site/nav-items.ts` | Nav + footer link lists, `SUPPORT_HREF`, `isActive()` |
| `frontend/shared/components/site/use-hide-on-scroll.ts` | Hide-on-scroll hook used by the header |
| `frontend/shared/components/site/logo-mark.tsx` | `<LogoMark />` React component |
| `frontend/shared/components/site/opera-house-loader.tsx` | `<OperaHouseLoader />` loading animation |
| `web/public/*` | favicon.ico (16/32/48), favicon.svg, apple-touch-icon.png, icon-192/512.png, site.webmanifest |

## Where it's wired in

- Tokens and the `.ldp-seg` loader CSS are in `frontend/shared/globals.css`.
- `frontend/web/app/layout.tsx` loads IBM Plex Sans (400/500/600/700) and IBM Plex Mono (400/500) through `next/font/google` as `--font-sans` and `--font-mono`.
- The same layout renders `<SiteHeader />` and `<SiteFooter />` and sets the icons, manifest and theme color.
- The header is sticky.
  Don't wrap it in another sticky or overflow container, or hide-on-scroll breaks, since it listens to `window` scroll.
- `frontend/web/app/globals.css` adds `frontend/shared` as a Tailwind `@source`, so classes used only in shared components are generated.

## Color roles

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | #ffffff | #111c2e | Page. Header uses the same, no border |
| `--foreground` | #14233c | #e8edf4 | Body text, headings, nav links |
| `--primary` | #1f4e8c | #8fb3ea | Links, primary buttons, nav hover, focus ring |
| `--highlight` (new) | #a3195b | #f08cb8 | Raspberry brand accent: Support button, eyebrows, key figures. Sparingly. Never orange |
| `--brand` (new) | #14233c | #0b1422 | Footer background |
| `--muted` / `--muted-foreground` | #f4f6f9 / #4a5568 | | Bands, table header / captions |
| `--accent` | #eef2f7 | #22324d | **shadcn hover background only.** Not the brand accent |
| `--destructive` | #b42318 | #f0857a | Errors, missing data |
| `--success` / `--warning` (new) | #1d6b3f / #8a5a00 | | Data-quality status, always with icon + label |
| `--border` / `--input` | #dde2ea / #c9d1dc | | Rules / input borders |

All text pairs meet WCAG AA (highlight 7.4:1 on white).

## Header and nav

- Links, in order: **Public safety** (`/public-safety`), **Properties** (`/properties`), **Government** (`/government`, which holds budgets and meetings), **Voter info** (`/elections`). No dropdowns.
- Rest: foreground, weight 500. Hover: `text-primary`. Current page: bold 700 + 2px underline at 8px offset + `aria-current="page"`. Bold width is reserved via `after:content-[attr(data-label)]` so links don't shift.
- Right side: **Support** pill in `bg-highlight`, `hover:bg-highlight/85`. No search in the header (search lives on each data page). No "About the data" in the header (it's in the footer).
- Background matches the page, no border, no shadow.
- Scroll: sticky; hides (`-translate-y-full`, 300ms, motion-safe) after ~1s of continuous downward scrolling; any upward scroll shows it; always visible near the top.
- Phone: mark + name + small Support pill + menu button. Menu is a full-screen dialog (Escape closes, body scroll locked, closes on navigation) with the same active style and a full-width "Support the project" button.

## Footer

`bg-brand text-brand-foreground`. Columns: brand (white mark, name, one-line description), **Explore** (the nav links), **About** (About the data, Support the project, Contact). Bottom line: independence disclaimer + © year.

## Charts (Recharts) and maps (MapLibre)

- Categorical series use `--chart-1`…`--chart-5` **in that fixed order** (blue, raspberry, ochre, teal, violet). Never cycle; more than 5 series fold into "Other". Color follows the entity, not its rank.
- Raspberry (chart-2) and teal (chart-4) converge for some color-blind readers: a chart using both must direct-label the series.
- Sequential (choropleths, heat grids): #e3ecf7 → #b6cdeb → #7fa6d9 → #4a7fc0 → #1f4e8c → #14335e.
- Diverging (change vs. last year): raspberry #a3195b · #d36b96 · #f1cadb · gray #e7e8eb · #c3d5ee · #7fa6d9 · #1f4e8c blue.
- One y-axis per chart. 4px rounded bar tops, 2px gaps, light grid (`--border`). Axis/labels in foreground/muted-foreground, never series colors. Map point markers: chart-2 with a 2px white ring.
- Status colors are never chart series.

## Type

- IBM Plex Sans for UI/body (16/26 body, 600 headings); IBM Plex Mono for eyebrows, case numbers, parcel IDs.
- Eyebrow: Plex Mono 12px, uppercase, 0.08em tracking, `text-highlight`.

## Logo

- Header: `<LogoMark size={44} strokeWidth={5.2} />` in foreground; footer: `size={40} strokeWidth={5.6}` in white.
- Minimums: clean mark 32px+; below that use `mark-simple.svg` (24–48) or `mark-favicon.svg` (≤24).
- Color only in foreground, white, or primary. Never chart or status colors.
- Loader: `<OperaHouseLoader size={160} />` for page loads, `size={56}` inline, `size={28}` in buttons.

## Open items

- `SUPPORT_HREF` in `nav-items.ts` is a placeholder (`/support`): point it at the real destination.
- `/contact` needs a page or a `mailto:`.
- Confirm the footer disclaimer ("Not affiliated with the City of Lebanon") is accurate.
- Sitemap still lists old routes (`/police-log`, `/budgets`, `/meetings`, `/people`, `/map`); routes under Public safety and Government need settling.
