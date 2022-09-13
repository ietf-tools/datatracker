import { DateTime } from 'luxon'
import path from 'path'
import { find, first, isEqual, times } from 'lodash-es'
import { faker } from '@faker-js/faker'
import slugify from 'slugify'
import meetingGenerator from '../../generators/meeting'

const xslugify = (str) => slugify(str.replace('/', '-'), { lower: true, strict: true })

const TEST_SEED = 123

const viewports = {
  desktop: [1536, 960],
  smallDesktop: [1280, 800],
  tablet: [768, 1024],
  mobile: [360, 760]
}

// Set randomness seed
faker.seed(TEST_SEED)

/**
 * Inject meeting info json into the page
 * 
 * @param {*} win Window Object
 * @param {*} meetingNumber Meeting Number
 */
function injectMeetingData (win, meetingNumber) {
  const meetingDataScript = win.document.createElement('script')
  meetingDataScript.id = 'meeting-data'
  meetingDataScript.type = 'application/json'
  meetingDataScript.innerHTML = `{"meetingNumber": "${meetingNumber}"}`
  win.document.querySelector('head').appendChild(meetingDataScript)
}

/**
 * Format URL by replacing inline variables
 * 
 * @param {String} url Raw URL
 * @param {Object} session Session Object
 * @param {String} meetingNumber Meeting Number
 * @returns Formatted URL
 */
function formatLinkUrl (url, session, meetingNumber) {
  return url ? url.replace('{meeting.number}', meetingNumber)
    .replace('{group.acronym}', session.groupAcronym)
    .replace('{short}', session.short)
    .replace('{order_number}', session.orderInMeeting) : url
}

/**
 * Find the first URL in text matching a conference domain
 * 
 * @param {String} txt Raw Text
 * @returns First URL found
 */
function findFirstConferenceUrl (txt) {
  try {
    const fUrl = txt.match(urlRe)
    if (fUrl && fUrl[0].length > 0) {
      const pUrl = new URL(fUrl[0])
      if (conferenceDomains.some(d => pUrl.hostname.endsWith(d))) {
        return fUrl[0]
      }
    }
  } catch (err) { }
  return null
}

// ====================================================================
// AGENDA-NEUE (past meeting) | DESKTOP viewport
// ====================================================================

describe('meeting -> agenda-neue [past, desktop]', {
    viewportWidth: viewports.desktop[0],
    viewportHeight: viewports.desktop[1]
  }, () => {
  let meetingData = null

  before(() => {
    // Set clock to 2022-02-01 (month is 0-indexed)
    cy.clock(new Date(2022, 1, 1))

    // Generate meeting data
    meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'past' })

    // Intercept Meeting Data API
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')

    // Visit agenda page
    cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
      onBeforeLoad: (win) => { injectMeetingData(win, meetingData.meeting.number) }
    })
    cy.wait('@getMeetingData')

    // Fix scroll behavior
    // See https://github.com/cypress-io/cypress/issues/3200
    cy.document().then(document => {
      const htmlElement = document.querySelector('html')
      if (htmlElement) {
        htmlElement.style.scrollBehavior = 'inherit'
      }
    })
  })

  // -> HEADER

  it(`has IETF 123 title`, () => {
    cy.get('.agenda h1').first().contains(`IETF ${meetingData.meeting.number} Meeting Agenda`)
    
    // Take a snapshot for visual diffing
    cy.percySnapshot('meeting -> agenda-neue [past, desktop]', { widths: [viewports.desktop[0]] })
  })
  it(`has meeting city subtitle`, () => {
    cy.get('.agenda h4').first().contains(meetingData.meeting.city)
  })
  it(`has meeting date subtitle`, () => {
    cy.get('.agenda h4').first().contains(/[a-zA-Z] [0-9]{1,2} - ([a-zA-Z]+ )?[0-9]{1,2}, [0-9]{4}/i)
  })
  it(`has meeting last updated datetime`, () => {
    const updatedDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone(meetingData.meeting.timezone).toFormat(`DD 'at' tt ZZZZ`)
    cy.get('.agenda h6').first().contains(updatedDateTime)
  })

  // -> NAV

  it(`has the correct navigation items`, () => {
    cy.get('.agenda .meeting-nav > li').should('have.length', 3)
    cy.get('.agenda .meeting-nav > li').first().contains('Agenda')
    cy.get('.agenda .meeting-nav > li').eq(1).contains('Floor plan')
    cy.get('.agenda .meeting-nav > li').last().contains('Plaintext')
  })
  it(`has the Settings button on the right`, () => {
    cy.get('.agenda .meeting-nav').next('button').should('exist')
      .and('include.text', 'Settings')
    cy.window().then(win => {
      cy.get('.agenda .meeting-nav').next('button').then(el => {
        const btnBounds = el[0].getBoundingClientRect()
        expect(btnBounds.x).to.be.greaterThan(win.innerWidth - btnBounds.width - 100)
      })
    })
  })

  // -> SCHEDULE LIST -> Header

  it(`has schedule list title`, () => {
    cy.get('.agenda h2').first().contains(`Schedule`)
  })
  it(`has info note`, () => {
    cy.get('.agenda .agenda-infonote').should('exist').and('include.text', meetingData.meeting.infoNote)
  })
  it(`info note can be dismissed / reopened`, () => {
    cy.get('.agenda .agenda-infonote > button').click()
    cy.get('.agenda .agenda-infonote').should('not.exist')
    cy.get('.agenda h2').first().next('button').should('exist')
    cy.get('.agenda h2').first().next('button').click()
    cy.get('.agenda .agenda-infonote').should('exist')
    cy.get('.agenda h2').first().next('button').should('not.exist')
  })
  it(`has timezone selector`, () => {
    cy.get('.agenda .agenda-tz-selector').should('exist')
    cy.get('.agenda .agenda-tz-selector').prev().should('exist').and('include.text', 'Timezone:').prev('.bi').should('exist')
    cy.get('.agenda .agenda-tz-selector > button').should('have.length', 3)
    cy.get('.agenda .agenda-tz-selector > button').first().contains('Meeting')
    cy.get('.agenda .agenda-tz-selector > button').eq(1).contains('Local')
    cy.get('.agenda .agenda-tz-selector > button').last().contains('UTC')
    cy.get('.agenda .agenda-timezone-ddn').should('exist')
  })
  it('can change timezone', () => {
    // Switch to local timezone
    cy.get('.agenda .agenda-tz-selector > button:nth-child(2)').click().should('have.class', 'n-button--primary-type')
    cy.get('.agenda .agenda-tz-selector > button:first-child').pause().should('not.have.class', 'n-button--primary-type')
    const localDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('local').toFormat(`DD 'at' tt ZZZZ`)
    cy.get('.agenda h6').first().contains(localDateTime)
    // Switch to UTC
    cy.get('.agenda .agenda-tz-selector > button:last-child').click().should('have.class', 'n-button--primary-type')
    cy.get('.agenda .agenda-tz-selector > button:nth-child(2)').should('not.have.class', 'n-button--primary-type')
    const utcDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('utc').toFormat(`DD 'at' tt ZZZZ`)
    cy.get('.agenda h6').first().contains(utcDateTime)
    cy.get('.agenda .agenda-timezone-ddn').contains('UTC')
    // Switch back to meeting timezone
    cy.get('.agenda .agenda-tz-selector > button:first-child').click().should('have.class', 'n-button--primary-type')
    cy.get('.agenda .agenda-timezone-ddn').contains('Tokyo')
  })

  // -> SCHEDULE LIST -> Table Headers

  it('has schedule list table headers', () => {
    // Table Headers
    cy.get('.agenda-table-head-time').should('exist').and('contain', 'Time')
    cy.get('.agenda-table-head-location').should('exist').and('contain', 'Location')
    cy.get('.agenda-table-head-event').should('exist').and('contain', 'Event')
    // Day Headers
    cy.get('.agenda-table-display-day').should('have.length', 7).each((el, idx) => {
      const localDateTime = DateTime.fromISO(meetingData.meeting.startDate).setZone('local').plus({ days: idx }).toLocaleString(DateTime.DATE_HUGE)
      cy.wrap(el).should('contain', localDateTime)
    })
  })

  // -> SCHEDULE LIST -> Table Events

  it('has schedule list table events (can take a while)', {
    // This test is VERY memory-intensive, so disable DOM snapshots to prevent browser crash
    numTestsKeptInMemory: 0
  }, () => {
    let isFirstSession = true
    cy.get('tr.agenda-table-display-event').should('have.length', meetingData.schedule.length).each((el, idx) => {
      // Apply small arbitrary wait every 10 rows to prevent the test UI from freezing
      if (idx % 10 === 0) {
        // eslint-disable-next-line cypress/no-unnecessary-waiting
        cy.wait(10, { log: false })
      }
      const event = meetingData.schedule[idx]
      const eventStart = DateTime.fromISO(event.startDateTime)
      const eventEnd = eventStart.plus({ seconds: event.duration })
      const eventTimeSlot = `${eventStart.toFormat('HH:mm')} - ${eventEnd.toFormat('HH:mm')}`
      // --------
      // Location
      // --------
      if (event.location?.short) {
        // Has floor badge
        cy.wrap(el).find('.agenda-table-cell-room > a').should('contain', event.room)
          .and('have.attr', 'href', `/meeting/` + meetingData.meeting.number + `/floor-plan-neue?room=` + xslugify(event.room))
          .prev('.badge').should('contain', event.location.short)
      } else {
        // No floor badge
        cy.wrap(el).find('.agenda-table-cell-room > span:not(.badge)').should('contain', event.room)
          .prev('.badge').should('not.exist')
      }
      // ---------------------------------------------------
      // Type-specific timeslot / group / name columns tests
      // ---------------------------------------------------
      if (event.type === 'regular') {
        // First session should have header row above it
        if (isFirstSession) {
          cy.wrap(el).prev('tr.agenda-table-display-session-head').should('exist')
            .find('.agenda-table-cell-ts').should('contain', eventTimeSlot)
            .next('.agenda-table-cell-name').should('contain', `${DateTime.fromISO(event.startDateTime).toFormat('cccc')} ${event.name}`)
        }
        // Timeslot
        cy.wrap(el).find('.agenda-table-cell-ts').should('contain', '—')
        // Group Acronym + Parent
        cy.wrap(el).find('.agenda-table-cell-group > .badge').should('contain', event.groupParent.acronym)
          .next('a').should('contain', event.acronym).and('have.attr', 'href', `/group/` + event.acronym + `/about/`)
        // Group Name
        cy.wrap(el).find('.agenda-table-cell-name').should('contain', event.groupName)
        isFirstSession = false
      } else {
        // Timeslot
        cy.wrap(el).find('.agenda-table-cell-ts').should('contain', eventTimeSlot)
        // Event Name
        cy.wrap(el).find('.agenda-table-cell-name').should('contain', event.name)
        isFirstSession = true
      }
      // -----------
      // Name column
      // -----------
      // Event icon
      if (['break', 'plenary'].includes(event.type) || (event.type === 'other' && ['office hours', 'hackathon'].some(s => event.name.toLowerCase().indexOf(s) >= 0))) {
        cy.wrap(el).find('.agenda-table-cell-name > i.bi').should('exist')
      }
      // Name link
      if (event.flags.agenda) {
        cy.wrap(el).find('.agenda-table-cell-name > a').should('have.attr', 'href', event.agenda.url)
      }
      // BoF badge
      if (event.isBoF) {
        cy.wrap(el).find('.agenda-table-cell-name > .badge').should('contain', 'BoF')
      }
      // Note
      if (event.note) {
        cy.wrap(el).find('.agenda-table-cell-name > .agenda-table-note').should('exist')
          .find('i.bi').should('exist')
          .next('span').should('contain', event.note)
      }
      // -----------------------
      // Buttons / Status Column
      // -----------------------
      switch (event.status) {
        // Cancelled
        case 'canceled': {
          cy.wrap(el).find('.agenda-table-cell-links > .badge.is-cancelled').should('contain', 'Cancelled')
          break
        }
        // Rescheduled
        case 'resched': {
          cy.wrap(el).find('.agenda-table-cell-links > .badge.is-rescheduled').should('contain', 'Rescheduled')
          break
        }
        // Scheduled
        case 'sched': {
          if (event.flags.showAgenda || ['regular', 'plenary'].includes(event.type)) {
            cy.wrap(el).find('.agenda-table-cell-links > .agenda-table-cell-links-buttons').as('eventbuttons')
            if (event.flags.agenda) {
              // Show meeting materials button
              cy.get('@eventbuttons').find('i.bi.bi-collection').should('exist')
              // ZIP materials button
              cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-tar`).should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.tgz`)
                .children('i.bi').should('exist')
              // PDF materials button
              cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-pdf`).should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.pdf`)
                .children('i.bi').should('exist')
            } else if (event.type === 'regular') {
              // No meeting materials yet warning badge
              cy.get('@eventbuttons').find('.no-meeting-materials').should('exist')
            }
            // Notepad button
            const hedgeDocLink = `https://notes.ietf.org/notes-ietf-${meetingData.meeting.number}-${event.type === 'plenary' ? 'plenary' : event.acronym}`
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-note`).should('have.attr', 'href', hedgeDocLink)
              .children('i.bi').should('exist')
            // Chat logs
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-logs`).should('have.attr', 'href', event.links.chatArchive)
              .children('i.bi').should('exist')
            // Recordings
            for (const rec of event.links.recordings) {
              if (rec.url.indexOf('audio') > 0) {
                // -> Audio
                cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-audio-${rec.id}`).should('have.attr', 'href', rec.url)
                  .children('i.bi').should('exist')
              } else if (rec.url.indexOf('youtu') > 0) {
                // -> Youtube
                cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-youtube-${rec.id}`).should('have.attr', 'href', rec.url)
                  .children('i.bi').should('exist')
              } else {
                // -> Others
                cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-video-${rec.id}`).should('have.attr', 'href', rec.url)
                  .children('i.bi').should('exist')
              }
            }
            // Video Stream
            if (event.links.videoStream) {
              const videoStreamLink = `https://www.meetecho.com/ietf${meetingData.meeting.number}/recordings#${event.acronym.toUpperCase()}`
              cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-rec`).should('have.attr', 'href', videoStreamLink)
                .children('i.bi').should('exist')
            }
          } else {
            cy.wrap(el).find('.agenda-table-cell-links > .agenda-table-cell-links-buttons').should('not.exist')
          }
          break
        }
      }
    })
  })

  // -> SCHEDULE LIST -> Search

  it('can search meetings', {
    // No need to keep DOM snapshots for this test
    numTestsKeptInMemory: 0
  }, () => {
    cy.get('.agenda-table > .agenda-table-search > button').click()
    cy.get('.agenda-search').should('exist').and('be.visible')
    const event = find(meetingData.schedule, s => s.type === 'regular')
    const eventWithNote = find(meetingData.schedule, s => s.note)
    // Search different terms
    const searchTerms = [
      'hack', // Should match hackathon events
      event.groupAcronym, // Match group name
      event.room.toLowerCase(), // Match room name
      eventWithNote.note.substring(0, 10).toLowerCase() // Match partial note
    ]
    for (const term of searchTerms) {
      cy.get('.agenda-search input[type=text]').clear().type(term)
      cy.get('.agenda-table .agenda-table-display-event').should('have.length.lessThan', meetingData.schedule.length)
      // Let the UI update before checking each displayed row
      // eslint-disable-next-line cypress/no-unnecessary-waiting
      cy.wait(1000, { log: false })
      cy.get('.agenda-table .agenda-table-display-event').each((el, idx) => {
        cy.wrap(el).contains(term, { matchCase: false })
      })
    }
    // Clear button
    cy.get('.agenda-search button').click()
    cy.get('.agenda-search input[type=text]').should('have.value', '')
    cy.get('.agenda-table .agenda-table-display-event').should('have.length', meetingData.schedule.length)
    // Invalid search
    cy.get('.agenda-search input[type=text]').type(faker.vehicle.vin())
    cy.get('.agenda-table .agenda-table-display-event').should('have.length', 0)
    cy.get('.agenda-table .agenda-table-display-noresult').should('exist').and('contain', 'No event matching your search query.')
    // Closing search should clear search
    cy.get('.agenda-table > .agenda-table-search > button').click()
    cy.get('.agenda-search').should('not.exist')
    cy.get('.agenda-table .agenda-table-display-event').should('have.length', meetingData.schedule.length)
  })

  // -> SCHEDULE LIST -> Show Meeting Materials dialog

  it('can show meeting materials dialog', () => {
    const event = find(meetingData.schedule, s => s.flags.showAgenda && s.flags.agenda)
    const eventStart = DateTime.fromISO(event.startDateTime)
    const eventEnd = eventStart.plus({ seconds: event.duration })
    // Intercept meeting materials request
    const materialsUrl = (new URL(event.agenda.url)).pathname
    const materialsInfo = {
      url: event.agenda.url,
      slides: times(5, idx => ({
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
    cy.intercept('GET', `/api/meeting/session/${event.sessionId}/materials`, { body: materialsInfo }).as('getMaterialsInfo')
    cy.intercept('GET', materialsUrl, { body: 'The internet is a series of tubes.' }).as('getMaterialsText')
    cy.intercept('GET', materialsInfo.minutes.url, { body: 'One does not simply walk into mordor.' }).as('getMaterialsMinutes')
    // Open dialog
    cy.get(`#agenda-rowid-${event.id}`).find(`#btn-lnk-${event.id}-mat`).click()
    cy.get('.agenda-eventdetails').should('exist').and('be.visible')
    cy.wait('@getMaterialsText')
    // Header
    cy.get('.agenda-eventdetails .n-card-header__main > .detail-header > .bi').should('exist')
      .next('span').should('contain', eventStart.toFormat('DDDD'))
    cy.get('.agenda-eventdetails .n-card-header__extra > .detail-header > .bi').should('exist')
      .next('strong').should('contain', `${eventStart.toFormat('T')} - ${eventEnd.toFormat('T')}`)
    cy.get('.agenda-eventdetails .detail-title > h6 > .bi').should('exist')
      .next('span').should('contain', event.name)
    cy.get('.agenda-eventdetails .detail-location > .bi').should('exist')
      .next('.badge').should('contain', event.location.short)
      .next('span').should('contain', event.room)
    // Navigation
    cy.get('.agenda-eventdetails .detail-nav > a').should('have.length', 3)
      .first().should('have.class', 'active')
      .nextAll().should('not.have.class', 'active')
    // Agenda Tab
    cy.get('.agenda-eventdetails .detail-text > iframe').should('have.attr', 'src', materialsUrl)
    // Slides Tab
    cy.get('.agenda-eventdetails .detail-nav > a').eq(1).click()
      .should('have.class', 'active')
      .siblings('a').should('not.have.class', 'active')
    cy.get('.agenda-eventdetails .detail-text > .list-group > .list-group-item').should('have.length', materialsInfo.slides.length).each((el, idx) => {
      cy.wrap(el).should('have.attr', 'href', materialsInfo.slides[idx].url)
        .children('.bi').should('have.class', `bi-filetype-${materialsInfo.slides[idx].ext}`)
        .next('span').should('contain', materialsInfo.slides[idx].title)
    })
    // Minutes Tab
    cy.get('.agenda-eventdetails .detail-nav > a').eq(2).click()
      .should('have.class', 'active')
      .prevAll('a').should('not.have.class', 'active')
    cy.wait('@getMaterialsMinutes')
    cy.get('.agenda-eventdetails .detail-text > iframe').should('have.attr', 'src', materialsInfo.minutes.url)
    // Footer Buttons
    const hedgeDocLink = `https://notes.ietf.org/notes-ietf-${meetingData.meeting.number}-${event.type === 'plenary' ? 'plenary' : event.acronym}`
    cy.get('.agenda-eventdetails .detail-action > a').should('have.length', 3)
      .first().should('contain', 'Download as tarball').should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.tgz`)
      .next().should('contain', 'Download as PDF').should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.pdf`)
      .next().should('contain', 'Notepad').should('have.attr', 'href', hedgeDocLink)
    // Clicking X should close the dialog
    cy.get('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
  })

  // -> SCHEDULE LIST -> Show Meeting Materials dialog (EMPTY VARIANT)

  it('can show meeting materials dialog (empty variant)', () => {
    const event = find(meetingData.schedule, s => s.flags.showAgenda && s.flags.agenda)
    // Intercept meeting materials request
    const materialsUrl = (new URL(event.agenda.url)).pathname
    const materialsInfo = {
      url: event.agenda.url,
      slides: [],
      minutes: null
    }
    cy.intercept('GET', `/api/meeting/session/${event.sessionId}/materials`, { body: materialsInfo }).as('getMaterialsInfo')
    cy.intercept('GET', materialsUrl, { body: 'The internet is a series of tubes.' }).as('getMaterialsText')
    // Open dialog
    cy.get(`#agenda-rowid-${event.id}`).find(`#btn-lnk-${event.id}-mat`).click()
    cy.get('.agenda-eventdetails').should('exist')
    cy.wait('@getMaterialsText')
    // Slides Tab
    cy.get('.agenda-eventdetails .detail-nav > a').eq(1).click()
    cy.get('.agenda-eventdetails .detail-text').should('contain', 'No slides submitted for this session.')
    // Minutes Tab
    cy.get('.agenda-eventdetails .detail-nav > a').eq(2).click()
    cy.get('.agenda-eventdetails .detail-text').should('contain', 'No minutes submitted for this session.')
    // Clicking X should close the dialog
    cy.get('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
  })

  // -> FILTER BY AREA/GROUP DIALOG

  it('can filter by area/group', {
    // This test has lot of UI element interactions and the UI can get slow with DOM snapshots, so disable it
    numTestsKeptInMemory: 0
  }, () => {
    // Open dialog
    cy.get('#agenda-quickaccess-filterbyareagroups-btn').should('exist').click()
    cy.get('.agenda-personalize').should('exist')
    // Check header elements
    cy.get('.agenda-personalize .n-drawer-header__main > span').contains('Filter Areas + Groups')
    cy.get('.agenda-personalize .agenda-personalize-actions > button').should('have.length', 3)
    cy.get('.agenda-personalize .agenda-personalize-actions > button').first().contains('Clear Selection')
    cy.get('.agenda-personalize .agenda-personalize-actions > button').eq(1).contains('Cancel')
    cy.get('.agenda-personalize .agenda-personalize-actions > button').last().contains('Apply')
    // Check categories
    cy.get('.agenda-personalize .agenda-personalize-category').should('have.length', meetingData.categories.length)
    // Check areas + groups
    cy.get('.agenda-personalize .agenda-personalize-category').each((el, idx) => {
      const cat = meetingData.categories[idx]
      cy.wrap(el).find('.agenda-personalize-area').should('have.length', cat.length)
        .each((areaEl, areaIdx) => {
          // Area Button
          const area = cat[areaIdx]
          cy.wrap(areaEl).find('.agenda-personalize-areamain').scrollIntoView()
          if (area.label) {
            cy.wrap(areaEl).find('.agenda-personalize-areamain > button').should('be.visible').contains(area.label)
          } else {
            cy.wrap(areaEl).find('.agenda-personalize-areamain > button').should('not.exist')
          }
          // Group Buttons
          cy.wrap(areaEl).find('.agenda-personalize-groups > button').should('have.length', area.children.length)
            .each((groupEl, groupIdx) => {
              const group = area.children[groupIdx]
              cy.wrap(groupEl).should('be.visible').contains(group.label)
              if (group.is_bof) {
                cy.wrap(groupEl).should('have.class', 'is-bof')
                cy.wrap(groupEl).find('.badge').should('be.visible').contains('BoF')
              }
            })
          // Test Area Selection
          if (area.label) {
            cy.wrap(areaEl).find('.agenda-personalize-areamain > button').click()
            cy.wrap(areaEl).find('.agenda-personalize-groups > button').should('have.class', 'is-checked')
            cy.wrap(areaEl).find('.agenda-personalize-areamain > button').click()
            cy.wrap(areaEl).find('.agenda-personalize-groups > button').should('not.have.class', 'is-checked')
          }
          // Test Group Selection
          cy.wrap(areaEl).find('.agenda-personalize-groups > button').any().click()
            .should('have.class', 'is-checked').click().should('not.have.class', 'is-checked')
        })
    })
    // Test multi-toggled_by button trigger
    cy.get(`.agenda-personalize .agenda-personalize-category:last .agenda-personalize-area:last .agenda-personalize-groups > button:contains('BoF')`).as('bofbtn')
    cy.get('@bofbtn').click()
    cy.get('.agenda-personalize .agenda-personalize-group:has(.badge)').should('have.class', 'is-checked')
    cy.get('@bofbtn').click()
    cy.get('.agenda-personalize .agenda-personalize-group:has(.badge)').should('not.have.class', 'is-checked')
    // Clicking all groups from area then area button should unselect all
    cy.get('.agenda-personalize .agenda-personalize-area:first .agenda-personalize-groups > button').click({ multiple: true })
    cy.get('.agenda-personalize .agenda-personalize-area:first .agenda-personalize-areamain > button').click()
    cy.get('.agenda-personalize .agenda-personalize-area:first .agenda-personalize-groups > button').should('not.have.class', 'is-checked')
    // Test Clear Selection
    cy.get('.agenda-personalize .agenda-personalize-group').any(10).click({ multiple: true })
    cy.get('.agenda-personalize .agenda-personalize-actions > button').first().click()
    cy.get('.agenda-personalize .agenda-personalize-group').should('not.have.class', 'is-checked')
    // Click Cancel should hide dialog
    cy.get('.agenda-personalize .agenda-personalize-actions > button').eq(1).click()
    cy.get('.agenda-personalize').should('not.exist')
  })

  // -> PICK SESSIONS

  it('can pick individual sessions', () => {
    // Enter pick mode
    cy.get('#agenda-quickaccess-picksessions-btn').should('be.visible').click().should('not.exist')
    cy.get('#agenda-quickaccess-applypick-btn').should('be.visible')
    cy.get('#agenda-quickaccess-discardpick-btn').should('be.visible')

    // Pick 10 random sessions
    cy.get('.agenda .agenda-table-cell-check > .n-checkbox').should('have.length', meetingData.schedule.length)
      .any(10).click({ multiple: true })
    cy.get('#agenda-quickaccess-applypick-btn').click().should('not.exist')
    cy.get('#agenda-quickaccess-modifypick-btn').should('be.visible')
    cy.get('#agenda-quickaccess-discardpick-btn').should('be.visible')
    cy.get('.agenda .agenda-table-display-event').should('have.length', 10)

    // Change selection (keep existing 5 + add 5 new ones)
    cy.get('#agenda-quickaccess-modifypick-btn').click().should('not.exist')
    cy.get('#agenda-quickaccess-applypick-btn').should('be.visible')
    cy.get('#agenda-quickaccess-discardpick-btn').should('be.visible')
    cy.get('.agenda .agenda-table-cell-check > .n-checkbox').should('have.length', meetingData.schedule.length)
      .filter('.n-checkbox--checked').should('have.length', 10)
      .take(5).click({ multiple: true })
    cy.get('.agenda .agenda-table-cell-check > .n-checkbox:not(.n-checkbox--checked)').any(5).click({ multiple: true })
    cy.get('#agenda-quickaccess-applypick-btn').click()
    cy.get('.agenda .agenda-table-display-event').should('have.length', 10)

    // Discard should clear selection
    cy.get('#agenda-quickaccess-discardpick-btn').click().should('not.exist')
    cy.get('#agenda-quickaccess-modifypick-btn').should('not.exist')
    cy.get('#agenda-quickaccess-picksessions-btn').should('be.visible')
    cy.get('.agenda .agenda-table-cell-check').should('not.exist')
    cy.get('.agenda .agenda-table-display-event').should('have.length', meetingData.schedule.length)
  })

  // -> CALENDAR VIEW

  it('can view calendar', () => {
    // Open dialog
    cy.get('#agenda-quickaccess-calview-btn').should('be.visible').click()
    cy.get('.agenda-calendar').should('exist').and('be.visible')
    // Check header elements
    cy.get('.agenda-calendar .n-drawer-header__main > span').contains('Calendar View')
    cy.get('.agenda-calendar .agenda-calendar-actions').as('diagheader')
    cy.get('@diagheader').children('button').should('have.length', 2)
    cy.get('@diagheader').children('button').first().should('include.text', 'Filter')
    cy.get('@diagheader').children('button').last().should('include.text', 'Close')
    // -----------------------
    // Check timezone controls
    // -----------------------
//     cy.get('@diagheader').children('small').first().should('contain', 'Timezone')
//     // Switch to local timezone
//     cy.get('@diagheader').children('.n-button-group').find('button').as('tzbuttons').eq(1).click().should('have.class', 'n-button--primary-type')
//       .prev('button').should('not.have.class', 'n-button--primary-type')
//     const localDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('local').toFormat(`DD 'at' tt ZZZZ`)
//     cy.get('.agenda h6').first().contains(localDateTime)
//     // Switch to UTC
//     cy.get('@tzbuttons').last().click().should('have.class', 'n-button--primary-type')
//       .prev('button').should('not.have.class', 'n-button--primary-type')
//     const utcDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('utc').toFormat(`DD 'at' tt ZZZZ`)
//     cy.get('.agenda h6').first().contains(utcDateTime)
//     // Switch back to meeting timezone
//     cy.get('@tzbuttons').first().click().should('have.class', 'n-button--primary-type')
    // ----------------------
    // Check Filters Shortcut
    // ----------------------
    cy.get('@diagheader').children('button').first().click()
    // Only check whether the dialog is shown. We already tested the dialog earlier.
    cy.get('.agenda-personalize').should('be.visible')
    // Close dialog
    cy.get('.agenda-personalize .agenda-personalize-actions > button').eq(1).click()
    cy.get('.agenda-personalize').should('not.exist')
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
    cy.intercept('GET', `/api/meeting/session/${firstEvent.sessionId}/materials`, { body: materialsInfo }).as('getMaterialsInfo')
    cy.intercept('GET', materialsUrl, { body: 'The internet is a series of tubes.' }).as('getMaterialsText')
    cy.get('.agenda-calendar .fc-event').first().click()
    // Only check whether the dialog is shown. We already tested the dialog earlier.
    cy.get('.agenda-eventdetails').should('be.visible')
    // Close dialog
    cy.get('.agenda-eventdetails .n-card-header__extra > .detail-header > button').click()
    // -----------
    // Event Hover
    // -----------
    // First Event
    let eventStart = DateTime.fromISO(firstEvent.startDateTime)
    let eventEnd = eventStart.plus({ seconds: firstEvent.duration })
    let hoverDateTime = `${eventStart.toFormat('DDDD')} from ${eventStart.toFormat('T')} to ${eventEnd.toFormat('T')}`
    cy.get('.agenda-calendar .fc-event').first().realHover({ position: 'center' })
    cy.get('.agenda-calendar-hint > div').first().should('include.text', firstEvent.name)
      .next().should('include.text', firstEvent.location.short).and('include.text', firstEvent.room)
      .next().should('include.text', hoverDateTime)
    // Second Event
    const secondEvent = meetingData.schedule[1]
    eventStart = DateTime.fromISO(secondEvent.startDateTime)
    eventEnd = eventStart.plus({ seconds: secondEvent.duration })
    hoverDateTime = `${eventStart.toFormat('DDDD')} from ${eventStart.toFormat('T')} to ${eventEnd.toFormat('T')}`
    cy.get('.agenda-calendar .fc-event').eq(1).realHover({ position: 'center' })
    cy.get('.agenda-calendar-hint > div').first().should('include.text', secondEvent.name)
      .next().should('include.text', secondEvent.location.short).and('include.text', secondEvent.room)
      .next().should('include.text', hoverDateTime)
    // ------------------------------
    // Click Close should hide dialog
    // ------------------------------
    cy.get('@diagheader').children('button').last().click()
    cy.get('.agenda-calendar').should('not.exist')
  })

  // -> SETTINGS DIALOG

  it('can change settings', () => {
    // Open dialog
    cy.get('.meeting-nav').next('button').should('exist').and('be.visible').click()
    cy.get('.agenda-settings').should('exist').and('be.visible')
    // Check header elements
    cy.get('.agenda-settings .n-drawer-header__main > span').contains('Agenda Settings')
    cy.get('.agenda-settings .agenda-settings-actions > button').should('have.length', 2)
    cy.get('.agenda-settings .agenda-settings-actions > button').first().should('be.visible')
    cy.get('.agenda-settings .agenda-settings-actions > button').last().contains('Close')
    // -------------------
    // Check export config
    // -------------------
    cy.get('.agenda-settings .agenda-settings-actions > button').first().click()
    cy.get('.n-dropdown-option:contains("Export Configuration")').should('exist').and('be.visible').click()
    cy.readFile(path.join(Cypress.config('downloadsFolder'), 'agenda-settings.json'), { timeout: 15000 }).then(cfg => {
      cy.fixture('agenda-settings.json').then(cfgValid => {
        expect(isEqual(cfg, cfgValid)).to.be.true
      })
    })
    // -------------------
    // Check import config
    // -------------------
    // Skip test if firefox/safari since they don't support the file picker API
    if (!Cypress.isBrowser('firefox') && !Cypress.isBrowser('safari')) {
      cy.fixture('agenda-settings.json', { encoding: 'utf8' }).then(cfgImport => {
        // Stub the native file picker
        // From https://cypresstips.substack.com/p/stub-the-browser-filesystem-api
        cy.window().then((win) => {
          cy.stub(win, 'showOpenFilePicker').resolves([{
            getFile: cy.stub().resolves({
              text: cy.stub().resolves(JSON.stringify(cfgImport))
            })
          }])
          cy.get('.agenda-settings .agenda-settings-actions > button').first().click()
          cy.get('.n-dropdown-option:contains("Import Configuration")').should('exist').and('be.visible').click()
          cy.get('.n-message').should('contain', 'Config imported successfully')
        })
      })
    } else {
      cy.log('Config import test skipped because this browser does not support file picker API, which is required for the test.')
    }
    // -----------------------
    // Check timezone controls
    // -----------------------
//     cy.get('.agenda-settings-content > .n-divider').first().should('contain', 'Timezone').as('settings-timezone')
//     // Switch to local timezone
//     cy.get('@settings-timezone').next('.n-button-group').find('button').eq(1).click().should('have.class', 'n-button--primary-type')
//       .prev('button').should('not.have.class', 'n-button--primary-type')
//     const localDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('local').toFormat(`DD 'at' tt ZZZZ`)
//     cy.get('.agenda h6').first().contains(localDateTime)
//     // Switch to UTC
//     cy.get('@settings-timezone').next('.n-button-group').find('button').last().click().should('have.class', 'n-button--primary-type')
//       .prev('button').should('not.have.class', 'n-button--primary-type')
//     const utcDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('utc').toFormat(`DD 'at' tt ZZZZ`)
//     cy.get('.agenda h6').first().contains(utcDateTime)
//     // Switch back to meeting timezone
//     cy.get('@settings-timezone').next('.n-button-group').find('button').first().click().should('have.class', 'n-button--primary-type')
//     cy.get('@settings-timezone').next('.n-button-group').next('.n-select').contains('Tokyo')
    // ----------------------
    // Check display controls
    // ----------------------
    cy.get('.agenda-settings-content > .n-divider').eq(1).should('contain', 'Display').as('settings-display')
    // -> Test Current Meeting Info Note toggle
    cy.get('@settings-display').nextAll('div.d-flex').eq(1).find('div[role=switch]').as('switch-infonote').click()
    cy.get('.agenda .agenda-infonote').should('not.exist')
    cy.get('@switch-infonote').click()
    cy.get('.agenda .agenda-infonote').should('exist')
    // -> Test Event Icons toggle
    cy.get('@settings-display').nextAll('div.d-flex').eq(2).find('div[role=switch]').as('switch-eventicons').click()
    cy.get('.agenda .agenda-event-icon').should('not.exist')
    cy.get('@switch-eventicons').click()
    cy.get('.agenda .agenda-event-icon').should('exist')
    // -> Test Floor Indicators toggle
    cy.get('@settings-display').nextAll('div.d-flex').eq(3).find('div[role=switch]').as('switch-floorind').click()
    cy.get('.agenda .agenda-table-cell-room > span.badge').should('not.exist')
    cy.get('@switch-floorind').click()
    cy.get('.agenda .agenda-table-cell-room > span.badge').should('exist')
    // -> Test Group Area Indicators toggle
    cy.get('@settings-display').nextAll('div.d-flex').eq(4).find('div[role=switch]').as('switch-groupind').click()
    cy.get('.agenda .agenda-table-cell-group > span.badge').should('not.exist')
    cy.get('@switch-groupind').click()
    cy.get('.agenda .agenda-table-cell-group > span.badge').should('exist')
    // -> Test Bolder Text toggle
    cy.get('@settings-display').nextAll('div.d-flex').eq(6).find('div[role=switch]').as('switch-boldertext').click()
    cy.get('.agenda').should('have.class', 'bolder-text')
    cy.get('@switch-boldertext').click()
    cy.get('.agenda').should('not.have.class', 'bolder-text')

    // ----------------------------
    // Check calendar view controls
    // ----------------------------
    cy.get('.agenda-settings-content > .n-divider').eq(2).should('contain', 'Calendar View').as('settings-calendar')
    // TODO: calendar view checks
    // ----------------------------
    // Check calendar view controls
    // ----------------------------
    cy.get('.agenda-settings-content > .n-divider').eq(3).should('contain', 'Custom Colors / Tags').as('settings-colors')
    // ------------------------------
    // Click Close should hide dialog
    // ------------------------------
    cy.get('.agenda-settings .agenda-settings-actions > button').last().click()
    cy.get('.agenda-settings').should('not.exist')
  })

  // -> ADD TO CALENDAR

  it('can add to calendar', () => {
    cy.get('#agenda-quickaccess-addtocal-btn').should('be.visible').and('include.text', 'Add to your calendar').click()
    cy.get('.n-dropdown-menu > .n-dropdown-option').should('have.length', 2)
      .first().should('include.text', 'Subscribe')
      .next().should('include.text', 'Download')

    // Cannot test if .ics download works because of cypress bug:
    // See https://github.com/cypress-io/cypress/issues/14857

    // // Intercept Download ICS Call
    // cy.intercept('GET', `/meeting/${meetingData.meeting.number}/agenda.ics`, {
    //   body: 'test',
    //   headers: {
    //     'Content-disposition': 'attachment; filename=agenda.ics',
    //     'Content-Type': 'text/calendar'
    //   }
    // }).as('getIcs')

    // // Test Download ICS
    // cy.get('.n-dropdown-menu > .n-dropdown-option').eq(1).click()
    // cy.wait('@getIcs')
  })

  // -> JUMP TO DAY

  it(`can jump to specific days`, () => {
    // -> Separator label
    cy.get('.agenda .agenda-quickaccess-jumpto').prev('div[role=separator]').should('be.visible').and('include.text', 'Jump to...')
    // -> Check nav items
    cy.get('.agenda .agenda-quickaccess-jumpto > .nav-item').should('have.length', 7).as('dayjumpbuttons')
      .each((el, idx) => {
        const localDateTime = DateTime.fromISO(meetingData.meeting.startDate).setZone('local').plus({ days: idx }).toLocaleString(DateTime.DATE_HUGE)
        cy.wrap(el).should('contain', localDateTime)
      })
    
    // Scroll to last day
    // Cypress does not handle the IntersectionObserver correctly, so disable this test for now.
    // See https://github.com/cypress-io/cypress/issues/3848
    cy.get('@dayjumpbuttons').last().children('a').click({ scrollBehavior: false, force: true }) // .should('have.class', 'active')
    cy.get('.agenda-table-display-day').last().isInViewport()

    // Scroll to second day
    cy.get('@dayjumpbuttons').eq(1).children('a').click({ scrollBehavior: false, force: true }) // .should('have.class', 'active')
    cy.get('.agenda-table-display-day').eq(1).isInViewport()

    cy.scrollTo('top')
  })

  // -> Color Tagging

  it(`can assign colors/tags to sessions`, () => {
    cy.scrollTo('top')
    cy.get('.agenda .agenda-table-colorpicker').should('be.visible').click({ scrollBehavior: false })

    // Check Legend
    cy.get('.agenda .agenda-colorlegend').should('be.visible')
      .children().first().should('include.text', 'Color Legend')
      .nextAll().should('have.length', 5)

    // Check color dots
    cy.get('.agenda .agenda-table-display-event .agenda-table-colorindicator.is-active').should('have.length', meetingData.schedule.length)

    // -------------------------
    // Assign colors to sessions
    // -------------------------
    cy.get('.agenda .agenda-table-display-event').take(5).each((el, idx) => {
      cy.wrap(el).find('.agenda-table-colorindicator').should('be.visible').click({ scrollBehavior: false, force: true })
      .prev('.agenda-table-colorchoices').should('be.visible')
      .children('.agenda-table-colorchoice').should('have.length', 6)
      .eq(idx + 1).click({ scrollBehavior: false }).should('not.exist')
    })

    // Exit color assignment mode
    cy.get('.agenda .agenda-table-colorpicker').click({ scrollBehavior: false })
    cy.get('.agenda .agenda-table-display-event .agenda-table-colorindicator').should('have.length', 5).and('not.have.class', 'is-active')
    cy.get('.agenda .agenda-colorlegend').should('be.visible')

    // ----------------------------------------
    // Change color legend from settings dialog
    // ----------------------------------------
    // Open dialog
    cy.get('.meeting-nav').next('button').should('exist').and('be.visible').click()
    cy.get('.agenda-settings').should('exist').and('be.visible')
    // Toggle color legend switch
    cy.get('.agenda-settings-content > .n-divider').eq(1).should('contain', 'Display')
      .next('div.d-flex').find('div[role=switch]').as('switch-colorlegend').click()
    // Legend should be hidden
    cy.get('.agenda .agenda-colorlegend').should('not.exist')
    // Toggle color legend back
    cy.get('@switch-colorlegend').click()
    // Legend should be visible
    cy.get('.agenda .agenda-colorlegend').should('be.visible')
    // Change color names
    cy.get('#agenda-settings-colors-header').nextAll('div.d-flex').each((el, idx) => {
      const newName = faker.music.genre()
      cy.wrap(el).find('.n-input').clear().type(newName)
      // TODO: Color names + values don't update in test mode for some reason... Watcher not triggering? Skipped for now.
      // cy.get('.agenda .agenda-colorlegend').children().eq(idx + 1).should('include.text', newName)
    })
    // Close dialog
    cy.get('.agenda-settings .agenda-settings-actions > button').last().click()
    cy.get('.agenda-settings').should('not.exist')

    // ---------------
    // Unassign colors
    // ---------------
    // Re-enter color assignment mode
    cy.get('.agenda .agenda-table-colorpicker').should('be.visible').click({ scrollBehavior: false })
    // Remove color selection
    cy.get('.agenda .agenda-table-display-event').take(5).each((el, idx) => {
      cy.wrap(el).find('.agenda-table-colorindicator').should('be.visible').click({ scrollBehavior: false, force: true })
      .prev('.agenda-table-colorchoices').should('be.visible')
      .children('.agenda-table-colorchoice').should('have.length', 6)
      .first().click({ scrollBehavior: false }).should('not.exist')
    })
    // Exit color assignment mode
    cy.get('.agenda .agenda-table-colorpicker').click({ scrollBehavior: false })
    // No colored dots should appear
    cy.get('.agenda .agenda-table-display-event .agenda-table-colorindicator').should('not.exist')
    // Clear all colors from Settings menu
    cy.get('.meeting-nav').next('button').should('exist').and('be.visible').click()
    cy.get('.agenda-settings').should('exist').and('be.visible')
    cy.get('.agenda-settings .agenda-settings-actions > button').first().click()
    cy.get('.n-dropdown-option:contains("Clear Color")').should('exist').and('be.visible').click()
    // Color legend should no longer be displayed
    cy.get('.agenda .agenda-colorlegend').should('not.exist')
    cy.get('.agenda-settings').should('not.exist')
  })
})

// ====================================================================
// AGENDA-NEUE (future meeting) | DESKTOP viewport
// ====================================================================

describe('meeting -> agenda-neue [future, desktop]', {
    viewportWidth: viewports.desktop[0],
    viewportHeight: viewports.desktop[1]
  }, () => {
  let meetingData = null

  before(() => {
    // Set clock to 2022-02-01 (month is 0-indexed)
    cy.clock(new Date(2022, 1, 1))

    // Generate future meeting data
    meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'future' })

    // Intercept Meeting Data API
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')

    // Visit agenda page
    cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
      onBeforeLoad: (win) => { injectMeetingData(win, meetingData.meeting.number) }
    })
    cy.wait('@getMeetingData')
  })

  // -> SCHEDULE LIST -> Warning

  it(`has current meeting warning`, () => {
    cy.get('.agenda .agenda-currentwarn').should('exist').and('include.text', 'Note: IETF agendas are subject to change, up to and during a meeting.')
  })

  // -> SCHEDULE LIST -> Table Events

  it('has schedule list table events (can take a while)', {
    // This test is VERY memory-intensive, so disable DOM snapshots to prevent browser crash
    numTestsKeptInMemory: 0
  }, () => {
    let isFirstSession = true
    cy.get('tr.agenda-table-display-event').should('have.length', meetingData.schedule.length).each((el, idx) => {
      // Apply small arbitrary wait every 10 rows to prevent the test UI from freezing
      if (idx % 10 === 0) {
        // eslint-disable-next-line cypress/no-unnecessary-waiting
        cy.wait(10)
      }
      const event = meetingData.schedule[idx]

      // -----------------------
      // Buttons / Status Column
      // -----------------------
      if (event.status === 'sched') {
        if (event.flags.showAgenda || ['regular', 'plenary'].includes(event.type)) {
          cy.wrap(el).find('.agenda-table-cell-links > .agenda-table-cell-links-buttons').as('eventbuttons')
          if (event.flags.agenda) {
            // Show meeting materials button
            cy.get('@eventbuttons').find('i.bi.bi-collection').should('exist')
            // ZIP materials button
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-tar`).should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.tgz`)
              .children('i.bi').should('exist')
            // PDF materials button
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-pdf`).should('have.attr', 'href', `/meeting/${meetingData.meeting.number}/agenda/${event.acronym}-drafts.pdf`)
              .children('i.bi').should('exist')
          } else if (event.type === 'regular') {
            // No meeting materials yet warning badge
            cy.get('@eventbuttons').find('.no-meeting-materials').should('exist')
          }
          // Notepad button
          const hedgeDocLink = `https://notes.ietf.org/notes-ietf-${meetingData.meeting.number}-${event.type === 'plenary' ? 'plenary' : event.acronym}`
          cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-note`).should('have.attr', 'href', hedgeDocLink)
            .children('i.bi').should('exist')
          // Chat room
          cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-room`).should('have.attr', 'href', event.links.chat)
            .children('i.bi').should('exist')
          // Video Stream
          if (event.links.videoStream) {
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-video`).should('have.attr', 'href', formatLinkUrl(event.links.videoStream, event, meetingData.meeting.number))
              .children('i.bi').should('exist')
          }
          // Onsite Tool
          if (event.links.onsitetool) {
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-onsitetool`).should('have.attr', 'href', formatLinkUrl(event.links.onsitetool, event, meetingData.meeting.number))
              .children('i.bi').should('exist')
          }
          // Audio Stream
          if (event.links.audioStream) {
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-audio`).should('have.attr', 'href', formatLinkUrl(event.links.audioStream, event, meetingData.meeting.number))
              .children('i.bi').should('exist')
          }
          // Remote Call-In
          let remoteCallInUrl = null
          if (event.note) {
            remoteCallInUrl = findFirstConferenceUrl(event.note)
          }
          if (!remoteCallInUrl && event.remoteInstructions) {
            remoteCallInUrl = findFirstConferenceUrl(event.remoteInstructions)
          }
          if (!remoteCallInUrl && event.links.webex) {
            remoteCallInUrl = event.links.webex
          }
          if (remoteCallInUrl) {
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-remotecallin`).should('have.attr', 'href', remoteCallInUrl)
              .children('i.bi').should('exist')
          }
          // calendar
          if (event.links.calendar) {
            cy.get('@eventbuttons').find(`#btn-lnk-${event.id}-calendar`).should('have.attr', 'href', event.links.calendar)
              .children('i.bi').should('exist')
          }
        } else {
          cy.wrap(el).find('.agenda-table-cell-links > .agenda-table-cell-links-buttons').should('not.exist')
        }
      }
    })
  })
})

// ====================================================================
// AGENDA-NEUE (live meeting) | DESKTOP viewport
// ====================================================================

describe('meeting -> agenda-neue [live, desktop]', {
  viewportWidth: viewports.desktop[0],
  viewportHeight: viewports.desktop[1]
  }, () => {
  let meetingData = null
  const currentTime = DateTime.fromISO('2022-02-01T13:45:15', { zone: 'Asia/Tokyo' })
  const liveEvents = []
  let lastLiveEvent = null

  before(() => {
    // Set clock to 2022-02-01 (month is 0-indexed)
    cy.clock(currentTime.toMillis())

    // Generate live meeting data
    meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'current' })

    // Calculate live events
    let lastEventStartTime = null
    for (const event of meetingData.schedule) {
      const eventStart = DateTime.fromISO(event.startDateTime, { zone: 'Asia/Tokyo' })
      const eventEnd = eventStart.plus({ seconds: event.duration })
      if (currentTime >= eventStart && currentTime < eventEnd) {
        liveEvents.push(event)
        // -> Find last event before current time
        if (lastEventStartTime === eventStart.toMillis()) {
          continue
        } else {
          lastEventStartTime = eventStart.toMillis()
          lastLiveEvent = event
        }
      }
      // -> Skip future events
      if (eventStart > currentTime) {
        break
      }
    }

    // Intercept Meeting Data API
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')

    // Visit agenda page
    cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
      onBeforeLoad: (win) => { injectMeetingData(win, meetingData.meeting.number) }
    })
    cy.wait('@getMeetingData')

    // Fix scroll behavior
    // See https://github.com/cypress-io/cypress/issues/3200
    cy.document().then(document => {
      const htmlElement = document.querySelector('html')
      if (htmlElement) {
        htmlElement.style.scrollBehavior = 'inherit'
      }
    })
  })

  beforeEach(() => {
    cy.clock(currentTime.toMillis())
  })

  // -> HIGHLIGHTED LIVE SESSIONS

  it(`has live sessions highlighted`, () => {
    cy.get('.agenda .agenda-table-display-event.agenda-table-live').should('have.length', liveEvents.length)
  })

  // -> LIVE RED LINE

  it(`has live red line`, () => {
    cy.get('.agenda .agenda-table-redhand').should('be.visible').then(el => {
      cy.get(`#agenda-rowid-${lastLiveEvent.id}`).then(elEv => {
        expect(el.offsetTop).to.equal(elEv.offsetTop)
      })
    })
  })

  // -> JUMP TO NOW

  it(`has jump to now button`, () => {
    cy.get('.agenda .agenda-quickaccess-jumpto > .nav-item').should('have.length', 8).first().should('include.text', 'Now').click()
    cy.get('.agenda .agenda-table-redhand').isInViewport()
  })

  // -> HIDE RED LINE
  // TODO: dialog fails to render for unknown reason (but clicking manually on the window triggers the render)
  // Seems like a cypress bug... Skipping for now.
  it.skip(`can toggle the live red line`, () => {
    // Open settings dialog
    cy.get('.meeting-nav').next('button').click()
    cy.get('.agenda-settings').should('exist').and('be.visible')
    // Toggle red line switch
    cy.get('.agenda-settings-content > .n-divider').eq(1).should('contain', 'Display')
      .nextAll('div.d-flex').eq(5).find('div[role=switch]').as('switch-redline').click()
    // Check red line disappeared
    cy.get('.agenda .agenda-table-redhand').should('not.exist')
    // Re-enable it
    cy.get('@switch-redline').click()
    // Check red line is visible again
    cy.get('.agenda .agenda-table-redhand').should('be.visible')
    // Close dialog
    cy.get('.agenda-settings .agenda-settings-actions > button').last().click()
    cy.get('.agenda-settings').should('not.exist')
  })
})

// ====================================================================
// AGENDA-NEUE (past meeting) | SMALL DESKTOP/TABLET/MOBILE  viewport
// ====================================================================

describe('meeting -> agenda-neue [past, small screens]', () => {
  // Generate meeting data
  const meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'past' })

  for (const vp of ['smallDesktop', 'tablet', 'mobile']) {
    describe(vp, {
      viewportWidth: viewports[vp][0],
      viewportHeight: viewports[vp][1]
    }, () => {
      before(() => {
        // Set clock to 2022-02-01 (month is 0-indexed)
        cy.clock(new Date(2022, 1, 1))

        // Intercept Meeting Data API
        cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')

        // Visit agenda page
        cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
          onBeforeLoad: (win) => { injectMeetingData(win, meetingData.meeting.number) }
        })
        cy.wait('@getMeetingData')

        // Fix scroll behavior
        // See https://github.com/cypress-io/cypress/issues/3200
        cy.document().then(document => {
          const htmlElement = document.querySelector('html')
          if (htmlElement) {
            htmlElement.style.scrollBehavior = 'inherit'
          }
        })
      })

      // -> NARROW QUICK ACCESS PANEL (smallDesktop only)

      if (vp === 'smallDesktop') {
        it('has narrow quick access panel', () => {
          // Alternate labels for buttons
          cy.get('#agenda-quickaccess-filterbyareagroups-btn').should('be.visible').and('include.text', 'Filter...')
            .next('button').should('be.visible').and('include.text', 'Pick...')
          cy.get('#agenda-quickaccess-calview-btn').should('be.visible').and('include.text', 'Cal View')
            .next('button').should('be.visible').and('include.text', '.ics')
          // -> Shorter date labels for Jump to buttons
          cy.get('.agenda .agenda-quickaccess-jumpto > .nav-item').should('have.length', 7).as('dayjumpbuttons')
            .each((el, idx) => {
              const localDateTime = DateTime.fromISO(meetingData.meeting.startDate).setZone('local').plus({ days: idx }).toFormat('ccc LLL d')
              cy.wrap(el).should('contain', localDateTime).find('i.bi').should('not.be.visible')
            })

          // Take a snapshot for visual diffing
          cy.percySnapshot(`meeting -> agenda-neue [past, ${vp}]`, { widths: [viewports[vp][0]] })
        })
      }

      // -> TABLET + MOBILE-specific tests

      if (vp === 'tablet' || vp === 'mobile') {

        // Check for elements that should not exist on smaller screens

        it('has no updated date', () => {
          cy.get('.agenda > h4 > h6').should('not.be.visible')

          // Take a snapshot for visual diffing
          cy.percySnapshot(`meeting -> agenda-neue [past, ${vp}]`, { widths: [viewports[vp][0]] })
        })

        it('has no timezone dropdown selector', () => {
          cy.get('.agenda .agenda-tz-selector').next('.agenda-timezone-ddn').should('not.exist')
        })

        it('has no floor + group indicators', () => {
          cy.get('.agenda .agenda-table-cell-room > .badge').should('not.be.visible')
          cy.get('.agenda .agenda-table-cell-group > .badge').should('not.exist')
        })

        // Session buttons should be hidden in a dropdown menu

        it('has session buttons dropdown', () => {
          cy.get('.agenda .agenda-table-display-event .agenda-table-cell-links-buttons').each(el => {
            cy.wrap(el).children().should('have.length', 1)
          })

          // TODO: Check for dropdown links once changed to a custom panel with standard links
        })

        // Bottom Mobile Bar

        it('has no lateral quick access panel', () => {
          cy.get('.agenda-quickaccess').should('not.exist')
        })

        it('has a bottom mobile bar', () => {
          cy.get('.agenda-mobile-bar').should('be.visible')
            .children().should('have.length', 4)
            .first().should('include.text', 'Filters')
            .next().should('include.text', 'Cal')
            .next().should('include.text', '.ics')
            .next().children().should('have.length', 1).and('have.class', 'bi')
        })

        it('can open the filters overlay', () => {
          cy.get('.agenda-mobile-bar > button').first().click()
          cy.get('.agenda-personalize').should('be.visible')
          cy.get('.agenda-personalize .agenda-personalize-actions > button').eq(1).click()
          cy.get('.agenda-personalize').should('not.exist')
        })

        it('can open the calendar view', () => {
          cy.get('.agenda-mobile-bar > button').eq(1).click()
          cy.get('.agenda-calendar').should('be.visible')
          cy.get('.agenda-calendar .agenda-calendar-actions > button').eq(1).click()
          cy.get('.agenda-calendar').should('not.exist')
        })

        it('can open the ics dropdown', () => {
          cy.get('.agenda-mobile-bar > button').eq(2).click()
          cy.get('.n-dropdown-menu > .n-dropdown-option').should('have.length', 2)
            .first().should('include.text', 'Subscribe')
            .next().should('include.text', 'Download')
        })

        it('can open the settings overlay', () => {
          cy.get('.agenda-mobile-bar > button').last().click()
          cy.get('.agenda-settings').should('be.visible')
          cy.get('.agenda-settings .agenda-settings-actions > button').eq(1).click()
          cy.get('.agenda-settings').should('not.exist')
        })
      }
    })
  }
})

// ====================================================================
// FLOOR-PLAN-NEUE | All Viewports
// ====================================================================

describe(`meeting -> floor-plan-neue`, () => {
  for (const vp of ['desktop', 'smallDesktop', 'tablet', 'mobile']) {
    describe(vp, {
        viewportWidth: viewports[vp][0],
        viewportHeight: viewports[vp][1]
      }, () => {
      const meetingData = meetingGenerator.generateAgendaResponse({ dateMode: 'past', skipSchedule: true })

      before(() => {
        cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')
        cy.visit(`/meeting/${meetingData.meeting.number}/floor-plan-neue`, {
          onBeforeLoad: (win) => { injectMeetingData(win, meetingData.meeting.number) }
        })
        cy.wait('@getMeetingData')
      })

      // -> HEADER

      it(`has IETF ${meetingData.meeting.number} title`, () => {
        cy.get('.floorplan h1').first().contains(`IETF ${meetingData.meeting.number} Floor Plan`)

        // Take a snapshot for visual diffing
        cy.percySnapshot(`meeting -> floor-plan-neue [${vp}]`, { widths: [viewports[vp][0]] })
      })
      it(`has meeting city subtitle`, () => {
        cy.get('.floorplan h4').first().contains(meetingData.meeting.city)
      })
      it(`has meeting date subtitle`, () => {
        cy.get('.floorplan h4').first().contains(/[a-zA-Z] [0-9]{1,2} - ([a-zA-Z]+ )?[0-9]{1,2}, [0-9]{4}/i)
      })

      // -> NAV

      it(`has the correct navigation items`, () => {
        cy.get('.floorplan .meeting-nav > li').should('have.length', 3)
        cy.get('.floorplan .meeting-nav > li').first().contains('Agenda')
        cy.get('.floorplan .meeting-nav > li').eq(1).contains('Floor plan')
        cy.get('.floorplan .meeting-nav > li').last().contains('Plaintext')
      })

      // -> FLOORS

      it(`can switch between floors`, () => {
        cy.get('.floorplan .floorplan-floors > .nav-link').should('have.length', meetingData.floors.length)
        cy.get('.floorplan .floorplan-floors > .nav-link').each((el, idx) => {
          cy.wrap(el).contains(meetingData.floors[idx].name)
          cy.wrap(el).click()
          cy.wrap(el).should('have.class', 'active')
          cy.wrap(el).siblings().should('not.have.class', 'active')
          // Wait for image to load + verify
          cy.get('.floorplan .floorplan-plan > img').should('be.visible').and(img => expect(img[0].naturalWidth).to.be.greaterThan(1))
        })
      })

      // -> ROOMS

      it(`can select rooms`, { retries: 2 }, () => {
        const floor = meetingData.floors[0]
        cy.get('.floorplan .floorplan-floors > .nav-link').first().click()
        cy.get('.floorplan .floorplan-rooms > .list-group-item').should('have.length', floor.rooms.length)
        cy.get('.floorplan .floorplan-rooms > .list-group-item').each((el, idx) => {
          // Room List
          const room = floor.rooms[idx]
          cy.wrap(el).find('strong').contains(room.name)
            .next('small').contains(room.functionalName)
          cy.wrap(el).find('.badge').should('exist').and('include.text', floor.short)
          cy.wrap(el).click()
          cy.wrap(el).should('have.class', 'active')
          cy.wrap(el).siblings().should('not.have.class', 'active')
          // URL query segment
          cy.location('search').should('include', `room=${room.slug}`)
          // Pin Drop
          cy.window().then(win => {
            cy.get('.floorplan .floorplan-plan > img').then(floorImg => {
              const planxRatio = floorImg[0].width / floor.width
              const planyRatio = floorImg[0].height / floor.height
              cy.get('.floorplan .floorplan-plan-pin').should('exist').then(el => {
                const pinMarginLeft = parseInt(win.getComputedStyle(el[0]).getPropertyValue('margin-left').match(/\d+/))
                const xPos = Math.round((room.left + (room.right - room.left) / 2) * planxRatio) - 25 + pinMarginLeft
                const yPos = Math.round((room.top + (room.bottom - room.top) / 2) * planyRatio) - 40
                expect(el[0].offsetLeft).to.equal(xPos)
                expect(el[0].offsetTop).to.equal(yPos)
              })
            })
          })
        })
      })
    })
  }
})
