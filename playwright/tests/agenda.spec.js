const { test, expect } = require('@playwright/test')
const { DateTime } = require('luxon')
const { faker } = require('@faker-js/faker')
const slugify = require('slugify')
const meetingGenerator = require('../helpers/meeting.js')
const _ = require('lodash')
const fs = require('fs/promises')
const { setTimeout } = require('timers/promises')

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

async function isIntersectingViewport (page, selector) {
  return page.$eval(selector, async el => {
    const bottom = window.innerHeight
    const rect = el.getBoundingClientRect()

    return rect.top < bottom && rect.top > 0 - rect.height
  })
}

// ====================================================================
// AGENDA-NEUE (past meeting) | DESKTOP viewport
// ====================================================================

test.describe('past - desktop', () => {
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

    // Visit agenda page and await Meeting Data API call to complete
    await Promise.all([
      page.waitForResponse(`**/api/meeting/${meetingData.meeting.number}/agenda-data`),
      page.goto(`/meeting/${meetingData.meeting.number}/agenda-neue`)
    ])

    // Wait for page to be ready
    await page.locator('.agenda h1').waitFor({ state: 'visible' })
    await setTimeout(500)
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

  test('agenda schedule list table events', async ({ page }) => {
    test.slow() // Triple the default timeout

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
          const headerRow = page.locator(`#agenda-rowid-sesshd-${event.id}`)
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

  test('agenda meeting materials dialog', async ({ page }) => {
    const event = _.find(meetingData.schedule, s => s.flags.showAgenda && s.flags.agenda)
    const eventStart = DateTime.fromISO(event.startDateTime)
    const eventEnd = eventStart.plus({ seconds: event.duration })
    // Intercept meeting materials request
    const materialsUrl = (new URL(event.agenda.url)).pathname
    const materialsInfo = {
      url: event.agenda.url,
      slides: _.times(5, idx => ({
        id: 100000 + idx,
        title: faker.commerce.productName(),
        url: `/meeting/${meetingData.meeting.number}/materials/slides-${meetingData.meeting.number}-${event.acronym}-${faker.internet.domainWord()}`,
        ext: ['pdf', 'html', 'md', 'txt', 'pptx'][idx]
      })),
      minutes: {
        ext: 'md',
        id: 123456,
        title: 'Minutes IETF123 Testing',
        url: `/meeting/${meetingData.meeting.number}/materials/minutes-${meetingData.meeting.number}-${event.acronym}-${faker.internet.domainWord()}`
      }
    }
    await page.route(`**/api/meeting/session/${event.sessionId}/materials`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(materialsInfo)
      })
    })
    await page.route(materialsUrl, route => {
      route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: 'The internet is a series of tubes.'
      })
    })
    await page.route(materialsInfo.minutes.url, route => {
      route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: 'One does not simply walk into mordor.'
      })
    })
    // Open dialog
    await page.locator(`#agenda-rowid-${event.id} #btn-lnk-${event.id}-mat`).click()
    await expect(page.locator('.agenda-eventdetails')).toBeVisible()
    // await page.waitForResponse(materialsUrl)
    // Header
    await expect(page.locator('.agenda-eventdetails .n-card-header__main > .detail-header > .bi')).toBeVisible()
    await expect(page.locator('.agenda-eventdetails .n-card-header__main > .detail-header > .bi + span')).toContainText(eventStart.toFormat('DDDD'))
    await expect(page.locator('.agenda-eventdetails .n-card-header__extra > .detail-header > .bi')).toBeVisible()
    await expect(page.locator('.agenda-eventdetails .n-card-header__extra > .detail-header > .bi + strong')).toContainText(`${eventStart.toFormat('T')} - ${eventEnd.toFormat('T')}`)
    await expect(page.locator('.agenda-eventdetails .detail-title > h6 > .bi')).toBeVisible()
    await expect(page.locator('.agenda-eventdetails .detail-title > h6 > .bi + span')).toContainText(event.name)
    await expect(page.locator('.agenda-eventdetails .detail-location > .bi')).toBeVisible()
    await expect(page.locator('.agenda-eventdetails .detail-location > .bi + .badge')).toContainText(event.location.short)
    await expect(page.locator('.agenda-eventdetails .detail-location > .bi + .badge + span')).toContainText(event.room)
    // Navigation
    const navLocator = await page.locator('.agenda-eventdetails .detail-nav > a')
    await expect(navLocator).toHaveCount(3)
    await expect(navLocator.first()).toHaveClass(/active/)
    await expect(navLocator.nth(1)).not.toHaveClass(/active/)
    await expect(navLocator.nth(2)).not.toHaveClass(/active/)
    // Agenda Tab
    await expect(page.locator('.agenda-eventdetails .detail-text > iframe')).toHaveAttribute('src', materialsUrl)
    // Slides Tab
    await navLocator.nth(1).click()
    await expect(navLocator.nth(1)).toHaveClass(/active/)
    await expect(navLocator.first()).not.toHaveClass(/active/)
    const slidesLocator = page.locator('.agenda-eventdetails .detail-text > .list-group > .list-group-item')
    await expect(slidesLocator).toHaveCount(materialsInfo.slides.length)
    for (let idx = 0; idx < materialsInfo.slides.length; idx++) {
      await expect(slidesLocator.nth(idx)).toHaveAttribute('href', materialsInfo.slides[idx].url)
      await expect(slidesLocator.nth(idx).locator('.bi')).toHaveClass(new RegExp(`bi-filetype-${materialsInfo.slides[idx].ext}`))
      await expect(slidesLocator.nth(idx).locator('span')).toContainText(materialsInfo.slides[idx].title)
    }
    // Minutes Tab
    await navLocator.last().click()
    await expect(navLocator.last()).toHaveClass(/active/)
    await expect(navLocator.nth(1)).not.toHaveClass(/active/)
    await expect(page.locator('.agenda-eventdetails .detail-text > iframe')).toHaveAttribute('src', materialsInfo.minutes.url)
    // Footer Buttons
    const hedgeDocLink = `https://notes.ietf.org/notes-ietf-${meetingData.meeting.number}-${event.type === 'plenary' ? 'plenary' : event.acronym}`
    const footerBtnsLocator = page.locator('.agenda-eventdetails .detail-action > a')
    await expect(footerBtnsLocator).toHaveCount(3)
    await expect(footerBtnsLocator.first()).toContainText('Download as tarball')
    await expect(footerBtnsLocator.first()).toHaveAttribute('href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.tgz`)
    await expect(footerBtnsLocator.nth(1)).toContainText('Download as PDF')
    await expect(footerBtnsLocator.nth(1)).toHaveAttribute('href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.pdf`)
    await expect(footerBtnsLocator.last()).toContainText('Notepad')
    await expect(footerBtnsLocator.last()).toHaveAttribute('href', hedgeDocLink)
    // Clicking X should close the dialog
    await page.locator('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
  })

  // -> SCHEDULE LIST -> Show Meeting Materials dialog (EMPTY VARIANT)

  test('agenda meeting materials dialog (empty variant)', async ({ page }) => {
    const event = _.find(meetingData.schedule, s => s.flags.showAgenda && s.flags.agenda)
    // Intercept meeting materials request
    const materialsUrl = (new URL(event.agenda.url)).pathname
    const materialsInfo = {
      url: event.agenda.url,
      slides: [],
      minutes: null
    }
    await page.route(`**/api/meeting/session/${event.sessionId}/materials`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(materialsInfo)
      })
    })
    await page.route(materialsUrl, route => {
      route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: 'The internet is a series of tubes.'
      })
    })
    // Open dialog
    await page.locator(`#btn-lnk-${event.id}-mat`).click()
    await expect(page.locator('.agenda-eventdetails')).toBeVisible()
    // Slides Tab
    await page.locator('.agenda-eventdetails .detail-nav > a').nth(1).click()
    await expect(page.locator('.agenda-eventdetails .detail-text')).toContainText('No slides submitted for this session.')
    // Minutes Tab
    await page.locator('.agenda-eventdetails .detail-nav > a').nth(2).click()
    await expect(page.locator('.agenda-eventdetails .detail-text')).toContainText('No minutes submitted for this session.')
    // Clicking X should close the dialog
    await page.locator('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
  })

  // -> FILTER BY AREA/GROUP DIALOG

  test('agenda filter by area/group', async ({ page }) => {
    // Open dialog
    await page.locator('#agenda-quickaccess-filterbyareagroups-btn').click()
    await expect(page.locator('.agenda-personalize')).toBeVisible()
    // Check header elements
    await expect(page.locator('.agenda-personalize .n-drawer-header__main > span')).toContainText('Filter Areas + Groups')
    const diagHeaderBtnLocator = page.locator('.agenda-personalize .agenda-personalize-actions > button')
    await expect(diagHeaderBtnLocator).toHaveCount(3)
    await expect(diagHeaderBtnLocator.first()).toContainText('Clear Selection')
    await expect(diagHeaderBtnLocator.nth(1)).toContainText('Cancel')
    await expect(diagHeaderBtnLocator.last()).toContainText('Apply')
    // Check categories
    const catsLocator = page.locator('.agenda-personalize .agenda-personalize-category')
    await expect(catsLocator).toHaveCount(meetingData.categories.length)
    // Check areas + groups
    for (let idx = 0; idx < meetingData.categories.length; idx++) {
      const cat = meetingData.categories[idx]
      const areasLocator = catsLocator.nth(idx).locator('.agenda-personalize-area')
      await expect(areasLocator).toHaveCount(cat.length)
      for (let areaIdx = 0; areaIdx < cat.length; areaIdx++) {
        // Area Button
        const area = cat[areaIdx]
        if (area.label) {
          await expect(areasLocator.nth(areaIdx).locator('.agenda-personalize-areamain > button')).toBeVisible()
          await expect(areasLocator.nth(areaIdx).locator('.agenda-personalize-areamain > button')).toContainText(area.label)
        } else {
          await expect(areasLocator.nth(areaIdx).locator('.agenda-personalize-areamain > button')).not.toBeVisible()
        }
        // Group Buttons
        const grpBtnsLocator = areasLocator.nth(areaIdx).locator('.agenda-personalize-groups > button')
        await expect(grpBtnsLocator).toHaveCount(area.children.length)
        for (let groupIdx = 0; groupIdx < area.children.length; groupIdx++) {
          const group = area.children[groupIdx]
          await expect(grpBtnsLocator.nth(groupIdx)).toBeVisible()
          await expect(grpBtnsLocator.nth(groupIdx)).toContainText(group.label)
          if (group.is_bof) {
            await expect(grpBtnsLocator.nth(groupIdx)).toHaveClass(/is-bof/)
            await expect(grpBtnsLocator.nth(groupIdx).locator('.badge')).toBeVisible()
            await expect(grpBtnsLocator.nth(groupIdx).locator('.badge')).toContainText('BoF')
          }
        }
        // Test Area Selection
        if (area.label) {
          await areasLocator.nth(areaIdx).locator('.agenda-personalize-areamain > button').click()
          for (let groupIdx = 0; groupIdx < area.children.length; groupIdx++) {
            await expect(grpBtnsLocator.nth(groupIdx)).toHaveClass(/is-checked/)
          }
          await areasLocator.nth(areaIdx).locator('.agenda-personalize-areamain > button').click()
          for (let groupIdx = 0; groupIdx < area.children.length; groupIdx++) {
            await expect(grpBtnsLocator.nth(groupIdx)).not.toHaveClass(/is-checked/)
          }
        }
        // Test Group Selection
        const randGroupIdx = _.random(area.children.length - 1)
        const groupLocator = areasLocator.nth(areaIdx).locator('.agenda-personalize-groups > button').nth(randGroupIdx)
        await groupLocator.click()
        await expect(groupLocator).toHaveClass(/is-checked/)
        await groupLocator.click()
        await expect(groupLocator).not.toHaveClass(/is-checked/)
      }
    }
    // Test multi-toggled_by button trigger
    const bofBtnLocator = page.locator('.agenda-personalize .agenda-personalize-category:last-child .agenda-personalize-area:last-child .agenda-personalize-groups > button', { hasText: 'BoF' })
    const bofGroupsLocator = page.locator('.agenda-personalize .agenda-personalize-group:has(.badge)')
    const bofGroupsCount = await bofGroupsLocator.count()
    await bofBtnLocator.click()
    for (let idx = 0; idx < bofGroupsCount; idx++) {
      await expect(bofGroupsLocator.nth(idx)).toHaveClass(/is-checked/)
    }
    await bofBtnLocator.click()
    for (let idx = 0; idx < bofGroupsCount; idx++) {
      await expect(bofGroupsLocator.nth(idx)).not.toHaveClass(/is-checked/)
    }
    // Clicking all groups from area then area button should unselect all
    const areaGroupsLocator = page.locator('.agenda-personalize .agenda-personalize-area >> nth=0 >> .agenda-personalize-groups > button')
    const areaGroupsCount = await areaGroupsLocator.count()
    for (let idx = 0; idx < areaGroupsCount; idx++) {
      await areaGroupsLocator.nth(idx).click()
    }
    await page.locator('.agenda-personalize .agenda-personalize-area >> nth=0 >> .agenda-personalize-areamain:first-child > button').click()
    for (let idx = 0; idx < areaGroupsCount; idx++) {
      await expect(areaGroupsLocator.nth(idx)).not.toHaveClass(/is-checked/)
    }
    // Test Clear Selection
    const groupsLocator = page.locator('.agenda-personalize .agenda-personalize-group')
    const groupsCount = await groupsLocator.count()
    const randGroupRange = _.take(_.shuffle(_.range(groupsCount)), 10)
    for (const idx of randGroupRange) {
      await groupsLocator.nth(idx).click()
    }
    await page.locator('.agenda-personalize .agenda-personalize-actions > button').first().click()
    await expect(page.locator('.agenda-personalize .agenda-personalize-group.is-checked')).toHaveCount(0)
    // Click Cancel should hide dialog
    await page.locator('.agenda-personalize .agenda-personalize-actions > button').nth(1).click()
    await expect(page.locator('.agenda-personalize')).not.toBeVisible()
  })

  // -> PICK SESSIONS

  test('agenda individual sessions picker', async ({ page }) => {
    const pickBtnLocator = page.locator('#agenda-quickaccess-picksessions-btn')
    const applyBtnLocator = page.locator('#agenda-quickaccess-applypick-btn')
    const modifyBtnLocator = page.locator('#agenda-quickaccess-modifypick-btn')
    const discardBtnLocator = page.locator('#agenda-quickaccess-discardpick-btn')
    const checkboxesLocator = page.locator('.agenda .agenda-table-cell-check > .n-checkbox')
    const checkedboxesLocator = page.locator('.agenda .agenda-table-cell-check > .n-checkbox.n-checkbox--checked')
    const uncheckedboxesLocator = page.locator('.agenda .agenda-table-cell-check > .n-checkbox:not(.n-checkbox--checked)')
    const eventsLocator = page.locator('.agenda .agenda-table-display-event')

    // Enter pick mode
    await expect(pickBtnLocator).toBeVisible()
    await pickBtnLocator.click()
    await expect(pickBtnLocator).not.toBeVisible()
    await expect(applyBtnLocator).toBeVisible()
    await expect(discardBtnLocator).toBeVisible()

    // Pick 10 random sessions
    await expect(checkboxesLocator).toHaveCount(meetingData.schedule.length)
    const randSessionsRange = _.take(_.shuffle(_.range(meetingData.schedule.length)), 10)
    for (const idx of randSessionsRange) {
      await checkboxesLocator.nth(idx).click()
    }
    await applyBtnLocator.click()
    await expect(applyBtnLocator).not.toBeVisible()
    await expect(modifyBtnLocator).toBeVisible()
    await expect(discardBtnLocator).toBeVisible()
    await expect(eventsLocator).toHaveCount(10)

    // Change selection (keep existing 5 + add 5 new ones)
    await modifyBtnLocator.click()
    await expect(modifyBtnLocator).not.toBeVisible()
    await expect(applyBtnLocator).toBeVisible()
    await expect(discardBtnLocator).toBeVisible()
    await expect(checkboxesLocator).toHaveCount(meetingData.schedule.length)
    await expect(checkedboxesLocator).toHaveCount(10)
    for (let idx = 0; idx < 5; idx++) {
      await checkedboxesLocator.nth(idx).click()
    }
    const uncheckedCount = await uncheckedboxesLocator.count()
    const uncheckedRandRange = _.take(_.shuffle(_.range(uncheckedCount)), 5)
    for (const idx of uncheckedRandRange) {
      await uncheckedboxesLocator.nth(idx).click()
    }
    await applyBtnLocator.click()
    await expect(eventsLocator).toHaveCount(10)

    // Discard should clear selection
    await discardBtnLocator.click()
    await expect(discardBtnLocator).not.toBeVisible()
    await expect(modifyBtnLocator).not.toBeVisible()
    await expect(pickBtnLocator).toBeVisible()
    await expect(page.locator('.agenda .agenda-table-cell-check')).toHaveCount(0)
    await expect(eventsLocator).toHaveCount(meetingData.schedule.length)
  })

  // -> CALENDAR VIEW

  test('agenda calendar view', async ({ page }) => {
    const diagHeaderLocator = page.locator('.agenda-calendar .agenda-calendar-actions')
    const tzButtonsLocator = diagHeaderLocator.locator('.n-button-group button')
    const calHintLocator = page.locator('.agenda-calendar-hint > div')

    // Open dialog
    await page.locator('#agenda-quickaccess-calview-btn').click()
    await expect(page.locator('.agenda-calendar')).toBeVisible()
    // Check header elements
    await expect(page.locator('.agenda-calendar .n-drawer-header__main > span')).toContainText('Calendar View')
    await expect(diagHeaderLocator.locator('> button')).toHaveCount(2)
    await expect(diagHeaderLocator.locator('> button').first()).toContainText('Filter')
    await expect(diagHeaderLocator.locator('> button').last()).toContainText('Close')
    // -----------------------
    // Check timezone controls
    // -----------------------
    await expect(diagHeaderLocator.locator('small').first()).toContainText('Timezone')
    // Switch to local timezone
    await tzButtonsLocator.nth(1).click()
    await expect(tzButtonsLocator.nth(1)).toHaveClass(/n-button--primary-type/)
    await expect(tzButtonsLocator.first()).not.toHaveClass(/n-button--primary-type/)
    const localDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone(BROWSER_TIMEZONE)
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(localDateTime)
    // Switch to UTC
    await tzButtonsLocator.last().click()
    await expect(tzButtonsLocator.last()).toHaveClass(/n-button--primary-type/)
    await expect(tzButtonsLocator.nth(1)).not.toHaveClass(/n-button--primary-type/)
    const utcDateTime = DateTime.fromISO(meetingData.meeting.updated)
      .setZone('utc')
      .setLocale(BROWSER_LOCALE)
      .toFormat('DD \'at\' tt ZZZZ')
    await expect(page.locator('.agenda h6').first()).toContainText(utcDateTime)
    // Switch back to meeting timezone
    await tzButtonsLocator.first().click()
    await expect(tzButtonsLocator.first()).toHaveClass(/n-button--primary-type/)
    // ----------------------
    // Check Filters Shortcut
    // ----------------------
    await diagHeaderLocator.locator('> button').first().click()
    // Only check whether the dialog is shown. We already tested the dialog earlier.
    await expect(page.locator('.agenda-personalize')).toBeVisible()
    // Close dialog
    await page.locator('.agenda-personalize .agenda-personalize-actions > button').nth(1).click()
    await expect(page.locator('.agenda-personalize')).not.toBeVisible()
    // ------------------
    // Check Event Dialog
    // ------------------
    const firstEvent = meetingData.schedule[0]
    const materialsUrl = (new URL(firstEvent.agenda.url)).pathname
    const materialsInfo = {
      url: firstEvent.agenda.url,
      slides: [],
      minutes: null
    }
    await page.route(`**/api/meeting/session/${firstEvent.sessionId}/materials`, route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(materialsInfo)
      })
    })
    await page.route(materialsUrl, route => {
      route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: 'The internet is a series of tubes.'
      })
    })
    await page.locator('.agenda-calendar .fc-event').first().click()
    // Only check whether the dialog is shown. We already tested the dialog earlier.
    await expect(page.locator('.agenda-eventdetails')).toBeVisible()
    // Close dialog
    await page.locator('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
    // -----------
    // Event Hover
    // -----------
    // First Event
    let eventStart = DateTime.fromISO(firstEvent.startDateTime)
    let eventEnd = eventStart.plus({ seconds: firstEvent.duration })
    let hoverDateTime = `${eventStart.toFormat('DDDD')} from ${eventStart.toFormat('T')} to ${eventEnd.toFormat('T')}`
    await page.locator('.agenda-calendar .fc-event').first().hover()
    await expect(calHintLocator.first()).toContainText(firstEvent.name)
    await expect(calHintLocator.nth(1)).toContainText(firstEvent.location.short)
    await expect(calHintLocator.nth(1)).toContainText(firstEvent.room)
    await expect(calHintLocator.nth(2)).toContainText(hoverDateTime)
    // Second Event
    const secondEvent = meetingData.schedule[1]
    eventStart = DateTime.fromISO(secondEvent.startDateTime)
    eventEnd = eventStart.plus({ seconds: secondEvent.duration })
    hoverDateTime = `${eventStart.toFormat('DDDD')} from ${eventStart.toFormat('T')} to ${eventEnd.toFormat('T')}`
    await page.locator('.agenda-calendar .fc-event').nth(1).hover()
    await expect(calHintLocator.first()).toContainText(secondEvent.name)
    await expect(calHintLocator.nth(1)).toContainText(secondEvent.location.short)
    await expect(calHintLocator.nth(1)).toContainText(secondEvent.room)
    await expect(calHintLocator.nth(2)).toContainText(hoverDateTime)
    // ------------------------------
    // Click Close should hide dialog
    // ------------------------------
    await diagHeaderLocator.locator('button').last().click()
    await expect(page.locator('.agenda-calendar')).not.toBeVisible()
  })

  // -> SETTINGS DIALOG

  test('agenda settings', async ({ page, browserName }) => {
    // Open dialog
    await page.locator('.meeting-nav + button').click()
    await expect(page.locator('.agenda-settings')).toBeVisible()
    // Check header elements
    await expect(page.locator('.agenda-settings .n-drawer-header__main > span')).toContainText('Agenda Settings')
    await expect(page.locator('.agenda-settings .agenda-settings-actions > button')).toHaveCount(2)
    await expect(page.locator('.agenda-settings .agenda-settings-actions > button').first()).toBeVisible()
    await expect(page.locator('.agenda-settings .agenda-settings-actions > button').last()).toContainText('Close')

    // -------------------
    // Check export config
    // -------------------
    await page.locator('.agenda-settings .agenda-settings-actions > button').first().click()
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('.n-dropdown-option:has-text("Export Configuration")').click()
    ])

    const downloadPath = await download.path()
    try {
      const downloadedConfig = JSON.parse(await fs.readFile(downloadPath, 'utf8'))
      const expectedConfig = JSON.parse(await fs.readFile('data/agenda-settings.json', 'utf8'))
      await expect(downloadedConfig).toEqual(expectedConfig)
    } catch (err) {
      expect(err).toBeUndefined()
    }

    // -------------------
    // Check import config
    // -------------------
    await test.step('import config', async () => {
      if (browserName === 'chromium') {
        // Chromium use the experimental file selector API so this test won't work, skipping...
        // See https://github.com/microsoft/playwright/issues/8850')
        return
      }
      await page.locator('.agenda-settings .agenda-settings-actions > button').first().click()
      const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser'),
        page.locator('.n-dropdown-option:has-text("Import Configuration")').click()
      ])
      await fileChooser.setFiles('data/agenda-settings.json')
      await expect(page.locator('.n-message')).toContainText('Config imported successfully')
    })

    // -----------------------
    // Check timezone controls
    // -----------------------
    const tzMeetingBtnLocator = page.locator('#agenda-settings-tz-btn button:first-child')
    const tzLocalBtnLocator = page.locator('#agenda-settings-tz-btn button:nth-child(2)')
    const tzUtcBtnLocator = page.locator('#agenda-settings-tz-btn button:last-child')
    await expect(page.locator('.agenda-settings-content > .n-divider').first()).toContainText('Timezone')
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
    // Switch back to meeting timezone
    await tzMeetingBtnLocator.click()
    await expect(tzMeetingBtnLocator).toHaveClass(/n-button--primary-type/)
    await expect(page.locator('#agenda-settings-tz-ddn')).toContainText('Tokyo')

    // ----------------------
    // Check display controls
    // ----------------------
    await expect(page.locator('.agenda-settings-content > .n-divider').nth(1)).toContainText('Display')
    // -> Test Current Meeting Info Note toggle
    const infonoteSwitchLocator = page.locator('#agenda-settings-tgl-infonote div[role=switch]')
    await infonoteSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-infonote')).not.toBeVisible()
    await infonoteSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-infonote')).toBeVisible()
    // -> Test Event Icons toggle
    const eventiconsSwitchLocator = page.locator('#agenda-settings-tgl-eventicons div[role=switch]')
    await eventiconsSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-event-icon')).toHaveCount(0)
    await eventiconsSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-event-icon')).not.toHaveCount(0)
    // -> Test Floor Indicators toggle
    const floorindSwitchLocator = page.locator('#agenda-settings-tgl-floorind div[role=switch]')
    await floorindSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-table-cell-room > span.badge')).toHaveCount(0)
    await floorindSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-table-cell-room > span.badge')).not.toHaveCount(0)
    // -> Test Group Area Indicators toggle
    const groupindSwitchLocator = page.locator('#agenda-settings-tgl-groupind div[role=switch]')
    await groupindSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-table-cell-group > span.badge')).toHaveCount(0)
    await groupindSwitchLocator.click()
    await expect(page.locator('.agenda .agenda-table-cell-group > span.badge')).not.toHaveCount(0)
    // -> Test Bolder Text toggle
    const boldertxtSwitchLocator = page.locator('#agenda-settings-tgl-boldertxt div[role=switch]')
    await boldertxtSwitchLocator.click()
    await expect(page.locator('.agenda')).toHaveClass(/bolder-text/)
    await boldertxtSwitchLocator.click()
    await expect(page.locator('.agenda')).not.toHaveClass(/bolder-text/)

    // ----------------------------
    // Check calendar view controls
    // ----------------------------
    await expect(page.locator('.agenda-settings-content > .n-divider').nth(2)).toContainText('Calendar View')
    // TODO: calendar view checks
    // ----------------------------
    // Check calendar view controls
    // ----------------------------
    await expect(page.locator('.agenda-settings-content > .n-divider').nth(3)).toContainText('Custom Colors / Tags')
    // ------------------------------
    // Click Close should hide dialog
    // ------------------------------
    await page.locator('.agenda-settings .agenda-settings-actions > button').last().click()
    await expect(page.locator('.agenda-settings')).not.toBeVisible()
  })

  // -> ADD TO CALENDAR

  test('agenda add to calendar', async ({ page }) => {
    await expect(page.locator('#agenda-quickaccess-addtocal-btn')).toContainText('Add to your calendar')
    await page.locator('#agenda-quickaccess-addtocal-btn').click()
    const ddnLocator = page.locator('.n-dropdown-menu > .n-dropdown-option')
    await expect(ddnLocator).toHaveCount(2)
    await expect(ddnLocator.first()).toContainText('Subscribe')
    await expect(ddnLocator.last()).toContainText('Download')

    // Intercept Download ICS Call
    await page.route(`**/meeting/${meetingData.meeting.number}/agenda.ics`, route => {
      route.fulfill({
        status: 200,
        contentType: 'text/calendar',
        headers: {
          'Content-disposition': 'attachment; filename=agenda.ics'
        },
        body: 'test'
      })
    })

    // Cannot test if webcam link works because external app handling not supported:
    // See https://github.com/microsoft/playwright/issues/11014

    // Test Download ICS
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      ddnLocator.nth(1).click()
    ])
    const downloadPath = await download.path()
    try {
      const testIcs = await fs.readFile(downloadPath, 'utf8')
      await expect(testIcs).toEqual('test')
    } catch (err) {
      expect(err).toBeUndefined()
    }
  })

  // -> JUMP TO DAY

  test('agenda jump to specific days', async ({ page }) => {
    // -> Separator label
    await expect(page.locator('div[role=separator]:above(.agenda .agenda-quickaccess-jumpto)').first()).toContainText('Jump to...')

    // -> Check nav items
    const navItemLocator = page.locator('.agenda .agenda-quickaccess-jumpto > .nav-item')
    await expect(navItemLocator).toHaveCount(7)
    for (let idx = 0; idx < 7; idx++) {
      const localDateTime = DateTime.fromISO(meetingData.meeting.startDate)
        .setZone(BROWSER_TIMEZONE)
        .setLocale(BROWSER_LOCALE)
        .plus({ days: idx })
        .toLocaleString(DateTime.DATE_HUGE)
      await expect(navItemLocator.nth(idx)).toContainText(localDateTime)
    }

    // -> Jump to specific days
    for (const idx of [6, 1, 5, 2, 4, 0, 3]) {
      await navItemLocator.nth(idx).locator('a').click()
      await setTimeout(1500)
      await expect(await isIntersectingViewport(page, `.agenda-table-display-day >> nth=${idx}`)).toBeTruthy()
    }
  })
})
