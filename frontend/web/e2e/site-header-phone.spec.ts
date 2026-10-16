import { expect, test } from '@playwright/test';

test.skip(({ isMobile }) => !isMobile, 'phone layout only');

test('phone header has the menu left, the mark centered and Support right', async ({ page }) => {
  await page.goto('/');
  const header = page.getByRole('banner');

  const menu = await header.getByRole('button', { name: 'Open menu' }).boundingBox();
  const home = await header.getByRole('link', { name: 'Lebanon Data Project home' }).boundingBox();
  const support = await header.getByRole('link', { name: 'Support' }).boundingBox();
  const viewportWidth = page.viewportSize()!.width;

  expect(menu!.x).toBeLessThan(viewportWidth / 4);
  expect(Math.abs(home!.x + home!.width / 2 - viewportWidth / 2)).toBeLessThanOrEqual(1);
  expect(support!.x + support!.width).toBeGreaterThan((viewportWidth * 3) / 4);
  await expect(header.getByText('Lebanon Data Project')).toBeHidden();
});

test('menu closes from the same corner it opened from', async ({ page }) => {
  await page.goto('/');
  const open = await page.getByRole('button', { name: 'Open menu' }).boundingBox();
  await page.getByRole('button', { name: 'Open menu' }).click();
  const close = await page.getByRole('button', { name: 'Close menu' }).boundingBox();

  expect(Math.abs(close!.x - open!.x)).toBeLessThanOrEqual(1);
});
