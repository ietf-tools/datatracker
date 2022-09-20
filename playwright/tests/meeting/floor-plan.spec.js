const { test, expect } = require('@playwright/test')
const { faker } = require('@faker-js/faker')
const seedrandom = require('seedrandom')
const meetingGenerator = require('../../helpers/meeting.js')
const viewports = require('../../helpers/viewports')
const { setTimeout } = require('timers/promises')

const TEST_SEED = 123

// Set randomness seed
seedrandom(TEST_SEED.toString(), { global: true })
faker.seed(TEST_SEED)

// ====================================================================
// FLOOR-PLAN-NEUE | All Viewports
// ====================================================================

test.describe('floor-plan', () => {
  let meetingData

  test.beforeAll(async () => {
    // Generate meeting data (without schedule data)
    meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'past', skipSchedule: true })
  })

  for (const vp of ['desktop', 'smallDesktop', 'tablet', 'mobile']) {
    test(vp, async ({ page }) => {
      // Intercept Meeting Data API
      await page.route(`**/api/meeting/${meetingData.meeting.number}/agenda-data`, route => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(meetingData)
        })
      })

      await page.setViewportSize({
        width: viewports[vp][0],
        height: viewports[vp][1]
      })

      // Visit floor plan page and await Meeting Data API call to complete
      await Promise.all([
        page.waitForResponse(`**/api/meeting/${meetingData.meeting.number}/agenda-data`),
        page.goto(`/meeting/${meetingData.meeting.number}/floor-plan-neue`)
      ])

      // Wait for page to be ready
      await page.locator('.floorplan h1').waitFor({ state: 'visible' })
      await setTimeout(500)

      // -> HEADER

      await test.step(`has IETF ${meetingData.meeting.number} title`, async () => {
        await expect(page.locator('.floorplan h1').first()).toContainText(`IETF ${meetingData.meeting.number} Floor Plan`)
      })
      await test.step('has meeting city subtitle', async () => {
        await expect(page.locator('.floorplan h4').first()).toContainText(meetingData.meeting.city)
      })
      await test.step('has meeting date subtitle', async () => {
        await expect(page.locator('.floorplan h4').first()).toContainText(/[a-zA-Z] [0-9]{1,2} - ([a-zA-Z]+ )?[0-9]{1,2}, [0-9]{4}/i)
      })

      // -> NAV

      await test.step('has the correct navigation items', async () => {
        const navItemsLocator = page.locator('.floorplan .meeting-nav > li')
        await expect(navItemsLocator).toHaveCount(3)
        await expect(navItemsLocator.first()).toContainText('Agenda')
        await expect(navItemsLocator.nth(1)).toContainText('Floor plan')
        await expect(navItemsLocator.last()).toContainText('Plaintext')
      })

      // -> FLOORS

      await test.step('can switch between floors', async () => {
        const floorsLocator = page.locator('.floorplan .floorplan-floors > .nav-link')
        const floorImageLocator = page.locator('.floorplan .floorplan-plan > img')

        await expect(floorsLocator).toHaveCount(meetingData.floors.length)
        for (let idx = 0; idx < meetingData.floors.length; idx++) {
          await expect(floorsLocator.nth(idx)).toContainText(meetingData.floors[idx].name)
          await floorsLocator.nth(idx).click()
          await expect(floorsLocator.nth(idx)).toHaveClass(/active/)
          await expect(page.locator('.floorplan .floorplan-floors > .nav-link:not(.active)')).toHaveCount(meetingData.floors.length - 1)
          // Wait for image to load + verify
          await expect(floorImageLocator).toBeVisible()
          await setTimeout(100)
          await expect(await floorImageLocator.evaluate(node => node.naturalWidth)).toBeGreaterThan(1)
        }
      })

      // -> ROOMS

      await test.step('can select rooms', async () => {
        const roomsLocator = page.locator('.floorplan .floorplan-rooms > .list-group-item')
        const floorImageLocator = page.locator('.floorplan .floorplan-plan > img')
        const pinLocator = page.locator('.floorplan .floorplan-plan-pin')
        const floor = meetingData.floors[0]
        await page.locator('.floorplan .floorplan-floors > .nav-link').first().click()
        await expect(roomsLocator).toHaveCount(floor.rooms.length)
        for (let idx = 0; idx < floor.rooms.length; idx++) {
          // Room List
          const room = floor.rooms[idx]
          await expect(roomsLocator.nth(idx).locator('strong')).toContainText(room.name)
          await expect(roomsLocator.nth(idx).locator('strong + small')).toContainText(room.functionalName)
          await expect(roomsLocator.nth(idx).locator('.badge')).toContainText(floor.short)
          await roomsLocator.nth(idx).click()
          await expect(roomsLocator.nth(idx)).toHaveClass(/active/)
          await expect(page.locator('.floorplan .floorplan-rooms > .list-group-item:not(.active)')).toHaveCount(floor.rooms.length - 1)
          // URL query segment
          await expect(page.url()).toMatch(`room=${room.slug}`)
          // Pin Drop
          const planxRatio = (await floorImageLocator.evaluate(node => node.width)) / floor.width
          const planyRatio = (await floorImageLocator.evaluate(node => node.height)) / floor.height
          await expect(pinLocator).toBeVisible()
          // eslint-disable-next-line no-useless-escape, quotes
          const pinMarginLeft = await page.evaluate(`parseInt(window.getComputedStyle(document.querySelector('.floorplan .floorplan-plan-pin')).getPropertyValue('margin-left').match(/\\d+/))`)
          const xPos = Math.round((room.left + (room.right - room.left) / 2) * planxRatio) - 25 + pinMarginLeft
          const yPos = Math.round((room.top + (room.bottom - room.top) / 2) * planyRatio) - 40
          const offsetLeft = await pinLocator.evaluate(node => node.offsetLeft)
          const offsetTop = await pinLocator.evaluate(node => node.offsetTop)
          expect(offsetLeft).toBe(xPos)
          expect(offsetTop).toBe(yPos)
        }
      })
    })
  }
})
