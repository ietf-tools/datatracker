import { DateTime } from 'luxon'
import meetingGenerator from '../../generators/meeting'

const viewports = {
  desktop: [1536, 960]
}

describe('meeting -> agenda-neue [past, desktop]', {
    viewportWidth: viewports.desktop[0],
    viewportHeight: viewports.desktop[1]
  }, () => {
  const meetingData = meetingGenerator.generateAgendaResponse({ future: false })

  before(() => {
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')
    cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
      onBeforeLoad: (win) => {
        const meetingDataScript = win.document.createElement('script')
        meetingDataScript.id = 'meeting-data'
        meetingDataScript.type = 'application/json'
        meetingDataScript.innerHTML = `{"meetingNumber": "${meetingData.meeting.number}"}`
        win.document.querySelector('head').appendChild(meetingDataScript)
      }
    })
    cy.wait('@getMeetingData')
  })

  // -> HEADER

  it(`has IETF ${meetingData.meeting.number} title`, () => {
    cy.get('.agenda h1').first().contains(`IETF ${meetingData.meeting.number} Meeting Agenda`)
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
    cy.get('.agenda .agenda-tz-selector > button').eq(1).click().should('have.class', 'n-button--primary-type')
      .prev('button').should('not.have.class', 'n-button--primary-type')
    const localDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('local').toFormat(`DD 'at' tt ZZZZ`)
    cy.get('.agenda h6').first().contains(localDateTime)
    // Switch to UTC
    cy.get('.agenda .agenda-tz-selector > button').last().click().should('have.class', 'n-button--primary-type')
      .prev('button').should('not.have.class', 'n-button--primary-type')
    const utcDateTime = DateTime.fromISO(meetingData.meeting.updated).setZone('utc').toFormat(`DD 'at' tt ZZZZ`)
    cy.get('.agenda h6').first().contains(utcDateTime)
    cy.get('.agenda .agenda-timezone-ddn').contains('UTC')
    // Switch back to meeting timezone
    cy.get('.agenda .agenda-tz-selector > button').first().click().should('have.class', 'n-button--primary-type')
    cy.get('.agenda .agenda-timezone-ddn').contains('Tokyo')
  })

})

describe('meeting -> agenda-neue [future, desktop]', {
    viewportWidth: viewports.desktop[0],
    viewportHeight: viewports.desktop[1]
  }, () => {
  const meetingData = meetingGenerator.generateAgendaResponse({ future: true })

  before(() => {
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')
    cy.visit(`/meeting/${meetingData.meeting.number}/agenda-neue`, {
      onBeforeLoad: (win) => {
        const meetingDataScript = win.document.createElement('script')
        meetingDataScript.id = 'meeting-data'
        meetingDataScript.type = 'application/json'
        meetingDataScript.innerHTML = `{"meetingNumber": "${meetingData.meeting.number}"}`
        win.document.querySelector('head').appendChild(meetingDataScript)
      }
    })
    cy.wait('@getMeetingData')
  })

  // -> SCHEDULE LIST

  it(`has current meeting warning`, () => {
    cy.get('.agenda .agenda-currentwarn').should('exist').and('include.text', 'Note: IETF agendas are subject to change, up to and during a meeting.')
  })
})
