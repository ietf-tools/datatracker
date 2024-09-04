# Copyright The IETF Trust 2014-2021, All Rights Reserved
# -*- coding: utf-8 -*-

import os

from django.urls import reverse as urlreverse
from unittest import skipIf

skip_selenium = False
skip_message  = ""
try:
    from selenium import webdriver
    from selenium.webdriver.firefox.service import Service
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
except ImportError as e:
    skip_selenium = True
    skip_message = "Skipping selenium tests: %s" % e


from ietf.utils.pipe import pipe
from ietf.utils.test_runner import IetfLiveServerTestCase

executable_name = 'geckodriver'
code, out, err = pipe('{} --version'.format(executable_name))
if code != 0:
    skip_selenium = True
    skip_message = "Skipping selenium tests: '{}' executable not found.".format(executable_name)
if skip_selenium:
    print("     "+skip_message)

def start_web_driver():
    service = Service(executable_path=f"/usr/bin/{executable_name}", log_output=f"{executable_name}.log", service_args=['--log-no-truncate'])
    options = Options()
    options.add_argument("--headless")
    os.environ["MOZ_REMOTE_SETTINGS_DEVTOOLS"] = "1"
    return webdriver.Firefox(service=service, options=options)


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
        super(IetfSeleniumTestCase, self).tearDown()
        self.driver.close()

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
        self.driver.find_element(By.XPATH, '//*[@id="content"]//button[@type="submit"]').click()

    def scroll_to_element(self, element):
        """Scroll an element into view"""
        # Compute the offset to put the element in the center of the window
        win_height = self.driver.get_window_rect()['height']
        offset = element.rect['y'] + (element.rect['height'] - win_height) // 2
        self.driver.execute_script(
            'window.scroll({top: arguments[0], behavior: "instant"})',
            offset,
        )
        # The ActionChains approach below seems to be fragile, hence he JS above.
        # actions = ActionChains(self.driver)
        # actions.move_to_element(element).perform()


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
