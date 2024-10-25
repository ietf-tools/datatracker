# Copyright The IETF Trust 2009-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import logging                          # pyflakes:ignore
import re
import requests
import requests_mock
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
from urllib.parse import urlsplit

import django.core.signing
from django.urls import reverse as urlreverse
from django.contrib.auth.models import User
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.group.models import Group, Role, RoleName
from ietf.ietfauth.utils import has_role
from ietf.meeting.factories import MeetingFactory
from ietf.nomcom.factories import NomComFactory
from ietf.person.factories import PersonFactory, EmailFactory, UserFactory, PersonalApiKeyFactory
from ietf.person.models import Person, Email
from ietf.person.tasks import send_apikey_usage_emails_task
from ietf.review.factories import ReviewRequestFactory, ReviewAssignmentFactory
from ietf.review.models import ReviewWish, UnavailablePeriod
from ietf.stats.models import MeetingRegistration
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import TestCase, login_testing_unauthorized
from ietf.utils.timezone import date_today


class IetfAuthTests(TestCase):

    def test_index(self):
        self.assertEqual(self.client.get(urlreverse("ietf.ietfauth.views.index")).status_code, 200)

    def test_login_and_logout(self):
        PersonFactory(user__username='plain')

        # try logging in without a next
        r = self.client.get(urlreverse("ietf.ietfauth.views.login"))
        self.assertEqual(r.status_code, 200)

        r = self.client.post(urlreverse("ietf.ietfauth.views.login"), {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse("ietf.ietfauth.views.profile"))

        # try logging out
        r = self.client.post(urlreverse('django.contrib.auth.views.logout'), {})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "accounts/logout")

        r = self.client.get(urlreverse("ietf.ietfauth.views.profile"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse("ietf.ietfauth.views.login"))

        # try logging in with a next
        r = self.client.post(urlreverse("ietf.ietfauth.views.login") + "?next=/foobar", {"username":"plain", "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], "/foobar")

    def test_login_button(self):
        PersonFactory(user__username='plain')

        def _test_login(url):
            # try mashing the sign-in button repeatedly
            r = self.client.get(url)
            if r.status_code == 302:
                r = self.client.get(r["Location"])
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            login_url = q("a:Contains('Sign in')").attr("href")
            self.assertEqual(login_url, "/accounts/login/?next=" + url)
            r = self.client.get(login_url)
            self.assertEqual(r.status_code, 200)
            q = PyQuery(r.content)
            login_url = q("a:Contains('Sign in')").attr("href")
            self.assertEqual(login_url, "/accounts/login/?next=" + url)

            # try logging in with the provided next
            r = self.client.post(login_url, {"username":"plain", "password":"plain+password"})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(urlsplit(r["Location"])[2], url)
            self.client.logout()

        # try with a trivial next
        _test_login("/")
        # try with a next that requires login
        _test_login(urlreverse("ietf.ietfauth.views.profile"))

    def test_login_with_different_email(self):
        person = PersonFactory(user__username='plain')
        email = EmailFactory(person=person)

        # try logging in without a next
        r = self.client.get(urlreverse("ietf.ietfauth.views.login"))
        self.assertEqual(r.status_code, 200)

        r = self.client.post(urlreverse("ietf.ietfauth.views.login"), {"username":email, "password":"plain+password"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(urlsplit(r["Location"])[2], urlreverse("ietf.ietfauth.views.profile"))

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


# For the lowered barrier to account creation period, we are disabling this kind of failure
    # def test_create_account_failure(self):

    #     url = urlreverse("ietf.ietfauth.views.create_account")

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

    def register(self, email):
        url = urlreverse("ietf.ietfauth.views.create_account")

        # register email
        empty_outbox()
        r = self.client.post(url, { 'email': email })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Account request received")
        self.assertEqual(len(outbox), 1)

    def register_and_verify(self, email):
        self.register(email)

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

        
    # This also tests new account creation.
    def test_create_existing_account(self):
        # create account once
        email = "new-account@example.com"
        self.register_and_verify(email)

        # create account again
        self.register(email)

        # check notification
        note = get_payload_text(outbox[-1])
        self.assertIn(email, note)
        self.assertIn("A datatracker account for that email already exists", note)
        self.assertIn(urlreverse("ietf.ietfauth.views.password_reset"), note)

    def test_ietfauth_profile(self):
        EmailFactory(person__user__username='plain')
        GroupFactory(acronym='mars')

        username = "plain"
        email_address = Email.objects.filter(person__user__username=username).first().address

        url = urlreverse("ietf.ietfauth.views.profile")
        login_testing_unauthorized(self, username, url)


        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q('.form-control-plaintext:contains("%s")' % username)), 1)
        self.assertEqual(len(q('[name="active_emails"][value="%s"][checked]' % email_address)), 1)

        base_data = {
            "name": "Test Nãme",
            "plain": "",
            "ascii": "Test Name",
            "ascii_short": "T. Name",
            "pronouns_freetext": "foo/bar",
            "affiliation": "Test Org",
            "active_emails": email_address,
        }

        # edit details - faulty ASCII
        faulty_ascii = base_data.copy()
        faulty_ascii["ascii"] = "Test Nãme"
        r = self.client.post(url, faulty_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .invalid-feedback")) == 1)

        # edit details - blank ASCII
        blank_ascii = base_data.copy()
        blank_ascii["ascii"] = ""
        r = self.client.post(url, blank_ascii)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form div.invalid-feedback")) == 1) # we get a warning about reconstructed name
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

        # try and add it again
        empty_outbox()
        r = self.client.post(url, with_new_email_address)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)
        note = get_payload_text(outbox[-1])
        self.assertIn(new_email_address, note)
        self.assertIn("already associated with your account", note)

        pronoundish = base_data.copy()
        pronoundish["pronouns_freetext"] = "baz/boom"
        r = self.client.post(url, pronoundish)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)
        self.assertEqual(person.pronouns_freetext,"baz/boom")       
        pronoundish["pronouns_freetext"]=""
        r = self.client.post(url, pronoundish)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)
        self.assertEqual(person.pronouns_freetext, None)

        pronoundish = base_data.copy()
        del pronoundish["pronouns_freetext"]
        pronoundish["pronouns_selectable"] = []
        r = self.client.post(url, pronoundish)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)
        self.assertEqual(person.pronouns_selectable,[])
        pronoundish["pronouns_selectable"] = ['he/him','she/her']
        r = self.client.post(url, pronoundish)
        self.assertEqual(r.status_code, 200)
        person = Person.objects.get(user__username=username)
        self.assertEqual(person.pronouns_selectable,['he/him','she/her'])
        self.assertEqual(person.pronouns(),"he/him, she/her")

        # Can't have both selectables and freetext
        pronoundish["pronouns_freetext"] = "foo/bar/baz"
        r = self.client.post(url, pronoundish)
        self.assertContains(r, 'but not both' ,status_code=200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form div.invalid-feedback")) == 1)


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

    def test_email_case_insensitive_protection(self):
        EmailFactory(address="TestAddress@example.net")
        person = PersonFactory()
        url = urlreverse("ietf.ietfauth.views.profile")
        login_testing_unauthorized(self, person.user.username, url)

        data = {
            "name": person.name,
            "plain": person.plain,
            "ascii": person.ascii,
            "active_emails": [e.address for e in person.email_set.filter(active=True)],
            "new_email": "testaddress@example.net",
        }
        r = self.client.post(url, data)
        self.assertContains(r, "A confirmation email has been sent to", status_code=200)

    def test_nomcom_dressing_on_profile(self):
        url = urlreverse('ietf.ietfauth.views.profile')

        nobody = PersonFactory()
        login_testing_unauthorized(self, nobody.user.username, url)
        r = self.client.get(url)
        self.assertEqual(r.status_code,200)
        q = PyQuery(r.content)
        self.assertFalse(q('#volunteer-button'))
        self.assertFalse(q('#volunteered'))

        year = date_today().year
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
        url = urlreverse("ietf.ietfauth.views.password_reset")
        email = 'someone@example.com'
        password = 'foobar'

        user = PersonFactory(user__email=email).user
        user.set_password(password)
        user.save()

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        # ask for reset, wrong username (form should not fail)
        r = self.client.post(url, { 'username': "nobody@example.com" })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .is-invalid")) == 0)

        # ask for reset
        empty_outbox()
        r = self.client.post(url, { 'username': user.username })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)

        # goto change password page, logged in as someone else
        confirm_url = self.extract_confirm_url(outbox[-1])
        other_user = UserFactory()
        self.client.login(username=other_user.username, password=other_user.username + '+password')
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 403)

        # sign out and go back to change password page
        self.client.logout()
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertNotIn(user.username, q('.nav').text(),
                         'user should not appear signed in while resetting password')

        # password mismatch
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'nosecret' })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .is-invalid")) > 0)

        # confirm
        r = self.client.post(confirm_url, { 'password': 'secret', 'password_confirmation': 'secret' })
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEqual(len(q("form .is-invalid")), 0)

        # reuse reset url
        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 404)

        # login after reset request
        empty_outbox()
        user.set_password(password)
        user.save()

        r = self.client.post(url, { 'username': user.username })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)
        confirm_url = self.extract_confirm_url(outbox[-1])

        r = self.client.post(urlreverse("ietf.ietfauth.views.login"), {'username': email, 'password': password})

        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 404)

        # change password after reset request
        empty_outbox()

        r = self.client.post(url, { 'username': user.username })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(outbox), 1)
        confirm_url = self.extract_confirm_url(outbox[-1])

        user.set_password('newpassword')
        user.save()

        r = self.client.get(confirm_url)
        self.assertEqual(r.status_code, 404)

    def test_reset_password_without_person(self):
        """No password reset for account without a person"""
        url = urlreverse('ietf.ietfauth.views.password_reset')
        user = UserFactory()
        user.set_password('some password')
        user.save()
        empty_outbox()
        r = self.client.post(url, { 'username': user.username})
        self.assertContains(r, 'We have sent you an email with instructions', status_code=200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .is-invalid")) == 0)
        self.assertEqual(len(outbox), 0)

    def test_reset_password_address_handling(self):
        """Reset password links are only sent to known, active addresses"""
        url = urlreverse('ietf.ietfauth.views.password_reset')
        person = PersonFactory()
        person.email_set.update(active=False)
        empty_outbox()
        r = self.client.post(url, { 'username': person.user.username})
        self.assertContains(r, 'We have sent you an email with instructions', status_code=200)
        q = PyQuery(r.content)
        self.assertTrue(len(q("form .is-invalid")) == 0)
        self.assertEqual(len(outbox), 0)

        active_address = EmailFactory(person=person).address
        r = self.client.post(url, {'username': person.user.username})
        self.assertContains(r, 'We have sent you an email with instructions', status_code=200)
        self.assertEqual(len(outbox), 1)
        to = outbox[0].get('To')
        self.assertIn(active_address, to)
        self.assertNotIn(person.user.username, to)

    def test_reset_password_without_username(self):
        """Reset password using non-username email address"""
        url = urlreverse('ietf.ietfauth.views.password_reset')
        person = PersonFactory()
        secondary_address = EmailFactory(person=person).address
        inactive_secondary_address = EmailFactory(person=person, active=False).address
        empty_outbox()
        r = self.client.post(url, { 'username': secondary_address})
        self.assertContains(r, 'We have sent you an email with instructions', status_code=200)
        self.assertEqual(len(outbox), 1)
        to = outbox[0].get('To')
        self.assertIn(person.user.username, to)
        self.assertIn(secondary_address, to)
        self.assertNotIn(inactive_secondary_address, to)

    def test_reset_password_without_user(self):
        """Reset password using email address for person without a user account"""
        url = urlreverse('ietf.ietfauth.views.password_reset')
        email = EmailFactory()
        person = email.person
        # Remove the user object from the person to get a Email/Person without User:
        person.user = None
        person.save()
        # Remove the remaining User record, since reset_password looks for that by username:
        User.objects.filter(username__iexact=email.address).delete()
        empty_outbox()
        r = self.client.post(url, { 'username': email.address })
        self.assertEqual(len(outbox), 1)
        lastReceivedEmail = outbox[-1]
        self.assertIn(email.address, lastReceivedEmail.get('To'))
        self.assertTrue(lastReceivedEmail.get('Subject').startswith("Confirm password reset"))
        self.assertContains(r, "Your password reset request has been successfully received", status_code=200)

    def test_review_overview(self):
        review_req = ReviewRequestFactory()
        assignment = ReviewAssignmentFactory(review_request=review_req,reviewer=EmailFactory(person__user__username='reviewer'))
        RoleFactory(name_id='reviewer',group=review_req.team,person=assignment.reviewer.person)
        doc = review_req.doc

        reviewer = assignment.reviewer.person

        UnavailablePeriod.objects.create(
            team=review_req.team,
            person=reviewer,
            start_date=date_today() - datetime.timedelta(days=10),
            availability="unavailable",
        )

        url = urlreverse("ietf.ietfauth.views.review_overview")

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

    def test_change_password(self):
        chpw_url = urlreverse("ietf.ietfauth.views.change_password")
        prof_url = urlreverse("ietf.ietfauth.views.profile")
        login_url = urlreverse("ietf.ietfauth.views.login")
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
        self.assertFormError(r.context["form"], 'current_password', 'Invalid password')

        # mismatching new passwords
        r = self.client.post(chpw_url, {"current_password": "password",
                                        "new_password": "foobar",
                                        "new_password_confirmation": "barfoo",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r.context["form"], None, "The password confirmation is different than the new password")

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

        chun_url = urlreverse("ietf.ietfauth.views.change_username")
        prof_url = urlreverse("ietf.ietfauth.views.profile")
        login_url = urlreverse("ietf.ietfauth.views.login")
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
        self.assertFormError(r.context["form"], 'username',
            "Select a valid choice. fiddlesticks is not one of the available choices.")

        # wrong password
        r = self.client.post(chun_url, {"username": "othername@example.org",
                                        "password": "foobar",
                                       })
        self.assertEqual(r.status_code, 200)
        self.assertFormError(r.context["form"], 'password', 'Invalid password')

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
        self.assertContains(r, 'API keys')
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
        self.assertEqual(len(q('td code')), len(endpoints) * 2) # hash and endpoint
        self.assertEqual(len(q('td a:contains("Disable")')), len(endpoints))

        # Get one of the keys
        key = person.apikeys.first()

        # Check the disable key form content
        url = urlreverse('ietf.ietfauth.views.apikey_disable')
        r = self.client.get(url)

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Disable a personal API key')
        self.assertContains(r, 'Key')

        # Try to delete something that doesn't exist
        r = self.client.post(url, {'hash': key.hash()+'bad'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r,"Key validation failed; key not disabled")

        # Try to delete someone else's key
        otherkey = PersonalApiKeyFactory()
        r = self.client.post(url, {'hash': otherkey.hash()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r,"Key validation failed; key not disabled")
        
        # Delete a key
        r = self.client.post(url, {'hash': key.hash()})
        self.assertRedirects(r, urlreverse('ietf.ietfauth.views.apikey_index'))

        # Check the api key list content again
        url = urlreverse('ietf.ietfauth.views.apikey_index')
        r = self.client.get(url)
        q = PyQuery(r.content)
        self.assertEqual(len(q('td code')), len(endpoints) * 2) # key hash and endpoint
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
            unauthorized_url = urlreverse('ietf.api.views.app_auth', kwargs={'app': 'authortools'})
            invalidated_apikey = PersonalApiKeyFactory(endpoint=unauthorized_url, person=person, valid=False)
            r = self.client.post(unauthorized_url, {'apikey': invalidated_apikey.hash()})
            self.assertContains(r, 'Invalid apikey', status_code=403)

            # too long since regular login
            person.user.last_login = timezone.now() - datetime.timedelta(days=settings.UTILS_APIKEY_GUI_LOGIN_LIMIT_DAYS+1)
            person.user.save()
            r = self.client.post(key.endpoint, {'apikey':key.hash(), 'dummy':'dummy',})
            self.assertContains(r, 'Too long since last regular login', status_code=400)
            person.user.last_login = timezone.now()
            person.user.save()

            # endpoint mismatch
            key2 = PersonalApiKeyFactory(
                person=person,
                endpoint='/',
                validate_model=False,  # allow invalid endpoint
            )
            r = self.client.post(key.endpoint, {'apikey':key2.hash(), 'dummy':'dummy',})
            self.assertContains(r, 'Apikey endpoint mismatch', status_code=400)
            key2.delete()

    def test_send_apikey_report(self):
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
        if timezone.now().time() > datetime.time(hour=23, minute=59, second=58):
            time.sleep(2)
        for i in range(count):
            for key in person.apikeys.all():
                self.client.post(key.endpoint, {'apikey':key.hash(), 'dummy': 'dummy', })
        date = str(date_today())

        empty_outbox()
        send_apikey_usage_emails_task(days=7)

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
            self.assertTrue(q('.invalid-feedback'))

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

    def test_confirm_new_email(self):
        person = PersonFactory()
        valid_auth = django.core.signing.dumps(
            [person.user.username, "new_email@example.com"], salt="add_email"
        )
        invalid_auth = django.core.signing.dumps(
            [person.user.username, "not_this_one@example.com"], salt="pepper"
        )

        # Test that we check the salt
        r = self.client.get(
            urlreverse("ietf.ietfauth.views.confirm_new_email", kwargs={"auth": invalid_auth})
        )
        self.assertEqual(r.status_code, 404)
        r = self.client.post(
            urlreverse("ietf.ietfauth.views.confirm_new_email", kwargs={"auth": invalid_auth})
        )
        self.assertEqual(r.status_code, 404)

        # Now check that the valid auth works
        self.assertFalse(
            person.email_set.filter(address__icontains="new_email@example.com").exists()
        )
        confirm_url = urlreverse(
            "ietf.ietfauth.views.confirm_new_email", kwargs={"auth": valid_auth}
        )
        r = self.client.get(confirm_url)
        self.assertContains(r, urllib.parse.quote(confirm_url), status_code=200)
        r = self.client.post(confirm_url, data={"action": "confirm"})
        self.assertContains(r, "has been updated", status_code=200)
        self.assertTrue(
            person.email_set.filter(address__icontains="new_email@example.com").exists()
        )

        # Authorizing a second time should be handled gracefully
        r = self.client.post(confirm_url, data={"action": "confirm"})
        self.assertContains(r, "already includes", status_code=200)

        # Another person should not be able to add the same address and should be told so,
        # whether they use the same or different letter case
        other_person = PersonFactory()
        other_auth = django.core.signing.dumps(
            [other_person.user.username, "new_email@example.com"], salt="add_email"
        )
        r = self.client.post(
            urlreverse("ietf.ietfauth.views.confirm_new_email", kwargs={"auth": other_auth}),
            data={"action": "confirm"},
        )
        self.assertContains(r, "in use by another user", status_code=200)

        other_auth = django.core.signing.dumps(
            [other_person.user.username, "NeW_eMaIl@eXaMpLe.CoM"], salt="add_email"
        )
        r = self.client.post(
            urlreverse("ietf.ietfauth.views.confirm_new_email", kwargs={"auth": other_auth}),
            data={"action": "confirm"},
        )

        self.assertContains(r, "in use by another user", status_code=200)
        self.assertFalse(
            other_person.email_set.filter(address__icontains="new_email@example.com").exists()
        )
        self.assertTrue(
            person.email_set.filter(address__icontains="new_email@example.com").exists()
        )


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
            person = PersonFactory(with_bio=True, pronouns_freetext="foo/bar")
            active_group = RoleFactory(name_id='chair', person=person).group
            closed_group = RoleFactory(name_id='chair', person=person, group__state_id='conclude').group
            # an additional email
            EmailFactory(person=person)
            email_list = person.email_set.all().values_list('address', flat=True)
            meeting = MeetingFactory(type_id='ietf', date=date_today())
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
                "scope": ['openid', 'profile', 'email', 'roles', 'registration', 'dots', 'pronouns' ],
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
            for key in [ 'email', 'family_name', 'given_name', 'meeting', 'name', 'pronouns', 'roles',
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


class UtilsTests(TestCase):
    def test_has_role_empty_role_names(self):
        """has_role is False if role_names is empty"""
        role = RoleFactory(name_id='secr', group__acronym='secretariat')
        self.assertTrue(has_role(role.person.user, ['Secretariat']), 'Test is broken')
        self.assertFalse(has_role(role.person.user, []), 'has_role() should return False when role_name is empty')
