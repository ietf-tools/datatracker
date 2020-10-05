# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import time
import datetime
import shutil
import os
from unittest import skipIf

import django
from django.urls import reverse as urlreverse
from django.utils.text import slugify
from django.db.models import F
#from django.test.utils import override_settings

import debug                            # pyflakes:ignore

from ietf.doc.factories import DocumentFactory
from ietf.group import colors
from ietf.person.models import Person
from ietf.group.models import Group
from ietf.meeting.factories import SessionFactory
from ietf.meeting.test_data import make_meeting_test_data
from ietf.meeting.models import (Schedule, SchedTimeSessAssignment, Session,
                                 Room, TimeSlot, Constraint, ConstraintName,
                                 Meeting, SchedulingEvent, SessionStatusName)
from ietf.meeting.utils import add_event_info_to_session_qs
from ietf.utils.test_runner import IetfLiveServerTestCase
from ietf.utils.pipe import pipe
from ietf import settings

skip_selenium = False
skip_message  = ""
try:
    from selenium import webdriver
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions
    from selenium.common.exceptions import NoSuchElementException
except ImportError as e:
    skip_selenium = True
    skip_message = "Skipping selenium tests: %s" % e

executable_name = 'chromedriver'
code, out, err = pipe('{} --version'.format(executable_name))
if code != 0:
    skip_selenium = True
    skip_message = "Skipping selenium tests: '{}' executable not found.".format(executable_name)
if skip_selenium:
    print("     "+skip_message)

def start_web_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    options.add_argument("disable-extensions")
    options.add_argument("disable-gpu") # headless needs this
    options.add_argument("no-sandbox") # docker needs this
    return webdriver.Chrome(options=options, service_log_path=settings.TEST_GHOSTDRIVER_LOG_PATH)

class MeetingTestCase(IetfLiveServerTestCase):
    def __init__(self, *args, **kwargs):
        super(MeetingTestCase, self).__init__(*args, **kwargs)
        self.login_view = 'ietf.ietfauth.views.login'

    def setUp(self):
        super(MeetingTestCase, self).setUp()
        self.driver = start_web_driver()
        self.driver.set_window_size(1024,768)

    def tearDown(self):
        self.driver.close()

    def absreverse(self,*args,**kwargs):
        return '%s%s'%(self.live_server_url,urlreverse(*args,**kwargs))

    def login(self, username='plain'):
        url = self.absreverse(self.login_view)
        password = '%s+password' % username
        self.driver.get(url)
        self.driver.find_element_by_name('username').send_keys(username)
        self.driver.find_element_by_name('password').send_keys(password)
        self.driver.find_element_by_xpath('//button[@type="submit"]').click()

    def debug_snapshot(self,filename='debug_this.png'):
        self.driver.execute_script("document.body.bgColor = 'white';")
        self.driver.save_screenshot(filename)


@skipIf(skip_selenium, skip_message)
class EditMeetingScheduleTests(MeetingTestCase):
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


@skipIf(skip_selenium, skip_message)
@skipIf(django.VERSION[0]==2, "Skipping test with race conditions under Django 2")
class ScheduleEditTests(MeetingTestCase):
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

@skipIf(skip_selenium, skip_message)
class SlideReorderTests(MeetingTestCase):
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


@skipIf(skip_selenium, skip_message)
class AgendaTests(MeetingTestCase):
    def setUp(self):
        super(AgendaTests, self).setUp()
        self.meeting = make_meeting_test_data()

    def row_id_for_item(self, item):
        return 'row-%s' % item.slug()

    def get_expected_items(self):
        expected_items = self.meeting.schedule.assignments.exclude(timeslot__type__in=['lead','offagenda'])
        self.assertGreater(len(expected_items), 0, 'Test setup generated an empty schedule')
        return expected_items
    
    def test_agenda_view_displays_all_items(self):
        """By default, all agenda items should be displayed"""
        self.login()
        self.driver.get(self.absreverse('ietf.meeting.views.agenda'))

        for item in self.get_expected_items():
            row_id = 'row-%s' % item.slug()
            try:
                item_row = self.driver.find_element_by_id(row_id)
            except NoSuchElementException:
                item_row = None
            self.assertIsNotNone(item_row, 'No row for schedule item "%s"' % row_id)
            self.assertTrue(item_row.is_displayed(), 'Row for schedule item "%s" is not displayed' % row_id)

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
        weekview_iframe = self.driver.find_element_by_id('weekview')
        if len(querystring) == 0:
            self.assertFalse(weekview_iframe.is_displayed(), 'Weekview should be hidden when filters off')
        else:
            self.assertTrue(weekview_iframe.is_displayed(), 'Weekview should be visible when filters on')
            self.driver.switch_to.frame(weekview_iframe)
            self.assert_weekview_item_visibility(visible_groups)
            self.driver.switch_to.default_content()

    def test_agenda_view_filter_show_none(self):
        """Filtered agenda view should display only matching rows (no group selected)"""
        self.do_agenda_view_filter_test('?show=', [])

    def test_agenda_view_filter_show_one(self):
        """Filtered agenda view should display only matching rows (one group selected)"""
        self.do_agenda_view_filter_test('?show=mars', ['mars'])

    def test_agenda_view_filter_show_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        self.do_agenda_view_filter_test('?show=%s' % area.acronym, ['ames', 'mars'])

    def test_agenda_view_filter_bof(self):
        mars = Group.objects.get(acronym='mars')
        mars.state_id = 'bof'
        mars.save()
        self.do_agenda_view_filter_test('?show=bof', ['mars'])
        self.do_agenda_view_filter_test('?show=bof,mars', ['mars'])
        self.do_agenda_view_filter_test('?show=bof,ames', ['mars','ames'])

    def test_agenda_view_filter_show_two(self):
        """Filtered agenda view should display only matching rows (two groups selected)"""
        self.do_agenda_view_filter_test('?show=mars,ames', ['mars', 'ames'])

    def test_agenda_view_filter_all(self):
        """Filtered agenda view should display only matching rows (all groups selected)"""
        self.do_agenda_view_filter_test('', None)  # None means all should be visible

    def test_agenda_view_filter_hide(self):
        self.do_agenda_view_filter_test('?hide=ietf', [])

    def test_agenda_view_filter_hide_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        self.do_agenda_view_filter_test('?show=mars&hide=%s' % area.acronym, [])

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

    def test_agenda_view_group_filter_toggle(self):
        """Clicking a group toggle enables/disables agenda filtering"""
        group_acronym = 'mars'

        self.login()
        url = self.absreverse('ietf.meeting.views.agenda')
        self.driver.get(url)
        
        # Click the 'customize' anchor to reveal the group buttons
        customize_anchor = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, '#accordion a[data-toggle="collapse"]')
            )
        )
        customize_anchor.click()
        
        # Click the group button
        group_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.pickview.%s' % group_acronym)
            )
        )
        group_button.click()

        # Check visibility
        self.assert_agenda_item_visibility([group_acronym])
        
        # Click the group button again
        group_button = WebDriverWait(self.driver, 2).until(
            expected_conditions.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.pickview.%s' % group_acronym)
            )
        )
        group_button.click()

        # Check visibility
        self.assert_agenda_item_visibility()

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


@skipIf(skip_selenium, skip_message)
class InterimTests(MeetingTestCase):
    def setUp(self):
        super(InterimTests, self).setUp()
        self.materials_dir = self.tempdir('materials')
        self.saved_agenda_path = settings.AGENDA_PATH
        settings.AGENDA_PATH = self.materials_dir
        self.meeting = make_meeting_test_data(create_interims=True)

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

    def assert_upcoming_meeting_visibility(self, visible_meetings=None):
        """Assert that correct items are visible in current browser window

        If visible_meetings is None (the default), expects all items to be visible.
        """
        expected = {mtg.number for mtg in visible_meetings}
        not_visible = set()
        unexpected = set()
        entries = self.driver.find_elements_by_css_selector(
            'table#upcoming-meeting-table a.ietf-meeting-link, table#upcoming-meeting-table a.interim-meeting-link'
        )
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

        # Check the ical links
        simplified_querystring = querystring.replace(' ', '%20')  # encode spaces'
        ics_link = self.driver.find_element_by_link_text('Download as .ics')
        self.assertIn(simplified_querystring, ics_link.get_attribute('href'))
        webcal_link = self.driver.find_element_by_link_text('Subscribe with webcal')
        self.assertIn(simplified_querystring, webcal_link.get_attribute('href'))

    def test_upcoming_view_displays_all_interims(self):
        """By default, all upcoming interims and IETF meetings should be displayed"""
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims())
        self.do_upcoming_view_filter_test('', meetings)

    def test_upcoming_view_filter_show_none(self):
        meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?show=', meetings)

    def test_upcoming_view_filter_show_one(self):
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars']))
        self.do_upcoming_view_filter_test('?show=mars', meetings)

    def test_upcoming_view_filter_show_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars', 'ames']))
        self.do_upcoming_view_filter_test('?show=%s' % area.acronym, meetings)

    def test_upcoming_view_filter_show_two(self):
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars', 'ames']))
        self.do_upcoming_view_filter_test('?show=mars,ames', meetings)

    def test_upcoming_view_filter_whitespace(self):
        """Whitespace in filter lists should be ignored"""
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars']))
        self.do_upcoming_view_filter_test('?show=mars , ames &hide=   ames', meetings)

    def test_upcoming_view_filter_hide(self):
        # Not a useful application, but test for completeness...
        meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?hide=mars', meetings)

    def test_upcoming_view_filter_hide_area(self):
        mars = Group.objects.get(acronym='mars')
        area = mars.parent
        meetings = set(self.all_ietf_meetings())
        self.do_upcoming_view_filter_test('?show=mars&hide=%s' % area.acronym, meetings)

    def test_upcoming_view_filter_show_and_hide_same_group(self):
        meetings = set(self.all_ietf_meetings())
        meetings.update(self.displayed_interims(groups=['mars']))
        self.do_upcoming_view_filter_test('?show=mars,ames&hide=ames', meetings)

    # The upcoming meetings view does not handle showtypes / hidetypes

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
