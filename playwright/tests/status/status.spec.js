const { test,
  //expect
} = require('@playwright/test')
// const { setTimeout } = require('timers/promises')

test.describe('status', () => {
  test.beforeEach(async ({ page }) => {

    await page.route('/status/latest.json', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          "hasMessage": true,
          "id": 1,
          "slug": "2024-7-9fdfdf-sdfsdf",
          "title": "My status title",
          "body": "My status body",
          "url": "/status/2024-7-9fdfdf-sdfsdf",
          "date": "2024-07-09T07:05:13+00:00",
          "by": "Robert Sparks"
        })
      })
    })
  })
})
