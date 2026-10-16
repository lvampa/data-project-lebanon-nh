import { expect, test } from '@playwright/test'

test('home page renders the site header', async ({ page }) => {
  await page.goto('/')

  const header = page.getByRole('banner')
  await expect(header).toBeVisible()
  await expect(header.getByRole('link', { name: 'Lebanon Data Project home' })).toBeVisible()
})
