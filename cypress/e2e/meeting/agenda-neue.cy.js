describe('meeting -> agenda-neue', () => {
  const meetingNumber = 113

  before(() => {
    cy.intercept('GET', `/api/meeting/${meetingNumber}/agenda-data`, { fixture: `agenda-${meetingNumber}-data.json` }).as('getMeetingData')
    cy.visit(`/meeting/${meetingNumber}/agenda-neue`)
    cy.wait('@getMeetingData')
  })

  it(`have IETF ${meetingNumber} title`, () => {
    cy.get('h1').should('have.string', `IETF ${meetingNumber}`)
  })
})
