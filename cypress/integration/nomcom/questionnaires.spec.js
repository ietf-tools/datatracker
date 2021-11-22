/// <reference types="cypress" />

describe('questionnaires', () => {
    before(() => {
      cy.visit('/nomcom/2021/questionnaires/')
    })
  
    it('position tabs should display the appropriate panel on click', () => {
        cy.get('.nomcom-questnr-positions-tabs > li > a').each($tab => {
            cy.wrap($tab).click()
            cy.wrap($tab).parent().should('have.class', 'active')

            cy.wrap($tab).invoke('attr', 'href').then($tabId => {
                cy.get($tabId).should('have.class', 'tab-pane').and('have.class', 'active').and('be.visible')
            })
        })
    })
})