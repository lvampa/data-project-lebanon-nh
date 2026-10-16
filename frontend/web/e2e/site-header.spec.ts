import { expect, test, type Page } from '@playwright/test'

function headerTop(page: Page) {
  return page.evaluate(() => document.querySelector('header')!.getBoundingClientRect().top)
}

async function expectShown(page: Page) {
  await expect.poll(() => headerTop(page)).toBe(0)
}

async function expectHidden(page: Page) {
  await expect.poll(() => headerTop(page)).toBeLessThan(0)
}

async function wheel(page: Page, dy: number) {
  await page.mouse.wheel(0, dy)
  await expect.poll(() => page.evaluate(() => window.scrollY)).not.toBe(0)
}

test.describe('site header on scroll', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // The home page is barely taller than the viewport.
    await page.addStyleTag({ content: 'main { min-height: 5000px }' })
    await page.mouse.move(100, 400)
  })

  test('stays put for a short scroll down', async ({ page }) => {
    await wheel(page, 100)
    await page.waitForTimeout(400)
    expect(await headerTop(page)).toBe(0)
  })

  test('hides after slow wheel notches add up', async ({ page }) => {
    for (let i = 0; i < 3; i++) {
      await wheel(page, 100)
      await page.waitForTimeout(300)
    }
    await expectHidden(page)
  })

  test('hides after a single flick', async ({ page }) => {
    await wheel(page, 400)
    await expectHidden(page)
  })

  test('comes back on any scroll up', async ({ page }) => {
    await wheel(page, 600)
    await expectHidden(page)

    await page.mouse.wheel(0, -50)
    await expectShown(page)
  })

  test('hides again after scrolling down from where it came back', async ({ page }) => {
    await wheel(page, 600)
    await page.mouse.wheel(0, -50)
    await expectShown(page)

    await page.mouse.wheel(0, 100)
    await page.waitForTimeout(400)
    expect(await headerTop(page)).toBe(0)

    await page.mouse.wheel(0, 100)
    await expectHidden(page)
  })
})
