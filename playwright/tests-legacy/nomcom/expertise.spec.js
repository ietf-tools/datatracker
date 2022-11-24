const { test, expect } = require('@playwright/test')
const viewports = require('../../helpers/viewports')

// ====================================================================
// NOMCOM - EXPERTISE
// ====================================================================

test.describe('expertise', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })

    await page.goto('/nomcom/2021/expertise/')
  })

  test('expertises with expandable panels should expand', async ({ page }) => {
    const tabsLocator = page.locator('.nomcom-req-positions-tabs > li > button')
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

      // Check accordion
      const accordionHeadsLocator = paneLocator.locator('.accordion-header > button')
      const accordionHeadsCount = await accordionHeadsLocator.count()

      if (accordionHeadsCount > 0) {
        for (let aIdx = 0; aIdx < accordionHeadsCount; aIdx++) {
          await accordionHeadsLocator.nth(aIdx).click()
          const expandPaneId = await accordionHeadsLocator.nth(aIdx).getAttribute('data-bs-target')

          const sectionLocator = page.locator(expandPaneId)

          await expect(sectionLocator).toBeVisible()
        }
      }
    }
  })
})
