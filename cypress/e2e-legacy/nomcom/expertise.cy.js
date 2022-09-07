describe('expertise', () => {
  before(() => {
    cy.visit('/nomcom/2021/expertise/')
  })

  it('expertises with expandable panels should expand', () => {
    cy.get('.nomcom-req-positions-tabs > li > button').each($tab => {
      cy.wrap($tab).click()
      cy.wrap($tab).should('have.class', 'active')

      cy.wrap($tab).invoke('attr', 'data-bs-target').then($tabId => {
        cy.get($tabId).should('have.class', 'tab-pane').and('have.class', 'active').and('be.visible')

        cy.get($tabId).then($tabContent => {
          if ($tabContent.find('.generic_iesg_reqs_header').length) {
            cy.wrap($tabContent).find('.generic_iesg_reqs_header').click()
            cy.wrap($tabContent).find('.generic_iesg_reqs_header').invoke('attr', 'href').then($expandId => {
              cy.get($expandId).should('be.visible')
            })
          }
        })
      })
    })
  })
})
