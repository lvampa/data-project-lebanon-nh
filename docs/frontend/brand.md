# Brand rules

Values live in CSS, not here.
Colors are in `frontend/shared/styles/colors.css`, the type scale and `eyebrow` utility are in `frontend/shared/styles/typography.css`, and button styles are variants of `Button` in `frontend/shared/components/ui/button.tsx`.
This file holds the rules the CSS can't enforce.

## Color

- `highlight` (raspberry) is an accent: the Support button, eyebrows, key figures, one call-out per page.
  Use it sparingly and never pair it with orange.
- `accent` is shadcn's hover background only, not the brand accent.
- Status colors (`success`, `warning`, `destructive`) always come with an icon and a label, never color alone.
- Every text pair meets WCAG AA. Check new pairs before using them.

## Charts and maps

- Categorical series use `--chart-1` to `--chart-5` in that fixed order: blue, raspberry, ochre, teal, violet.
- Color follows the entity, not its rank, and never cycles. More than five series fold into "Other".
- Raspberry and teal converge for some color-blind readers, so a chart using both must label series directly.
- Status colors are never chart series.
- Sequential scale: #e3ecf7, #b6cdeb, #7fa6d9, #4a7fc0, #1f4e8c, #14335e.
- Diverging scale: #a3195b, #d36b96, #f1cadb, #e7e8eb, #c3d5ee, #7fa6d9, #1f4e8c.
- One y-axis per chart, 4px rounded bar tops, 2px gaps, a light grid in `border`.
  Axes and labels use foreground or muted-foreground, never series colors.
- Map point markers use `chart-2` with a 2px white ring.

## Type

- IBM Plex Sans for UI and body, IBM Plex Mono for eyebrows, case numbers and parcel IDs.
- Headings use `text-display-1` (hero), `text-display-2` (section) or `text-display-3` (card) instead of pixel sizes.
- Small labels above a heading use `eyebrow`.

## Header

- Nav order: Voter Info, Public safety, Properties, Government. No dropdowns.
- No search in the header; search lives on each data page.
  About the data lives in the footer, not the header.
- The header is sticky and hides after scrolling about 150px down. Any upward scroll shows it.
  Don't wrap it in another sticky or overflow container, since it listens to `window` scroll.
- Phone: menu button on the left, the mark alone in the center, a small Support pill on the right.
  The menu is a full-screen dialog that closes on Escape and on navigation.

## Footer

- Opens with a call-out: the mark, a statement in `text-display-2`, and a highlight pill.
- Then the brand column, Explore, About, and the independence disclaimer.

## Logo

- Files are in `frontend/shared/brand/logo/`. Use `<LogoMark />` in React.
- The clean mark is for 32px and up, `mark-simple.svg` for 24 to 48px, and `mark-favicon.svg` for 24px and below.
- The mark is only ever foreground, white or primary, never a chart or status color.
- `<OperaHouseLoader />` is the loading animation: 160 for page loads, 56 inline, 28 in buttons.

## Open items

- `SUPPORT_HREF` in `nav-items.ts` is a placeholder.
- `/contact` needs a page or a `mailto:`.
- Confirm the footer disclaimer is accurate before launch.
- Routes under Public safety and Government still need settling.
