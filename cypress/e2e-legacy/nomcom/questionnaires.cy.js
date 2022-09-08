describe('questionnaires', () => {
  before(() => {
    cy.visit('/nomcom/2021/questionnaires/')
  })

  it('position tabs should display the appropriate panel on click', () => {
    cy.get('.nomcom-questnr-positions-tabs > li > button').each($tab => {
      cy.wrap($tab).click()
      cy.wrap($tab).should('have.class', 'active')

      cy.wrap($tab).invoke('attr', 'data-bs-target').then($tabId => {
        cy.get($tabId).should('have.class', 'tab-pane').and('have.class', 'active').and('be.visible')
      })
    })
  })
})
