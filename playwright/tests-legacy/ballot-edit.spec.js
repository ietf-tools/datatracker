const { test, expect } = require('@playwright/test')
const viewports = require('../helpers/viewports')
const session = require('../helpers/session')

// ====================================================================
// BALLOT - EDITING
// ====================================================================

test.describe('ballot edit position ', () => {
  test.beforeEach(async ({ page, baseURL }) => {
    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })
    // Is there an AD user for local testing?
    await session.login(page, baseURL, 'gunter@vandevelde.cc', 'password')
  })

  test('redirect back to ballot_edit_return_point param' , async ({ page, baseURL }, workerInfo) => {
    await page.goto('/doc/draft-ietf-opsawg-ipfix-tcpo-v6eh/ballot/')
    const editPositionButton = await page.getByRole('link', { name: 'Edit position' })
    const href = await editPositionButton.getAttribute('href')
    // The href's query param 'ballot_edit_return_point' should point to the current page
    const hrefUrl = new URL(href, baseURL)

    const entryPageUrl = new URL(page.url(), baseURL)
    await expect(hrefUrl.searchParams.get('ballot_edit_return_point')).toBe(entryPageUrl.pathname)
    await editPositionButton.click()
    await page.waitForURL('**/position')

    // The position page has several ways through it so we'll test each one to see if 'ballot_edit_return_point' works

    // Option 1. Try the default 'Save' button
    await page.getByRole('button', { name: 'Save' })
    await page.waitForURL(entryPageUrl.pathname)

    // Option 2. Try the 'Save & send email' button
    await page.getByRole('link', { name: 'Edit position' }).click()
    await page.waitForURL('**/position')
    await page.getByRole('button', { name: 'Save & send email' }).click()
    await page.waitForURL('**/emailposition/')
    await page.getByRole('button', { name: 'Send' }).click()
    await page.waitForURL(entryPageUrl.pathname)

    // TODO: Option 3. Try the 'Defer ballot' button
    // This doens't yet work.
    // await page.getByRole('link', { name: 'Edit position' }).click()
    // await page.waitForURL('**/position')
    // await page.getByRole('button', { name: 'Defer ballot' }).click()
    // await page.waitForURL('**/deferballot/')
  })
})

