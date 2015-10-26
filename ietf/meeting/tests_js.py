import time
from pyquery import PyQuery 
from unittest import skipIf

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.group import colors
from ietf.meeting.test_data import make_meeting_test_data
from ietf.meeting.models import SchedTimeSessAssignment
from ietf import settings

skip_selenium = getattr(settings,'SKIP_SELENIUM',None)
skip_message  = ""
if skip_selenium:
    skip_message = "settings.SKIP_SELENIUM = %s" % skip_selenium
else:
    try:
        from selenium import webdriver
        from selenium.webdriver.common.action_chains import ActionChains
    except ImportError as e:
        skip_selenium = True
        skip_message = str(e)

def condition_data():
        make_meeting_test_data()
        colors.fg_group_colors['FARFUT'] = 'blue'
        colors.bg_group_colors['FARFUT'] = 'white'

   
@skipIf(skip_selenium, skip_message)
class ScheduleEditTests(StaticLiveServerTestCase):
    def setUp(self):
        condition_data()
        self.driver = webdriver.PhantomJS(service_log_path=settings.TEST_GHOSTDRIVER_LOG_PATH)
        self.driver.set_window_size(1024,768)

    def debugSnapshot(self,filename='debug_this.png'):
        self.driver.execute_script("document.body.bgColor = 'white';")
        self.driver.save_screenshot(filename)

    def absreverse(self,*args,**kwargs):
        return '%s%s'%(self.live_server_url,urlreverse(*args,**kwargs))

    def login(self):
        #url = self.absreverse('ietf.ietfauth.views.login')
        url = '%s%s'%(self.live_server_url,'/accounts/login')
        self.driver.get(url)
        self.driver.find_element_by_name('username').send_keys('plain')
        self.driver.find_element_by_name('password').send_keys('plain+password')
        self.driver.find_element_by_xpath('//button[@type="submit"]').click()
    
    def testUnschedule(self):
        
        self.assertEqual(SchedTimeSessAssignment.objects.filter(session__meeting__number=42,session__group__acronym='mars').count(),1)

        self.login()
        url = self.absreverse('ietf.meeting.views.edit_agenda',kwargs=dict(num='42',name='test-agenda',owner='plain@example.com'))
        self.driver.get(url)

        q = PyQuery(self.driver.page_source)
        self.assertEqual(len(q('#sortable-list #session_1')),0)

        element = self.driver.find_element_by_id('session_1')
        target  = self.driver.find_element_by_id('sortable-list')
        ActionChains(self.driver).drag_and_drop(element,target).perform()

        q = PyQuery(self.driver.page_source)
        self.assertTrue(len(q('#sortable-list #session_1'))>0)

        time.sleep(0.1) # The API that modifies the database runs async
        self.assertEqual(SchedTimeSessAssignment.objects.filter(session__meeting__number=42,session__group__acronym='mars').count(),0)

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
#        condition_data()
#
#    def testOpenSchedule(self):
#        url = urlreverse('ietf.meeting.views.edit_agenda', kwargs=dict(num='42',name='test-agenda'))
#        r = self.client.get(url)
