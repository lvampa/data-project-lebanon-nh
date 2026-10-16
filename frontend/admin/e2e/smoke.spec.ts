import { expect, test } from '@playwright/test'

test('home page redirects to incidents', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL(/\/incidents$/)
  await expect(page.getByRole('link', { name: 'Incidents' })).toHaveAttribute(
    'aria-current',
    'page',
  )
})
