const {
  test,
  expect
} = require('@playwright/test')
const { STATUS_STORAGE_KEY, generateStatusTestId } = require('../../../client/shared/status-common.js')

test.describe('site status', () => {
  const noStatus = {
    hasMessage: false
  }

  const status1 = {
    hasMessage: true,
    id: 1,
    slug: '2024-7-9fdfdf-sdfsdf',
    title: 'My status title',
    body: 'My status body',
    url: '/status/2024-7-9fdfdf-sdfsdf',
    date: '2024-07-09T07:05:13+00:00',
    by: 'Exile is a cool Amiga game'
  }

  test.beforeEach(({ browserName }) => {
    test.skip(browserName === 'firefox', 'bypassing flaky tests on Firefox')
  })

  test('Renders server status as Notification', async ({ page }) => {
    await page.route('/status/latest.json', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(status1)
      })
    })
    await page.goto('/')
    await expect(page.getByTestId(generateStatusTestId(status1.id)), 'should have status').toHaveCount(1)
  })

  test("Doesn't render dismissed server statuses", async ({ page }) => {
    await page.route('/status/latest.json', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(status1)
      })
    })
    await page.goto('/')
    await page.evaluate(({ key, value }) => localStorage.setItem(key, value), { key: STATUS_STORAGE_KEY, value: JSON.stringify([status1.id]) })
    await expect(page.getByTestId(generateStatusTestId(status1.id)), 'should have status').toHaveCount(0)
  })

  test('Handles no server status', async ({ page }) => {
    await page.route('/status/latest.json', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(noStatus)
      })
    })

    await page.goto('/')

    await expect(page.getByTestId(generateStatusTestId(status1.id)), 'should have status').toHaveCount(0)
  })
})
