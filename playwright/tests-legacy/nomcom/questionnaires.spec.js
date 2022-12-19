const { test, expect } = require('@playwright/test')
const viewports = require('../../helpers/viewports')

// ====================================================================
// NOMCOM - QUESTIONNAIRES
// ====================================================================

test.describe('expertise', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })

    await page.goto('/nomcom/2021/questionnaires/')
  })

  test('position tabs should display the appropriate panel on click', async ({ page }) => {
    const tabsLocator = page.locator('.nomcom-questnr-positions-tabs > li > button')
    const tabsCount = await tabsLocator.count()

    expect(tabsCount).toBeGreaterThan(0)

    for (let idx = 0; idx < tabsCount; idx++) {
      await tabsLocator.nth(idx).click()
      await expect(tabsLocator.nth(idx)).toHaveClass(/active/)

      const targetId = await tabsLocator.nth(idx).getAttribute('data-bs-target')

      const paneLocator = page.locator(targetId)

      await expect(paneLocator).toBeVisible()
      await expect(paneLocator).toHaveClass(/tab-pane/)
      await expect(paneLocator).toHaveClass(/active/)
    }
  })
})
