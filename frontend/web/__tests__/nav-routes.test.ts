import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
// The shared package exports only its .tsx components, so the nav list is read by path.
import { NAV_ITEMS } from '../../shared/components/site/nav-items'

const APP = join(__dirname, '..', 'app')

describe('the site nav', () => {
  // The nav pointed at /public-safety while the page lived at /map, so the link 404ed.
  it('links every ready topic to a page that exists', () => {
    const missing = NAV_ITEMS.filter((item) => !item.soon)
      .map((item) => item.href)
      .filter((href) => !existsSync(join(APP, href, 'page.tsx')))
    expect(missing).toEqual([])
  })
})
