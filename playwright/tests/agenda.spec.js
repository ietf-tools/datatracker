const { test, expect } = require('@playwright/test')
const { DateTime } = require('luxon')
const { faker } = require('@faker-js/faker')
const slugify = require('slugify')
const meetingGenerator = require('../helpers/meeting.js')
const _ = require('lodash')

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

    // Wait for page to be ready
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

    // NAV

    const navLocator = page.locator('.agenda .meeting-nav > li')
    await expect(navLocator).toHaveCount(3)
    await expect(navLocator.first()).toContainText('Agenda')
    await expect(navLocator.nth(1)).toContainText('Floor plan')
    await expect(navLocator.last()).toContainText('Plaintext')

    // SETTINGS BUTTON

    await expect(page.locator('.agenda .meeting-nav + button')).toContainText('Settings')
  })

  test('agenda schedule list header', async ({ page }) => {
    const infonoteLocator = page.locator('.agenda .agenda-infonote')
    const infonoteToggleLocator = page.locator('.agenda h2 + button')
    const tzMeetingBtnLocator = page.locator('.agenda .agenda-tz-selector > button:nth-child(1)')
    const tzLocalBtnLocator = page.locator('.agenda .agenda-tz-selector > button:nth-child(2)')
    const tzUtcBtnLocator = page.locator('.agenda .agenda-tz-selector > button:nth-child(3)')

    await expect(page.locator('.agenda h2')).toContainText('Schedule')
    await expect(infonoteLocator).toBeVisible()
    await expect(infonoteLocator).toContainText(meetingData.meeting.infoNote)

    // INFO-NOTE TOGGLE

    await page.locator('.agenda .agenda-infonote > button').click()
    await expect(infonoteLocator).not.toBeVisible()
    await expect(infonoteToggleLocator).toBeVisible()
    await infonoteToggleLocator.click()
    await expect(infonoteLocator).toBeVisible()
    await expect(infonoteToggleLocator).not.toBeVisible()

    // TIMEZONE SELECTOR

    await expect(page.locator('.agenda .agenda-tz-selector')).toBeVisible()
    await expect(page.locator('small:left-of(.agenda .agenda-tz-selector)')).toContainText('Timezone:')
    await expect(page.locator('.agenda .agenda-tz-selector > button')).toHaveCount(3)
    await expect(tzMeetingBtnLocator).toContainText('Meeting')
    await expect(tzLocalBtnLocator).toContainText('Local')
    await expect(tzUtcBtnLocator).toContainText('UTC')
    await expect(page.locator('.agenda .agenda-timezone-ddn')).toBeVisible()

    // CHANGE TIMEZONE

    // Switch to local timezone
    await tzLocalBtnLocator.click()
    await expect(tzLocalBtnLocator).toHaveClass(/n-button--primary-type/)
    await expect(tzMeetingBtnLocator).not.toHaveClass(/n-button--primary-type/)
    const localDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone(BROWSER_TIMEZONE)
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(localDateTime)
    // Switch to UTC
    await tzUtcBtnLocator.click()
    await expect(tzUtcBtnLocator).toHaveClass(/n-button--primary-type/)
    await expect(tzLocalBtnLocator).not.toHaveClass(/n-button--primary-type/)
    const utcDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone('utc')
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(utcDateTime)
    await expect(page.locator('.agenda .agenda-timezone-ddn')).toContainText('UTC')
    // Switch back to meeting timezone
    await tzMeetingBtnLocator.click()
    await expect(tzMeetingBtnLocator).toHaveClass(/n-button--primary-type/)
    await expect(page.locator('.agenda .agenda-timezone-ddn')).toContainText('Tokyo')
  })

  test('agenda schedule list table', async ({ page }) => {
    const dayHeadersLocator = page.locator('.agenda-table-display-day')

    // TABLE HEADERS

    await expect(page.locator('.agenda-table-head-time')).toContainText('Time')
    await expect(page.locator('.agenda-table-head-location')).toContainText('Location')
    await expect(page.locator('.agenda-table-head-event')).toContainText('Event')

    // DAY HEADERS

    await expect(dayHeadersLocator).toHaveCount(7)
    for (let idx = 0; idx < 7; idx++) {
      const localDateTime = DateTime.fromISO(meetingData.meeting.startDate)
        .setZone(BROWSER_TIMEZONE)
        .setLocale(BROWSER_LOCALE)
        .plus({ days: idx })
        .toLocaleString(DateTime.DATE_HUGE)
      await expect(dayHeadersLocator.nth(idx)).toContainText(localDateTime)
    }
  })

  test('agenda schedule list search', async ({ page }) => {
    const eventRowsLocator = page.locator('.agenda-table .agenda-table-display-event')
    const searchInputLocator = page.locator('.agenda-search input[type=text]')

    await page.locator('.agenda-table > .agenda-table-search > button').click()
    await expect(page.locator('.agenda-search')).toBeVisible()

    const event = _.find(meetingData.schedule, s => s.type === 'regular')
    const eventWithNote = _.find(meetingData.schedule, s => s.note)

    // Search different terms
    const searchTerms = [
      'hack', // Should match hackathon events
      event.groupAcronym, // Match group name
      event.room.toLowerCase(), // Match room name
      eventWithNote.note.substring(0, 10).toLowerCase() // Match partial note
    ]

    for (const term of searchTerms) {
      await searchInputLocator.fill(term)
      // Let the UI update before checking each displayed row
      await page.waitForTimeout(1000)
      await expect(eventRowsLocator).not.toHaveCount(meetingData.schedule.length)
      const rowsCount = await eventRowsLocator.count()
      for (let idx = 0; idx < rowsCount; idx++) {
        await expect(eventRowsLocator.nth(idx)).toContainText(term, { ignoreCase: true })
      }
    }

    // Clear button
    await page.locator('.agenda-search button').click()
    await expect(searchInputLocator).toHaveValue('')
    await expect(eventRowsLocator).toHaveCount(meetingData.schedule.length)
    // Invalid search
    await searchInputLocator.fill(faker.vehicle.vin())
    await expect(eventRowsLocator).toHaveCount(0)
    await expect(page.locator('.agenda-table .agenda-table-display-noresult')).toContainText('No event matching your search query.')
    // Closing search should clear search
    await page.locator('.agenda-table > .agenda-table-search > button').click()
    await expect(page.locator('.agenda-search')).not.toBeVisible()
    await expect(eventRowsLocator).toHaveCount(meetingData.schedule.length)
  })
})
