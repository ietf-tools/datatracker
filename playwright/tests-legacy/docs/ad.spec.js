const { test, expect } = require('@playwright/test')
const viewports = require('../../helpers/viewports')

// ====================================================================
// IESG Dashboard
// ====================================================================

test.describe('/doc/ad/', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })

    await page.goto('/doc/ad/')
  })

  test('Pre pubreq', async ({ page }) => {
    const tablesLocator = page.locator('table')
    const tablesCount = await tablesLocator.count()
    expect(tablesCount).toBeGreaterThan(0)
    const firstTable = tablesLocator.nth(0)
    const theadTexts = await firstTable.locator('thead').allInnerTexts()
    expect(theadTexts.join('')).toContain('Pre pubreq')
  })
})
