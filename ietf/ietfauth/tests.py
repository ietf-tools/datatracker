# Copyright The IETF Trust 2009-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import logging                          # pyflakes:ignore
import os
import re
import requests
import requests_mock
import shutil
import time
import urllib

from .factories import OidClientRecordFactory
from Cryptodome.PublicKey import RSA
from oic import rndstr
from oic.oic import Client as OidClient
from oic.oic.message import RegistrationResponse, AuthorizationResponse
from oic.utils.authn.client import CLIENT_AUTHN_METHOD
from oidc_provider.models import RSAKey
from pyquery import PyQuery
from unittest import skipIf
from urllib.parse import urlsplit

from django.urls import reverse as urlreverse
from django.contrib.auth.models import User
from django.conf import settings
from django.template.loader import render_to_string 

import debug                            # pyflakes:ignore

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group, Role, RoleName
from ietf.ietfauth.htpasswd import update_htpasswd_file
from ietf.mailinglists.models import Subscribed
from ietf.meeting.factories import MeetingFactory
from ietf.nomcom.factories import NomComFactory
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.person.models import Person, Email, PersonalApiKey
from ietf.review.factories import ReviewRequestFactory, ReviewAssignmentFactory
from ietf.review.models import ReviewWish, UnavailablePeriod
from ietf.stats.models import MeetingRegistration
from ietf.utils.decorators import skip_coverage
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized

import ietf.ietfauth.views

if os.path.exists(settings.HTPASSWD_COMMAND):
    skip_htpasswd_command = False
    skip_message = ""
else:
    skip_htpasswd_command = True
    skip_message = ("Skipping htpasswd test: The binary for htpasswd wasn't found in the\n       "
                    "location indicated in settings.py.")
    print("     "+skip_message)

class IetfAuthTests(TestCase):
    def setUp(self):
        super().setUp()
        self.saved_use_python_htdigest = getattr(settings, "USE_PYTHON_HTDIGEST", None)
        settings.USE_PYTHON_HTDIGEST = True

        self.saved_htpasswd_file = settings.HTPASSWD_FILE
        self.htpasswd_dir = self.tempdir('htpasswd')
        settings.HTPASSWD_FILE = os.path.join(self.htpasswd_dir, "htpasswd")
        io.open(settings.HTPASSWD_FILE, 'a').close() # create empty file

        self.saved_htdigest_realm = getattr(settings, "HTDIGEST_REALM", None)
        settings.HTDIGEST_REALM = "test-realm"

    def tearDown(self):
        shutil.rmtree(self.htpasswd_dir)
        settings.USE_PYTHON_HTDIGEST = self.saved_use_python_htdigest
        settings.HTPASSWD_FILE = self.saved_htpasswd_file
        settings.HTDIGEST_REALM = self.saved_htdigest_realm
        super().tearDown()

    def test_index(self):
        self.assertEqual(self.client.get(urlreverse(ietf.ietfauth.views.index)).status_code, 200)

    def test_login_and_logout(self):
        PersonFactory(user__username='plain')

        # try logging in without a next
        r = self.client.get(urlreverse(ietf.ietfauth.views.login))
        self.assertEqual(r.status_code, 200)

        r = self.client.post(urlreverse(ietf.ietfauth.views.login), {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.profile))

        # try logging out
        r = self.client.get(urlreverse('django.contrib.auth.views.logout'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "accounts/logout")

        r = self.client.get(urlreverse(ietf.ietfauth.views.profile))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.login))

        # try logging in with a next
        r = self.client.post(urlreverse(ietf.ietfauth.views.login) + "?next=/foobar", {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/foobar")

    def test_login_with_different_email(self):
        person = PersonFactory(user__username='plain')
        email = EmailFactory(person=person)

        # try logging in without a next
        r = self.client.get(urlreverse(ietf.ietfauth.views.login))
        self.assertEqual(r.status_code, 200)

        r = self.client.post(urlreverse(ietf.ietfauth.views.login), {"username":email, "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.profile))

    def extract_confirm_url(self, confirm_email):
        # dig out confirm_email link
        msg = get_payload_text(confirm_email)
        line_re = r"http.*/.*confirm"
        confirm_url = None
        for line in msg.split("\n"):
            if re.search(line_re, line.strip()):
                confirm_url = line.strip()
        self.assertTrue(confirm_url)

        return confirm_url

    def username_in_htpasswd_file(self, username):
        with io.open(settings.HTPASSWD_FILE) as f:
            for l in f:
                if l.startswith(username + ":"):
                    return True
        with io.open(settings.HTPASSWD_FILE) as f:
            print(f.read())

        return False

# For the lowered barrier to account creation period, we are disabling this kind of failure
    # def test_create_account_failure(self):

    #     url = urlreverse(ietf.ietfauth.views.create_account)

    #     # get
    #     r = self.client.get(url)
    #     self.assertEqual(r.status_code, 200)

    #     # register email and verify failure
    #     email = 'new-account@example.com'
    #     empty_outbox()
    #     r = self.client.post(url, { 'email': email })
    #     self.assertEqual(r.status_code, 200)
    #     self.assertContains(r, "Additional Assistance Required")

# Rather than delete the failure template just yet, here's a test to make sure it still renders should we need to revert to it.
    def test_create_account_failure_template(self):
        r = render_to_string('registration/manual.html', { 'account_request_email': settings.ACCOUNT_REQUEST_EMAIL })
        self.assertTrue("Additional Assistance Required" in r)

    def register_and_verify(self, email):
        url = urlreverse(ietf.ietfauth.views.create_account)

        # register email
        empty_outbox()
        r = self.client.post(url, { 'email': email })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Account request received")
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
        r = self.client.post(confirm_url, { 'name': 'User Name', 'ascii': 'User Name', 'password': 'secret', 'password_confirmation': 'secret' })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(username=email).count(), 1)
        self.assertEqual(Person.objects.filter(user__username=email).count(), 1)
        self.assertEqual(Email.objects.filter(person__user__username=email).count(), 1)

        self.assertTrue(self.username_in_htpasswd_file(email))

    def test_create_whitelisted_account(self):
        email = "new-account@example.com"

        # add whitelist entry
        r = self.client.post(urlreverse(ietf.ietfauth.views.login), {"username":"secretary", "password":"secretary+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse(ietf.ietfauth.views.profile))

        r = self.client.get(urlreverse(ietf.ietfauth.views.add_account_whitelist))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Add a whitelist entry")

        r = self.client.post(urlreverse(ietf.ietfauth.views.add_account_whitelist), {"email": email})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Whitelist entry creation successful")

        # log out
        r = self.client.get(urlreverse('django.contrib.auth.views.logout'))
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

    def test_ietfauth_profile(self):
        EmailFactory(person__user__username='plain')
        GroupFactory(acronym='mars')

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
            "name": "Test Nãme",
            "plain": "",
            "ascii": "Test Name",
            "ascii_short": "T. Name",
            "affiliation": "Test Org",
            "active_emails": email_address,
            "consent": True,
        }

        # edit details - faulty ASCII
        faulty_ascii = base_data.copy()
        faulty_ascii["ascii"] = "Test Nãme"
        r = self.client.post(url, faulty_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .has-error")) == 1)

        # edit details - blank ASCII
        blank_ascii = base_data.copy()
        blank_ascii["ascii"] = ""
        r = self.client.post(url, blank_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form div.has-error ")) == 1) # we get a warning about reconstructed name
        self.assertEqual(q("input[name=ascii]").val(), base_data["ascii"])

        # edit details
        r = self.client.post(url, base_data)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)

        self.assertEqual(person.name, "Test Nãme")
        self.assertEqual(person.ascii, "Test Name")
        self.assertEqual(Person.objects.filter(alias__name="Test Name", user__username=username).count(), 1)
        self.assertEqual(Person.objects.filter(alias__name="Test Nãme", user__username=username).count(), 1)
        self.assertEqual(Email.objects.filter(address=email_address, person__user__username=username, active=True).count(), 1)

        # deactivate address
        without_email_address = { k: v for k, v in base_data.items() if k != "active_emails" }

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


    def test_nomcom_dressing_on_profile(self):
        url = urlreverse('ietf.ietfauth.views.profile')

        nobody = PersonFactory()
        login_testing_unauthorized(self, nobody.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertFalse(q('#volunteer-button'))
        self.assertFalse(q('#volunteered'))

        year = datetime.date.today().year
        nomcom = NomComFactory(group__acronym=f'nomcom{year}',is_accepting_volunteers=True)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertTrue(q('#volunteer-button'))
        self.assertFalse(q('#volunteered'))

        nomcom.volunteer_set.create(person=nobody)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertFalse(q('#volunteer-button'))
        self.assertTrue(q('#volunteered'))


    def test_reset_password(self):
        url = urlreverse(ietf.ietfauth.views.password_reset)

        user = User.objects.create(username="someone@example.com", email="someone@example.com")
        user.set_password("forgotten")
        user.save()
        p = Person.objects.create(name="Some One", ascii="Some One", user=user)
        Email.objects.create(address=user.username, person=p, origin=user.username)
        
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
        review_req = ReviewRequestFactory()
        assignment = ReviewAssignmentFactory(review_request=review_req,reviewer=EmailFactory(person__user__username='reviewer'))
        RoleFactory(name_id='reviewer',group=review_req.team,person=assignment.reviewer.person)
        doc = review_req.doc

        reviewer = assignment.reviewer.person

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
        self.assertContains(r, review_req.doc.name)

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
        

    def test_change_password(self):

        chpw_url = urlreverse(ietf.ietfauth.views.change_password)
        prof_url = urlreverse(ietf.ietfauth.views.profile)
        login_url = urlreverse(ietf.ietfauth.views.login)
        redir_url = '%s?next=%s' % (login_url, chpw_url)

        # get without logging in
        r = self.client.get(chpw_url)
        self.assertRedirects(r, redir_url)

        user = User.objects.create(username="someone@example.com", email="someone@example.com")
        user.set_password("password")
        user.save()
        p = Person.objects.create(name="Some One", ascii="Some One", user=user)
        Email.objects.create(address=user.username, person=p, origin=user.username)

        # log in
        r = self.client.post(redir_url, {"username":user.username, "password":"password"})
        self.assertRedirects(r, chpw_url)

        # wrong current password
        r = self.client.post(chpw_url, {"current_password": "fiddlesticks",
                                        "new_password": "foobar",
                                        "new_password_confirmation": "foobar",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', 'current_password', 'Invalid password')

        # mismatching new passwords
        r = self.client.post(chpw_url, {"current_password": "password",
                                        "new_password": "foobar",
                                        "new_password_confirmation": "barfoo",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', None, "The password confirmation is different than the new password")

        # correct password change
        r = self.client.post(chpw_url, {"current_password": "password",
                                        "new_password": "foobar",
                                        "new_password_confirmation": "foobar",
                                       })
        self.assertRedirects(r, prof_url)
        # refresh user object
        user = User.objects.get(username="someone@example.com")
        self.assertTrue(user.check_password('foobar'))

    def test_change_username(self):

        chun_url = urlreverse(ietf.ietfauth.views.change_username)
        prof_url = urlreverse(ietf.ietfauth.views.profile)
        login_url = urlreverse(ietf.ietfauth.views.login)
        redir_url = '%s?next=%s' % (login_url, chun_url)

        # get without logging in
        r = self.client.get(chun_url)
        self.assertRedirects(r, redir_url)

        user = User.objects.create(username="someone@example.com", email="someone@example.com")
        user.set_password("password")
        user.save()
        p = Person.objects.create(name="Some One", ascii="Some One", user=user)
        Email.objects.create(address=user.username, person=p, origin=user.username)
        Email.objects.create(address="othername@example.org", person=p, origin=user.username)

        # log in
        r = self.client.post(redir_url, {"username":user.username, "password":"password"})
        self.assertRedirects(r, chun_url)

        # wrong username
        r = self.client.post(chun_url, {"username": "fiddlesticks",
                                        "password": "password",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', 'username',
            "Select a valid choice. fiddlesticks is not one of the available choices.")

        # wrong password
        r = self.client.post(chun_url, {"username": "othername@example.org",
                                        "password": "foobar",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r, 'form', 'password', 'Invalid password')

        # correct username change
        r = self.client.post(chun_url, {"username": "othername@example.org",
                                        "password": "password",
                                       })
        self.assertRedirects(r, prof_url)
        # refresh user object
        prev = user
        user = User.objects.get(username="othername@example.org")
        self.assertEqual(prev, user)
        self.assertTrue(user.check_password('password'))

    def test_apikey_management(self):
        # Create a person with a role that will give at least one valid apikey
        person =  RoleFactory(name_id='robot', group__acronym='secretariat').person

        url = urlreverse('ietf.ietfauth.views.apikey_index')

        # Check that the url is protected, then log in
        login_testing_unauthorized(self, person.user.username, url)

        # Check api key list content
        r = self.client.get(url)
        self.assertContains(r, 'Personal API keys')
        self.assertContains(r, 'Get a new personal API key')

        # Check the add key form content
        url = urlreverse('ietf.ietfauth.views.apikey_create')
        r = self.client.get(url)
        self.assertContains(r, 'Create a new personal API key')
        self.assertContains(r, 'Endpoint')

        # Add 2 keys
        endpoints = person.available_api_endpoints()
        for endpoint, display in endpoints:
            r = self.client.post(url, {'endpoint': endpoint})
            self.assertRedirects(r, urlreverse('ietf.ietfauth.views.apikey_index'))
        
        # Check api key list content
        url = urlreverse('ietf.ietfauth.views.apikey_index')
        r = self.client.get(url)
        for endpoint, display in endpoints:
            self.assertContains(r, endpoint)
        q = PyQuery(r.content)
        self.assertEqual(len(q('td code')), len(endpoints)) # hash
        self.assertEqual(len(q('td a:contains("Disable")')), len(endpoints))

        # Get one of the keys
        key = person.apikeys.first()

        # Check the disable key form content
        url = urlreverse('ietf.ietfauth.views.apikey_disable')
        r = self.client.get(url)

        self.assertContains(r, 'Disable a personal API key')
        self.assertContains(r, 'Key')
        
        # Delete a key
        r = self.client.post(url, {'hash': key.hash()})
        self.assertRedirects(r, urlreverse('ietf.ietfauth.views.apikey_index'))

        # Check the api key list content again
        url = urlreverse('ietf.ietfauth.views.apikey_index')
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('td code')), len(endpoints)) # key hash
        self.assertEqual(len(q('td a:contains("Disable")')), len(endpoints)-1)

    def test_apikey_errors(self):
        BAD_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        person = PersonFactory()
        area = GroupFactory(type_id='area')
        area.role_set.create(name_id='ad', person=person, email=person.email())

        url = urlreverse('ietf.ietfauth.views.apikey_create')
        # Check that the url is protected, then log in
        login_testing_unauthorized(self, person.user.username, url)

        # Add keys
        for endpoint, display in person.available_api_endpoints():
            r = self.client.post(url, {'endpoint': endpoint})
            self.assertRedirects(r, urlreverse('ietf.ietfauth.views.apikey_index'))

        for key in person.apikeys.all()[:3]:

            # bad method
            r = self.client.put(key.endpoint, {'apikey':key.hash()})
            self.assertContains(r, 'Method not allowed', status_code=405)

            # missing apikey
            r = self.client.post(key.endpoint, {'dummy':'dummy',})
            self.assertContains(r, 'Missing apikey parameter', status_code=400)

            # invalid apikey
            r = self.client.post(key.endpoint, {'apikey':BAD_KEY, 'dummy':'dummy',})
            self.assertContains(r, 'Invalid apikey', status_code=403)

            # invalid garbage apikey (decode error)
            r = self.client.post(key.endpoint, {'apikey':'foobar', 'dummy':'dummy',})
            self.assertContains(r, 'Invalid apikey', status_code=403)

            # invalid garbage apikey (struct unpack error)
            # number of characters in apikey must be divisible by 4
            r = self.client.post(key.endpoint, {'apikey':'foob', 'dummy':'dummy',})
            self.assertContains(r, 'Invalid apikey', status_code=403)

            # invalid apikey (invalidated api key)
            unauthorized_url = urlreverse('ietf.api.views.app_auth')
            invalidated_apikey = PersonalApiKey.objects.create(
                        endpoint=unauthorized_url, person=person, valid=False)
            r = self.client.post(unauthorized_url, {'apikey': invalidated_apikey.hash()})
            self.assertContains(r, 'Invalid apikey', status_code=403)

            # too long since regular login
            person.user.last_login = datetime.datetime.now() - datetime.timedelta(days=settings.UTILS_APIKEY_GUI_LOGIN_LIMIT_DAYS+1)
            person.user.save()
            r = self.client.post(key.endpoint, {'apikey':key.hash(), 'dummy':'dummy',})
            self.assertContains(r, 'Too long since last regular login', status_code=400)
            person.user.last_login = datetime.datetime.now()
            person.user.save()

            # endpoint mismatch
            key2 = PersonalApiKey.objects.create(person=person, endpoint='/')
            r = self.client.post(key.endpoint, {'apikey':key2.hash(), 'dummy':'dummy',})
            self.assertContains(r, 'Apikey endpoint mismatch', status_code=400)
            key2.delete()

    def test_send_apikey_report(self):
        from ietf.ietfauth.management.commands.send_apikey_usage_emails import Command
        from ietf.utils.mail import outbox, empty_outbox

        person =  RoleFactory(name_id='secr', group__acronym='secretariat').person

        url = urlreverse('ietf.ietfauth.views.apikey_create')
        # Check that the url is protected, then log in
        login_testing_unauthorized(self, person.user.username, url)

        # Add keys
        endpoints = person.available_api_endpoints()
        for endpoint, display in endpoints:
            r = self.client.post(url, {'endpoint': endpoint})
            self.assertRedirects(r, urlreverse('ietf.ietfauth.views.apikey_index'))
        
        # Use the endpoints (the form content will not be acceptable, but the
        # apikey usage will be registered)
        count = 2
        # avoid usage across dates
        if datetime.datetime.now().time() > datetime.time(hour=23, minute=59, second=58):
            time.sleep(2)
        for i in range(count):
            for key in person.apikeys.all():
                self.client.post(key.endpoint, {'apikey':key.hash(), 'dummy': 'dummy', })
        date = str(datetime.date.today())

        empty_outbox()
        cmd = Command()
        cmd.handle(verbosity=0, days=7)
        
        self.assertEqual(len(outbox), len(endpoints))
        for mail in outbox:
            body = get_payload_text(mail)
            self.assertIn("API key usage", mail['subject'])
            self.assertIn(" %s times" % count, body)
            self.assertIn(date, body)

    def test_edit_person_extresources(self):
        url = urlreverse('ietf.ietfauth.views.edit_person_externalresources')
        person = PersonFactory()

        r = self.client.get(url)
        self.assertNotEqual(r.status_code, 200)

        self.client.login(username=person.user.username,password=person.user.username+'+password')

        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('form textarea[id=id_resources]')),1)

        badlines = (
            'github_repo https://github3.com/some/repo',
            'github_notify  badaddr',
            'website /not/a/good/url',
            'notavalidtag blahblahblah',
            'website',
        )

        for line in badlines:
            r = self.client.post(url, dict(resources=line, submit="1"))
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            self.assertTrue(q('.alert-danger'))

        goodlines = """
            github_repo https://github.com/some/repo Some display text
            github_username githubuser
            webpage http://example.com/http/is/fine
        """

        r = self.client.post(url, dict(resources=goodlines, submit="1"))
        self.assertEqual(r.status_code,302)
        self.assertEqual(person.personextresource_set.count(), 3)
        self.assertEqual(person.personextresource_set.get(name__slug='github_repo').display_name, 'Some display text')
        self.assertIn(person.personextresource_set.first().name.slug, str(person.personextresource_set.first()))


class OpenIDConnectTests(TestCase):
    def request_matcher(self, request):
        method, url = str(request).split(None, 1)
        response = requests.Response()
        if method == 'GET':
            r = self.client.get(request.path)
        elif method == 'POST':
            data = dict(urllib.parse.parse_qsl(request.text))
            extra = request.headers
            for key in [ 'Authorization', ]:
                if key in request.headers:
                    extra['HTTP_%s'%key.upper()] = request.headers[key]
            r = self.client.post(request.path, data=data, **extra)
        else:
            raise ValueError('Unexpected method: %s' % method)
        response = requests.Response()
        response.status_code = r.status_code
        response.raw = r
        response.url = url
        response.request = request
        response._content = r.content
        response.encoding = 'utf-8'
        for (k,v) in r.items():
            response.headers[k] = v
        return response

    def test_oidc_code_auth(self):

        key = RSA.generate(2048)
        RSAKey.objects.create(key=key.exportKey('PEM').decode('utf8'))

        r = self.client.get('/')
        host = r.wsgi_request.get_host()

        redirect_uris = [
                'https://foo.example.com/',
            ]
        oid_client_record = OidClientRecordFactory(_redirect_uris='\n'.join(redirect_uris), )

        with requests_mock.Mocker() as mock:
            pass
            mock._adapter.add_matcher(self.request_matcher)

            # Get a client
            client = OidClient(client_authn_method=CLIENT_AUTHN_METHOD)

            # Get provider info
            client.provider_config( 'http://%s/api/openid' % host)

            # No registration step -- we only support this out-of-band

            # Set shared client/provider information in the client
            client_reg = RegistrationResponse(  client_id= oid_client_record.client_id,
                                                client_secret= oid_client_record.client_secret)
            client.store_registration_info(client_reg)

            # Get a user for which we want to get access
            person = PersonFactory(with_bio=True)
            active_group = RoleFactory(name_id='chair', person=person).group
            closed_group = RoleFactory(name_id='chair', person=person, group__state_id='conclude').group
            # an additional email
            EmailFactory(person=person)
            email_list = person.email_set.all().values_list('address', flat=True)
            meeting = MeetingFactory(type_id='ietf', date=datetime.date.today())
            MeetingRegistration.objects.create(
                    meeting=meeting, person=None, first_name=person.first_name(), last_name=person.last_name(),
                    email=email_list[0], ticket_type='full_week', reg_type='remote', affiliation='Some Company',
                )

            # Get access authorisation
            session = {}
            session["state"] = rndstr()
            session["nonce"] = rndstr()
            args = {
                "response_type": "code",
                "scope": ['openid', 'profile', 'email', 'roles', 'registration', 'dots' ],
                "nonce": session["nonce"],
                "redirect_uri": redirect_uris[0],
                "state": session["state"]
            }
            auth_req = client.construct_AuthorizationRequest(request_args=args)
            auth_url = auth_req.request(client.authorization_endpoint)
            r = self.client.get(auth_url, follow=True)
            self.assertEqual(r.status_code, 200)
            login_url, __ = r.redirect_chain[-1]
            self.assertTrue(login_url.startswith(urlreverse('ietf.ietfauth.views.login')))
 
            # Do login
            username = person.user.username
            r = self.client.post(login_url, {'username':username, 'password':'%s+password'%username}, follow=True)
            self.assertContains(r, 'Request for Permission')
            q = PyQuery(r.content)
            forms = q('form[action="/api/openid/authorize"]')
            self.assertEqual(len(forms), 1)
 
            # Authorize the client to access account information
            data = {'allow': 'Authorize'}
            for input in q('form[action="/api/openid/authorize"] input[type="hidden"]'):
                name = input.get("name")
                value = input.get("value")
                data[name] = value
            r = self.client.post(urlreverse('oidc_provider:authorize'), data)

            # Check authorization returns
            self.assertEqual(r.status_code, 302)
            location = r['Location']
            self.assertTrue(location.startswith(redirect_uris[0]))
            self.assertIn('state=%s'%data['state'], location)

            # Extract the grant code
            params = client.parse_response(AuthorizationResponse, info=urllib.parse.urlsplit(location).query, sformat="urlencoded")

            # Use grant code to get access token
            access_token_info = client.do_access_token_request(state=params['state'],
                                    authn_method='client_secret_basic')

            for key in ['access_token', 'refresh_token', 'token_type', 'expires_in', 'id_token']:
                self.assertIn(key, access_token_info)
            for key in ['iss', 'sub', 'aud', 'exp', 'iat', 'auth_time', 'nonce', 'at_hash']:
                self.assertIn(key, access_token_info['id_token'])

            # Get userinfo, check keys present
            userinfo = client.do_user_info_request(state=params["state"], scope=args['scope'])
            for key in [ 'email', 'family_name', 'given_name', 'meeting', 'name', 'roles',
                         'ticket_type', 'reg_type', 'affiliation', 'picture', 'dots', ]:
                self.assertIn(key, userinfo)
                self.assertTrue(userinfo[key])
            self.assertIn('remote', set(userinfo['reg_type'].split()))
            self.assertNotIn('hackathon', set(userinfo['reg_type'].split()))
            self.assertIn(active_group.acronym, [i[1] for i in userinfo['roles']])
            self.assertNotIn(closed_group.acronym, [i[1] for i in userinfo['roles']])

            # Create another registration, with a different email
            MeetingRegistration.objects.create(
                    meeting=meeting, person=None, first_name=person.first_name(), last_name=person.last_name(),
                    email=email_list[1], ticket_type='one_day', reg_type='hackathon', affiliation='Some Company, Inc',
                )
            userinfo = client.do_user_info_request(state=params["state"], scope=args['scope'])
            self.assertIn('hackathon', set(userinfo['reg_type'].split()))
            self.assertIn('remote', set(userinfo['reg_type'].split()))
            self.assertIn('full_week', set(userinfo['ticket_type'].split()))
            self.assertIn('Some Company', userinfo['affiliation'])

            # Create a third registration, with a composite reg type
            MeetingRegistration.objects.create(
                    meeting=meeting, person=None, first_name=person.first_name(), last_name=person.last_name(),
                    email=email_list[1], ticket_type='one_day', reg_type='hackathon remote', affiliation='Some Company, Inc',
                )
            userinfo = client.do_user_info_request(state=params["state"], scope=args['scope'])
            self.assertEqual(set(userinfo['reg_type'].split()), set(['remote', 'hackathon']))

            # Check that ending a session works
            r = client.do_end_session_request(state=params["state"], scope=args['scope'])
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r.headers["Location"], urlreverse('ietf.ietfauth.views.login'))

            # The pyjwkent.jwt and oic.utils.keyio modules have had problems with calling
            # logging.debug() instead of logger.debug(), which results in setting a root
            # handler, causing later logging to become visible even if that wasn't intended.
            # Fail here if that happens.
            self.assertEqual(logging.root.handlers, [])

