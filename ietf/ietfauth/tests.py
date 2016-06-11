# -*- coding: utf-8 -*-
import os, shutil
from urlparse import urlsplit
from pyquery import PyQuery
from unittest import skipIf

from django.core.urlresolvers import reverse as urlreverse
import django.contrib.auth.views
from django.contrib.auth.models import User
from django.conf import settings

from ietf.utils.test_utils import TestCase, login_testing_unauthorized, unicontent
from ietf.utils.test_data import make_test_data
from ietf.utils.mail import outbox, empty_outbox
from ietf.person.models import Person, Email
from ietf.group.models import Group, Role, RoleName
from ietf.ietfauth.htpasswd import update_htpasswd_file
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

    def test_create_account(self):
        make_test_data()

        url = urlreverse(ietf.ietfauth.views.create_account)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # register email
        email = 'new-account@example.com'
        empty_outbox()
        r = self.client.post(url, { 'email': email })
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Account created" in unicontent(r))
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

    def test_htpasswd_file_with_python(self):
        # make sure we test both Python and call-out to binary
        settings.USE_PYTHON_HTDIGEST = True

        update_htpasswd_file("foo", "passwd")
        self.assertTrue(self.username_in_htpasswd_file("foo"))

    @skipIf(skip_htpasswd_command, skip_message)
    def test_htpasswd_file_with_htpasswd_binary(self):
        # make sure we test both Python and call-out to binary
        settings.USE_PYTHON_HTDIGEST = False

        update_htpasswd_file("foo", "passwd")
        self.assertTrue(self.username_in_htpasswd_file("foo"))
        
