const { test, expect } = require('@playwright/test')
const { DateTime } = require('luxon')
const { faker } = require('@faker-js/faker')
const slugify = require('slugify')
const meetingGenerator = require('../helpers/meeting.js')

const xslugify = (str) => slugify(str.replace('/', '-'), { lower: true, strict: true })

const TEST_SEED = 123
const BROWSER_LOCALE = 'en-US'
const BROWSER_TIMEZONE = 'America/Toronto'

const viewports = {
  desktop: [1536, 960],
  smallDesktop: [1280, 800],
  tablet: [768, 1024],
  mobile: [360, 760]
}

// Set randomness seed
faker.seed(TEST_SEED)

/**
 * Format URL by replacing inline variables
 *
 * @param {String} url Raw URL
 * @param {Object} session Session Object
 * @param {String} meetingNumber Meeting Number
 * @returns Formatted URL
 */
function formatLinkUrl (url, session, meetingNumber) {
  return url
    ? url.replace('{meeting.number}', meetingNumber)
      .replace('{group.acronym}', session.groupAcronym)
      .replace('{short}', session.short)
      .replace('{order_number}', session.orderInMeeting)
    : url
}

// ====================================================================
// AGENDA-NEUE (past meeting) | DESKTOP viewport
// ====================================================================

test.describe('meeting -> agenda-neue [past, desktop]', () => {
  let meetingData

  test.beforeAll(async () => {
    // Generate meeting data
    meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'past' })
  })

  test.beforeEach(async ({ page }) => {
    // Intercept Meeting Data API
    await page.route(`**/api/meeting/${meetingData.meeting.number}/agenda-data`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(meetingData)
      })
    })

    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })

    // Visit agenda page
    await page.goto(`/meeting/${meetingData.meeting.number}/agenda-neue`)

    // Wait for Meeting Data API call
    await page.waitForResponse(`**/api/meeting/${meetingData.meeting.number}/agenda-data`)
    await page.locator('.agenda h1').waitFor({ state: 'visible' })
  })

  test('agenda header section', async ({ page }) => {
    await expect(page.locator('.agenda h1'), 'should have agenda title').toContainText(`IETF ${meetingData.meeting.number} Meeting Agenda`)
    await expect(page.locator('.agenda h4').first(), 'should have meeting city subtitle').toContainText(meetingData.meeting.city)
    await expect(page.locator('.agenda h4').first(), 'should have meeting date subtitle').toContainText(/[a-zA-Z] [0-9]{1,2} - ([a-zA-Z]+ )?[0-9]{1,2}, [0-9]{4}/i)

    const updatedDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone(meetingData.meeting.timezone)
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first(), 'should have meeting last updated datetime').toContainText(updatedDateTime)
  })

  test('agenda nav section', async ({ page }) => {
    await expect(page.locator('.agenda .meeting-nav > li')).toHaveCount(3)
    await expect(page.locator('.agenda .meeting-nav > li').first()).toContainText('Agenda')
    await expect(page.locator('.agenda .meeting-nav > li').nth(1)).toContainText('Floor plan')
    await expect(page.locator('.agenda .meeting-nav > li').last()).toContainText('Plaintext')
  })

  test('change agenda timezone', async ({ page }) => {
    const meetingSelector = page.locator('.agenda .agenda-tz-selector > button:nth-child(1)')
    const localSelector = page.locator('.agenda .agenda-tz-selector > button:nth-child(2)')
    const utcSelector = page.locator('.agenda .agenda-tz-selector > button:nth-child(3)')
    // Switch to local timezone
    await localSelector.click()
    await expect(localSelector).toHaveClass(/n-button--primary-type/)
    await expect(meetingSelector).not.toHaveClass(/n-button--primary-type/)
    const localDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone(BROWSER_TIMEZONE)
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(localDateTime)
    // Switch to UTC
    await utcSelector.click()
    await expect(utcSelector).toHaveClass(/n-button--primary-type/)
    await expect(localSelector).not.toHaveClass(/n-button--primary-type/)
    const utcDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone('utc')
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(utcDateTime)
    await expect(page.locator('.agenda .agenda-timezone-ddn')).toContainText('UTC')
    // Switch back to meeting timezone
    await meetingSelector.click()
    await expect(meetingSelector).toHaveClass(/n-button--primary-type/)
    await expect(page.locator('.agenda .agenda-timezone-ddn')).toContainText('Tokyo')
  })
})
