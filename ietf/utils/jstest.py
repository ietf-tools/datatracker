# Copyright The IETF Trust 2014-2021, All Rights Reserved
# -*- coding: utf-8 -*-

import re

from django.urls import reverse as urlreverse
from unittest import skipIf

skip_selenium = False
skip_message  = ""
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
except ImportError as e:
    skip_selenium = True
    skip_message = "Skipping selenium tests: %s" % e


from ietf.utils.pipe import pipe
from ietf.utils.test_runner import IetfLiveServerTestCase
from ietf import settings

executable_name = 'chromedriver'
code, out, err = pipe('{} --version'.format(executable_name))
if code != 0:
    skip_selenium = True
    skip_message = "Skipping selenium tests: '{}' executable not found.".format(executable_name)
if skip_selenium:
    print("     "+skip_message)

def start_web_driver():
    service = Service(executable_path="chromedriver",
                      log_path=settings.TEST_GHOSTDRIVER_LOG_PATH)
    service.start()
    options = Options()
    options.add_argument("headless")
    options.add_argument("disable-extensions")
    options.add_argument("disable-gpu") # headless needs this
    options.add_argument("no-sandbox") # docker needs this
    dc = DesiredCapabilities.CHROME
    dc["goog:loggingPrefs"] = {"browser": "ALL"}
    # For selenium 3:
    return webdriver.Chrome("chromedriver", options=options, desired_capabilities=dc)
    # For selenium 4:
    # return webdriver.Chrome(service=service, options=options, desired_capabilities=dc)


def selenium_enabled():
    """Are Selenium tests enabled?"""
    return not skip_selenium


def ifSeleniumEnabled(func):
    """Only run test if Selenium testing is enabled"""
    return skipIf(skip_selenium, skip_message)(func)


class IetfSeleniumTestCase(IetfLiveServerTestCase):
    login_view = 'ietf.ietfauth.views.login'

    def setUp(self):
        super(IetfSeleniumTestCase, self).setUp()
        self.driver = start_web_driver()
        self.driver.set_window_size(1024,768)
    
    def tearDown(self):
        msg = ""
        for type in ["browser", "driver"]:
            log = self.driver.get_log(type)
            if not log:
                continue
            for entry in log:
                line = entry["message"]
                # suppress a bunch of benign/expected messages
                if (
                    re.search(r"JQMIGRATE: Migrate is installed", line)
                    or re.search(r"No color for (farfut|acronym\d+):", line)
                    or re.search(r"Could not find parent \d+", line)
                    or re.search(r"/materials/.*mars.*status of 404", line)
                ):
                    continue
                msg += f"{entry['level']}: {line}\n"

        super(IetfSeleniumTestCase, self).tearDown()
        self.driver.close()
        self.maxDiff = None
        self.assertEqual("", msg)
    
    def absreverse(self,*args,**kwargs):
        return '%s%s'%(self.live_server_url, urlreverse(*args, **kwargs))
    
    def debug_snapshot(self,filename='debug_this.png'):
        self.driver.execute_script("document.body.bgColor = 'white';")
        self.driver.save_screenshot(filename)

    def login(self, username='plain'):
        url = self.absreverse(self.login_view)
        password = '%s+password' % username
        self.driver.get(url)
        self.driver.find_element(By.NAME, 'username').send_keys(username)
        self.driver.find_element(By.NAME, 'password').send_keys(password)
        self.driver.find_element(By.XPATH, '//button[@type="submit"]').click()

    def scroll_to_element(self, element):
        """Scroll an element into view"""
        actions = ActionChains(self.driver)
        actions.move_to_element(element).perform()


class presence_of_element_child_by_css_selector:
    """Wait for presence of a child of a WebElement matching a CSS selector

    This is a condition class for use with WebDriverWait.
    """
    def __init__(self, element, child_selector):
        self.element = element
        self.child_selector = child_selector

    def __call__(self, driver):
        child = self.element.find_element(By.CSS_SELECTOR, self.child_selector)
        return child if child is not None else False