import { DateTime } from 'luxon'
import meetingGenerator from '../../generators/meeting'

const meetingData = meetingGenerator.generateAgendaResponse({ future: false })

describe('meeting -> agenda-neue [past, desktop]', () => {
  before(() => {
    cy.intercept('GET', `/api/meeting/${meetingData.meeting.number}/agenda-data`, { body: meetingData }).as('getMeetingData')
    cy.viewport('macbook-16')
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
    // cy.get('.agenda .meeting-nav').next('button').its('offsetLeft').should('be.greaterThan', 1000)
  })
})
