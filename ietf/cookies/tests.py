# Copyright The IETF Trust 2015-2020, All Rights Reserved

from pyquery import PyQuery
from http.cookies import SimpleCookie

from django.urls import reverse as urlreverse
from django.conf import settings

import debug  # pyflakes:ignore

from ietf.utils.test_utils import TestCase


def q(r, q):
    return PyQuery(r.content)(
        'div a.active[href="/accounts/settings/' + q + '"]'
    ).text()


def qn(r, q):
    return PyQuery(r.content)(
        'div a.active[href^="/accounts/settings/' + q + '"]'
    ).text()


class CookieTests(TestCase):
    def r(self, c, **kwargs):
        r = self.client.get(urlreverse("ietf.cookies.views." + c, **kwargs))
        self.assertEqual(r.status_code, 200)
        return r

    def test_settings_defaults(self):
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        if settings.USER_PREFERENCE_DEFAULTS["full_draft"] == "off":
            self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        else:
            self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_defaults_from_cookies(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "7",
                "expires_soon": 7,
                "left_menu": "on",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "expires_soon/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "left_menu/on"), r"\s*On\s*")

    def test_settings_values_from_cookies_garbage(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "foo",
                "new_enough": "foo",
                "expires_soon": "foo",
                "left_menu": "foo",
            }
        )
        r = self.r("preferences")
        if settings.USER_PREFERENCE_DEFAULTS["full_draft"] == "off":
            self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        else:
            self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_values_from_cookies_random(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "zappa",
                "new_enough": "365",
                "expires_soon": "5",
                "left_menu": "zappa",
            }
        )
        r = self.r("preferences")
        if settings.USER_PREFERENCE_DEFAULTS["full_draft"] == "off":
            self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        else:
            self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(qn(r, "new_enough"), r"\s*\s*")
        self.assertRegex(qn(r, "expires_soon"), r"\s*\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_values_from_cookies_1(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "90",
                "expires_soon": 7,
                "left_menu": "off",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/90"), r"\s*90 days\s*")
        self.assertRegex(q(r, "expires_soon/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_values_from_cookies_2(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "60",
                "expires_soon": 14,
                "left_menu": "on",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/60"), r"\s*60 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "left_menu/on"), r"\s*On\s*")

    def test_settings_values_from_cookies_3(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "30",
                "expires_soon": 21,
                "left_menu": "off",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/30"), r"\s*30 days\s*")
        self.assertRegex(q(r, "expires_soon/21"), r"\s*21 days\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_values_from_cookies_4(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "21",
                "expires_soon": 30,
                "left_menu": "on",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/21"), r"\s*21 days\s*")
        self.assertRegex(q(r, "expires_soon/30"), r"\s*30 days\s*")
        self.assertRegex(q(r, "left_menu/on"), r"\s*On\s*")

    def test_settings_values_from_cookies_5(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "14",
                "expires_soon": 60,
                "left_menu": "off",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/60"), r"\s*60 days\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_settings_values_from_cookies_6(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "7",
                "expires_soon": 90,
                "left_menu": "on",
            }
        )
        r = self.r("preferences")
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "expires_soon/90"), r"\s*90 days\s*")
        self.assertRegex(q(r, "left_menu/on"), r"\s*On\s*")

    def test_full_draft(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("full_draft")  # no value: reset
        self.assertEqual(r.cookies["full_draft"].value, "")
        self.assertListEqual(["full_draft"], list(r.cookies.keys()))
        if settings.USER_PREFERENCE_DEFAULTS["full_draft"] == "off":
            self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        else:
            self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_full_draft_on(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("full_draft", kwargs=dict(enabled="on"))
        self.assertEqual(r.cookies["full_draft"].value, "on")
        self.assertListEqual(["full_draft"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")

    def test_full_draft_off(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("full_draft", kwargs=dict(enabled="off"))
        self.assertEqual(r.cookies["full_draft"].value, "off")
        self.assertListEqual(["full_draft"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")

    def test_full_draft_foo(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("full_draft", kwargs=dict(enabled="foo"))
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")

    def test_left_menu(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
                "left_menu": "on",
            }
        )
        r = self.r("left_menu")  # no value: reset
        self.assertEqual(r.cookies["left_menu"].value, "")
        self.assertListEqual(["left_menu"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_left_menu_on(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
                "left_menu": "off",
            }
        )
        r = self.r("left_menu", kwargs=dict(enabled="on"))
        self.assertEqual(r.cookies["left_menu"].value, "on")
        self.assertListEqual(["left_menu"], list(r.cookies.keys()))
        self.assertRegex(q(r, "left_menu/on"), r"\s*On\s*")

    def test_left_menu_off(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
                "left_menu": "off",
            }
        )
        r = self.r("left_menu", kwargs=dict(enabled="off"))
        self.assertEqual(r.cookies["left_menu"].value, "off")
        self.assertListEqual(["left_menu"], list(r.cookies.keys()))
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_left_menu_foo(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
                "left_menu": "off",
            }
        )
        r = self.r("left_menu", kwargs=dict(enabled="foo"))
        self.assertListEqual([], list(r.cookies.keys()))
        self.assertRegex(q(r, "left_menu/off"), r"\s*Off\s*")

    def test_new_enough(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("new_enough")  # no value: reset
        self.assertEqual(r.cookies["new_enough"].value, "")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_new_enough_7(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "14",
                "expires_soon": 21,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="7"))
        self.assertEqual(r.cookies["new_enough"].value, "7")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "expires_soon/21"), r"\s*21 days\s*")

    def test_new_enough_14(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "7",
                "expires_soon": 99,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="14"))
        self.assertEqual(r.cookies["new_enough"].value, "14")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(qn(r, "expires_soon/14"), r"\s*\s*")

    def test_new_enough_21(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "new_enough": "14",
                "expires_soon": 90,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="21"))
        self.assertEqual(r.cookies["new_enough"].value, "21")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/21"), r"\s*21 days\s*")
        self.assertRegex(q(r, "expires_soon/90"), r"\s*90 days\s*")

    def test_new_enough_30(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 7,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="30"))
        self.assertEqual(r.cookies["new_enough"].value, "30")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/30"), r"\s*30 days\s*")
        self.assertRegex(q(r, "expires_soon/7"), r"\s*7 days\s*")

    def test_new_enough_60(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "14",
                "expires_soon": 14,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="60"))
        self.assertEqual(r.cookies["new_enough"].value, "60")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/60"), r"\s*60 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_new_enough_90(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "new_enough": "22",
                "expires_soon": 60,
            }
        )
        r = self.r("new_enough", kwargs=dict(days="90"))
        self.assertEqual(r.cookies["new_enough"].value, "90")
        self.assertListEqual(["new_enough"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/90"), r"\s*90 days\s*")
        self.assertRegex(q(r, "expires_soon/60"), r"\s*60 days\s*")

    def test_expires_soon(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "expires_soon": "14",
                "new_enough": 14,
            }
        )
        r = self.r("expires_soon")  # no value: reset
        self.assertEqual(r.cookies["expires_soon"].value, "")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_expires_soon_7(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "expires_soon": "14",
                "new_enough": 21,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="7"))
        self.assertEqual(r.cookies["expires_soon"].value, "7")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/21"), r"\s*21 days\s*")
        self.assertRegex(q(r, "expires_soon/7"), r"\s*7 days\s*")

    def test_expires_soon_14(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "expires_soon": "7",
                "new_enough": 99,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="14"))
        self.assertEqual(r.cookies["expires_soon"].value, "14")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(qn(r, "new_enough"), r"\s*\s*")
        self.assertRegex(q(r, "expires_soon/14"), r"\s*14 days\s*")

    def test_expires_soon_21(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "on",
                "expires_soon": "14",
                "new_enough": 90,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="21"))
        self.assertEqual(r.cookies["expires_soon"].value, "21")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/on"), r"\s*On\s*")
        self.assertRegex(q(r, "new_enough/90"), r"\s*90 days\s*")
        self.assertRegex(q(r, "expires_soon/21"), r"\s*21 days\s*")

    def test_expires_soon_30(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "expires_soon": "14",
                "new_enough": 7,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="30"))
        self.assertEqual(r.cookies["expires_soon"].value, "30")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/7"), r"\s*7 days\s*")
        self.assertRegex(q(r, "expires_soon/30"), r"\s*30 days\s*")

    def test_expires_soon_60(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "expires_soon": "14",
                "new_enough": 14,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="60"))
        self.assertEqual(r.cookies["expires_soon"].value, "60")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/14"), r"\s*14 days\s*")
        self.assertRegex(q(r, "expires_soon/60"), r"\s*60 days\s*")

    def test_expires_soon_90(self):
        self.client.cookies = SimpleCookie(
            {
                "full_draft": "off",
                "expires_soon": "22",
                "new_enough": 60,
            }
        )
        r = self.r("expires_soon", kwargs=dict(days="90"))
        self.assertEqual(r.cookies["expires_soon"].value, "90")
        self.assertListEqual(["expires_soon"], list(r.cookies.keys()))
        self.assertRegex(q(r, "full_draft/off"), r"\s*Off\s*")
        self.assertRegex(q(r, "new_enough/60"), r"\s*60 days\s*")
        self.assertRegex(q(r, "expires_soon/90"), r"\s*90 days\s*")