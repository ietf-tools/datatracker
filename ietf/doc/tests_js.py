# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

import debug                            # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory, DocumentAuthorFactory
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
from ietf.utils.jstest import ( IetfSeleniumTestCase, ifSeleniumEnabled, selenium_enabled,
                                presence_of_element_child_by_css_selector )

if selenium_enabled():
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions


@ifSeleniumEnabled
class EditAuthorsTests(IetfSeleniumTestCase):
    def setUp(self):
        super(EditAuthorsTests, self).setUp()
        self.wait = WebDriverWait(self.driver, 2)

    def test_add_author_forms(self):
        def _fill_in_author_form(form_elt, name, email, affiliation, country):
            """Fill in an author form on the edit authors page

            The form_elt input should be an element containing all the relevant inputs.
            """
            # To enter the person, type their name in the select2 search box, wait for the
            # search to offer the result, then press 'enter' to accept the result and close
            # the search input.
            person_span = form_elt.find_element(By.CLASS_NAME, 'select2-selection')
            self.scroll_to_element(person_span)
            person_span.click()
            input = self.driver.find_element(By.CSS_SELECTOR, '.select2-search__field[aria-controls*=author]')
            input.send_keys(name)
            result_selector = 'ul.select2-results__options[id*=author] > li.select2-results__option--selectable'
            self.wait.until(
                expected_conditions.text_to_be_present_in_element(
                    (By.CSS_SELECTOR, result_selector),
                    name
                ))
            self.driver.find_element(By.CSS_SELECTOR, result_selector).click()

            # After the author is selected, the email select options will be populated.
            # Wait for that, then click on the option corresponding to the requested email.
            # This will only work if the email matches an address for the selected person.
            email_select = form_elt.find_element(By.CSS_SELECTOR, 'select[name$="email"]')
            email_option = self.wait.until(
                presence_of_element_child_by_css_selector(email_select, 'option[value="{}"]'.format(email))
            )
            email_option.click()  # select the email

            # Fill in the affiliation and country. Finally, simple text inputs!
            affil_input = form_elt.find_element(By.CSS_SELECTOR, 'input[name$="affiliation"]')
            affil_input.send_keys(affiliation)
            country_input = form_elt.find_element(By.CSS_SELECTOR, 'input[name$="country"]')
            country_input.send_keys(country)

        def _read_author_form(form_elt):
            """Read values from an author form

            Note: returns the Person instance named in the person field, not just their name.
            """
            hidden_person_input = form_elt.find_element(By.CSS_SELECTOR, 'select[name$="person"]')
            email_select = form_elt.find_element(By.CSS_SELECTOR, 'select[name$="email"]')
            affil_input = form_elt.find_element(By.CSS_SELECTOR, 'input[name$="affiliation"]')
            country_input = form_elt.find_element(By.CSS_SELECTOR, 'input[name$="country"]')
            return (
                Person.objects.get(pk=hidden_person_input.get_attribute('value')),
                email_select.get_attribute('value'),
                affil_input.get_attribute('value'),
                country_input.get_attribute('value'),
            )

        # Create testing resources
        draft = WgDraftFactory()
        DocumentAuthorFactory(document=draft)
        authors = PersonFactory.create_batch(2)  # authors we will add
        orgs = ['some org', 'some other org']  # affiliations for the authors
        countries = ['France', 'Uganda']  # countries for the authors
        url = self.absreverse('ietf.doc.views_doc.edit_authors', kwargs=dict(name=draft.name))

        # Star the test by logging in with appropriate permissions and retrieving the edit page
        self.login('secretary')
        self.driver.get(url)

        # The draft has one author to start with. Find the list and check the count.
        authors_list = self.driver.find_element(By.ID, 'authors-list')
        author_forms = authors_list.find_elements(By.CLASS_NAME, 'author-panel')
        self.assertEqual(len(author_forms), 1)

        # get the "add author" button so we can add blank author forms
        for index, auth in enumerate(authors):
            self.scroll_and_click((By.ID, 'add-author-button'))  # Create new form. Automatically scrolls to it.
            author_forms = authors_list.find_elements(By.CLASS_NAME, 'author-panel')
            authors_added = index + 1
            self.assertEqual(len(author_forms), authors_added + 1)  # Started with 1 author, hence +1
            _fill_in_author_form(author_forms[index + 1], auth.name, str(auth.email()), orgs[index], countries[index])

        # Check that the author forms have correct (and distinct) values
        first_auth = draft.documentauthor_set.first()
        self.assertEqual(
            _read_author_form(author_forms[0]),
            (first_auth.person, str(first_auth.email), first_auth.affiliation, first_auth.country),
        )
        for index, auth in enumerate(authors):
            self.assertEqual(
                _read_author_form(author_forms[index + 1]),
                (auth, str(auth.email()), orgs[index], countries[index]),
            )

        # Must provide a "basis" (change reason)
        self.driver.find_element(By.ID, 'id_basis').send_keys('change testing')
        # Now click the 'submit' button and check that the update was accepted.
        submit_button = self.driver.find_element(By.CSS_SELECTOR, '#content button[type="submit"]')
        self.scroll_to_element(submit_button)
        submit_button.click()
        # Wait for redirect to the document_main view
        self.wait.until(
            expected_conditions.url_to_be(
                self.absreverse('ietf.doc.views_doc.document_main', kwargs=dict(name=draft.name))
            ))
        # Just a basic check that the expected authors show up. Details of the updates
        # are tested separately.
        self.assertEqual(
            list(draft.documentauthor_set.values_list('person', flat=True)),
            [first_auth.person.pk] + [auth.pk for auth in authors]
        )
