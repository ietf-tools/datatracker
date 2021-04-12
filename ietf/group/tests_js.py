# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

import datetime
import debug                            # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory
from ietf.group.factories import GroupFactory, RoleFactory, DatedGroupMilestoneFactory
from ietf.utils.jstest import IetfSeleniumTestCase, ifSeleniumEnabled, selenium_enabled

if selenium_enabled():
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions


@ifSeleniumEnabled
class MilestoneTests(IetfSeleniumTestCase):
    def setUp(self):
        super(MilestoneTests, self).setUp()
        
        self.wait = WebDriverWait(self.driver, 2)
        self.group = GroupFactory()
        self.chair = RoleFactory(group=self.group, name_id='chair').person

    def _search_draft_and_locate_result(self, draft_input, search_string, draft):
        """Search for a draft and get the search result element"""
        draft_input.send_keys(search_string)

        result_selector = 'ul.select2-results > li > div.select2-result-label'
        self.wait.until(
            expected_conditions.text_to_be_present_in_element(
                (By.CSS_SELECTOR, result_selector),
                draft.name
            ))
        results = self.driver.find_elements_by_css_selector(result_selector)
        matching_results = [r for r in results if draft.name in r.text]
        self.assertEqual(len(matching_results), 1)
        return matching_results[0]
        
    def _click_milestone_submit_button(self, label):
        submit_button_selector = 'form#milestones-form button[type="submit"]'
        submit_button = self.wait.until(
            expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, submit_button_selector))
        )
        self.assertIn(label, submit_button.text)
        submit_button.click()

    def _assert_milestone_changed(self):
        """Wait for milestone to be marked as changed and assert that this succeeded"""
        milestone_selector = 'form#milestones-form .milestone'
        try:
            found_expected_text = self.wait.until(
                expected_conditions.text_to_be_present_in_element(
                    (By.CSS_SELECTOR, milestone_selector),
                    'Changed'
                )
            )
        except TimeoutException:
            found_expected_text = False
        self.assertTrue(found_expected_text, 'Milestone never marked as "changed"')
        return self.driver.find_element_by_css_selector(milestone_selector)

    def test_add_milestone(self):
        draft = WgDraftFactory()
        WgDraftFactory.create_batch(3)  # some drafts to ignore
        description = 'some description'
        due_date = datetime.date.today() + datetime.timedelta(days=60)

        assert(len(draft.name) > 5)
        draft_search_string = draft.name[-5:]
        
        self.login(self.chair.user.username)
        url = self.absreverse('ietf.group.milestones.edit_milestones;current',
                              kwargs=dict(acronym=self.group.acronym))
        self.driver.get(url)

        add_milestone_button = self.wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.add-milestone')
            ))
        add_milestone_button.click()

        edit_div = self.wait.until(
            expected_conditions.visibility_of_element_located(
                (By.CSS_SELECTOR, 'form#milestones-form div.edit-milestone')
            ))

        desc_input = edit_div.find_element_by_css_selector('input[id$="_desc"]')
        due_input = edit_div.find_element_by_css_selector('input[id$="_due"]')
        draft_input = edit_div.find_element_by_css_selector(
            'div.select2-container[id$="id_docs"] input.select2-input'
        )
        
        # fill in the edit milestone form
        desc_input.send_keys(description)
        due_input.send_keys(due_date.strftime('%m %Y\n'))  # \n closes the date selector
        self._search_draft_and_locate_result(draft_input, draft_search_string, draft).click()

        self._click_milestone_submit_button('Review')
        result_row = self._assert_milestone_changed()
        self.assertIn(description, result_row.text)
        self._click_milestone_submit_button('Save')
        
        # Wait for page to return to group page
        self.wait.until(
            expected_conditions.text_to_be_present_in_element(
                (By.CSS_SELECTOR, 'div#content h1'),
                self.group.name
            )
        )
        self.assertIn('1 new milestone', self.driver.page_source)
        self.assertEqual(self.group.groupmilestone_set.count(), 1)
        gms = self.group.groupmilestone_set.first()
        self.assertEqual(gms.desc, description)
        self.assertEqual(gms.due.strftime('%m %Y'), due_date.strftime('%m %Y'))
        self.assertEqual(list(gms.docs.all()), [draft])
        
    def test_edit_milestone(self):
        milestone = DatedGroupMilestoneFactory(group=self.group)
        draft = WgDraftFactory()
        WgDraftFactory.create_batch(3)  # some drafts to ignore

        assert(len(draft.name) > 5)
        draft_search_string = draft.name[-5:]

        url = self.absreverse('ietf.group.milestones.edit_milestones;current',
                              kwargs=dict(acronym=self.group.acronym))
        self.login(self.chair.user.username)
        self.driver.get(url)

        # should only be one milestone row - test will fail later if we somehow get the wrong one
        edit_element = self.wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'form#milestones-form div.milestonerow')
            )
        )
        edit_element.click()

        # find the description field corresponding to our milestone
        desc_field = self.wait.until(
            expected_conditions.visibility_of_element_located(
                (By.CSS_SELECTOR, 'input[value="%s"]' % milestone.desc)
            )
        )
        # Get the prefix used to identify inputs related to this milestone
        prefix = desc_field.get_attribute('id')[:-4]  # -4 to strip off 'desc', leave '-'

        due_field = self.driver.find_element_by_id(prefix + 'due')
        hidden_drafts_field = self.driver.find_element_by_id(prefix + 'docs')
        draft_input = self.driver.find_element_by_css_selector(
            'div.select2-container[id*="%s"] input.select2-input' % prefix
        )
        self.assertEqual(due_field.get_attribute('value'), milestone.due.strftime('%B %Y'))
        self.assertEqual(hidden_drafts_field.get_attribute('value'),
                         ','.join([str(doc.pk) for doc in milestone.docs.all()]))

        # modify the fields
        new_due_date = (milestone.due + datetime.timedelta(days=31)).strftime('%m %Y')
        due_field.clear()
        due_field.send_keys(new_due_date + '\n')

        self._search_draft_and_locate_result(draft_input, draft_search_string, draft).click()

        self._click_milestone_submit_button('Review')
        self._assert_milestone_changed()
        self._click_milestone_submit_button('Save')

        # Wait for page to return to group page
        self.wait.until(
            expected_conditions.text_to_be_present_in_element(
                (By.CSS_SELECTOR, 'div#content h1'),
                self.group.name
            )
        )

        expected_desc = milestone.desc
        expected_due_date = new_due_date
        expected_docs = [draft]

        self.assertEqual(self.group.groupmilestone_set.count(), 1)
        gms = self.group.groupmilestone_set.first()
        self.assertEqual(gms.desc, expected_desc)
        self.assertEqual(gms.due.strftime('%m %Y'), expected_due_date)
        self.assertCountEqual(expected_docs, gms.docs.all())
