# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import time
import datetime
import shutil
import os
import re
from unittest import skipIf

import django
from django.utils.text import slugify
from django.db.models import F
import pytz

#from django.test.utils import override_settings

import debug                            # pyflakes:ignore

from ietf.doc.factories import DocumentFactory
from ietf.doc.models import State
from ietf.group import colors
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.group.factories import GroupFactory
from ietf.meeting.factories import SessionFactory, TimeSlotFactory
from ietf.meeting.test_data import make_meeting_test_data, make_interim_meeting
from ietf.meeting.models import (Schedule, SchedTimeSessAssignment, Session,
                                 Room, TimeSlot, Constraint, ConstraintName,
                                 Meeting, SchedulingEvent, SessionStatusName)
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.utils.test_utils import assert_ical_response_is_valid
from ietf.utils.jstest import IetfSeleniumTestCase, ifSeleniumEnabled, selenium_enabled
from ietf import settings

if selenium_enabled():
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions
    from selenium.common.exceptions import NoSuchElementException


@ifSeleniumEnabled
class EditMeetingScheduleTests(IetfSeleniumTestCase):
    def test_edit_meeting_schedule(self):
        meeting = make_meeting_test_data()

        schedule = Schedule.objects.filter(meeting=meeting, owner__user__username="plain").first()

        room1 = Room.objects.get(name="Test Room")
        slot1 = TimeSlot.objects.filter(meeting=meeting, location=room1).order_by('time').first()

        room2 = Room.objects.create(meeting=meeting, name="Test Room2", capacity=1)
        room2.session_types.add('regular')
        slot2 = TimeSlot.objects.create(
            meeting=meeting,
            type_id='regular',
            location=room2,
            duration=datetime.timedelta(hours=2),
            time=slot1.time - datetime.timedelta(minutes=10),
        )

        slot3 = TimeSlot.objects.create(
            meeting=meeting,
            type_id='regular',
            location=room2,
            duration=datetime.timedelta(hours=2),
            time=max(slot1.end_time(), slot2.end_time()) + datetime.timedelta(minutes=10),
        )
        
        slot4 = TimeSlot.objects.create(
            meeting=meeting,
            type_id='regular',
            location=room1,
            duration=datetime.timedelta(hours=2),
            time=slot1.time + datetime.timedelta(days=1),
        )
        
        s1, s2 = Session.objects.filter(meeting=meeting, type='regular')
        s2.requested_duration = slot2.duration + datetime.timedelta(minutes=10)
        s2.save()
        SchedTimeSessAssignment.objects.filter(session=s1).delete()

        s2b = Session.objects.create(meeting=meeting, group=s2.group, attendees=10, requested_duration=datetime.timedelta(minutes=60), type_id='regular')

        SchedulingEvent.objects.create(
            session=s2b,
            status=SessionStatusName.objects.get(slug='appr'),
            by=Person.objects.get(name='(System)'),
        )

        Constraint.objects.create(
            meeting=meeting,
            source=s1.group,
            target=s2.group,
            name=ConstraintName.objects.get(slug="conflict"),
        )

        self.login()
        url = self.absreverse('ietf.meeting.views.edit_meeting_schedule', kwargs=dict(num=meeting.number, name=schedule.name, owner=schedule.owner_email()))
        self.driver.get(url)

        WebDriverWait(self.driver, 2).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '.edit-meeting-schedule')))

        self.assertEqual(len(self.driver.find_elements_by_css_selector('.session')), 3)

        # select - show session info
        s2_element = self.driver.find_element_by_css_selector('#session{}'.format(s2.pk))
        s2_element.click()

        session_info_container = self.driver.find_element_by_css_selector('.session-info-container')
        self.assertIn(s2.group.acronym, session_info_container.find_element_by_css_selector(".title").text)
        self.assertEqual(session_info_container.find_element_by_css_selector(".other-session .time").text, "not yet scheduled")

        # deselect
        self.driver.find_element_by_css_selector('.scheduling-panel').click()

        self.assertEqual(session_info_container.find_elements_by_css_selector(".title"), [])

        # unschedule

        # we would like to do
        #
        # unassigned_sessions_element = self.driver.find_element_by_css_selector('.unassigned-sessions')
        # ActionChains(self.driver).drag_and_drop(s2_element, unassigned_sessions_element).perform()
        #
        # but unfortunately, Selenium does not simulate drag and drop events, see
        #
        #  https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/3604
        #
        # so for the time being we inject the Javascript workaround here and do it from JS
        #
        #  https://storage.googleapis.com/google-code-attachments/selenium/issue-3604/comment-9/drag_and_drop_helper.js

        self.driver.execute_script('!function(s){s.fn.simulateDragDrop=function(t){return this.each(function(){new s.simulateDragDrop(this,t)})},s.simulateDragDrop=function(t,a){this.options=a,this.simulateEvent(t,a)},s.extend(s.simulateDragDrop.prototype,{simulateEvent:function(t,a){var e="dragstart",n=this.createEvent(e);this.dispatchEvent(t,e,n),e="drop";var r=this.createEvent(e,{});r.dataTransfer=n.dataTransfer,this.dispatchEvent(s(a.dropTarget)[0],e,r),e="dragend";var i=this.createEvent(e,{});i.dataTransfer=n.dataTransfer,this.dispatchEvent(t,e,i)},createEvent:function(t){var a=document.createEvent("CustomEvent");return a.initCustomEvent(t,!0,!0,null),a.dataTransfer={data:{},setData:function(t,a){this.data[t]=a},getData:function(t){return this.data[t]}},a},dispatchEvent:function(t,a,e){t.dispatchEvent?t.dispatchEvent(e):t.fireEvent&&t.fireEvent("on"+a,e)}})}(jQuery);')

        self.driver.execute_script("jQuery('#session{}').simulateDragDrop({{dropTarget: '.unassigned-sessions .drop-target'}});".format(s2.pk))

        WebDriverWait(self.driver, 2).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '.unassigned-sessions #session{}'.format(s2.pk))))

        self.assertEqual(list(SchedTimeSessAssignment.objects.filter(session=s2, schedule=schedule)), [])

        # sorting unassigned
        sorted_pks = [s.pk for s in sorted([s1, s2, s2b], key=lambda s: (s.group.acronym, s.requested_duration, s.pk))]
        self.driver.find_element_by_css_selector('[name=sort_unassigned] option[value=name]').click()
        self.assertTrue(self.driver.find_element_by_css_selector('.unassigned-sessions .drop-target #session{} + #session{} + #session{}'.format(*sorted_pks)))

        sorted_pks = [s.pk for s in sorted([s1, s2, s2b], key=lambda s: (s.group.parent.acronym, s.group.acronym, s.requested_duration, s.pk))]
        self.driver.find_element_by_css_selector('[name=sort_unassigned] option[value=parent]').click()
        self.assertTrue(self.driver.find_element_by_css_selector('.unassigned-sessions .drop-target #session{} + #session{}'.format(*sorted_pks)))
        
        sorted_pks = [s.pk for s in sorted([s1, s2, s2b], key=lambda s: (s.requested_duration, s.group.parent.acronym, s.group.acronym, s.pk))]
        self.driver.find_element_by_css_selector('[name=sort_unassigned] option[value=duration]').click()
        self.assertTrue(self.driver.find_element_by_css_selector('.unassigned-sessions .drop-target #session{} + #session{}'.format(*sorted_pks)))
        
        sorted_pks = [s.pk for s in sorted([s1, s2, s2b], key=lambda s: (int(bool(s.comments)), s.group.parent.acronym, s.group.acronym, s.requested_duration, s.pk))]
        self.driver.find_element_by_css_selector('[name=sort_unassigned] option[value=comments]').click()
        self.assertTrue(self.driver.find_element_by_css_selector('.unassigned-sessions .drop-target #session{} + #session{}'.format(*sorted_pks)))

        # schedule
        self.driver.execute_script("jQuery('#session{}').simulateDragDrop({{dropTarget: '#timeslot{} .drop-target'}});".format(s2.pk, slot1.pk))

        WebDriverWait(self.driver, 2).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '#timeslot{} #session{}'.format(slot1.pk, s2.pk))))

        assignment = SchedTimeSessAssignment.objects.get(session=s2, schedule=schedule)
        self.assertEqual(assignment.timeslot, slot1)

        # timeslot constraint hints when selected
        s1_element = self.driver.find_element_by_css_selector('#session{}'.format(s1.pk))
        s1_element.click()

        # violated due to constraints
        self.assertTrue(self.driver.find_elements_by_css_selector('#timeslot{}.would-violate-hint'.format(slot1.pk)))
        # violated due to missing capacity
        self.assertTrue(self.driver.find_elements_by_css_selector('#timeslot{}.would-violate-hint'.format(slot3.pk)))

        # reschedule
        self.driver.execute_script("jQuery('#session{}').simulateDragDrop({{dropTarget: '#timeslot{} .drop-target'}});".format(s2.pk, slot2.pk))

        WebDriverWait(self.driver, 2).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '#timeslot{} #session{}'.format(slot2.pk, s2.pk))))

        assignment = SchedTimeSessAssignment.objects.get(session=s2, schedule=schedule)
        self.assertEqual(assignment.timeslot, slot2)

        # too many attendees warning
        self.assertTrue(self.driver.find_elements_by_css_selector('#session{}.too-many-attendees'.format(s2.pk)))

        # overfull timeslot
        self.assertTrue(self.driver.find_elements_by_css_selector('#timeslot{}.overfull'.format(slot2.pk)))

        # constraint hints
        s1_element.click()
        constraint_element = s2_element.find_element_by_css_selector(".constraints span[data-sessions=\"{}\"].would-violate-hint".format(s1.pk))
        self.assertTrue(constraint_element.is_displayed())

        # current constraint violations
        self.driver.execute_script("jQuery('#session{}').simulateDragDrop({{dropTarget: '#timeslot{} .drop-target'}});".format(s1.pk, slot1.pk))

        WebDriverWait(self.driver, 2).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, '#timeslot{} #session{}'.format(slot1.pk, s1.pk))))

        constraint_element = s2_element.find_element_by_css_selector(".constraints span[data-sessions=\"{}\"].violated-hint".format(s1.pk))
        self.assertTrue(constraint_element.is_displayed())

        # hide sessions in area
        self.assertTrue(s1_element.is_displayed())
        self.driver.find_element_by_css_selector(".session-parent-toggles [value=\"{}\"]".format(s1.group.parent.acronym)).click()
        self.assertTrue(not s1_element.is_displayed())
        self.driver.find_element_by_css_selector(".session-parent-toggles [value=\"{}\"]".format(s1.group.parent.acronym)).click()
        self.assertTrue(s1_element.is_displayed())

        # hide timeslots
        self.driver.find_element_by_css_selector(".timeslot-group-toggles button").click()
        self.assertTrue(self.driver.find_element_by_css_selector("#timeslot-group-toggles-modal").is_displayed())
        self.driver.find_element_by_css_selector("#timeslot-group-toggles-modal [value=\"{}\"]".format("ts-group-{}-{}".format(slot2.time.strftime("%Y%m%d-%H%M"), int(slot2.duration.total_seconds() / 60)))).click()
        self.driver.find_element_by_css_selector("#timeslot-group-toggles-modal [data-dismiss=\"modal\"]").click()
        self.assertTrue(not self.driver.find_element_by_css_selector("#timeslot-group-toggles-modal").is_displayed())

        # swap days
        self.driver.find_element_by_css_selector(".day [data-target=\"#swap-days-modal\"][data-dayid=\"{}\"]".format(slot4.time.date().isoformat())).click()
        self.assertTrue(self.driver.find_element_by_css_selector("#swap-days-modal").is_displayed())
        self.driver.find_element_by_css_selector("#swap-days-modal input[name=\"target_day\"][value=\"{}\"]".format(slot1.time.date().isoformat())).click()
        self.driver.find_element_by_css_selector("#swap-days-modal button[type=\"submit\"]").click()

        self.assertTrue(self.driver.find_elements_by_css_selector('#timeslot{} #session{}'.format(slot4.pk, s1.pk)))

    def test_unassigned_sessions_drop_target_visible_when_empty(self):
        """The drop target for unassigned sessions should not collapse to 0 size

        This test checks that issue #3174 has not regressed. A test that exercises
        moving items from the schedule into the unassigned-sessions area is needed,
        but as of 2021-05-04, Selenium does not support the HTML5 drag-and-drop
        event interface. See:

        https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/3604
        https://gist.github.com/rcorreia/2362544

        Note, however, that the workarounds are inadequate - they do not handle
        all of the events needed by the editor.
        """
        # Set up a meeting and a schedule a plain user can edit
        meeting = make_meeting_test_data()
        schedule = Schedule.objects.filter(meeting=meeting, owner__user__username="plain").first()
        sessions = meeting.session_set.filter(type_id='regular')
        timeslots = meeting.timeslot_set.filter(type_id='regular')
        self.assertGreaterEqual(timeslots.count(), sessions.count(),
                                'Need a timeslot for each session')
        for index, session in enumerate(sessions):
            SchedTimeSessAssignment.objects.create(
                schedule=schedule,
                timeslot=timeslots[index],
                session=session,
            )

        # Open the editor
        self.login()
        url = self.absreverse(
            'ietf.meeting.views.edit_meeting_schedule',
            kwargs=dict(num=meeting.number, name=schedule.name, owner=schedule.owner_email())
        )
        self.driver.get(url)

        # Check that the drop target for unassigned sessions is actually empty
        drop_target = self.driver.find_element_by_css_selector(
            '.unassigned-sessions .drop-target'
        )
        self.assertEqual(len(drop_target.find_elements_by_class_name('session')), 0,
                         'Unassigned sessions box is not empty, test is broken')

        # Check that the drop target has non-zero size
        self.assertGreater(drop_target.size['height'], 0,
                           'Drop target for unassigned sessions collapsed to 0 height')
        self.assertGreater(drop_target.size['width'], 0,
                           'Drop target for unassigned sessions collapsed to 0 width')

@ifSeleniumEnabled
@skipIf(django.VERSION[0]==2, "Skipping test with race conditions under Django 2")
class ScheduleEditTests(IetfSeleniumTestCase):
    def testUnschedule(self):

        meeting = make_meeting_test_data()
        colors.fg_group_colors['FARFUT'] = 'blue'
        colors.bg_group_colors['FARFUT'] = 'white'
        
        self.assertEqual(SchedTimeSessAssignment.objects.filter(session__meeting=meeting, session__group__acronym='mars', schedule__name='test-schedule').count(),1)


        ss = list(SchedTimeSessAssignment.objects.filter(session__meeting__number=72,session__group__acronym='mars',schedule__name='test-schedule')) # pyflakes:ignore

        self.login()
        url = self.absreverse('ietf.meeting.views.edit_schedule',kwargs=dict(num='72',name='test-schedule',owner='plain@example.com'))
        self.driver.get(url)

        # driver.get() will wait for scripts to finish, but not ajax
        # requests.  Wait for completion of the permissions check:
        read_only_note = self.driver.find_element_by_id('read_only')
        WebDriverWait(self.driver, 10).until(expected_conditions.invisibility_of_element(read_only_note), "Read-only schedule")

        s1 = Session.objects.filter(group__acronym='mars', meeting=meeting).first()
        selector = "#session_{}".format(s1.pk)
        WebDriverWait(self.driver, 30).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, selector)), "Did not find %s"%selector)

        self.assertEqual(self.driver.find_elements_by_css_selector("#sortable-list #session_{}".format(s1.pk)), [])

        element = self.driver.find_element_by_id('session_{}'.format(s1.pk))
        target  = self.driver.find_element_by_id('sortable-list')
        ActionChains(self.driver).drag_and_drop(element,target).perform()

        self.assertTrue(self.driver.find_elements_by_css_selector("#sortable-list #session_{}".format(s1.pk)))

        time.sleep(0.1) # The API that modifies the database runs async

        self.assertEqual(SchedTimeSessAssignment.objects.filter(session__meeting__number=72,session__group__acronym='mars',schedule__name='test-schedule').count(),0)

@ifSeleniumEnabled
class SlideReorderTests(IetfSeleniumTestCase):
    def setUp(self):
        super(SlideReorderTests, self).setUp()
        self.session = SessionFactory(meeting__type_id='ietf', status_id='sched')
        self.session.sessionpresentation_set.create(document=DocumentFactory(type_id='slides',name='one'),order=1)
        self.session.sessionpresentation_set.create(document=DocumentFactory(type_id='slides',name='two'),order=2)
        self.session.sessionpresentation_set.create(document=DocumentFactory(type_id='slides',name='three'),order=3)

    def secr_login(self):
        self.login('secretary')

    #@override_settings(DEBUG=True)
    def testReorderSlides(self):
        return
        url = self.absreverse('ietf.meeting.views.session_details',
                  kwargs=dict(
                      num=self.session.meeting.number,
                      acronym = self.session.group.acronym,))
        self.secr_login()
        self.driver.get(url)        
        #debug.show('unicode(self.driver.page_source)')
        second = self.driver.find_element_by_css_selector('#slides tr:nth-child(2)')
        third = self.driver.find_element_by_css_selector('#slides tr:nth-child(3)')
        ActionChains(self.driver).drag_and_drop(second,third).perform()

        time.sleep(0.1) # The API that modifies the database runs async
        names=self.session.sessionpresentation_set.values_list('document__name',flat=True) 
        self.assertEqual(list(names),['one','three','two'])


@ifSeleniumEnabled
class AgendaTests(IetfSeleniumTestCase):
    def setUp(self):
        super(AgendaTests, self).setUp()
        self.meeting = make_meeting_test_data()

    def row_id_for_item(self, item):
        return 'row-%s' % item.slug()

    def get_expected_items(self):
        expected_items = self.meeting.schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
        self.assertGreater(len(expected_items), 0, 'Test setup generated an empty schedule')
        return expected_items

    def test_agenda_view_js_func_parse_query_params(self):
        """Test parse_query_params() function"""
        self.driver.get(self.absreverse('ietf.meeting.views.agenda'))

        parse_query_params = 'return agenda_filter_for_testing.parse_query_params'

        # Only 'show' param
        result = self.driver.execute_script(
            parse_query_params + '("?show=group1,group2,group3");'
        )
        self.assertEqual(result, dict(show='group1,group2,group3'))

        # Only 'hide' param
        result = self.driver.execute_script(
            parse_query_params + '("?hide=group4,group5,group6");'
        )
        self.assertEqual(result, dict(hide='group4,group5,group6'))

        # Both 'show' and 'hide'
        result = self.driver.execute_script(
            parse_query_params + '("?show=group1,group2,group3&hide=group4,group5,group6");'
        )
        self.assertEqual(result, dict(show='group1,group2,group3', hide='group4,group5,group6'))

        # Encoded
        result = self.driver.execute_script(
            parse_query_params + '("?show=%20group1,%20group2,%20group3&hide=group4,group5,group6");'
        )
        self.assertEqual(result, dict(show=' group1, group2, group3', hide='group4,group5,group6'))

    def test_agenda_view_js_func_toggle_list_item(self):
        """Test toggle_list_item() function"""
        self.driver.get(self.absreverse('ietf.meeting.views.agenda'))

        result = self.driver.execute_script(
            """
            // start empty, add item
            var list0=[];
            %(toggle_list_item)s(list0, 'item');
            
            // one item, remove it
            var list1=['item'];
            %(toggle_list_item)s(list1, 'item');
            
            // one item, add another
            var list2=['item1'];
            %(toggle_list_item)s(list2, 'item2');
            
            // multiple items, remove first
            var list3=['item1', 'item2', 'item3'];
            %(toggle_list_item)s(list3, 'item1');
            
            // multiple items, remove middle
            var list4=['item1', 'item2', 'item3'];
            %(toggle_list_item)s(list4, 'item2');
            
            // multiple items, remove last
            var list5=['item1', 'item2', 'item3'];
            %(toggle_list_item)s(list5, 'item3');
            
            return [list0, list1, list2, list3, list4, list5];
            """ % {'toggle_list_item': 'agenda_filter_for_testing.toggle_list_item'}
        )
        self.assertEqual(result[0], ['item'], 'Adding item to empty list failed')
        self.assertEqual(result[1], [], 'Removing only item in a list failed')
        self.assertEqual(result[2], ['item1', 'item2'], 'Adding second item to list failed')
        self.assertEqual(result[3], ['item2', 'item3'], 'Removing first item from list failed')
        self.assertEqual(result[4], ['item1', 'item3'], 'Removing middle item from list failed')
        self.assertEqual(result[5], ['item1', 'item2'], 'Removing last item from list failed')

    def do_agenda_view_filter_test(self, querystring, visible_groups=()):
        self.login()
        self.driver.get(self.absreverse('ietf.meeting.views.agenda') + querystring)
        self.assert_agenda_item_visibility(visible_groups)
        self.assert_agenda_view_filter_matches_ics_filter(querystring)
        weekview_iframe = self.driver.find_element_by_id('weekview')
        if len(querystring) == 0:
            self.assertFalse(weekview_iframe.is_displayed(), 'Weekview should be hidden when filters off')
        else:
            self.assertTrue(weekview_iframe.is_displayed(), 'Weekview should be visible when filters on')
            self.driver.switch_to.frame(weekview_iframe)
            self.assert_weekview_item_visibility(visible_groups)
            self.driver.switch_to.default_content()

    def test_agenda_view_filter_default(self):
        """Filtered agenda view should display only matching rows (all groups selected)"""
        self.do_agenda_view_filter_test('', None)  # None means all should be visible

    def test_agenda_view_filter_show_group(self):
        self.do_agenda_view_filter_test('?show=', [])
        self.do_agenda_view_filter_test('?show=mars', ['mars'])
        self.do_agenda_view_filter_test('?show=mars,ames', ['mars', 'ames'])

    def test_agenda_view_filter_show_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        self.do_agenda_view_filter_test('?show=%s' % area.acronym, ['ames', 'mars'])

    def test_agenda_view_filter_show_type(self):
        self.do_agenda_view_filter_test('?show=reg,break', ['secretariat'])

    def test_agenda_view_filter_show_bof(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        self.do_agenda_view_filter_test('?show=bof', ['mars'])
        self.do_agenda_view_filter_test('?show=bof,ames', ['ames', 'mars'])

    def test_agenda_view_filter_show_ad_office_hours(self):
        area = GroupFactory(type_id='area')
        SessionFactory(
            meeting__type_id='ietf', 
            type_id='other',
            group=area,
            name='%s Office Hours' % area.acronym,
        )
        self.do_agenda_view_filter_test('?show=adofficehours', [area.acronym])

    def test_agenda_view_filter_hide_group(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        area = mars.parent

        # Nothing shown, nothing visible
        self.do_agenda_view_filter_test('?hide=mars', [])
        
        # Group shown
        self.do_agenda_view_filter_test('?show=ames,mars&hide=mars', ['ames'])
        
        # Area shown
        self.do_agenda_view_filter_test('?show=%s&hide=mars' % area.acronym, ['ames'])

        # Type shown
        self.do_agenda_view_filter_test('?show=plenary,regular&hide=mars', ['ames','ietf'])

        # bof shown
        self.do_agenda_view_filter_test('?show=bof&hide=mars', [])


    def test_agenda_view_filter_hide_area(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        area = mars.parent
        SessionFactory(
            meeting__type_id='ietf',
            type_id='other',
            group=area,
            name='%s Office Hours' % area.acronym,
        )

        # Nothing shown
        self.do_agenda_view_filter_test('?hide=%s' % area.acronym, [])
        
        # Group shown
        self.do_agenda_view_filter_test('?show=ames,mars&hide=%s' % area.acronym, [])
        
        # Area shown
        self.do_agenda_view_filter_test('?show=%s&hide=%s' % (area.acronym, area.acronym), [])

        # Type shown
        self.do_agenda_view_filter_test('?show=plenary,regular&hide=%s' % area.acronym, ['ietf'])

        # bof shown
        self.do_agenda_view_filter_test('?show=bof&hide=%s' % area.acronym, [])
        
        # AD office hours shown
        self.do_agenda_view_filter_test('?show=adofficehours&hide=%s' % area.acronym, [])

    def test_agenda_view_filter_hide_type(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        area = mars.parent
        SessionFactory(
            meeting__type_id='ietf',
            type_id='other',
            group=area,
            name='%s Office Hours' % area.acronym,
        )

        # Nothing shown
        self.do_agenda_view_filter_test('?hide=plenary', [])

        # Group shown
        self.do_agenda_view_filter_test('?show=ietf,ames&hide=plenary', ['ames'])

        # Area shown
        self.do_agenda_view_filter_test('?show=%s&hide=regular' % area.acronym, [])

        # Type shown
        self.do_agenda_view_filter_test('?show=plenary,regular&hide=plenary', ['ames', 'mars'])

        # bof shown
        self.do_agenda_view_filter_test('?show=bof&hide=regular', [])

        # AD office hours shown
        self.do_agenda_view_filter_test('?show=adofficehours&hide=other', [])

    def test_agenda_view_filter_hide_bof(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        area = mars.parent

        # Nothing shown
        self.do_agenda_view_filter_test('?hide=bof', [])

        # Group shown
        self.do_agenda_view_filter_test('?show=mars,ames&hide=bof', ['ames'])

        # Area shown
        self.do_agenda_view_filter_test('?show=%s&hide=bof' % area.acronym, ['ames'])

        # Type shown
        self.do_agenda_view_filter_test('?show=regular&hide=bof', ['ames'])

        # bof shown
        self.do_agenda_view_filter_test('?show=bof&hide=bof', [])

    def test_agenda_view_filter_hide_ad_office_hours(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        area = mars.parent
        SessionFactory(
            meeting__type_id='ietf',
            type_id='other',
            group=area,
            name='%s Office Hours' % area.acronym,
        )

        # Nothing shown
        self.do_agenda_view_filter_test('?hide=adofficehours', [])

        # Area shown
        self.do_agenda_view_filter_test('?show=%s&hide=adofficehours' % area.acronym, ['ames', 'mars'])

        # Type shown
        self.do_agenda_view_filter_test('?show=plenary,other&hide=adofficehours', ['ietf'])

        # AD office hours shown
        self.do_agenda_view_filter_test('?show=adofficehours&hide=adofficehours', [])

    def test_agenda_view_filter_whitespace(self):
        self.do_agenda_view_filter_test('?show=  ames , mars &hide=  mars ', ['ames'])

    def assert_agenda_item_visibility(self, visible_groups=None):
        """Assert that correct items are visible in current browser window
        
        If visible_groups is None (the default), expects all items to be visible.
        """
        for item in self.get_expected_items():
            row_id = self.row_id_for_item(item)
            try:
                item_row = self.driver.find_element_by_id(row_id)
            except NoSuchElementException:
                item_row = None
            self.assertIsNotNone(item_row, 'No row for schedule item "%s"' % row_id)
            if visible_groups is None or item.session.group.acronym in visible_groups:
                self.assertTrue(item_row.is_displayed(), 'Row for schedule item "%s" is not displayed but should be' % row_id)
            else:
                self.assertFalse(item_row.is_displayed(), 'Row for schedule item "%s" is displayed but should not be' % row_id)

    def assert_weekview_item_visibility(self, visible_groups=None):
        for item in self.get_expected_items():
            if item.session.name:
                label = item.session.name
            elif item.timeslot.type_id == 'break':
                label = item.timeslot.name
            elif item.session.group:
                label = item.session.group.name
            else:
                label = 'Free Slot'

            try:
                item_div = self.driver.find_element_by_xpath('//div/span[contains(text(),"%s")]/..' % label)
            except NoSuchElementException:
                item_div = None

            if visible_groups is None or item.session.group.acronym in visible_groups:
                self.assertIsNotNone(item_div, 'No weekview entry for "%s" (%s)' % (label, item.slug()))
                self.assertTrue(item_div.is_displayed(), 'Entry for "%s (%s)" is not displayed but should be' % (label, item.slug()))
            else:
                self.assertIsNone(item_div, 'Unexpected weekview entry for "%s" (%s)' % (label, item.slug()))

    @staticmethod
    def open_agenda_filter_ui(wait):
        """Click the 'customize' anchor to reveal the group buttons"""
        customize_anchor = wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '#accordion a[data-toggle="collapse"]')
            )
        )
        customize_anchor.click()
        return customize_anchor

    @staticmethod
    def get_agenda_filter_group_button(wait, group_acronym):
        return wait.until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.pickview.%s' % group_acronym)
            )
        )

    def test_agenda_timeslot_label_visibility(self):
        """The timeslot label for regular sessions should only be shown when a session is visible"""
        wait = WebDriverWait(self.driver, 2)
        url = self.absreverse('ietf.meeting.views.agenda')
        mars_assignments = self.meeting.schedule.assignments.filter(session__group__acronym='mars')
        ames_assignments = self.meeting.schedule.assignments.filter(session__group__acronym='ames')
        assert(mars_assignments.count() == 1)  # if not, need to update test
        assert(ames_assignments.count() == 1)  # if not, need to update test
        assignments = dict(
            mars=mars_assignments.first(),
            ames=ames_assignments.first(),
        )
        # test relies on these timeslots being different so they will have separate label rows
        assert(assignments['mars'].timeslot.time != assignments['ames'].timeslot.time)
        label_row_selectors = {
            grp: (By.CSS_SELECTOR, 'tr.session-label-row[data-slot-start-ts="{}"][data-slot-end-ts="{}"]'.format(
                int(assignment.timeslot.utc_start_time().timestamp()),
                int(assignment.timeslot.utc_end_time().timestamp()),
            ))
            for grp, assignment in assignments.items()
        }

        self.login()

        # get page with all items visible
        self.driver.get(url)
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['ames']))
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['mars']))

        # get page with ames hidden
        self.driver.get(url + '?show=mars&hide=ames')
        wait.until(expected_conditions.invisibility_of_element_located(label_row_selectors['ames']))
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['mars']))

        # get page with mars hidden
        self.driver.get(url + '?show=ames&hide=mars')
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['ames']))
        wait.until(expected_conditions.invisibility_of_element_located(label_row_selectors['mars']))

        # create an ames session in the mars timeslot, should cause the mars timeslot label to reappear
        sess = SessionFactory(group=Group.objects.get(acronym='ames'),
                              meeting=self.meeting,
                              add_to_schedule=False)
        sess.timeslotassignments.create(timeslot=assignments['mars'].timeslot,
                                        schedule=self.meeting.schedule)
        self.driver.get(url + '?show=ames&hide=mars')
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['ames']))
        wait.until(expected_conditions.visibility_of_element_located(label_row_selectors['mars']))

        # get page with ames and mars hidden
        self.driver.get(url + '?hide=ames,mars')
        wait.until(expected_conditions.invisibility_of_element_located(label_row_selectors['ames']))
        wait.until(expected_conditions.invisibility_of_element_located(label_row_selectors['mars']))

    def test_agenda_view_group_filter_toggle(self):
        """Clicking a group toggle enables/disables agenda filtering"""
        wait = WebDriverWait(self.driver, 2)
        group_acronym = 'mars'

        self.login()
        url = self.absreverse('ietf.meeting.views.agenda')
        self.driver.get(url)
        
        self.open_agenda_filter_ui(wait)
        
        # Click the group button
        group_button = self.get_agenda_filter_group_button(wait, group_acronym)
        group_button.click()

        # Check visibility
        self.assert_agenda_item_visibility([group_acronym])
        
        # Click the group button again
        group_button.click()

        # Check visibility
        self.assert_agenda_item_visibility()

    def test_agenda_view_team_group_filter_toggle(self):
        """'Team' group sessions should not respond to area filter button

        Sessions belonging to 'team' groups should not respond to their parent buttons. This prevents,
        e.g., 'hackathon', or 'tools' group sessions from being shown/hidden when their parent group
        filter button is clicked. 
        """
        def _schedule_session(meeting, session):
            """Schedule a session, guaranteeing that it is not in a private timeslot"""
            SchedTimeSessAssignment.objects.create(
                schedule=meeting.schedule,
                timeslot=TimeSlotFactory(meeting=meeting),
                session=session,
            )

        wait = WebDriverWait(self.driver, 10)
        meeting = Meeting.objects.get(type_id='ietf')
        parent_group = GroupFactory(type_id='area')
        other_group = GroupFactory(parent=parent_group, type_id='wg')
        hackathon_group = GroupFactory(acronym='hackathon', type_id='team', parent=parent_group)

        # hackathon session
        #
        # Add to schedule ourselves because the default scheduling sometimes puts the session
        # in a private timeslot, preventing the session from appearing on the agenda and breaking
        # the test.
        _schedule_session(
            meeting,
            SessionFactory(
                meeting=meeting,
                type_id='other',
                group=hackathon_group,
                name='Hackathon',
                add_to_schedule=False
            )
        )

        # Session to cause the parent_group to appear in the filter UI tables.
        _schedule_session(
            meeting,
            SessionFactory(meeting=meeting, type_id='regular', group=other_group, add_to_schedule=False)
        )

        self.login()
        url = self.absreverse('ietf.meeting.views.agenda')
        self.driver.get(url)

        self.open_agenda_filter_ui(wait)

        self.get_agenda_filter_group_button(wait, 'mars').click()
        self.assert_agenda_item_visibility(['mars'])

        # enable hackathon group
        group_button = self.get_agenda_filter_group_button(wait, 'hackathon')
        group_button.click()
        self.assert_agenda_item_visibility(['mars', 'hackathon'])

        # disable hackathon group
        group_button.click()
        self.assert_agenda_item_visibility(['mars'])

        # clicking area should not show the hackathon
        self.get_agenda_filter_group_button(wait, parent_group.acronym).click()
        self.assert_agenda_item_visibility(['mars', other_group.acronym])

    def test_agenda_view_group_filter_toggle_without_replace_state(self):
        """Toggle should function for browsers without window.history.replaceState"""
        group_acronym = 'mars'

        self.login()
        url = self.absreverse('ietf.meeting.views.agenda')
        self.driver.get(url)
        
        # Rather than digging up an ancient browser, simulate absence of history.replaceState
        self.driver.execute_script('window.history.replaceState = undefined;')

        
        # Click the 'customize' anchor to reveal the group buttons
        customize_anchor = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '#accordion a[data-toggle="collapse"]')
            )
        )
        customize_anchor.click()

        
        # Get ready to click the group button
        group_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.pickview.%s' % group_acronym)
            )
        )

        # Be sure we're at the URL we think we're at before we click
        self.assertEqual(self.driver.current_url, url)
        group_button.click()  # click!

        expected_url = '%s?show=%s' % (url, group_acronym)
        WebDriverWait(self.driver, 2).until(expected_conditions.url_to_be(expected_url))
        # no assertion here - if WebDriverWait raises an exception, the test will fail.
        # We separately test whether this URL will filter correctly.

    def session_from_agenda_row_id(self, row_id):
        """Find session corresponding to a row in the agenda HTML"""
        components = row_id.split('-', 8)
        # for regular session:
        #   row-<meeting#>-<year>-<month>-<day>-<DoW>-<HHMM>-<parent acro>-<group acro>
        # for plenary session:
        #   row-<meeting#>-<year>-<month>-<day>-<DoW>-<HHMM>-1plenary-<group acro>
        # for others (break, reg, other):
        #   row-<meeting#>-<year>-<month>-<day>-<DoW>-<HHMM>-<group acro>-<session name slug>
        meeting_number = components[1]
        start_time = datetime.datetime(
            year=int(components[2]),
            month=int(components[3]),
            day=int(components[4]),
            hour=int(components[6][0:2]),
            minute=int(components[6][2:4]),
        )
        # If labeled as plenary, it's plenary...
        if components[7] == '1plenary':
            session_type = 'plenary'
            group = Group.objects.get(acronym=components[8])
        else:
            # If not a plenary, see if the last component is a group
            try:
                group = Group.objects.get(acronym=components[8])
            except Group.DoesNotExist:
                # Last component was not a group, so this must not be a regular session
                session_type = 'other'
                group = Group.objects.get(acronym=components[7])
            else:
                # Last component was a group, this is a regular session
                session_type = 'regular'
        
        meeting = Meeting.objects.get(number=meeting_number)
        possible_assignments = SchedTimeSessAssignment.objects.filter(
            schedule__in=[meeting.schedule, meeting.schedule.base],
            timeslot__time=start_time,
        )
        if session_type == 'other':
            possible_sessions = [pa.session for pa in possible_assignments.filter(
                timeslot__type_id__in=['break', 'reg', 'other'], session__group=group
            ) if slugify(pa.session.name) == components[8]]
            if len(possible_sessions) != 1:
                raise ValueError('No unique matching session for row %s (found %d)' % (
                    row_id, len(possible_sessions)
                ))
            session = possible_sessions[0]
        else:
            session = possible_assignments.filter(
                timeslot__type_id=session_type
            ).get(session__group=group).session
        return session, possible_assignments.get(session=session).timeslot

    def assert_agenda_view_filter_matches_ics_filter(self, filter_string):
        """The agenda view and ics view should show the same events for a given filter
        
        This must be called after using self.driver.get to load the agenda page
        to be checked.
        """
        ics_url = self.absreverse('ietf.meeting.views.agenda_ical')
        
        # parse out the events
        agenda_rows = self.driver.find_elements_by_css_selector('[id^="row-"]')
        visible_rows = [r for r in agenda_rows if r.is_displayed()]
        sessions = [self.session_from_agenda_row_id(row.get_attribute("id")) 
                    for row in visible_rows]
        r = self.client.get(ics_url + filter_string)
        # verify that all expected sessions are found
        expected_uids = [
            'ietf-%s-%s-%s' % (session.meeting.number, timeslot.pk, session.group.acronym) 
            for (session, timeslot) in sessions
        ]
        assert_ical_response_is_valid(self, r, 
                                      expected_event_uids=expected_uids,
                                      expected_event_count=len(sessions))

    def test_session_materials_modal(self):
        """Test opening and re-opening a session materals modal

        This currently only tests the slides to ensure that changes to these are picked up
        without reloading the main agenda page. This should also test that the agenda and
        minutes are displayed and updated correctly, but problems with WebDriver/Selenium/Chromedriver
        are blocking this.
        """
        session = self.meeting.session_set.filter(group__acronym="mars").first()
        assignment = session.official_timeslotassignment()
        slug = assignment.slug()

        url = self.absreverse('ietf.meeting.views.agenda')
        self.driver.get(url)

        # modal should start hidden
        modal_div = self.driver.find_element_by_css_selector('div#modal-%s' % slug)
        self.assertFalse(modal_div.is_displayed())

        # Click the 'materials' button
        open_modal_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-target="#modal-%s"]' % slug)
            ),
            'Modal open button not found or not clickable',
        )
        open_modal_button.click()
        WebDriverWait(self.driver, 2).until(
            expected_conditions.visibility_of(modal_div),
            'Modal did not become visible after clicking open button',
        )

        # Check that we have the expected slides
        not_deleted_slides = session.materials.filter(
            type='slides'
        ).exclude(
            states__type__slug='slides',states__slug='deleted'
        )
        self.assertGreater(not_deleted_slides.count(), 0)  # make sure this isn't a pointless test
        for slide in not_deleted_slides:
            anchor = self.driver.find_element_by_xpath('//a[text()="%s"]' % slide.title)
            self.assertIsNotNone(anchor)

        deleted_slides = session.materials.filter(
            type='slides', states__type__slug='slides', states__slug='deleted'
        )
        self.assertGreater(deleted_slides.count(), 0)  # make sure this isn't a pointless test
        for slide in deleted_slides:
            with self.assertRaises(NoSuchElementException):
                self.driver.find_element_by_xpath('//a[text()="%s"]' % slide.title)

        # Now close the modal
        close_modal_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '.modal-footer button[data-dismiss="modal"]')
            ),
            'Modal close button not found or not clickable',
        )
        close_modal_button.click()
        WebDriverWait(self.driver, 2).until(
            expected_conditions.invisibility_of_element(modal_div),
            'Modal was not hidden after clicking close button',
        )

        # Modify the session info
        newly_deleted_slide = not_deleted_slides.first()
        newly_undeleted_slide = deleted_slides.first()
        newly_deleted_slide.set_state(State.objects.get(type="slides", slug="deleted"))
        newly_undeleted_slide.set_state(State.objects.get(type="slides", slug="active"))

        # Click the 'materials' button
        open_modal_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-target="#modal-%s"]' % slug)
            ),
            'Modal open button not found or not clickable for refresh test',
        )
        open_modal_button.click()
        WebDriverWait(self.driver, 2).until(
            expected_conditions.visibility_of(modal_div),
            'Modal did not become visible after clicking open button for refresh test',
        )

        # Check that we now see the updated slides
        not_deleted_slides = session.materials.filter(
            type='slides'
        ).exclude(
            states__type__slug='slides',states__slug='deleted'
        )
        self.assertNotIn(newly_deleted_slide, not_deleted_slides)
        self.assertIn(newly_undeleted_slide, not_deleted_slides)
        for slide in not_deleted_slides:
            anchor = self.driver.find_element_by_xpath('//a[text()="%s"]' % slide.title)
            self.assertIsNotNone(anchor)

        deleted_slides = session.materials.filter(
            type='slides', states__type__slug='slides', states__slug='deleted'
        )
        self.assertIn(newly_deleted_slide, deleted_slides)
        self.assertNotIn(newly_undeleted_slide, deleted_slides)
        for slide in deleted_slides:
            with self.assertRaises(NoSuchElementException):
                self.driver.find_element_by_xpath('//a[text()="%s"]' % slide.title)

    def test_agenda_time_zone_selection(self):
        self.assertNotEqual(self.meeting.time_zone, 'UTC', 'Meeting time zone must not be UTC')

        wait = WebDriverWait(self.driver, 2)
        self.driver.get(self.absreverse('ietf.meeting.views.agenda'))

        # wait for the select box to be updated - look for an arbitrary time zone to be in
        # its options list to detect this
        arbitrary_tz = 'America/Halifax'
        arbitrary_tz_opt = WebDriverWait(self.driver, 2).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, '#timezone-select > option[value="%s"]' % arbitrary_tz)
            )
        )

        tz_select_input = self.driver.find_element_by_id('timezone-select')
        meeting_tz_link = self.driver.find_element_by_id('meeting-timezone')
        local_tz_link = self.driver.find_element_by_id('local-timezone')
        utc_tz_link = self.driver.find_element_by_id('utc-timezone')
        tz_displays = self.driver.find_elements_by_css_selector('.current-tz')
        self.assertGreaterEqual(len(tz_displays), 1)
        # we'll check that all current-tz elements are updated, but first check that at least one is in the nav sidebar
        self.assertIsNotNone(self.driver.find_element_by_css_selector('.nav .current-tz'))

        # Moment.js guesses local time zone based on the behavior of Selenium's web client. This seems
        # to inherit Django's settings.TIME_ZONE but I don't know whether that's guaranteed to be consistent.
        # To avoid test fragility, ask Moment what it considers local and expect that.
        local_tz = self.driver.execute_script('return moment.tz.guess();')
        self.assertNotEqual(self.meeting.time_zone, local_tz, 'Meeting time zone must not be local time zone')
        self.assertNotEqual(local_tz, 'UTC', 'Local time zone must not be UTC')

        meeting_tz_opt = tz_select_input.find_element_by_css_selector('option[value="%s"]' % self.meeting.time_zone)
        local_tz_opt = tz_select_input.find_element_by_css_selector('option[value="%s"]' % local_tz)
        utc_tz_opt = tz_select_input.find_element_by_css_selector('option[value="UTC"]')

        # Should start off in meeting time zone
        self.assertTrue(meeting_tz_opt.is_selected())
        # don't yet know local_tz, so can't check that it's deselected here
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), self.meeting.time_zone)

        # Click 'local' button
        local_tz_link.click()
        wait.until(expected_conditions.element_selection_state_to_be(meeting_tz_opt, False))
        self.assertFalse(meeting_tz_opt.is_selected())
        # just identified the local_tz_opt as being selected, so no check here, either
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), local_tz)

        # click 'utc' button
        utc_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(utc_tz_opt))
        self.assertFalse(meeting_tz_opt.is_selected())
        self.assertFalse(local_tz_opt.is_selected())  # finally!
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertTrue(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), 'UTC')

        # click back to meeting
        meeting_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(meeting_tz_opt))
        self.assertTrue(meeting_tz_opt.is_selected())
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), self.meeting.time_zone)

        # and then back to UTC...
        utc_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(utc_tz_opt))
        self.assertFalse(meeting_tz_opt.is_selected())
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertTrue(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), 'UTC')

        # ... and test the switch from UTC to local
        local_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(local_tz_opt))
        self.assertFalse(meeting_tz_opt.is_selected())
        self.assertTrue(local_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), local_tz)

        # Now select a different item from the select input
        arbitrary_tz_opt.click()
        wait.until(expected_conditions.element_to_be_selected(arbitrary_tz_opt))
        self.assertFalse(meeting_tz_opt.is_selected())
        self.assertFalse(local_tz_opt.is_selected())
        self.assertTrue(arbitrary_tz_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        for disp in tz_displays:
            self.assertEqual(disp.text.strip(), arbitrary_tz)
    
    def test_agenda_time_zone_selection_updates_weekview(self):
        """Changing the time zone should update the weekview to match"""
        class in_iframe_href:
            """Condition class for use with WebDriverWait"""
            def __init__(self, fragment, iframe):
                self.fragment = fragment
                self.iframe = iframe

            def __call__(self, driver):
                driver.switch_to.frame(self.iframe)
                current_href= driver.execute_script(
                    'return document.location.href'
                )
                driver.switch_to.default_content()
                return self.fragment in current_href
            
        # enable a filter so the weekview iframe is visible
        self.driver.get(self.absreverse('ietf.meeting.views.agenda') + '?show=mars')
        # wait for the select box to be updated - look for an arbitrary time zone to be in
        # its options list to detect this
        wait = WebDriverWait(self.driver, 2)
        option = wait.until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, '#timezone-select > option[value="America/Halifax"]'))
        )
        # Now select a different item from the select input
        option.click()
        try:
            wait.until(in_iframe_href('tz=america/halifax', 'weekview'))
        except:
            self.fail('iframe href not updated to contain selected time zone')
        

@ifSeleniumEnabled
class WeekviewTests(IetfSeleniumTestCase):
    def setUp(self):
        super(WeekviewTests, self).setUp()
        self.meeting = make_meeting_test_data()

    def get_expected_items(self):
        expected_items = self.meeting.schedule.assignments.exclude(timeslot__type__in=['lead', 'offagenda'])
        self.assertGreater(len(expected_items), 0, 'Test setup generated an empty schedule')
        return expected_items

    def test_timezone_default(self):
        """Week view should show UTC times by default"""
        self.assertNotEqual(self.meeting.time_zone.lower(), 'utc',
                            'Cannot test local time weekview because meeting is using UTC time.')
        self.login()
        self.driver.get(self.absreverse('ietf.meeting.views.week_view'))
        for item in self.get_expected_items():
            if item.session.name:
                expected_name = item.session.name
            elif item.timeslot.type_id == 'break':
                expected_name = item.timeslot.name
            else:
                expected_name = item.session.group.name
            expected_time = '-'.join([item.timeslot.utc_start_time().strftime('%H%M'),
                                      item.timeslot.utc_end_time().strftime('%H%M')])
            WebDriverWait(self.driver, 2).until(
                expected_conditions.presence_of_element_located(
                    (By.XPATH, 
                     '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                         expected_time, expected_name))
                )
            )

    def test_timezone_selection(self):
        """Week view should show time zones when requested"""
        # Must test utc; others are picked arbitrarily
        zones_to_test = ['utc', 'America/Halifax', 'Asia/Bangkok', 'Africa/Dakar', 'Europe/Dublin']
        self.login()
        for zone_name in zones_to_test:
            zone = pytz.timezone(zone_name)
            self.driver.get(self.absreverse('ietf.meeting.views.week_view') + '?tz=' + zone_name)
            for item in self.get_expected_items():
                if item.session.name:
                    expected_name = item.session.name
                elif item.timeslot.type_id == 'break':
                    expected_name = item.timeslot.name
                else:
                    expected_name = item.session.group.name

                start_time = item.timeslot.utc_start_time().astimezone(zone)
                end_time = item.timeslot.utc_end_time().astimezone(zone)
                expected_time = '-'.join([start_time.strftime('%H%M'),
                                          end_time.strftime('%H%M')])

                WebDriverWait(self.driver, 2).until(
                    expected_conditions.presence_of_element_located(
                        (By.XPATH, 
                         '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                             expected_time, expected_name))
                    ),
                    'Could not find event "%s" at %s for time zone %s' % (expected_name, 
                                                                          expected_time,
                                                                          zone_name),
                )

    def test_event_wrapping(self):
        """Events that overlap midnight should be shown on both days
        
        This assumes that the meeting is in US/Eastern timezone.
        """
        def _assert_wrapped(displayed, expected_time_string):
            self.assertEqual(len(displayed), 2)
            first = displayed[0]
            first_parent = first.find_element_by_xpath('..')
            second = displayed[1]
            second_parent = second.find_element_by_xpath('..')
            self.assertNotIn('continued', first.text)
            self.assertIn(expected_time_string, first_parent.text)
            self.assertIn('continued', second.text)
            self.assertIn(expected_time_string, second_parent.text)

        def _assert_not_wrapped(displayed, expected_time_string):
            self.assertEqual(len(displayed), 1)
            first = displayed[0]
            first_parent = first.find_element_by_xpath('..')
            self.assertNotIn('continued', first.text)
            self.assertIn(expected_time_string, first_parent.text)

        duration = datetime.timedelta(minutes=120)  # minutes
        local_tz = self.meeting.time_zone
        self.assertEqual(local_tz.lower(), 'us/eastern',
                         'Test logic error - meeting local time zone must be US/Eastern')

        # Session during a single day in meeting local time but multi-day UTC
        # Compute a time that overlaps midnight, UTC, but won't when shifted to a local time zone
        start_time_utc = pytz.timezone('UTC').localize(
            datetime.datetime.combine(self.meeting.date, datetime.time(23,0))
        )
        start_time_local = start_time_utc.astimezone(pytz.timezone(self.meeting.time_zone))

        daytime_session = SessionFactory(
            meeting=self.meeting,
            name='Single Day Session for Wrapping Test',
            add_to_schedule=False,
        )
        daytime_timeslot = TimeSlotFactory(
            meeting=self.meeting,
            time=start_time_local.replace(tzinfo=None),  # drop timezone for Django
            duration=duration,
        )
        daytime_session.timeslotassignments.create(timeslot=daytime_timeslot, schedule=self.meeting.schedule)

        # Session that overlaps midnight in meeting local time
        overnight_session = SessionFactory(
            meeting=self.meeting,
            name='Overnight Session for Wrapping Test',
            add_to_schedule=False,
        )
        overnight_timeslot = TimeSlotFactory(
            meeting=self.meeting,
            time=datetime.datetime.combine(self.meeting.date, datetime.time(23,0)),
            duration=duration,
        )
        overnight_session.timeslotassignments.create(timeslot=overnight_timeslot, schedule=self.meeting.schedule)

        # Check assumptions about events overlapping midnight
        self.assertEqual(daytime_timeslot.local_start_time().day,
                         daytime_timeslot.local_end_time().day,
                         'Daytime event should not overlap midnight in local time')
        self.assertNotEqual(daytime_timeslot.utc_start_time().day,
                           daytime_timeslot.utc_end_time().day,
                           'Daytime event should overlap midnight in UTC')

        self.assertNotEqual(overnight_timeslot.local_start_time().day,
                            overnight_timeslot.local_end_time().day,
                            'Overnight event should overlap midnight in local time')
        self.assertEqual(overnight_timeslot.utc_start_time().day,
                         overnight_timeslot.utc_end_time().day,
                         'Overnight event should not overlap midnight in UTC')

        self.login()
        
        # Test in meeting local time
        self.driver.get(self.absreverse('ietf.meeting.views.week_view') + '?tz=%s' % local_tz.lower())

        time_string = '-'.join([daytime_timeslot.local_start_time().strftime('%H%M'),
                                daytime_timeslot.local_end_time().strftime('%H%M')])
        displayed = WebDriverWait(self.driver, 2).until(
            expected_conditions.presence_of_all_elements_located(
                (By.XPATH,
                 '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                     time_string,
                     daytime_session.name))
            )
        )
        _assert_not_wrapped(displayed, time_string)

        time_string = '-'.join([overnight_timeslot.local_start_time().strftime('%H%M'),
                                overnight_timeslot.local_end_time().strftime('%H%M')])
        displayed = WebDriverWait(self.driver, 2).until(
            expected_conditions.presence_of_all_elements_located(
                (By.XPATH,
                 '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                     time_string,
                     overnight_session.name))
            )
        )
        _assert_wrapped(displayed, time_string)

        # Test in utc time
        self.driver.get(self.absreverse('ietf.meeting.views.week_view') + '?tz=utc')

        time_string = '-'.join([daytime_timeslot.utc_start_time().strftime('%H%M'),
                                daytime_timeslot.utc_end_time().strftime('%H%M')])
        displayed = WebDriverWait(self.driver, 2).until(
            expected_conditions.presence_of_all_elements_located(
                (By.XPATH,
                 '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                     time_string,
                     daytime_session.name))
            )
        )
        _assert_wrapped(displayed, time_string)

        time_string = '-'.join([overnight_timeslot.utc_start_time().strftime('%H%M'),
                                overnight_timeslot.utc_end_time().strftime('%H%M')])
        displayed = WebDriverWait(self.driver, 2).until(
            expected_conditions.presence_of_all_elements_located(
                (By.XPATH,
                 '//div/div[contains(text(), "%s")]/span[contains(text(), "%s")]' % (
                     time_string,
                     overnight_session.name))
            )
        )
        _assert_not_wrapped(displayed, time_string)

@ifSeleniumEnabled
class InterimTests(IetfSeleniumTestCase):
    def setUp(self):
        super(InterimTests, self).setUp()
        self.materials_dir = self.tempdir('materials')
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir
        self.meeting = make_meeting_test_data(create_interims=True)

        # Create a group with a plenary interim session for testing type filters
        somegroup = GroupFactory(acronym='sg', name='Some Group')
        sg_interim = make_interim_meeting(somegroup, datetime.date.today() + datetime.timedelta(days=20))
        sg_sess = sg_interim.session_set.first()
        sg_slot = sg_sess.timeslotassignments.first().timeslot
        sg_sess.type_id = 'plenary'
        sg_slot.type_id = 'plenary'
        sg_sess.save()
        sg_slot.save()


    def tearDown(self):
        settings.AGENDA_PATH = self.saved_agenda_path
        shutil.rmtree(self.materials_dir)
        super(InterimTests, self).tearDown()

    def tempdir(self, label):
        # Borrowed from  test_utils.TestCase
        slug = slugify(self.__class__.__name__.replace('.','-'))
        dirname = "tmp-{label}-{slug}-dir".format(**locals())
        if 'VIRTUAL_ENV' in os.environ:
            dirname = os.path.join(os.environ['VIRTUAL_ENV'], dirname)
        path = os.path.abspath(dirname)
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    def displayed_interims(self, groups=None):
        sessions = add_event_info_to_session_qs(
            Session.objects.filter(
                meeting__type_id='interim',
                timeslotassignments__schedule=F('meeting__schedule'),
                timeslotassignments__timeslot__time__gte=datetime.datetime.today()
            )
        ).filter(current_status__in=('sched','canceled'))
        meetings = []
        for s in sessions:
            if groups is None or s.group.acronym in groups:
                s.meeting.calendar_label = s.group.acronym  # annotate with group
                meetings.append(s.meeting)
        return meetings

    def all_ietf_meetings(self):
        meetings = Meeting.objects.filter(
            type_id='ietf',
            date__gte=datetime.datetime.today()-datetime.timedelta(days=7)
        )
        for m in meetings:
            m.calendar_label = 'IETF %s' % m.number
        return meetings

    def find_upcoming_meeting_entries(self):
        return self.driver.find_elements_by_css_selector(
            'table#upcoming-meeting-table a.ietf-meeting-link, table#upcoming-meeting-table a.interim-meeting-link'
        )

    def assert_upcoming_meeting_visibility(self, visible_meetings=None):
        """Assert that correct items are visible in current browser window

        If visible_meetings is None (the default), expects all items to be visible.
        """
        expected = {mtg.number for mtg in visible_meetings}
        not_visible = set()
        unexpected = set()
        entries = self.find_upcoming_meeting_entries()
        for entry in entries:
            entry_text = entry.get_attribute('innerHTML').strip()  # gets text, even if element is hidden
            nums = [n for n in expected if n in entry_text]
            self.assertLessEqual(len(nums), 1, 'Multiple matching meeting numbers')
            if len(nums) > 0:  # asserted that it's at most 1, so if it's not 0, it's 1.
                expected.remove(nums[0])
                if not entry.is_displayed():
                    not_visible.add(nums[0])
                continue
            # Found an unexpected row - this is only a problem if it is visible
            if entry.is_displayed():
                unexpected.add(entry_text)

        self.assertEqual(expected, set(), "Missing entries for expected iterim meetings.")
        self.assertEqual(not_visible, set(), "Hidden rows for expected interim meetings.")
        self.assertEqual(unexpected, set(), "Unexpected row visible")

    def assert_upcoming_meeting_calendar(self, visible_meetings=None):
        """Assert that correct items are sent to the calendar"""
        def advance_month():
            button = WebDriverWait(self.driver, 2).until(
                expected_conditions.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'div#calendar button.fc-next-button')))
            button.click()

        seen = set()
        not_visible = set()
        unexpected = set()

        # Test that we see all the expected meetings when we scroll through the
        # entire year. We only check the group names / IETF numbers. This should
        # be good enough to catch filtering errors but does not validate the
        # details of what's shown on the calendar. Need 13 iterations instead of
        # 12 in order to check the starting month of the following year, which
        # will usually contain the day 1 year from the start date.
        for _ in range(13):
            entries = self.driver.find_elements_by_css_selector(
                'div#calendar div.fc-content'
            )
            for entry in entries:
                meetings = [m for m in visible_meetings if m.calendar_label in entry.text]
                if len(meetings) > 0:
                    seen.add(meetings[0])
                    if not entry.is_displayed():
                        not_visible.add(meetings[0])
                    continue
                # Found an unexpected row - this is ok as long as it's hidden
                if entry.is_displayed():
                    unexpected.add(entry.text)
            advance_month()

        self.assertEqual(seen, visible_meetings, "Expected calendar entries not shown.")
        self.assertEqual(not_visible, set(), "Hidden calendar entries for expected interim meetings.")
        self.assertEqual(unexpected, set(), "Unexpected calendar entries visible")

    def do_upcoming_view_filter_test(self, querystring, visible_meetings=()):
        self.login()
        self.driver.get(self.absreverse('ietf.meeting.views.upcoming') + querystring)
        self.assert_upcoming_meeting_visibility(visible_meetings)
        self.assert_upcoming_meeting_calendar(visible_meetings)
        self.assert_upcoming_view_filter_matches_ics_filter(querystring)

        # Check the ical links
        simplified_querystring = querystring.replace(' ', '%20')  # encode spaces'
        ics_link = self.driver.find_element_by_link_text('Download as .ics')
        self.assertIn(simplified_querystring, ics_link.get_attribute('href'))
        webcal_link = self.driver.find_element_by_link_text('Subscribe with webcal')
        self.assertIn(simplified_querystring, webcal_link.get_attribute('href'))

    def assert_upcoming_view_filter_matches_ics_filter(self, filter_string):
        """The upcoming view and ics view should show matching events for a given filter

        The upcoming ics view shows more detail than the upcoming view, so this
        test expands the upcoming meeting list into the corresponding set of expected
        sessions.
 
        This must be called after using self.driver.get to load the upcoming page
        to be checked.
        """
        ics_url = self.absreverse('ietf.meeting.views.upcoming_ical')

        # parse out the meetings shown on the upcoming view
        upcoming_meetings = self.find_upcoming_meeting_entries()
        visible_meetings = [mtg for mtg in upcoming_meetings if mtg.is_displayed()]
        
        # Have list of meetings, now get sessions that should be shown
        expected_ietfs = []
        expected_interim_sessions = []
        expected_schedules = []
        for meeting_elt in visible_meetings:
            # meeting_elt is an anchor element
            label_text = meeting_elt.get_attribute('innerHTML')
            match = re.search(r'(?P<ietf>IETF\s+)?(?P<number>\S+)', label_text)
            meeting = Meeting.objects.get(number=match.group('number'))
            if match.group('ietf'):
                expected_ietfs.append(meeting)
            else:
                expected_interim_sessions.extend([s.pk for s in meeting.session_set.all()])
                if meeting.schedule:
                    expected_schedules.extend([meeting.schedule, meeting.schedule.base])
        
        # Now find the sessions we expect to see - should match the upcoming_ical view
        expected_assignments = list(SchedTimeSessAssignment.objects.filter(
            schedule__in=expected_schedules,
            session__in=expected_interim_sessions,
            timeslot__time__gte=datetime.date.today(),
        ))
        # The UID formats should match those in the upcoming.ics template
        expected_uids = [
            'ietf-%s-%s' % (item.session.meeting.number, item.timeslot.pk)
            for item in expected_assignments
        ] + [
            'ietf-%s' % (ietf.number) for ietf in expected_ietfs
        ]
        r = self.client.get(ics_url + filter_string)
        assert_ical_response_is_valid(self, r,
                                      expected_event_uids=expected_uids,
                                      expected_event_count=len(expected_uids))

    def test_upcoming_view_default(self):
        """By default, all upcoming interims and IETF meetings should be displayed"""
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('', ietf_meetings.union(self.displayed_interims()))

    def test_upcoming_view_filter_show_group(self):
        # Show none
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?show=', ietf_meetings)

        # Show one
        self.do_upcoming_view_filter_test('?show=mars', 
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['mars'])
                                          ))

        # Show two
        self.do_upcoming_view_filter_test('?show=mars,ames', 
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['mars', 'ames'])
                                          ))

    def test_upcoming_view_filter_show_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?show=%s' % area.acronym,
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['mars', 'ames'])
                                          ))

    def test_upcoming_view_filter_show_type(self):
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?show=plenary',
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['sg'])
                                          ))

    def test_upcoming_view_filter_hide_group(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent

        # Without anything shown, should see only ietf meetings
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?hide=mars', ietf_meetings)

        # With group shown
        self.do_upcoming_view_filter_test('?show=ames,mars&hide=mars',
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['ames'])
                                          ))
        # With area shown
        self.do_upcoming_view_filter_test('?show=%s&hide=mars' % area.acronym, 
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['ames'])
                                          ))

        # With type shown
        self.do_upcoming_view_filter_test('?show=plenary&hide=sg',
                                          ietf_meetings)

    def test_upcoming_view_filter_hide_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent

        # Without anything shown, should see only ietf meetings
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?hide=%s' % area.acronym, ietf_meetings)

        # With area shown
        self.do_upcoming_view_filter_test('?show=%s&hide=%s' % (area.acronym, area.acronym),
                                          ietf_meetings)

        # With group shown
        self.do_upcoming_view_filter_test('?show=mars&hide=%s' % area.acronym, ietf_meetings)

        # With type shown
        self.do_upcoming_view_filter_test('?show=regular&hide=%s' % area.acronym, ietf_meetings)

    def test_upcoming_view_filter_hide_type(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent

        # Without anything shown, should see only ietf meetings
        ietf_meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?hide=regular', ietf_meetings)

        # With group shown
        self.do_upcoming_view_filter_test('?show=mars&hide=regular', ietf_meetings)

        # With type shown
        self.do_upcoming_view_filter_test('?show=plenary,regular&hide=%s' % area.acronym, 
                                          ietf_meetings.union(
                                              self.displayed_interims(groups=['sg'])
                                          ))

    def test_upcoming_view_filter_whitespace(self):
        """Whitespace in filter lists should be ignored"""
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars']))
        self.do_upcoming_view_filter_test('?show=mars , ames &hide=   ames', meetings)

    def test_upcoming_view_time_zone_selection(self):
        wait = WebDriverWait(self.driver, 2)

        def _assert_interim_tz_correct(sessions, tz):
            zone = pytz.timezone(tz)
            for session in sessions:
                ts = session.official_timeslotassignment().timeslot
                start = ts.utc_start_time().astimezone(zone).strftime('%Y-%m-%d %H:%M')
                end = ts.utc_end_time().astimezone(zone).strftime('%H:%M')
                meeting_link = self.driver.find_element_by_link_text(session.meeting.number)
                time_td = meeting_link.find_element_by_xpath('../../td[@class="session-time"]')
                self.assertIn('%s - %s' % (start, end), time_td.text)

        def _assert_ietf_tz_correct(meetings, tz):
            zone = pytz.timezone(tz)
            for meeting in meetings:
                meeting_zone = pytz.timezone(meeting.time_zone)
                start_dt = meeting_zone.localize(datetime.datetime.combine(
                    meeting.date, 
                    datetime.time.min
                ))
                end_dt = meeting_zone.localize(datetime.datetime.combine(
                    start_dt + datetime.timedelta(days=meeting.days - 1),
                    datetime.time.max
                ))
                
                start = start_dt.astimezone(zone).strftime('%Y-%m-%d')
                end = end_dt.astimezone(zone).strftime('%Y-%m-%d')
                meeting_link = self.driver.find_element_by_link_text("IETF " + meeting.number)
                time_td = meeting_link.find_element_by_xpath('../../td[@class="meeting-time"]')
                self.assertIn('%s - %s' % (start, end), time_td.text)

        sessions = [m.session_set.first() for m in self.displayed_interims()]
        self.assertGreater(len(sessions), 0)
        ietf_meetings = self.all_ietf_meetings()
        self.assertGreater(len(ietf_meetings), 0)

        self.driver.get(self.absreverse('ietf.meeting.views.upcoming'))
        tz_select_input = self.driver.find_element_by_id('timezone-select')
        tz_select_bottom_input = self.driver.find_element_by_id('timezone-select-bottom')
        local_tz_link = self.driver.find_element_by_id('local-timezone')
        utc_tz_link = self.driver.find_element_by_id('utc-timezone')
        local_tz_bottom_link = self.driver.find_element_by_id('local-timezone-bottom')
        utc_tz_bottom_link = self.driver.find_element_by_id('utc-timezone-bottom')
        
        # wait for the select box to be updated - look for an arbitrary time zone to be in
        # its options list to detect this
        arbitrary_tz = 'America/Halifax'
        arbitrary_tz_opt = wait.until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, '#timezone-select > option[value="%s"]' % arbitrary_tz)
            )
        )
        arbitrary_tz_bottom_opt = tz_select_bottom_input.find_element_by_css_selector(
            'option[value="%s"]' % arbitrary_tz)

        utc_tz_opt = tz_select_input.find_element_by_css_selector('option[value="UTC"]')
        utc_tz_bottom_opt= tz_select_bottom_input.find_element_by_css_selector('option[value="UTC"]')

        # Moment.js guesses local time zone based on the behavior of Selenium's web client. This seems
        # to inherit Django's settings.TIME_ZONE but I don't know whether that's guaranteed to be consistent.
        # To avoid test fragility, ask Moment what it considers local and expect that.
        local_tz = self.driver.execute_script('return moment.tz.guess();')
        local_tz_opt = tz_select_input.find_element_by_css_selector('option[value=%s]' % local_tz)
        local_tz_bottom_opt = tz_select_bottom_input.find_element_by_css_selector('option[value="%s"]' % local_tz)

        # Should start off in local time zone
        self.assertTrue(local_tz_opt.is_selected())
        self.assertTrue(local_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, local_tz)
        _assert_ietf_tz_correct(ietf_meetings, local_tz)

        # click 'utc' button
        utc_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(utc_tz_opt))
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(local_tz_bottom_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_bottom_opt.is_selected())
        self.assertTrue(utc_tz_opt.is_selected())
        self.assertTrue(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, 'UTC')
        _assert_ietf_tz_correct(ietf_meetings, 'UTC')

        # click back to 'local'
        local_tz_link.click()
        wait.until(expected_conditions.element_to_be_selected(local_tz_opt))
        self.assertTrue(local_tz_opt.is_selected())
        self.assertTrue(local_tz_bottom_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_bottom_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        self.assertFalse(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, local_tz)
        _assert_ietf_tz_correct(ietf_meetings, local_tz)

        # Now select a different item from the select input
        arbitrary_tz_opt.click()
        wait.until(expected_conditions.element_to_be_selected(arbitrary_tz_opt))
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(local_tz_bottom_opt.is_selected())
        self.assertTrue(arbitrary_tz_opt.is_selected())
        self.assertTrue(arbitrary_tz_bottom_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        self.assertFalse(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, arbitrary_tz)
        _assert_ietf_tz_correct(ietf_meetings, arbitrary_tz)

        # Now repeat those tests using the widgets at the bottom of the page
        # click 'utc' button
        utc_tz_bottom_link.click()
        wait.until(expected_conditions.element_to_be_selected(utc_tz_opt))
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(local_tz_bottom_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_bottom_opt.is_selected())
        self.assertTrue(utc_tz_opt.is_selected())
        self.assertTrue(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, 'UTC')
        _assert_ietf_tz_correct(ietf_meetings, 'UTC')

        # click back to 'local'
        local_tz_bottom_link.click()
        wait.until(expected_conditions.element_to_be_selected(local_tz_opt))
        self.assertTrue(local_tz_opt.is_selected())
        self.assertTrue(local_tz_bottom_opt.is_selected())
        self.assertFalse(arbitrary_tz_opt.is_selected())
        self.assertFalse(arbitrary_tz_bottom_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        self.assertFalse(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, local_tz)
        _assert_ietf_tz_correct(ietf_meetings, local_tz)

        # Now select a different item from the select input
        arbitrary_tz_bottom_opt.click()
        wait.until(expected_conditions.element_to_be_selected(arbitrary_tz_opt))
        self.assertFalse(local_tz_opt.is_selected())
        self.assertFalse(local_tz_bottom_opt.is_selected())
        self.assertTrue(arbitrary_tz_opt.is_selected())
        self.assertTrue(arbitrary_tz_bottom_opt.is_selected())
        self.assertFalse(utc_tz_opt.is_selected())
        self.assertFalse(utc_tz_bottom_opt.is_selected())
        _assert_interim_tz_correct(sessions, arbitrary_tz)
        _assert_ietf_tz_correct(ietf_meetings, arbitrary_tz)


# The following are useful debugging tools

# If you add this to a LiveServerTestCase and run just this test, you can browse
# to the test server with the data loaded by setUp() to debug why, for instance,
# a particular view isn't giving you what you expect
#    def testJustSitThere(self):
#        time.sleep(10000)

# The LiveServerTestCase server runs in a mode like production - it hides crashes with the
# user-friendly message about mail being sent to the maintainers, and eats that mail.
# Loading the page that crashed with just a TestCase will at least let you see the
# traceback.
#
#from ietf.utils.test_utils import TestCase
#class LookAtCrashTest(TestCase):
#    def setUp(self):
#        make_meeting_test_data()
#
#    def testOpenSchedule(self):
#        url = urlreverse('ietf.meeting.views.edit_schedule', kwargs=dict(num='72',name='test-schedule'))
#        r = self.client.get(url)
