/// <reference types="cypress" />

describe.skip('meeting agenda', () => {
    before(() => {
      cy.visit('/meeting/agenda/')
    })
  
    it('toggle customize panel when clicking on customize header bar', () => {
      cy.get('#agenda-filter-customize').click()
      cy.get('#customize').should('be.visible').and('have.class', 'in')

      cy.get('#agenda-filter-customize').click()
      cy.get('#customize').should('not.be.visible').and('not.have.class', 'in')
    })

    it('customize panel should have at least 3 areas', () => {
        cy.get('#agenda-filter-customize').click()
        cy.get('.agenda-filter-areaselectbtn').should('have.length.at.least', 3)
    })

    it('customize panel should have at least 10 groups', () => {
        cy.get('.agenda-filter-groupselectbtn').should('have.length.at.least', 10)
    })

    it('filtering the agenda should modify the URL', () => {
        // cy.intercept({
        //     method: 'GET',
        //     path: '/meeting/agenda/week-view.html**',
        //     times: 10
        // }, {
        //     forceNetworkError: true
        // })

        cy.get('.agenda-filter-groupselectbtn').any(5).as('selectedGroups').each(randomElement => {
            cy.wrap(randomElement).click()
            cy.wrap(randomElement).invoke('attr', 'data-filter-item').then(keyword => {
                cy.url().should('contain', keyword)
            })
        })

        // Deselect everything
        cy.get('@selectedGroups').click({ multiple: true })
    })

    it('selecting an area should select all corresponding groups', () => {
        cy.get('.agenda-filter-areaselectbtn').any().click().invoke('attr', 'data-filter-item').then(area => {
            cy.url().should('contain', area)

            cy.get(`.agenda-filter-groupselectbtn[data-filter-keywords*="${area}"]`).each(group => {
                cy.wrap(group).invoke('attr', 'data-filter-keywords').then(groupKeywords => {
                    // In case value is a comma-separated list of keywords...
                    if (groupKeywords.indexOf(',') < 0 || groupKeywords.split(',').includes(area)) {
                        cy.wrap(group).should('have.class', 'active')
                    }
                })
            })
        })
    })

    it('weekview iframe should load', () => {
        cy.get('iframe#weekview').its('0.contentDocument').should('exist')
        cy.get('iframe#weekview').its('0.contentDocument.readyState').should('equal', 'complete')
        cy.get('iframe#weekview').its('0.contentDocument.body', {
            timeout: 30000
        }).should('not.be.empty')
    })
})

describe('meeting agenda weekview', () => {
    before(() => {
      cy.visit('/meeting/agenda/week-view.html')
    })
    it('should have day headers', () => {
        cy.get('.agenda-weekview-day').should('have.length.greaterThan', 0).and('be.visible')
    })
    it('should have day columns', () => {
        cy.get('.agenda-weekview-column').should('have.length.greaterThan', 0).and('be.visible')
    })

    it('should have the same number of day headers and columns', () => {
        cy.get('.agenda-weekview-day').its('length').then(lgth => {
            cy.get('.agenda-weekview-column').should('have.length', lgth)
        })
    })

    it('should have meetings', () => {
        cy.get('.agenda-weekview-meeting').should('have.length.greaterThan', 0).and('be.visible')
    })

    it('meeting hover should cause expansion to column width', () => {
        cy.get('.agenda-weekview-column:first').invoke('outerWidth').then(colWidth => {
            cy.get('.agenda-weekview-meeting-mini').any(5).each(meeting => {
                cy.wrap(meeting)
                    .wait(250)
                    .realHover({ position: 'center' })
                    .invoke('outerWidth')
                    .should('be.closeTo', colWidth, 1)
                // Move over to top left corner of the page to end the mouseover of the current meeting block
                cy.get('.agenda-weekview-day:first').realHover().wait(250)
            })
        })
    })
})