const { test, expect } = require('@playwright/test')
const { DateTime } = require('luxon')
const { faker } = require('@faker-js/faker')
const slugify = require('slugify')
const meetingGenerator = require('../helpers/meeting.js')
const _ = require('lodash')

/* eslint-disable cypress/no-async-tests */

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
      const localDateTime = DateTime.fromISO(meetingData.meeting.startDate, { zone: BROWSER_TIMEZONE })
        .setZone(BROWSER_TIMEZONE)
        .setLocale(BROWSER_LOCALE)
        .plus({ days: idx })
        .toLocaleString(DateTime.DATE_HUGE)
      await expect(dayHeadersLocator.nth(idx)).toContainText(localDateTime)
    }
  })

  test.only('agenda schedule list table events', async ({ page }) => {
    const eventRowsLocator = page.locator('.agenda-table .agenda-table-display-event')

    await expect(eventRowsLocator).toHaveCount(meetingData.schedule.length)

    let isFirstSession = true
    for (let idx = 0; idx < meetingData.schedule.length; idx++) {
      const row = eventRowsLocator.nth(idx)
      const event = meetingData.schedule[idx]
      const eventStart = DateTime.fromISO(event.startDateTime)
      const eventEnd = eventStart.plus({ seconds: event.duration })
      const eventTimeSlot = `${eventStart.toFormat('HH:mm')} - ${eventEnd.toFormat('HH:mm')}`
      // --------
      // Location
      // --------
      if (event.location?.short) {
        // Has floor badge
        await expect(row.locator('.agenda-table-cell-room > a')).toContainText(event.room)
        await expect(row.locator('.agenda-table-cell-room > a')).toHaveAttribute('href', `/meeting/${meetingData.meeting.number}/floor-plan-neue?room=${xslugify(event.room)}`)
        await expect(row.locator('.agenda-table-cell-room > .badge')).toContainText(event.location.short)
      } else {
        // No floor badge
        await expect(row.locator('.agenda-table-cell-room > span:not(.badge)')).toContainText(event.room)
        await expect(row.locator('.agenda-table-cell-room > .badge')).not.toBeVisible()
      }
      // ---------------------------------------------------
      // Type-specific timeslot / group / name columns tests
      // ---------------------------------------------------
      if (event.type === 'regular') {
        // First session should have header row above it
        if (isFirstSession) {
          const headerRow = await page.locator(`#agenda-rowid-sesshd-${event.id}`)
          await expect(headerRow).toBeVisible()
          await expect(headerRow.locator('.agenda-table-cell-ts')).toContainText(eventTimeSlot)
          await expect(headerRow.locator('.agenda-table-cell-name')).toContainText(`${DateTime.fromISO(event.startDateTime).toFormat('cccc')} ${event.name}`)
        }
        // Timeslot
        await expect(row.locator('.agenda-table-cell-ts')).toContainText('—')
        // Group Acronym + Parent
        await expect(row.locator('.agenda-table-cell-group > .badge')).toContainText(event.groupParent.acronym)
        await expect(row.locator('.agenda-table-cell-group > .badge + a')).toContainText(event.acronym)
        await expect(row.locator('.agenda-table-cell-group > .badge + a')).toHaveAttribute('href', `/group/${event.acronym}/about/`)
        // Group Name
        await expect(row.locator('.agenda-table-cell-name')).toContainText(event.groupName)
        isFirstSession = false
      } else {
        // Timeslot
        await expect(row.locator('.agenda-table-cell-ts')).toContainText(eventTimeSlot)
        // Event Name
        await expect(row.locator('.agenda-table-cell-name')).toContainText(event.name)
        isFirstSession = true
      }
      // -----------
      // Name column
      // -----------
      // Event icon
      if (['break', 'plenary'].includes(event.type) || (event.type === 'other' && ['office hours', 'hackathon'].some(s => event.name.toLowerCase().indexOf(s) >= 0))) {
        await expect(row.locator('.agenda-table-cell-name > i.bi')).toBeVisible()
      }
      // Name link
      if (event.flags.agenda) {
        await expect(row.locator('.agenda-table-cell-name > a')).toHaveAttribute('href', event.agenda.url)
      }
      // BoF badge
      if (event.isBoF) {
        await expect(row.locator('.agenda-table-cell-name > .badge')).toContainText('BoF')
      }
      // Note
      if (event.note) {
        await expect(row.locator('.agenda-table-cell-name > .agenda-table-note')).toBeVisible()
        await expect(row.locator('.agenda-table-cell-name > .agenda-table-note i.bi')).toBeVisible()
        await expect(row.locator('.agenda-table-cell-name > .agenda-table-note i.bi + span')).toContainText(event.note)
      }
      // -----------------------
      // Buttons / Status Column
      // -----------------------
      switch (event.status) {
        // Cancelled
        case 'canceled': {
          await expect(row.locator('.agenda-table-cell-links > .badge.is-cancelled')).toContainText('Cancelled')
          break
        }
        // Rescheduled
        case 'resched': {
          await expect(row.locator('.agenda-table-cell-links > .badge.is-rescheduled')).toContainText('Rescheduled')
          break
        }
        // Scheduled
        case 'sched': {
          if (event.flags.showAgenda || ['regular', 'plenary'].includes(event.type)) {
            const eventButtons = row.locator('.agenda-table-cell-links > .agenda-table-cell-links-buttons')
            if (event.flags.agenda) {
              // Show meeting materials button
              await expect(eventButtons.locator('i.bi.bi-collection')).toBeVisible()
              // ZIP materials button
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-tar`)).toHaveAttribute('href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.tgz`)
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-tar > i.bi`)).toBeVisible()
              // PDF materials button
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-pdf`)).toHaveAttribute('href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.pdf`)
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-pdf > i.bi`)).toBeVisible()
            } else if (event.type === 'regular') {
              // No meeting materials yet warning badge
              await expect(eventButtons.locator('.no-meeting-materials')).toBeVisible()
            }
            // Notepad button
            const hedgeDocLink = `https://notes.ietf.org/notes-ietf-${meetingData.meeting.number}-${event.type === 'plenary' ? 'plenary' : event.acronym}`
            await expect(eventButtons.locator(`#btn-lnk-${event.id}-note`)).toHaveAttribute('href', hedgeDocLink)
            await expect(eventButtons.locator(`#btn-lnk-${event.id}-note > i.bi`)).toBeVisible()
            // Chat logs
            await expect(eventButtons.locator(`#btn-lnk-${event.id}-logs`)).toHaveAttribute('href', event.links.chatArchive)
            await expect(eventButtons.locator(`#btn-lnk-${event.id}-logs > i.bi`)).toBeVisible()
            // Recordings
            for (const rec of event.links.recordings) {
              if (rec.url.indexOf('audio') > 0) {
                // -> Audio
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-audio-${rec.id}`)).toHaveAttribute('href', rec.url)
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-audio-${rec.id} > i.bi`)).toBeVisible()
              } else if (rec.url.indexOf('youtu') > 0) {
                // -> Youtube
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-youtube-${rec.id}`)).toHaveAttribute('href', rec.url)
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-youtube-${rec.id} > i.bi`)).toBeVisible()
              } else {
                // -> Others
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-video-${rec.id}`)).toHaveAttribute('href', rec.url)
                await expect(eventButtons.locator(`#btn-lnk-${event.id}-video-${rec.id} > i.bi`)).toBeVisible()
              }
            }
            // Video Stream
            if (event.links.videoStream) {
              const videoStreamLink = `https://www.meetecho.com/ietf${meetingData.meeting.number}/recordings#${event.acronym.toUpperCase()}`
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-rec`)).toHaveAttribute('href', videoStreamLink)
              await expect(eventButtons.locator(`#btn-lnk-${event.id}-rec > i.bi`)).toBeVisible()
            }
          } else {
            await expect(row.locator('.agenda-table-cell-links > .agenda-table-cell-links-buttons')).not.toBeVisible()
          }
          break
        }
      }
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
