import { DateTime } from 'luxon'
import meetingGenerator from '../../generators/meeting'

describe('meeting -> agenda-neue [past, desktop]', {
    viewportWidth: 1536,
    viewportHeight: 960
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

  // -> SCHEDULE LIST

  it(`has schedule list title`, () => {
    cy.get('.agenda h2').first().contains(`Schedule`)
  })
  it(`has info note`, () => {
    cy.get('.agenda .agenda-infonote').should('exist').and('include.text', meetingData.meeting.infoNote)
  })
  it(`info note can be dismissed`, () => {
    cy.get('.agenda .agenda-infonote > button').click()
    cy.get('.agenda .agenda-infonote').should('not.exist')
  })
  it(`info note can be re-opened`, () => {
    cy.viewport('macbook-16')
    cy.get('.agenda h2').first().next('button').should('exist')
    cy.get('.agenda h2').first().next('button').click()
    cy.get('.agenda .agenda-infonote').should('exist')
    cy.get('.agenda h2').first().next('button').should('not.exist')
  })
})
