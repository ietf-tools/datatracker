# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os, shutil, time, datetime
from urlparse import urlsplit
from pyquery import PyQuery
from unittest import skipIf

from django.core.urlresolvers import reverse as urlreverse
import django.contrib.auth.views
from django.contrib.auth.models import User
from django.conf import settings

from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.test_data import make_test_data, make_review_data
from ietf.utils.mail import outbox, empty_outbox
from ietf.person.models import Person, Email
from ietf.group.models import Group, Role, RoleName
from ietf.ietfauth.htpasswd import update_htpasswd_file
from ietf.mailinglists.models import Subscribed
from ietf.review.models import ReviewWish, UnavailablePeriod
from ietf.utils.decorators import skip_coverage

import ietf.ietfauth.views

if os.path.exists(settings.HTPASSWD_COMMAND):
    skip_htpasswd_command = False
    skip_message = ""
else:
    skip_htpasswd_command = True
    skip_message = ("The binary for htpasswd wasn't found "
                    "in the locations indicated in settings.py.")

class IetfAuthTests(TestCase):
    def setUp(self):
        self.saved_use_python_htdigest = getattr(settings, "USE_PYTHON_HTDIGEST", None)
        settings.USE_PYTHON_HTDIGEST = True

        self.saved_htpasswd_file = settings.HTPASSWD_FILE
        self.htpasswd_dir = os.path.abspath("tmp-htpasswd-dir")
        os.mkdir(self.htpasswd_dir)
        settings.HTPASSWD_FILE = os.path.join(self.htpasswd_dir, "htpasswd")
        open(settings.HTPASSWD_FILE, 'a').close() # create empty file

        self.saved_htdigest_realm = getattr(settings, "HTDIGEST_REALM", None)
        settings.HTDIGEST_REALM = "test-realm"

    def tearDown(self):
        shutil.rmtree(self.htpasswd_dir)
        settings.USE_PYTHON_HTDIGEST = self.saved_use_python_htdigest
        settings.HTPASSWD_FILE = self.saved_htpasswd_file
        settings.HTDIGEST_REALM = self.saved_htdigest_realm

    def test_index(self):
        self.assertEqual(self.client.get(urlreverse(ietf.ietfauth.views.index)).status_code, 200)

    def test_login_and_logout(self):
        make_test_data()

        # try logging in without a next
        r = self.client.get(urlreverse(django.contrib.auth.views.login))
        self.assertEqual(r.status_code, 200)

        r = self.client.post(urlreverse(django.contrib.auth.views.login), {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.profile))

        # try logging out
        r = self.client.get(urlreverse(django.contrib.auth.views.logout))
        self.assertEqual(r.status_code, 200)

        r = self.client.get(urlreverse(ietf.ietfauth.views.profile))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(django.contrib.auth.views.login))

        # try logging in with a next
        r = self.client.post(urlreverse(django.contrib.auth.views.login) + "?next=/foobar", {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/foobar")

    def extract_confirm_url(self, confirm_email):
        # dig out confirm_email link
        msg = confirm_email.get_payload(decode=True)
        line_start = "http"
        confirm_url = None
        for line in msg.split("\n"):
            if line.strip().startswith(line_start):
                confirm_url = line.strip()
        self.assertTrue(confirm_url)

        return confirm_url

    def username_in_htpasswd_file(self, username):
        with open(settings.HTPASSWD_FILE) as f:
            for l in f:
                if l.startswith(username + ":"):
                    return True
        with open(settings.HTPASSWD_FILE) as f:
            print f.read()

        return False

    def test_create_account_failure(self):
        make_test_data()

        url = urlreverse(ietf.ietfauth.views.create_account)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # register email and verify failure
        email = 'new-account@example.com'
        empty_outbox()
        r = self.client.post(url, { 'email': email })
        self.assertEqual(r.status_code, 200)
        self.assertIn("Account creation failed", unicontent(r))

    def register_and_verify(self, email):
        url = urlreverse(ietf.ietfauth.views.create_account)

        # register email
        empty_outbox()
        r = self.client.post(url, { 'email': email })
        self.assertEqual(r.status_code, 200)
        self.assertIn("Account created", unicontent(r))
        self.assertEqual(len(outbox), 1)

        # go to confirm page
        confirm_url = self.extract_confirm_url(outbox[-1])
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 200)

        # password mismatch
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'nosecret' })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(username=email).count(), 0)

        # confirm
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'secret' })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(username=email).count(), 1)
        self.assertEqual(Person.objects.filter(user__username=email).count(), 1)
        self.assertEqual(Email.objects.filter(person__user__username=email).count(), 1)

        self.assertTrue(self.username_in_htpasswd_file(email))

    def test_create_whitelisted_account(self):
        email = "new-account@example.com"

        # add whitelist entry
        r = self.client.post(urlreverse(django.contrib.auth.views.login), {"username":"secretary", "password":"secretary+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.profile))

        r = self.client.get(urlreverse(ietf.ietfauth.views.add_account_whitelist))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Add a whitelist entry", unicontent(r))

        r = self.client.post(urlreverse(ietf.ietfauth.views.add_account_whitelist), {"email": email})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Whitelist entry creation successful", unicontent(r))

        # log out
        r = self.client.get(urlreverse(django.contrib.auth.views.logout))
        self.assertEqual(r.status_code, 200)

        # register and verify whitelisted email
        self.register_and_verify(email)


    def test_create_subscribed_account(self):
        # verify creation with email in subscribed list
        saved_delay = settings.LIST_ACCOUNT_DELAY
        settings.LIST_ACCOUNT_DELAY = 1
        email = "subscribed@example.com"
        s = Subscribed(email=email)
        s.save()
        time.sleep(1.1)
        self.register_and_verify(email)
        settings.LIST_ACCOUNT_DELAY = saved_delay

    def test_profile(self):
        make_test_data()

        username = "plain"
        email_address = Email.objects.filter(person__user__username=username).first().address

        url = urlreverse(ietf.ietfauth.views.profile)
        login_testing_unauthorized(self, username, url)


        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('.form-control-static:contains("%s")' % username)), 1)
        self.assertEqual(len(q('[name="active_emails"][value="%s"][checked]' % email_address)), 1)

        base_data = {
            "name": u"Test Nãme",
            "ascii": u"Test Name",
            "ascii_short": u"T. Name",
            "address": "Test address",
            "affiliation": "Test Org",
            "active_emails": email_address,
        }

        # edit details - faulty ASCII
        faulty_ascii = base_data.copy()
        faulty_ascii["ascii"] = u"Test Nãme"
        r = self.client.post(url, faulty_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)

        # edit details - blank ASCII
        blank_ascii = base_data.copy()
        blank_ascii["ascii"] = u""
        r = self.client.post(url, blank_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0) # we get a warning about reconstructed name
        self.assertEqual(q("input[name=ascii]").val(), base_data["ascii"])

        # edit details
        r = self.client.post(url, base_data)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)
        self.assertEqual(person.name, u"Test Nãme")
        self.assertEqual(person.ascii, u"Test Name")
        self.assertEqual(Person.objects.filter(alias__name=u"Test Name", user__username=username).count(), 1)
        self.assertEqual(Person.objects.filter(alias__name=u"Test Nãme", user__username=username).count(), 1)
        self.assertEqual(Email.objects.filter(address=email_address, person__user__username=username, active=True).count(), 1)

        # deactivate address
        without_email_address = { k: v for k, v in base_data.iteritems() if k != "active_emails" }

        r = self.client.post(url, without_email_address)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Email.objects.filter(address=email_address, person__user__username="plain", active=True).count(), 0)

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[name="%s"][checked]' % email_address)), 0)

        # add email address
        empty_outbox()
        new_email_address = "plain2@example.com"
        with_new_email_address = base_data.copy()
        with_new_email_address["new_email"] = new_email_address
        r = self.client.post(url, with_new_email_address)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)

        # confirm new email address
        confirm_url = self.extract_confirm_url(outbox[-1])
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[name="action"][value=confirm]')), 1)

        r = self.client.post(confirm_url, { "action": "confirm" })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Email.objects.filter(address=new_email_address, person__user__username=username, active=1).count(), 1)

        # check that we can't re-add it - that would give a duplicate
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[name="action"][value="confirm"]')), 0)

        # change role email
        role = Role.objects.create(
            person=Person.objects.get(user__username=username),
            email=Email.objects.get(address=email_address),
            name=RoleName.objects.get(slug="chair"),
            group=Group.objects.get(acronym="mars"),
        )

        role_email_input_name = "role_%s-email" % role.pk

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('[name="%s"]' % role_email_input_name)), 1)
        
        with_changed_role_email = base_data.copy()
        with_changed_role_email["active_emails"] = new_email_address
        with_changed_role_email[role_email_input_name] = new_email_address
        r = self.client.post(url, with_changed_role_email)
        self.assertEqual(r.status_code, 200)
        updated_roles = Role.objects.filter(person=role.person, name=role.name, group=role.group)
        self.assertEqual(len(updated_roles), 1)
        self.assertEqual(updated_roles[0].email_id, new_email_address)


    def test_reset_password(self):
        url = urlreverse(ietf.ietfauth.views.password_reset)

        user = User.objects.create(username="someone@example.com", email="someone@example.com")
        user.set_password("forgotten")
        user.save()
        p = Person.objects.create(name="Some One", ascii="Some One", user=user)
        Email.objects.create(address=user.username, person=p)
        
        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # ask for reset, wrong username
        r = self.client.post(url, { 'username': "nobody@example.com" })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)

        # ask for reset
        empty_outbox()
        r = self.client.post(url, { 'username': user.username })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)

        # go to change password page
        confirm_url = self.extract_confirm_url(outbox[-1])
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 200)

        # password mismatch
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'nosecret' })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) > 0)

        # confirm
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'secret' })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form .has-error")), 0)
        self.assertTrue(self.username_in_htpasswd_file(user.username))

    def test_review_overview(self):
        doc = make_test_data()

        review_req = make_review_data(doc)
        review_req.reviewer = Email.objects.get(person__user__username="reviewer")
        review_req.save()

        reviewer = review_req.reviewer.person

        UnavailablePeriod.objects.create(
            team=review_req.team,
            person=reviewer,
            start_date=datetime.date.today() - datetime.timedelta(days=10),
            availability="unavailable",
        )

        url = urlreverse(ietf.ietfauth.views.review_overview)

        login_testing_unauthorized(self, reviewer.user.username, url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(review_req.doc.name in unicontent(r))

        # wish to review
        r = self.client.post(url, {
            "action": "add_wish",
            'doc': doc.pk,
            "team": review_req.team_id,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ReviewWish.objects.filter(doc=doc, team=review_req.team).count(), 1)

        # delete wish
        r = self.client.post(url, {
            "action": "delete_wish",
            'wish_id': ReviewWish.objects.get(doc=doc, team=review_req.team).pk,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ReviewWish.objects.filter(doc=doc, team=review_req.team).count(), 0)

    def test_htpasswd_file_with_python(self):
        # make sure we test both Python and call-out to binary
        settings.USE_PYTHON_HTDIGEST = True

        update_htpasswd_file("foo", "passwd")
        self.assertTrue(self.username_in_htpasswd_file("foo"))

    @skipIf(skip_htpasswd_command, skip_message)
    @skip_coverage
    def test_htpasswd_file_with_htpasswd_binary(self):
        # make sure we test both Python and call-out to binary
        settings.USE_PYTHON_HTDIGEST = False

        update_htpasswd_file("foo", "passwd")
        self.assertTrue(self.username_in_htpasswd_file("foo"))
        
