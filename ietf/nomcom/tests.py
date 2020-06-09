# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import random
import shutil

from pyquery import PyQuery
from urllib.parse import urlparse

from django.db import IntegrityError
from django.db.models import Max
from django.conf import settings
from django.core.files import File
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.encoding import force_str

import debug                            # pyflakes:ignore

from ietf.dbtemplate.factories import DBTemplateFactory
from ietf.dbtemplate.models import DBTemplate
from ietf.group.models import Group
from ietf.meeting.factories import MeetingFactory
from ietf.message.models import Message
from ietf.nomcom.test_data import nomcom_test_data, generate_cert, check_comments, \
                                  COMMUNITY_USER, CHAIR_USER, \
                                  MEMBER_USER, SECRETARIAT_USER, EMAIL_DOMAIN, NOMCOM_YEAR
from ietf.nomcom.models import NomineePosition, Position, Nominee, \
                               NomineePositionStateName, Feedback, FeedbackTypeName, \
                               Nomination, FeedbackLastSeen, TopicFeedbackLastSeen, ReminderDates
from ietf.nomcom.management.commands.send_reminders import Command, is_time_to_send
from ietf.nomcom.factories import NomComFactory, FeedbackFactory, TopicFactory, \
                                  nomcom_kwargs_for_year, provide_private_key_to_test_client, \
                                  key
from ietf.nomcom.utils import get_nomcom_by_year, make_nomineeposition, get_hash_nominee_position
from ietf.person.factories import PersonFactory, EmailFactory
from ietf.person.models import Email, Person
from ietf.stats.models import MeetingRegistration
from ietf.utils.mail import outbox, empty_outbox, get_payload_text
from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent

client_test_cert_files = None

def get_cert_files():
    global client_test_cert_files
    if not client_test_cert_files:
        client_test_cert_files = generate_cert()
    return client_test_cert_files

def setup_test_public_keys_dir(obj):
    obj.saved_nomcom_public_keys_dir = settings.NOMCOM_PUBLIC_KEYS_DIR
    obj.nomcom_public_keys_dir = obj.tempdir('nomcom-public-keys')
    settings.NOMCOM_PUBLIC_KEYS_DIR = obj.nomcom_public_keys_dir

def teardown_test_public_keys_dir(obj):
    settings.NOMCOM_PUBLIC_KEYS_DIR = obj.saved_nomcom_public_keys_dir
    shutil.rmtree(obj.nomcom_public_keys_dir)

class NomcomViewsTest(TestCase):
    """Tests to create a new nomcom"""

    def check_url_status(self, url, status):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)
        return response

    def setUp(self):
        setup_test_public_keys_dir(self)
        nomcom_test_data()
        self.cert_file, self.privatekey_file = get_cert_files()
        self.year = NOMCOM_YEAR
        self.email_from = settings.NOMCOM_FROM_EMAIL.format(year=self.year)
        self.assertIn(self.year, self.email_from)

        # private urls
        self.private_index_url = reverse('ietf.nomcom.views.private_index', kwargs={'year': self.year})
        self.private_merge_person_url = reverse('ietf.nomcom.views.private_merge_person', kwargs={'year': self.year})
        self.private_merge_nominee_url = reverse('ietf.nomcom.views.private_merge_nominee', kwargs={'year': self.year})
        self.edit_members_url = reverse('ietf.nomcom.views.edit_members', kwargs={'year': self.year})
        self.edit_nomcom_url = reverse('ietf.nomcom.views.edit_nomcom', kwargs={'year': self.year})
        self.private_nominate_url = reverse('ietf.nomcom.views.private_nominate', kwargs={'year': self.year})
        self.private_nominate_newperson_url = reverse('ietf.nomcom.views.private_nominate_newperson', kwargs={'year': self.year})
        self.add_questionnaire_url = reverse('ietf.nomcom.views.private_questionnaire', kwargs={'year': self.year})
        self.private_feedback_url = reverse('ietf.nomcom.views.private_feedback', kwargs={'year': self.year})
        self.positions_url = reverse('ietf.nomcom.views.list_positions', kwargs={'year': self.year})        
        self.edit_position_url = reverse('ietf.nomcom.views.edit_position', kwargs={'year': self.year})

        # public urls
        self.index_url = reverse('ietf.nomcom.views.year_index', kwargs={'year': self.year})
        self.requirements_url = reverse('ietf.nomcom.views.requirements', kwargs={'year': self.year})
        self.questionnaires_url = reverse('ietf.nomcom.views.questionnaires', kwargs={'year': self.year})
        self.public_feedback_url = reverse('ietf.nomcom.views.public_feedback', kwargs={'year': self.year})
        self.public_nominate_url = reverse('ietf.nomcom.views.public_nominate', kwargs={'year': self.year})
        self.public_nominate_newperson_url = reverse('ietf.nomcom.views.public_nominate_newperson', kwargs={'year': self.year})

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def access_member_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        self.check_url_status(url, 200)
        self.client.logout()
        login_testing_unauthorized(self, MEMBER_USER, url)
        return self.check_url_status(url, 200)

    def access_chair_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, MEMBER_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        return self.check_url_status(url, 200)

    def access_secretariat_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        login_testing_unauthorized(self, SECRETARIAT_USER, url)
        return self.check_url_status(url, 200)

    def test_private_index_view(self):
        """Verify private home view"""
        self.access_member_url(self.private_index_url)

        # Verify that nominee table has links to person and feedback pages
        nom_pos = self.create_nominee('accepted', COMMUNITY_USER, 'APP')
        person_url = reverse('ietf.person.views.profile', 
                             kwargs={'email_or_name': nom_pos.nominee.name()})
        feedback_url = reverse('ietf.nomcom.views.view_feedback_nominee', 
                               kwargs={'year': self.year, 'nominee_id': nom_pos.nominee.pk})

        # With a single nominee, the first row will have our data.
        # Require that the row have at least one link to the person URL
        # and one to the feedback URL.
        response = self.client.get(self.private_index_url)
        q = PyQuery(response.content)
        row_q = q('#nominee-position-table tbody tr').eq(0)
        self.assertTrue(row_q('a[href="%s"]' % (person_url)), 
                        'Nominee table does not link to nominee profile page')
        self.assertTrue(row_q('a[href="%s#comment"]' % (feedback_url)), 
                        'Nominee table does not link to nominee feedback page')
        self.client.logout()

    def create_nominee(self, base_state, username, pos_name):
        cnominee = Nominee.objects.get(email__person__user__username=username)
        position = Position.objects.get(name=pos_name)
        return NomineePosition.objects.create(position=position,
                                              nominee=cnominee,
                                              state=NomineePositionStateName.objects.get(slug=base_state))

    def create_nominees_for_states(self, base_state):
        nom_pos = self.create_nominee(base_state, COMMUNITY_USER, 'APP')
        self.create_nominee(base_state, COMMUNITY_USER, 'INT')
        self.create_nominee(base_state, COMMUNITY_USER, 'OAM')
        return nom_pos

    def test_private_index_post_accept(self):
        nom_pos = self.create_nominees_for_states('pending')
        login_testing_unauthorized(self, CHAIR_USER, self.private_index_url)
        test_data = {"action": "set_as_accepted",
                     "selected": [nom_pos.pk]}
        r = self.client.post(self.private_index_url, test_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.alert-success'))
        self.assertEqual(NomineePosition.objects.filter(state='accepted').count (), 1)
        self.client.logout()

    def test_private_index_post_decline(self):
        nom_pos = self.create_nominees_for_states('pending')
        login_testing_unauthorized(self, CHAIR_USER, self.private_index_url)
        test_data = {"action": "set_as_declined",
                     "selected": [nom_pos.pk]}
        r = self.client.post(self.private_index_url, test_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.alert-success'))
        self.assertEqual(NomineePosition.objects.filter(state='declined').count (), 1)
        self.client.logout()

    def test_private_index_post_pending(self):
        nom_pos = self.create_nominees_for_states('declined')
        login_testing_unauthorized(self, CHAIR_USER, self.private_index_url)
        test_data = {"action": "set_as_pending",
                     "selected": [nom_pos.pk]}
        r = self.client.post(self.private_index_url, test_data)
        self.assertEqual(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(q('.alert-success'))
        self.assertEqual(NomineePosition.objects.filter(state='pending').count (), 1)
        self.client.logout()


    def test_private_merge_view(self):
        """Verify private nominee merge view"""

        nominees = ['nominee0@example.com',
                    'nominee1@example.com',
                    'nominee2@example.com',
                    'nominee3@example.com']

        # do nominations
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)
        self.nominate_view(public=True,
                           nominee_email=nominees[0],
                           position='IAOC')
        self.nominate_view(public=True,
                           nominee_email=nominees[0],
                           position='IAOC')
        self.nominate_view(public=True,
                           nominee_email=nominees[0],
                           position='IAB')
        self.nominate_view(public=True,
                           nominee_email=nominees[0],
                           position='TSV')
        self.nominate_view(public=True,
                           nominee_email=nominees[1],
                           position='IAOC')
        self.nominate_view(public=True,
                           nominee_email=nominees[1],
                           position='IAOC')
        self.nominate_view(public=True,
                           nominee_email=nominees[2],
                           position='IAB')
        self.nominate_view(public=True,
                           nominee_email=nominees[2],
                           position='IAB')
        self.nominate_view(public=True,
                           nominee_email=nominees[3],
                           position='TSV')
        self.nominate_view(public=True,
                           nominee_email=nominees[3],
                           position='TSV')
        # Check nominee positions
        self.assertEqual(NomineePosition.objects.count(), 6)
        self.assertEqual(Feedback.objects.nominations().count(), 10)

        # Accept and declined nominations
        nominee_position = NomineePosition.objects.get(position__name='IAOC',
                                                       nominee__email__address=nominees[0])
        nominee_position.state = NomineePositionStateName.objects.get(slug='accepted')
        nominee_position.save()

        nominee_position = NomineePosition.objects.get(position__name='IAOC',
                                                       nominee__email__address=nominees[1])
        nominee_position.state = NomineePositionStateName.objects.get(slug='declined')
        nominee_position.save()

        nominee_position = NomineePosition.objects.get(position__name='IAB',
                                                       nominee__email__address=nominees[2])
        nominee_position.state = NomineePositionStateName.objects.get(slug='declined')
        nominee_position.save()

        nominee_position = NomineePosition.objects.get(position__name='TSV',
                                                       nominee__email__address=nominees[3])
        nominee_position.state = NomineePositionStateName.objects.get(slug='accepted')
        nominee_position.save()

        self.client.logout()

        # fill questionnaires (internally the function does new nominations)
        self.access_chair_url(self.add_questionnaire_url)

        self.add_questionnaire(public=False,
                               nominee_email=nominees[0],
                               position='IAOC')
        self.add_questionnaire(public=False,
                               nominee_email=nominees[1],
                               position='IAOC')
        self.add_questionnaire(public=False,
                               nominee_email=nominees[2],
                               position='IAB')
        self.add_questionnaire(public=False,
                               nominee_email=nominees[3],
                               position='TSV')
        self.assertEqual(Feedback.objects.questionnaires().count(), 4)

        self.client.logout()

        ## Add feedbacks (internally the function does new nominations)
        self.access_member_url(self.private_feedback_url)
        self.feedback_view(public=False,
                           nominee_email=nominees[0],
                           position='IAOC')
        self.feedback_view(public=False,
                           nominee_email=nominees[1],
                           position='IAOC')
        self.feedback_view(public=False,
                           nominee_email=nominees[2],
                           position='IAB')
        self.feedback_view(public=False,
                           nominee_email=nominees[3],
                           position='TSV')

        self.assertEqual(Feedback.objects.comments().count(), 4)
        self.assertEqual(Feedback.objects.nominations().count(), 18)
        self.assertEqual(Feedback.objects.nominations().filter(nominees__email__address=nominees[0]).count(), 6)
        self.assertEqual(Feedback.objects.nominations().filter(nominees__email__address=nominees[1]).count(), 4)
        self.assertEqual(Feedback.objects.nominations().filter(nominees__email__address=nominees[2]).count(), 4)
        self.assertEqual(Feedback.objects.nominations().filter(nominees__email__address=nominees[3]).count(), 4)
        for nominee in nominees:
            self.assertEqual(Feedback.objects.comments().filter(nominees__email__address=nominee).count(),
                         1)
            self.assertEqual(Feedback.objects.questionnaires().filter(nominees__email__address=nominee).count(),
                         1)

        self.client.logout()

        ## merge nominations
        self.access_chair_url(self.private_merge_nominee_url)

        test_data = {"secondary_emails": "%s, %s" % (nominees[0], nominees[1]),
                     "primary_email": nominees[0]}
        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q("form .has-error"))

        test_data = {"primary_email": nominees[0],
                     "secondary_emails": ""}
        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q("form .has-error"))

        test_data = {"primary_email": "",
                     "secondary_emails": nominees[0]}
        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q("form .has-error"))

        test_data = {"primary_email": "unknown@example.com",
                     "secondary_emails": nominees[0]}
        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q("form .has-error"))

        test_data = {"primary_email": nominees[0],
                     "secondary_emails": "unknown@example.com"}
        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue(q("form .has-error"))

        test_data = {"secondary_emails": """%s,
                                            %s,
                                            %s""" % (nominees[1], nominees[2], nominees[3]),
                     "primary_email": nominees[0]}

        response = self.client.post(self.private_merge_nominee_url, test_data)
        self.assertEqual(response.status_code, 302)
        redirect_url = response["Location"]
        redirect_path = urlparse(redirect_url).path
        self.assertEqual(redirect_path, reverse('ietf.nomcom.views.private_index', kwargs={"year": NOMCOM_YEAR}))

        response = self.client.get(redirect_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-success")

        self.assertEqual(Nominee.objects.filter(email__address=nominees[1],
                                                duplicated__isnull=False).count(), 1)
        self.assertEqual(Nominee.objects.filter(email__address=nominees[2],
                                                duplicated__isnull=False).count(), 1)
        self.assertEqual(Nominee.objects.filter(email__address=nominees[3],
                                                duplicated__isnull=False).count(), 1)

        nominee = Nominee.objects.get(email__address=nominees[0])

        self.assertEqual(Nomination.objects.filter(nominee=nominee).count(), 18)
        self.assertEqual(Feedback.objects.nominations().filter(nominees__in=[nominee]).count(),
                         18)
        self.assertEqual(Feedback.objects.comments().filter(nominees__in=[nominee]).count(),
                         4)
        self.assertEqual(Feedback.objects.questionnaires().filter(nominees__in=[nominee]).count(),
                         4)

        for nominee_email in nominees[1:]:
            self.assertEqual(Feedback.objects.nominations().filter(nominees__email__address=nominee_email).count(),
                         0)
            self.assertEqual(Feedback.objects.comments().filter(nominees__email__address=nominee_email).count(),
                         0)
            self.assertEqual(Feedback.objects.questionnaires().filter(nominees__email__address=nominee_email).count(),
                         0)

        self.assertEqual(NomineePosition.objects.filter(nominee=nominee).count(), 3)

        # Check nominations state
        self.assertEqual(NomineePosition.objects.get(position__name='TSV',
                                                     nominee=nominee).state.slug, 'accepted')
        self.assertEqual(NomineePosition.objects.get(position__name='IAOC',
                                                     nominee=nominee).state.slug, 'accepted')
        self.assertEqual(NomineePosition.objects.get(position__name='IAB',
                                                     nominee=nominee).state.slug, 'declined')

        self.client.logout()

    def change_members(self, members):
        members_emails = ','.join(['%s%s' % (member, EMAIL_DOMAIN) for member in members])
        test_data = {'members': members_emails,}
        self.client.post(self.edit_members_url, test_data)

    def test_edit_members_view(self):
        """Verify edit member view"""
        self.access_chair_url(self.edit_members_url)
        self.change_members([CHAIR_USER, COMMUNITY_USER])

        # check member actions
        self.client.login(username=COMMUNITY_USER,password=COMMUNITY_USER+"+password")
        self.check_url_status(self.private_index_url, 200)
        self.client.logout()

        # revert edit nomcom members
        login_testing_unauthorized(self, CHAIR_USER, self.edit_members_url)
        self.change_members([CHAIR_USER])
        self.client.logout()

        self.client.login(username=COMMUNITY_USER,password=COMMUNITY_USER+"+password")
        self.check_url_status(self.private_index_url, 403)
        self.client.logout()

    def test_edit_nomcom_view(self):
        r = self.access_chair_url(self.edit_nomcom_url)
        q = PyQuery(r.content)
        reminder_date = '%s-09-30' % self.year

        f = io.open(self.cert_file.name)
        response = self.client.post(self.edit_nomcom_url, {
            'public_key': f,
            'reminderdates_set-TOTAL_FORMS': q('input[name="reminderdates_set-TOTAL_FORMS"]').val(),
            'reminderdates_set-INITIAL_FORMS': q('input[name="reminderdates_set-INITIAL_FORMS"]').val(),
            'reminderdates_set-MAX_NUM_FORMS': q('input[name="reminderdates_set-MAX_NUM_FORMS"]').val(),
            'reminderdates_set-0-date': reminder_date,
        })
        f.close()
        self.assertEqual(response.status_code, 200)


        nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')

        comment_text = 'Plain text. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        nomcom = get_nomcom_by_year(self.year)
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           comments=nomcom.encrypt(comment_text),
                                           type=FeedbackTypeName.objects.get(slug='nomina'))
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comment_text)

        self.assertEqual(check_comments(feedback.comments, comment_text, self.privatekey_file), True)

        # Check that the set reminder date is present
        reminder_dates = dict([ (d.id,str(d.date)) for d in nomcom.reminderdates_set.all() ])
        self.assertIn(reminder_date, list(reminder_dates.values()))

        # Remove reminder date
        q = PyQuery(response.content)          # from previous post
        r = self.client.post(self.edit_nomcom_url, {
            'reminderdates_set-TOTAL_FORMS': q('input[name="reminderdates_set-TOTAL_FORMS"]').val(),
            'reminderdates_set-INITIAL_FORMS': q('input[name="reminderdates_set-INITIAL_FORMS"]').val(),
            'reminderdates_set-MAX_NUM_FORMS': q('input[name="reminderdates_set-MAX_NUM_FORMS"]').val(),
            'reminderdates_set-0-id': str(list(reminder_dates.keys())[0]),
            'reminderdates_set-0-date': '',
        })
        self.assertEqual(r.status_code, 200)

        # Check that reminder date has been removed
        reminder_dates = dict([ (d.id,str(d.date)) for d in ReminderDates.objects.filter(nomcom=nomcom) ])
        self.assertNotIn(reminder_date, list(reminder_dates.values()))

        self.client.logout()

    def test_list_positions(self):
        login_testing_unauthorized(self, CHAIR_USER, self.positions_url)

    def test_list_positions_add(self):
        nomcom = get_nomcom_by_year(self.year)
        count = nomcom.position_set.all().count()
        login_testing_unauthorized(self, CHAIR_USER, self.edit_position_url)
        test_data = {"action" : "add", "name": "testpos" }
        r = self.client.post(self.edit_position_url, test_data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(nomcom.position_set.all().count(), count+1)


    def test_index_view(self):
        """Verify home view"""
        self.check_url_status(self.index_url, 200)

    def test_announcements_view(self):
        nomcom = Group.objects.get(acronym="nomcom%s" % self.year, type="nomcom")
        msg = Message.objects.create(
            by=Person.objects.all()[0],
            subject="This is a test",
            to="test@example.com",
            frm="nomcomchair@example.com",
            body="Hello World!",
            content_type="text/plain",
            )
        msg.related_groups.add(nomcom)
        
        r = self.client.get(reverse('ietf.nomcom.views.announcements'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, ("Messages from %s" % nomcom.time.year))
        self.assertContains(r, nomcom.role_set.filter(name="chair")[0].person.email_address())
        self.assertContains(r, msg.subject)


    def test_requirements_view(self):
        """Verify requirements view"""
        self.check_url_status(self.requirements_url, 200)

    def test_questionnaires_view(self):
        """Verify questionnaires view"""
        self.check_url_status(self.questionnaires_url, 200)

    def test_public_nominate(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)

        messages_before = len(outbox)

        self.nominate_view(public=True,confirmation=True)

        self.assertEqual(len(outbox), messages_before + 3)

        self.assertEqual('IETF Nomination Information', outbox[-3]['Subject'])
        self.assertEqual(self.email_from, outbox[-3]['From'])
        self.assertIn('nominee', outbox[-3]['To'])

        self.assertEqual('Nomination Information', outbox[-2]['Subject'])
        self.assertEqual(self.email_from, outbox[-2]['From'])
        self.assertIn('nomcomchair', outbox[-2]['To'])

        self.assertEqual('Nomination receipt', outbox[-1]['Subject'])
        self.assertEqual(self.email_from, outbox[-1]['From'])
        self.assertIn('plain', outbox[-1]['To'])
        self.assertIn('Comments with accents äöå', get_payload_text(outbox[-1]))

        # Nominate the same person for the same position again without asking for confirmation 

        messages_before = len(outbox)

        self.nominate_view(public=True)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertEqual('Nomination Information', outbox[-1]['Subject'])
        self.assertEqual(self.email_from, outbox[-1]['From'])
        self.assertIn('nomcomchair', outbox[-1]['To'])

    def test_private_nominate(self):
        self.access_member_url(self.private_nominate_url)
        return self.nominate_view(public=False)
        self.client.logout()

    def test_public_nominate_newperson(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)

        messages_before = len(outbox)

        self.nominate_newperson_view(public=True,confirmation=True)

        self.assertEqual(len(outbox), messages_before + 4)

        self.assertEqual('New person is created', outbox[-4]['Subject'])
        self.assertEqual(self.email_from, outbox[-4]['From'])
        self.assertIn('secretariat', outbox[-4]['To'])

        self.assertEqual('IETF Nomination Information', outbox[-3]['Subject'])
        self.assertEqual(self.email_from, outbox[-3]['From'])
        self.assertIn('nominee', outbox[-3]['To'])

        self.assertEqual('Nomination Information', outbox[-2]['Subject'])
        self.assertEqual(self.email_from, outbox[-2]['From'])
        self.assertIn('nomcomchair', outbox[-2]['To'])

        self.assertEqual('Nomination receipt', outbox[-1]['Subject'])
        self.assertEqual(self.email_from, outbox[-1]['From'])
        self.assertIn('plain', outbox[-1]['To'])
        self.assertIn('Comments with accents äöå', get_payload_text(outbox[-1]))

        # Nominate the same person for the same position again without asking for confirmation 

        messages_before = len(outbox)

        self.nominate_view(public=True)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertEqual('Nomination Information', outbox[-1]['Subject'])
        self.assertEqual(self.email_from, outbox[-1]['From'])
        self.assertIn('nomcomchair', outbox[-1]['To'])

    def test_private_nominate_newperson(self):
        self.access_member_url(self.private_nominate_url)
        return self.nominate_newperson_view(public=False)
        self.client.logout()

    def test_private_nominate_newperson_who_already_exists(self):
        EmailFactory(address='nominee@example.com')
        self.access_member_url(self.private_nominate_newperson_url)
        return self.nominate_newperson_view(public=False)       

    def test_public_nominate_with_automatic_questionnaire(self):
        nomcom = get_nomcom_by_year(self.year)
        nomcom.send_questionnaire = True
        nomcom.save()
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)
        empty_outbox()
        self.nominate_view(public=True)
        self.assertEqual(len(outbox), 3)
        # test_public_nominate checks the other messages
        self.assertEqual(self.email_from, outbox[-1]['From'])
        self.assertIn('Questionnaire', outbox[1]['Subject'])
        self.assertIn('nominee@', outbox[1]['To'])


    def nominate_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        searched_email = kwargs.pop('searched_email', None)
        nominee_email = kwargs.pop('nominee_email', 'nominee@example.com')
        if not searched_email:
            searched_email = Email.objects.filter(address=nominee_email).first() 
            if not searched_email:
                searched_email = EmailFactory(address=nominee_email, primary=True, origin='test')
        if not searched_email.person:
            searched_email.person = PersonFactory()
            searched_email.save()
        nominator_email = kwargs.pop('nominator_email', "%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))
        position_name = kwargs.pop('position', 'IAOC')
        confirmation = kwargs.pop('confirmation', False)

        if public:
            nominate_url = self.public_nominate_url
        else:
            nominate_url = self.private_nominate_url
        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            q = PyQuery(response.content)
            self.assertEqual(len(q("#nominate-form")), 0)

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#nominate-form")), 1)

        position = Position.objects.get(name=position_name)
        comment_text = 'Test nominate view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        candidate_phone = '123456'

        test_data = {'searched_email': searched_email.pk,
                     'candidate_phone': candidate_phone,
                     'position': position.id,
                     'qualifications': comment_text,
                     'confirmation': confirmation}
        if not public:
            test_data['nominator_email'] = nominator_email

        response = self.client.post(nominate_url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertContains(response, "alert-success")

        # check objects
        nominee = Nominee.objects.get(email=searched_email)
        NomineePosition.objects.get(position=position, nominee=nominee)
        feedback = Feedback.objects.filter(positions__in=[position],
                                           nominees__in=[nominee],
                                           type=FeedbackTypeName.objects.get(slug='nomina')).latest('id')
        if public:
            self.assertEqual(feedback.author, nominator_email)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comment_text)

        self.assertEqual(check_comments(feedback.comments, comment_text, self.privatekey_file), True)
        Nomination.objects.get(position=position,
                               candidate_name=nominee.person.plain_name(),
                               candidate_email=searched_email.address,
                               candidate_phone=candidate_phone,
                               nominee=nominee,
                               comments=feedback,
                               nominator_email="%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))

    def nominate_newperson_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', 'nominee@example.com')
        nominator_email = kwargs.pop('nominator_email', "%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))
        position_name = kwargs.pop('position', 'IAOC')
        confirmation = kwargs.pop('confirmation', False)

        if public:
            nominate_url = self.public_nominate_newperson_url
        else:
            nominate_url = self.private_nominate_newperson_url
        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            q = PyQuery(response.content)
            self.assertEqual(len(q("#nominate-form")), 0)

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#nominate-form")), 1)

        position = Position.objects.get(name=position_name)
        candidate_email = nominee_email
        candidate_name = 'nominee'
        comment_text = 'Test nominate view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        candidate_phone = '123456'

        test_data = {'candidate_name': candidate_name,
                     'candidate_email': candidate_email,
                     'candidate_phone': candidate_phone,
                     'position': position.id,
                     'qualifications': comment_text,
                     'confirmation': confirmation}
        if not public:
            test_data['nominator_email'] = nominator_email

        if Email.objects.filter(address=nominee_email).exists():
            response = self.client.post(nominate_url, test_data,follow=True)
            self.assertFalse(response.redirect_chain)
            self.assertEqual(response.status_code, 200)
            self.assertIn('already in the datatracker',unicontent(response))
        else:
            response = self.client.post(nominate_url, test_data,follow=True)
            self.assertTrue(response.redirect_chain)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertContains(response, "alert-success")

            # check objects
            email = Email.objects.get(address=candidate_email)
            Person.objects.get(name=candidate_name)
            nominee = Nominee.objects.get(email=email)
            NomineePosition.objects.get(position=position, nominee=nominee)
            feedback = Feedback.objects.filter(positions__in=[position],
                                               nominees__in=[nominee],
                                               type=FeedbackTypeName.objects.get(slug='nomina')).latest('id')
            if public:
                self.assertEqual(feedback.author, nominator_email)

            # to check feedback comments are saved like enrypted data
            self.assertNotEqual(feedback.comments, comment_text)

            self.assertEqual(check_comments(feedback.comments, comment_text, self.privatekey_file), True)
            Nomination.objects.get(position=position,
                                   candidate_name=candidate_name,
                                   candidate_email=candidate_email,
                                   candidate_phone=candidate_phone,
                                   nominee=nominee,
                                   comments=feedback,
                                   nominator_email="%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))

    def test_add_questionnaire(self):
        self.access_chair_url(self.add_questionnaire_url)
        return self.add_questionnaire()
        self.client.logout()

    def add_questionnaire(self, *args, **kwargs):
        public = kwargs.pop('public', False)
        nominee_email = kwargs.pop('nominee_email', 'nominee@example.com')
        nominator_email = kwargs.pop('nominator_email', "%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))
        position_name = kwargs.pop('position', 'IAOC')

        self.nominate_view(public=public,
                           nominee_email=nominee_email,
                           position=position_name,
                           nominator_email=nominator_email)

        response = self.client.get(self.add_questionnaire_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            self.assertNotContains(response, "questionnnaireform")

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        response = self.client.get(self.add_questionnaire_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "questionnnaireform")

        position = Position.objects.get(name=position_name)
        nominee = Nominee.objects.get(email__address=nominee_email)

        comment_text = 'Test add questionnaire view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'

        test_data = {'comment_text': comment_text,
                     'nominee': '%s_%s' % (position.id, nominee.id)}

        response = self.client.post(self.add_questionnaire_url, test_data)

        self.assertContains(response, "alert-success")

        ## check objects
        feedback = Feedback.objects.filter(positions__in=[position],
                                           nominees__in=[nominee],
                                           type=FeedbackTypeName.objects.get(slug='questio')).latest('id')

        ## to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comment_text)

        self.assertEqual(check_comments(feedback.comments, comment_text, self.privatekey_file), True)

    def test_public_feedback(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_feedback_url)
        position = "IAOC"

        empty_outbox()
        self.feedback_view(public=True, confirmation=True, position=position)
        # feedback_view does a nomination internally: there is a lot of email related to that - tested elsewhere
        # We're interested in the confirmation receipt here
        self.assertEqual(len(outbox),3)
        self.assertEqual('NomCom comment confirmation', outbox[2]['Subject'])
        email_body = get_payload_text(outbox[2])
        self.assertIn(position, email_body)
        self.assertNotIn('$', email_body)
        self.assertEqual(self.email_from, outbox[-2]['From'])
        self.assertIn('plain', outbox[2]['To'])
        self.assertIn('Comments with accents äöå', get_payload_text(outbox[2]))

        empty_outbox()
        self.feedback_view(public=True)
        self.assertEqual(len(outbox),1)
        self.assertNotIn('confirmation', outbox[0]['Subject'])

    def test_private_feedback(self):
        self.access_member_url(self.private_feedback_url)
        return self.feedback_view(public=False)

    def feedback_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', 'nominee@example.com')
        nominator_email = kwargs.pop('nominator_email', "%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))
        position_name = kwargs.pop('position', 'IAOC')
        confirmation = kwargs.pop('confirmation', False)

        self.nominate_view(public=public,
                           nominee_email=nominee_email,
                           position=position_name,
                           nominator_email=nominator_email)

        feedback_url = self.public_feedback_url
        if not public:
            feedback_url = self.private_feedback_url

        response = self.client.get(feedback_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            self.assertNotContains(response, "feedbackform")

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        response = self.client.get(feedback_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "feedbackform")

        position = Position.objects.get(name=position_name)
        nominee = Nominee.objects.get(email__address=nominee_email)

        feedback_url += "?nominee=%d&position=%d" % (nominee.id, position.id)
        response = self.client.get(feedback_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "feedbackform")
        # Test for a link to the nominee's profile page
        q = PyQuery(response.content)
        person_url = reverse('ietf.person.views.profile', kwargs={'email_or_name': nominee.name()})
        self.assertTrue(q('a[href="%s"]' % (person_url)), 
                        'Nominee feedback page does not link to profile page')                            
        
        comments = 'Test feedback view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'

        test_data = {'comment_text': comments,
                     'position_name': position.name,
                     'nominee_name': nominee.email.person.name,
                     'nominee_email': nominee.email.address,
                     'confirmation': confirmation}

        if public:
            test_data['nominator_email'] = nominator_email
            test_data['nominator_name'] = nominator_email

        nominee_position = NomineePosition.objects.get(nominee=nominee,
                                                       position=position)
        state = nominee_position.state
        if state.slug != 'accepted':
            response = self.client.post(feedback_url, test_data)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertTrue(q("form .has-error"))
            # accept nomination
            nominee_position.state = NomineePositionStateName.objects.get(slug='accepted')
            nominee_position.save()

        response = self.client.post(feedback_url, test_data)
        self.assertContains(response, "alert-success")
        self.assertNotContains(response, "feedbackform")

        ## check objects
        feedback = Feedback.objects.filter(positions__in=[position],
                                           nominees__in=[nominee],
                                           type=FeedbackTypeName.objects.get(slug='comment')).latest('id')
        if public:
            self.assertEqual(feedback.author, nominator_email)

        ## to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)

        # recovery state
        if state != nominee_position.state:
            nominee_position.state = state
            nominee_position.save()


class NomineePositionStateSaveTest(TestCase):
    """Tests for the NomineePosition save override method"""

    def setUp(self):
        setup_test_public_keys_dir(self)
        nomcom_test_data()
        self.nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_state_autoset(self):
        """Verify state is autoset correctly"""
        position = Position.objects.get(name='APP')
        nominee_position = NomineePosition.objects.create(position=position,
                                                          nominee=self.nominee)
        self.assertEqual(nominee_position.state.slug, 'pending')

    def test_state_specified(self):
        """Verify state if specified"""
        position = Position.objects.get(name='INT')
        nominee_position = NomineePosition.objects.create(position=position,
                                                          nominee=self.nominee,
                                                          state=NomineePositionStateName.objects.get(slug='accepted'))
        self.assertEqual(nominee_position.state.slug, 'accepted')

    def test_nomine_position_unique(self):
        """Verify nomine and position are unique together"""
        position = Position.objects.get(name='OAM')
        NomineePosition.objects.create(position=position,
                                       nominee=self.nominee)
        nominee_position = NomineePosition(position=position, nominee=self.nominee)

        self.assertRaises(IntegrityError, nominee_position.save)


class FeedbackTest(TestCase):

    def setUp(self):
        setup_test_public_keys_dir(self)

        nomcom_test_data()
        self.cert_file, self.privatekey_file = get_cert_files()

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_encrypted_comments(self):

        nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')
        nomcom = position.nomcom

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        comment_text = 'Plain text. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        comments = nomcom.encrypt(comment_text)
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           comments=comments,
                                           type=FeedbackTypeName.objects.get(slug='nomina'))
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comment_text)
        self.assertEqual(check_comments(feedback.comments, comment_text, self.privatekey_file), True)

class ReminderTest(TestCase):

    def setUp(self):
        setup_test_public_keys_dir(self)
        nomcom_test_data()
        self.nomcom = get_nomcom_by_year(NOMCOM_YEAR)
        self.cert_file, self.privatekey_file = get_cert_files()
        #self.nomcom.public_key.storage.location = tempfile.gettempdir()
        self.nomcom.public_key.save('cert', File(io.open(self.cert_file.name, 'r')))

        gen = Position.objects.get(nomcom=self.nomcom,name='GEN')
        rai = Position.objects.get(nomcom=self.nomcom,name='RAI')
        iab = Position.objects.get(nomcom=self.nomcom,name='IAB')

        today = datetime.date.today()
        t_minus_3 = today - datetime.timedelta(days=3)
        t_minus_4 = today - datetime.timedelta(days=4)
        e1 = EmailFactory(address="nominee1@example.org", person=PersonFactory(name="Nominee 1"), origin='test')
        e2 = EmailFactory(address="nominee2@example.org", person=PersonFactory(name="Nominee 2"), origin='test')
        n = make_nomineeposition(self.nomcom,e1.person,gen,None)
        np = n.nomineeposition_set.get(position=gen)
        np.time = t_minus_3
        np.save()
        n = make_nomineeposition(self.nomcom,e1.person,iab,None)
        np = n.nomineeposition_set.get(position=iab)
        np.state = NomineePositionStateName.objects.get(slug='accepted')
        np.time = t_minus_3
        np.save()
        n = make_nomineeposition(self.nomcom,e2.person,rai,None)
        np = n.nomineeposition_set.get(position=rai)
        np.time = t_minus_4
        np.save()
        n = make_nomineeposition(self.nomcom,e2.person,gen,None)
        np = n.nomineeposition_set.get(position=gen)
        np.state = NomineePositionStateName.objects.get(slug='accepted')
        np.time = t_minus_4
        np.save()
        feedback = Feedback.objects.create(nomcom=self.nomcom,
                                           comments=self.nomcom.encrypt('some non-empty comments'),
                                           type=FeedbackTypeName.objects.get(slug='questio'),
                                           user=User.objects.get(username=CHAIR_USER))
        feedback.positions.add(gen)
        feedback.nominees.add(n)

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_is_time_to_send(self):
        self.nomcom.reminder_interval = 4
        today = datetime.date.today()
        self.assertTrue(is_time_to_send(self.nomcom,today+datetime.timedelta(days=4),today))
        for delta in range(4):
            self.assertFalse(is_time_to_send(self.nomcom,today+datetime.timedelta(days=delta),today))
        self.nomcom.reminder_interval = None
        self.assertFalse(is_time_to_send(self.nomcom,today,today))
        self.nomcom.reminderdates_set.create(date=today)
        self.assertTrue(is_time_to_send(self.nomcom,today,today))

    def test_command(self):
        c = Command()
        messages_before=len(outbox)
        self.nomcom.reminder_interval = 3
        self.nomcom.save()
        c.handle(None,None)
        self.assertEqual(len(outbox), messages_before + 2)
        self.assertIn('nominee1@example.org', outbox[-1]['To'])
        self.assertIn('please complete', outbox[-1]['Subject'])
        self.assertIn('nominee1@example.org', outbox[-2]['To'])
        self.assertIn('please accept', outbox[-2]['Subject'])
        messages_before=len(outbox)
        self.nomcom.reminder_interval = 4
        self.nomcom.save()
        c.handle(None,None)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertIn('nominee2@example.org', outbox[-1]['To'])
        self.assertIn('please accept', outbox[-1]['Subject'])
     
    def test_remind_accept_view(self):
        url = reverse('ietf.nomcom.views.send_reminder_mail', kwargs={'year': NOMCOM_YEAR,'type':'accept'})
        login_testing_unauthorized(self, CHAIR_USER, url)
        messages_before=len(outbox)
        test_data = {'selected': [x.id for x in Nominee.objects.filter(nomcom=self.nomcom)]}
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(outbox), messages_before + 2)
        self.assertIn('nominee1@', outbox[-2]['To'])
        self.assertIn('nominee2@', outbox[-1]['To'])

    def test_remind_questionnaire_view(self):
        url = reverse('ietf.nomcom.views.send_reminder_mail', kwargs={'year': NOMCOM_YEAR,'type':'questionnaire'})
        login_testing_unauthorized(self, CHAIR_USER, url)
        messages_before=len(outbox)
        test_data = {'selected': [x.id for x in Nominee.objects.filter(nomcom=self.nomcom)]}
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertIn('nominee1@', outbox[-1]['To'])

class InactiveNomcomTests(TestCase):

    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year(group__state_id='conclude'))
        self.plain_person = PersonFactory.create()
        self.chair = self.nc.group.role_set.filter(name='chair').first().person
        self.member = self.nc.group.role_set.filter(name='member').first().person

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_feedback_closed(self):
        for view in ['ietf.nomcom.views.public_feedback', 'ietf.nomcom.views.private_feedback']:
            url = reverse(view, kwargs={'year': self.nc.year()})
            who = self.plain_person if 'public' in view else self.member
            login_testing_unauthorized(self, who.user.username, url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertIn( '(Concluded)', q('h1').text())
            self.assertIn( 'closed', q('#instructions').text())
            self.assertTrue( q('#nominees a') )
            self.assertFalse( q('#nominees a[href]') )
    
            url += "?nominee=%d&position=%d" % (self.nc.nominee_set.order_by('pk').first().id, self.nc.nominee_set.order_by('pk').first().nomineeposition_set.order_by('pk').first().position.id)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertFalse( q('#feedbackform'))        
            
            empty_outbox()
            fb_before = self.nc.feedback_set.count()
            test_data = {'comment_text': 'Test feedback view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.',
                         'nominator_email': self.plain_person.email_set.first().address,
                         'confirmation': True}
            response = self.client.post(url, test_data)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertIn( 'closed', q('#instructions').text())
            self.assertEqual( len(outbox), 0 )
            self.assertEqual( fb_before, self.nc.feedback_set.count() )

    def test_nominations_closed(self):
        for view in ['ietf.nomcom.views.public_nominate', 'ietf.nomcom.views.private_nominate']:
            url = reverse(view, kwargs={'year': self.nc.year() })
            who = self.plain_person if 'public' in view else self.member
            login_testing_unauthorized(self, who.user.username, url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertIn( '(Concluded)', q('h1').text())
            self.assertIn( 'closed', q('.alert-warning').text())

    def test_acceptance_closed(self):
        today = datetime.date.today().strftime('%Y%m%d')
        pid = self.nc.position_set.first().nomineeposition_set.order_by('pk').first().id 
        url = reverse('ietf.nomcom.views.process_nomination_status', kwargs = {
                      'year' : self.nc.year(),
                      'nominee_position_id' : pid,
                      'state' : 'accepted',
                      'date' : today,
                      'hash' : get_hash_nominee_position(today,pid),
                     })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_can_view_but_cannot_edit_nomcom_settings(self):
        url = reverse('ietf.nomcom.views.edit_nomcom',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_classify_feedback(self):
        url = reverse('ietf.nomcom.views.view_feedback_pending',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_modify_nominees(self):
        url = reverse('ietf.nomcom.views.private_index', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#batch-action-form'))
        test_data = {"action": "set_as_pending",
                     "selected": [1]}
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertIn('not active', q('.alert-warning').text() )

    def test_email_pasting_closed(self):
        url = reverse('ietf.nomcom.views.private_feedback_email', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#paste-email-feedback-form'))
        test_data = {"email_text": "some garbage text",
                    }
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertIn('not active', q('.alert-warning').text() )

    def test_questionnaire_entry_closed(self):
        url = reverse('ietf.nomcom.views.private_questionnaire', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#questionnaireform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertIn('not active', q('.alert-warning').text() )
        
    def _test_send_reminders_closed(self,rtype):
        url = reverse('ietf.nomcom.views.send_reminder_mail', kwargs={'year':self.nc.year(),'type':rtype })
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#reminderform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertIn('not active', q('.alert-warning').text() )

    def test_send_accept_reminders_closed(self):
        self._test_send_reminders_closed('accept')

    def test_send_questionnaire_reminders_closed(self):
        self._test_send_reminders_closed('questionnaire')

    def test_merge_closed(self):
        url = reverse('ietf.nomcom.views.private_merge_person', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        q = PyQuery(response.content)
        self.assertFalse( q('#mergeform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertIn('not active', q('.alert-warning').text() )

    def test_cannot_edit_position(self):
        url = reverse('ietf.nomcom.views.edit_position',kwargs={'year':self.nc.year(),'position_id':self.nc.position_set.first().id})
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_add_position(self):
        url = reverse('ietf.nomcom.views.edit_position',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_delete_position(self):
        url = reverse('ietf.nomcom.views.remove_position',kwargs={'year':self.nc.year(),'position_id':self.nc.position_set.first().id})
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_can_view_but_not_edit_templates(self):
        template = DBTemplateFactory.create(group=self.nc.group,
                                            title='Test template',
                                            path='/nomcom/'+self.nc.group.acronym+'/test',
                                            variables='',
                                            type_id='plain',
                                            content='test content')
        url = reverse('ietf.nomcom.views.edit_template',kwargs={'year':self.nc.year(), 'template_id':template.id})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#templateform') )

class FeedbackLastSeenTests(TestCase):

    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year())
        self.author = PersonFactory.create().email_set.first().address
        self.member = self.nc.group.role_set.filter(name='member').first().person
        self.nominee = self.nc.nominee_set.order_by('pk').first()
        self.position = self.nc.position_set.first()
        self.topic = self.nc.topic_set.first()
        for type_id in ['comment','nomina','questio']:
            f = FeedbackFactory.create(author=self.author,nomcom=self.nc,type_id=type_id)
            f.positions.add(self.position)
            f.nominees.add(self.nominee)
        f = FeedbackFactory.create(author=self.author,nomcom=self.nc,type_id='comment')
        f.topics.add(self.topic)
        now = datetime.datetime.now() 
        self.hour_ago = now - datetime.timedelta(hours=1)
        self.half_hour_ago = now - datetime.timedelta(minutes=30)
        self.second_from_now = now + datetime.timedelta(seconds=1)

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_feedback_index_badges(self):
        url = reverse('ietf.nomcom.views.view_feedback',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.member.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 4 )

        f = self.nc.feedback_set.first()
        f.time = self.hour_ago
        f.save()
        FeedbackLastSeen.objects.create(reviewer=self.member,nominee=self.nominee)
        FeedbackLastSeen.objects.update(time=self.half_hour_ago)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 3 )

        FeedbackLastSeen.objects.update(time=self.second_from_now)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 1 )

        TopicFeedbackLastSeen.objects.create(reviewer=self.member,topic=self.topic)
        TopicFeedbackLastSeen.objects.update(time=self.second_from_now)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 0 )

    def test_feedback_nominee_badges(self):
        url = reverse('ietf.nomcom.views.view_feedback_nominee', kwargs={'year':self.nc.year(), 'nominee_id':self.nominee.id})
        login_testing_unauthorized(self, self.member.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 3 )

        f = self.nc.feedback_set.first()
        f.time = self.hour_ago
        f.save()
        FeedbackLastSeen.objects.create(reviewer=self.member,nominee=self.nominee)
        FeedbackLastSeen.objects.update(time=self.half_hour_ago)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 2 )

        FeedbackLastSeen.objects.update(time=self.second_from_now)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 0 )

    def test_feedback_topic_badges(self):
        url = reverse('ietf.nomcom.views.view_feedback_topic', kwargs={'year':self.nc.year(), 'topic_id':self.topic.id})
        login_testing_unauthorized(self, self.member.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 1 )

        f = self.topic.feedback_set.first()
        f.time = self.hour_ago
        f.save()
        TopicFeedbackLastSeen.objects.create(reviewer=self.member,topic=self.topic)
        TopicFeedbackLastSeen.objects.update(time=self.half_hour_ago)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 0 )

        TopicFeedbackLastSeen.objects.update(time=self.second_from_now)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual( len(q('.label-success')), 0 )

class NewActiveNomComTests(TestCase):

    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year())
        self.chair = self.nc.group.role_set.filter(name='chair').first().person
        self.saved_days_to_expire_nomination_link = settings.DAYS_TO_EXPIRE_NOMINATION_LINK

    def tearDown(self):
        teardown_test_public_keys_dir(self)
        settings.DAYS_TO_EXPIRE_NOMINATION_LINK = self.saved_days_to_expire_nomination_link

    def test_help(self):
        url = reverse('ietf.nomcom.views.configuration_help',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_accept_reject_nomination_edges(self):
        self.client.logout()
        np = self.nc.nominee_set.order_by('pk').first().nomineeposition_set.order_by('pk').first()
        kwargs={'year':self.nc.year(),
                'nominee_position_id':np.id,
                'state':'accepted',
                'date':np.time.strftime("%Y%m%d"),
                'hash':get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id),
               }
        url = reverse('ietf.nomcom.views.process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertIn('already was', unicontent(response))

        settings.DAYS_TO_EXPIRE_NOMINATION_LINK = 2
        np.time = np.time - datetime.timedelta(days=3)
        np.save()
        kwargs['date'] = np.time.strftime("%Y%m%d")
        kwargs['hash'] = get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id)
        url = reverse('ietf.nomcom.views.process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertIn('Link expired', unicontent(response))

        kwargs['hash'] = 'bad'
        url = reverse('ietf.nomcom.views.process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertIn('Bad hash!', unicontent(response))

    def test_accept_reject_nomination_comment(self):
        np = self.nc.nominee_set.order_by('pk').first().nomineeposition_set.order_by('pk').first()
        hash = get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id)
        url = reverse('ietf.nomcom.views.process_nomination_status',
                      kwargs={'year':self.nc.year(),
                              'nominee_position_id':np.id,
                              'state':'accepted',
                              'date':np.time.strftime("%Y%m%d"),
                              'hash':hash,
                             }
                     )
        np.state_id='pending'
        np.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        feedback_count_before = Feedback.objects.count()
        response = self.client.post(url,{})
        # This view uses Yaco-style POST handling
        self.assertEqual(response.status_code,200)
        self.assertEqual(Feedback.objects.count(),feedback_count_before)
        np.state_id='pending'
        np.save()
        response = self.client.post(url,{'comments':'A nonempty comment'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Feedback.objects.count(),feedback_count_before+1)

    def test_provide_private_key(self):
        url = reverse('ietf.nomcom.views.private_key',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url,{'key': force_str(key)})
        self.assertEqual(response.status_code,302)

    def test_email_pasting(self):
        url = reverse('ietf.nomcom.views.private_feedback_email',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        fb_count_before = Feedback.objects.count()
        response = self.client.post(url,{'email_text':"""To: rjsparks@nostrum.com
From: Robert Sparks <rjsparks@nostrum.com>
Subject: Junk message for feedback testing =?iso-8859-1?q?p=F6stal?=
Message-ID: <566F2FE5.1050401@nostrum.com>
Date: Mon, 14 Dec 2015 15:08:53 -0600
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit

Junk body for testing

"""})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Feedback.objects.count(),fb_count_before+1)

    def test_simple_feedback_pending(self):
        url = reverse('ietf.nomcom.views.view_feedback_pending',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)

        # test simple classification when there's only one thing to classify

        # junk is the only category you can set directly from the first form the view presents
        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

        response = self.client.post(url, {'form-TOTAL_FORMS': 1,
                                          'form-INITIAL_FORMS': 1,
                                          'form-0-id': fb.id,
                                          'form-0-type': 'junk',
                                        })
        self.assertEqual(response.status_code,302)
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,'junk')

        # comments, nominations, and questionnare responses are catagorized via a second 
        # formset presented by the view (signaled by having 'end' appear in the POST)
        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        np = NomineePosition.objects.filter(position__nomcom = self.nc,state='accepted').first()
        fb_count_before = np.nominee.feedback_set.count()
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb.id,
                                          'form-0-type': 'comment',
                                          'form-0-nominee': '%s_%s'%(np.position.id,np.nominee.id),
                                        })
        self.assertEqual(response.status_code,302)
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,'comment')
        self.assertEqual(np.nominee.feedback_set.count(),fb_count_before+1)

        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        nominee = self.nc.nominee_set.order_by('pk').first()
        position = self.nc.position_set.exclude(nomineeposition__nominee=nominee).first()
        self.assertIsNotNone(position)
        fb_count_before = nominee.feedback_set.count()
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb.id,
                                          'form-0-type': 'nomina',
                                          'form-0-position': position.id,
                                          'form-0-searched_email' : nominee.email.address,
                                        })
        self.assertEqual(response.status_code,302)
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,'nomina')
        self.assertEqual(nominee.feedback_set.count(),fb_count_before+1)

        # Classify a newperson
        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        position = self.nc.position_set.first()
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb.id,
                                          'form-0-type': 'nomina',
                                          'form-0-position': position.id,
                                          'form-0-candidate_email' : 'newperson@example.com',
                                          'form-0-candidate_name'  : 'New Person',
                                        })
        self.assertEqual(response.status_code,302)
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,'nomina')
        self.assertTrue(fb.nominees.filter(person__name='New Person').exists())

        # check for failure when trying to add a newperson that already exists

        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        position = self.nc.position_set.all()[1]
        nominee = self.nc.nominee_set.get(person__email__address='newperson@example.com')
        fb_count_before = nominee.feedback_set.count()
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb.id,
                                          'form-0-type': 'nomina',
                                          'form-0-position': position.id,
                                          'form-0-candidate_email' : 'newperson@example.com',
                                          'form-0-candidate_name'  : 'New Person',
                                        })
        self.assertEqual(response.status_code,200)
        self.assertTrue('already exists' in unicontent(response))
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,None)
        self.assertEqual(nominee.feedback_set.count(),fb_count_before)

        fb = FeedbackFactory(nomcom=self.nc,type_id=None)
        np = NomineePosition.objects.filter(position__nomcom = self.nc,state='accepted').first()
        fb_count_before = np.nominee.feedback_set.count()
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb.id,
                                          'form-0-type': 'questio',
                                          'form-0-nominee' : '%s_%s'%(np.position.id,np.nominee.id),
                                        })
        self.assertEqual(response.status_code,302)
        fb = Feedback.objects.get(id=fb.id)
        self.assertEqual(fb.type_id,'questio')
        self.assertEqual(np.nominee.feedback_set.count(),fb_count_before+1)

    def test_complicated_feedback_pending(self):
        url = reverse('ietf.nomcom.views.view_feedback_pending',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)

        # Test having multiple things to classify
        # The view has some complicated to handle having some forms in the initial form formset
        # being categorized as 'junk' and others being categorized as something that requires
        # more information. The second formset presented will have forms for any others initially 
        # categorized as nominations, then a third formset will be presented with any that were 
        # initially categorized as comments or questionnaire responses. The following exercises
        # all the gears that glue these three formset presentations together.
      
        fb0 = FeedbackFactory(nomcom=self.nc,type_id=None)
        fb1 = FeedbackFactory(nomcom=self.nc,type_id=None)
        fb2 = FeedbackFactory(nomcom=self.nc,type_id=None)
        nominee = self.nc.nominee_set.order_by('pk').first()
        new_position_for_nominee = self.nc.position_set.exclude(nomineeposition__nominee=nominee).first()

        # Initial formset
        response = self.client.post(url, {'form-TOTAL_FORMS': 3,
                                          'form-INITIAL_FORMS': 3,
                                          'form-0-id': fb0.id,
                                          'form-0-type': 'junk',
                                          'form-1-id': fb1.id,
                                          'form-1-type': 'nomina',
                                          'form-2-id': fb2.id,
                                          'form-2-type': 'comment',
                                        })
        self.assertEqual(response.status_code,200) # Notice that this is not a 302
        fb0 = Feedback.objects.get(id=fb0.id)
        self.assertEqual(fb0.type_id,'junk')
        q = PyQuery(response.content)
        self.assertEqual(q('input[name=\"form-0-type\"]').attr['value'],'nomina')
        self.assertEqual(q('input[name=\"extra_ids\"]').attr['value'],'%s:comment' % fb2.id)

        # Second formset 
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': fb1.id,
                                          'form-0-type': 'nomina',
                                          'form-0-position': new_position_for_nominee.id,
                                          'form-0-candidate_name' : 'Totally New Person',
                                          'form-0-candidate_email': 'totallynew@example.org',
                                          'extra_ids': '%s:comment' % fb2.id,
                                        })
        self.assertEqual(response.status_code,200) # Notice that this is also is not a 302
        q = PyQuery(response.content)
        self.assertEqual(q('input[name=\"form-0-type\"]').attr['value'],'comment')
        self.assertFalse(q('input[name=\"extra_ids\"]'))
        fb1 = Feedback.objects.get(id=fb1.id)
        self.assertEqual(fb1.type_id,'nomina')

        # Exercising the resulting third formset is identical to the simple test above
        # that categorizes a single thing as a comment. Note that it returns a 302.

        # There is yet another code-path for transitioning to the second form when
        # nothing was classified as a nomination. 
        fb0 = FeedbackFactory(nomcom=self.nc,type_id=None)
        fb1 = FeedbackFactory(nomcom=self.nc,type_id=None)
        response = self.client.post(url, {'form-TOTAL_FORMS': 2,
                                          'form-INITIAL_FORMS': 2,
                                          'form-0-id': fb0.id,
                                          'form-0-type': 'junk',
                                          'form-1-id': fb1.id,
                                          'form-1-type': 'comment',
                                        })
        self.assertEqual(response.status_code,200) 
        q = PyQuery(response.content)
        self.assertEqual(q('input[name=\"form-0-type\"]').attr['value'],'comment')
        self.assertFalse(q('input[name=\"extra_ids\"]'))

    def test_feedback_unrelated(self):
        FeedbackFactory(nomcom=self.nc,type_id='junk')
        url=reverse('ietf.nomcom.views.view_feedback_unrelated',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_list_templates(self):
        DBTemplateFactory.create(group=self.nc.group,
                                 title='Test template',
                                 path='/nomcom/'+self.nc.group.acronym+'/test',
                                 variables='',
                                 type_id='plain',
                                 content='test content')
        url=reverse('ietf.nomcom.views.list_templates',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_edit_templates(self):
        template = DBTemplateFactory.create(group=self.nc.group,
                                            title='Test template',
                                            path='/nomcom/'+self.nc.group.acronym+'/test',
                                            variables='',
                                            type_id='plain',
                                            content='test content')
        url=reverse('ietf.nomcom.views.edit_template',kwargs={'year':self.nc.year(),'template_id':template.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url,{'content': 'more interesting test content'})
        self.assertEqual(response.status_code,302)
        template = DBTemplate.objects.get(id=template.id)
        self.assertEqual('more interesting test content',template.content)
        
    def test_list_positions(self):
        url = reverse('ietf.nomcom.views.list_positions',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_remove_position(self):
        position = self.nc.position_set.filter(nomineeposition__isnull=False).first()
        f = FeedbackFactory(nomcom=self.nc)
        f.positions.add(position)
        url = reverse('ietf.nomcom.views.remove_position',kwargs={'year':self.nc.year(),'position_id':position.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertTrue(any(['likely to be harmful' in x.text for x in q('.alert-warning')]))
        response = self.client.post(url,{'remove':position.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.nc.position_set.filter(id=position.id))

    def test_remove_invalid_position(self):
        no_such_position_id = self.nc.position_set.aggregate(Max('id'))['id__max']+1
        url = reverse('ietf.nomcom.views.remove_position',kwargs={'year':self.nc.year(),'position_id':no_such_position_id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_edit_position(self):
        position = self.nc.position_set.filter(is_open=True).first()
        url = reverse('ietf.nomcom.views.edit_position',kwargs={'year':self.nc.year(),'position_id':position.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'name':'more interesting test name'})
        self.assertEqual(response.status_code, 302)
        position = Position.objects.get(id=position.id)
        self.assertEqual('more interesting test name',position.name)
        self.assertFalse(position.is_open)

    def test_edit_invalid_position(self):
        no_such_position_id = self.nc.position_set.aggregate(Max('id'))['id__max']+1
        url = reverse('ietf.nomcom.views.edit_position',kwargs={'year':self.nc.year(),'position_id':no_such_position_id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_edit_nominee(self):
        nominee = self.nc.nominee_set.order_by('pk').first()
        new_email = EmailFactory(person=nominee.person, origin='test')
        url = reverse('ietf.nomcom.views.edit_nominee',kwargs={'year':self.nc.year(),'nominee_id':nominee.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'nominee_email':new_email.address})
        self.assertEqual(response.status_code, 302)
        nominee = self.nc.nominee_set.order_by('pk').first()
        self.assertEqual(nominee.email,new_email)

    def test_request_merge(self):
        nominee1, nominee2 = self.nc.nominee_set.all()[:2]
        url = reverse('ietf.nomcom.views.private_merge_person',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        empty_outbox()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'primary_person':nominee1.person.pk,
                                         'duplicate_persons':[nominee1.person.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('must not also be listed as a duplicate', unicontent(response))
        response = self.client.post(url,{'primary_person':nominee1.person.pk,
                                         'duplicate_persons':[nominee2.person.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(outbox),1)
        self.assertTrue(all([str(x.person.pk) in outbox[0].get_payload() for x in [nominee1,nominee2]]))

    def test_extract_email(self):
        url = reverse('ietf.nomcom.views.extract_email_lists',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_eligible(self):
        def first_meeting_of_year(year):
            assert isinstance(year, int)
            assert year >= 1991
            return (year-1985)*3+2
        # Create meetings to ensure we have the 'last 5'
        meeting_start = first_meeting_of_year(datetime.date.today().year-2)
        # Populate the meeting registration records
        for number in range(meeting_start, meeting_start+10):
            meeting = MeetingFactory.create(type_id='ietf', number=number)
            PersonFactory.create_batch(3)
            samples = Person.objects.count()//2
            for (person, ascii, email) in random.sample([ (p, p.ascii, p.email()) for p in Person.objects.all() ], samples):
                if not ' ' in ascii:
                    continue
                first_name, last_name = ascii.rsplit(None, 1)
                MeetingRegistration.objects.create(meeting=meeting, first_name=first_name, last_name=last_name, person=person, country_code='WO', email=email, attended=True)
        # test the page
        url = reverse('ietf.nomcom.views.eligible',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class NomComIndexTests(TestCase):
    def setUp(self):
        for year in range(2000,2014):
            NomComFactory.create(**nomcom_kwargs_for_year(year=year,populate_positions=False,populate_personnel=False))

    def testIndex(self):
        url = reverse('ietf.nomcom.views.index')
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

class NoPublicKeyTests(TestCase):
    def setUp(self):
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year(public_key=None))
        self.chair = self.nc.group.role_set.filter(name='chair').first().person

    def do_common_work(self,url,expected_form):
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q=PyQuery(response.content)
        text_bits = [x.xpath('./text()') for x in q('.alert-warning')]
        flat_text_bits = [item for sublist in text_bits for item in sublist]
        self.assertTrue(any(['not yet' in y for y in flat_text_bits]))
        self.assertEqual(bool(q('form:not(.navbar-form)')),expected_form)
        self.client.logout()

    def test_not_yet(self):
        # Warn reminder mail
        self.do_common_work(reverse('ietf.nomcom.views.send_reminder_mail',kwargs={'year':self.nc.year(),'type':'accept'}),True)
        # No nominations
        self.do_common_work(reverse('ietf.nomcom.views.private_nominate',kwargs={'year':self.nc.year()}),False)
        # No feedback
        self.do_common_work(reverse('ietf.nomcom.views.private_feedback',kwargs={'year':self.nc.year()}),False)
        # No feedback email
        self.do_common_work(reverse('ietf.nomcom.views.private_feedback_email',kwargs={'year':self.nc.year()}),False)
        # No questionnaire responses
        self.do_common_work(reverse('ietf.nomcom.views.private_questionnaire',kwargs={'year':self.nc.year()}),False)

        
class AcceptingTests(TestCase):
    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory(**nomcom_kwargs_for_year())
        self.plain_person = PersonFactory.create()
        self.member = self.nc.group.role_set.filter(name='member').first().person

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_public_accepting_nominations(self):
        url = reverse('ietf.nomcom.views.public_nominate',kwargs={'year':self.nc.year()})

        login_testing_unauthorized(self,self.plain_person.user.username,url)
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('#id_position option')) , 4 )

        pos = self.nc.position_set.first()
        pos.accepting_nominations=False
        pos.save()
        
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('#id_position option')) , 3 )

    def test_private_accepting_nominations(self):
        url = reverse('ietf.nomcom.views.private_nominate',kwargs={'year':self.nc.year()})

        login_testing_unauthorized(self,self.member.user.username,url)
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('#id_position option')) , 4 )

        pos = self.nc.position_set.first()
        pos.accepting_nominations=False
        pos.save()
        
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('#id_position option')) , 4 )

    def test_public_accepting_feedback(self):
        url = reverse('ietf.nomcom.views.public_feedback',kwargs={'year':self.nc.year()})

        login_testing_unauthorized(self,self.plain_person.user.username,url)
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('.badge')) , 6 )

        pos = self.nc.position_set.first()
        pos.accepting_feedback=False
        pos.save()
    
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('.badge')) , 5 )

        topic = self.nc.topic_set.first()
        topic.accepting_feedback=False
        topic.save()
    
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('.badge')) , 4 )

        posurl = url+ "?nominee=%d&position=%d" % (pos.nominee_set.first().pk, pos.pk)
        response = self.client.get(posurl)
        self.assertIn('not currently accepting feedback', unicontent(response))

        test_data = {'comment_text': 'junk',
                     'position_name': pos.name,
                     'nominee_name': pos.nominee_set.first().email.person.name,
                     'nominee_email': pos.nominee_set.first().email.address,
                     'confirmation': False,
                     'nominator_email': self.plain_person.email().address,
                     'nominator_name':  self.plain_person.plain_name(),
                    }
        response = self.client.post(posurl, test_data)
        self.assertIn('not currently accepting feedback', unicontent(response))

        topicurl = url+ "?topic=%d" % (topic.pk, )
        response = self.client.get(topicurl)
        self.assertIn('not currently accepting feedback', unicontent(response))

        test_data = {'comment_text': 'junk',
                     'confirmation': False,
                    }
        response = self.client.post(topicurl, test_data)
        self.assertIn('not currently accepting feedback', unicontent(response))

    def test_private_accepting_feedback(self):
        url = reverse('ietf.nomcom.views.private_feedback',kwargs={'year':self.nc.year()})

        login_testing_unauthorized(self,self.member.user.username,url)
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('.badge')) , 6 )

        pos = self.nc.position_set.first()
        pos.accepting_feedback=False
        pos.save()
    
        response = self.client.get(url)
        q=PyQuery(response.content)
        self.assertEqual( len(q('.badge')) , 6 )

class ShowNomineeTests(TestCase):
    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory(**nomcom_kwargs_for_year())
        self.plain_person = PersonFactory.create()

    def tearDown(self):
        teardown_test_public_keys_dir(self)

    def test_feedback_pictures(self):
        url = reverse('ietf.nomcom.views.public_nominate',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.plain_person.user.username,url)
        response = self.client.get(url)
        q = PyQuery(response.content)
        self.assertTrue(q('h3'))
        self.nc.show_accepted_nominees=False;
        self.nc.save()
        response = self.client.get(url)
        q = PyQuery(response.content)
        self.assertFalse(q('h3'))

class TopicTests(TestCase):
    def setUp(self):
        setup_test_public_keys_dir(self)
        self.nc = NomComFactory(**nomcom_kwargs_for_year(populate_topics=False))
        self.plain_person = PersonFactory.create()
        self.chair = self.nc.group.role_set.filter(name='chair').first().person

    def tearDown(self):
        teardown_test_public_keys_dir(self)
    
    def testAddEditListRemoveTopic(self):
        self.assertFalse(self.nc.topic_set.exists())

        url = reverse('ietf.nomcom.views.edit_topic', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)

        response = self.client.post(url,{'subject':'Test Topic', 'accepting_feedback':True, 'audience':'general'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.nc.topic_set.first().subject,'Test Topic') 
        self.assertEqual(self.nc.topic_set.first().accepting_feedback, True)
        self.assertEqual(self.nc.topic_set.first().audience.slug,'general')

        url = reverse('ietf.nomcom.views.edit_topic', kwargs={'year':self.nc.year(),'topic_id':self.nc.topic_set.first().pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        q = PyQuery(response.content)
        self.assertEqual(q('#id_subject').attr['value'],'Test Topic')

        response = self.client.post(url,{'subject':'Test Topic Modified', 'accepting_feedback':False, 'audience':'nominees'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.nc.topic_set.first().subject,'Test Topic Modified') 
        self.assertEqual(self.nc.topic_set.first().accepting_feedback, False)
        self.assertEqual(self.nc.topic_set.first().audience.slug,'nominees')
        
        self.client.logout()
        url = reverse('ietf.nomcom.views.list_topics',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIn('Test Topic Modified', unicontent(response))

        self.client.logout()
        url = reverse('ietf.nomcom.views.remove_topic', kwargs={'year':self.nc.year(),'topic_id':self.nc.topic_set.first().pk})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIn('Test Topic Modified', unicontent(response))
        response=self.client.post(url,{'remove':1})
        self.assertEqual(response.status_code,302)
        self.assertFalse(self.nc.topic_set.exists())

    def testClassifyTopicFeedback(self):
        topic = TopicFactory(nomcom=self.nc)
        feedback = FeedbackFactory(nomcom=self.nc,type_id=None)

        url = reverse('ietf.nomcom.views.view_feedback_pending',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)

        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': feedback.id,
                                          'form-0-type': 'comment',
                                        })
        self.assertIn('You must choose at least one Nominee or Topic', unicontent(response))
        response = self.client.post(url, {'form-TOTAL_FORMS':1,
                                          'form-INITIAL_FORMS':1,
                                          'end':'Save feedback',
                                          'form-0-id': feedback.id,
                                          'form-0-type': 'comment',
                                          'form-0-topic': '%s'%(topic.id,),
                                        })
        self.assertEqual(response.status_code,302)
        feedback = Feedback.objects.get(id=feedback.id)
        self.assertEqual(feedback.type_id,'comment')
        self.assertEqual(topic.feedback_set.count(),1)

    def testTopicFeedback(self):
        topic = TopicFactory(nomcom=self.nc)
        url = reverse('ietf.nomcom.views.public_feedback',kwargs={'year':self.nc.year() })
        url += '?topic=%d'%topic.pk
        login_testing_unauthorized(self, self.plain_person.user.username, url)
        response=self.client.post(url, {'comment_text':'junk', 'confirmation':False})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-success")
        self.assertNotContains(response, "feedbackform")
        self.assertEqual(topic.feedback_set.count(),1)

    def testAudience(self):
        for audience in ['nomcom','nominees']:
            topic = TopicFactory(nomcom=self.nc,audience_id=audience)
            feedback_url = reverse('ietf.nomcom.views.public_feedback',kwargs={'year':self.nc.year() })
            login_testing_unauthorized(self, self.plain_person.user.username, feedback_url)
            r = self.client.get(feedback_url)
            self.assertNotContains(r, topic.subject)
            topic_url = feedback_url + '?topic=%d'%topic.pk
            r = self.client.get(topic_url)
            self.assertEqual(r.status_code,404)
            r = self.client.post(topic_url, {'comment_text':'junk', 'confirmation':False})
            self.assertEqual(r.status_code,404)

            self.client.logout()
            if audience == 'nomcom':
                valid_user = self.nc.group.role_set.filter(name='member').first().person
            else:
                valid_user = self.nc.nominee_set.first().person
            self.client.login(username=valid_user.user.username,password=valid_user.user.username+"+password")
            r = self.client.get(feedback_url)
            self.assertContains(r, topic.subject)
            r = self.client.get(topic_url)
            self.assertEqual(r.status_code,200)
            r = self.client.post(topic_url, {'comment_text':'junk', 'confirmation':False})
            self.assertEqual(r.status_code,200)
            self.assertEqual(topic.feedback_set.count(),1)
            self.client.logout()
