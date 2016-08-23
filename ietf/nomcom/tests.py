# -*- coding: utf-8 -*-
#import tempfile
import datetime
import os
import shutil
from pyquery import PyQuery
import StringIO

from django.db import IntegrityError
from django.db.models import Max
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.auth.models import User

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import login_testing_unauthorized, TestCase, unicontent
from ietf.utils.mail import outbox, empty_outbox

from ietf.person.models import Email, Person
from ietf.group.models import Group
from ietf.message.models import Message

from ietf.person.utils import merge_persons

from ietf.nomcom.test_data import nomcom_test_data, generate_cert, check_comments, \
                                  COMMUNITY_USER, CHAIR_USER, \
                                  MEMBER_USER, SECRETARIAT_USER, EMAIL_DOMAIN, NOMCOM_YEAR
from ietf.nomcom.models import NomineePosition, Position, Nominee, \
                               NomineePositionStateName, Feedback, FeedbackTypeName, \
                               Nomination, FeedbackLastSeen
from ietf.nomcom.forms import EditMembersForm, EditMembersFormPreview
from ietf.nomcom.utils import get_nomcom_by_year, make_nomineeposition, get_hash_nominee_position
from ietf.nomcom.management.commands.send_reminders import Command, is_time_to_send

from ietf.nomcom.factories import NomComFactory, FeedbackFactory, \
                                  nomcom_kwargs_for_year, provide_private_key_to_test_client, \
                                  key
from ietf.person.factories import PersonFactory, EmailFactory, UserFactory
from ietf.dbtemplate.factories import DBTemplateFactory
from ietf.dbtemplate.models import DBTemplate

client_test_cert_files = None

def get_cert_files():
    global client_test_cert_files
    if not client_test_cert_files:
        client_test_cert_files = generate_cert()
    return client_test_cert_files

def build_test_public_keys_dir(obj):
    obj.saved_nomcom_public_keys_dir = settings.NOMCOM_PUBLIC_KEYS_DIR
    obj.nomcom_public_keys_dir = os.path.abspath("tmp-nomcom-public-keys-dir")
    if not os.path.exists(obj.nomcom_public_keys_dir):
        os.mkdir(obj.nomcom_public_keys_dir)
    settings.NOMCOM_PUBLIC_KEYS_DIR = obj.nomcom_public_keys_dir

def clean_test_public_keys_dir(obj):
    settings.NOMCOM_PUBLIC_KEYS_DIR = obj.saved_nomcom_public_keys_dir
    shutil.rmtree(obj.nomcom_public_keys_dir)

class NomcomViewsTest(TestCase):
    """Tests to create a new nomcom"""

    def check_url_status(self, url, status):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)
        return response

    def setUp(self):
        build_test_public_keys_dir(self)
        nomcom_test_data()
        self.cert_file, self.privatekey_file = get_cert_files()
        self.year = NOMCOM_YEAR

        # private urls
        self.private_index_url = reverse('nomcom_private_index', kwargs={'year': self.year})
        self.private_merge_url = reverse('nomcom_private_merge', kwargs={'year': self.year})
        self.edit_members_url = reverse('nomcom_edit_members', kwargs={'year': self.year})
        self.edit_nomcom_url = reverse('nomcom_edit_nomcom', kwargs={'year': self.year})
        self.private_nominate_url = reverse('nomcom_private_nominate', kwargs={'year': self.year})
        self.private_nominate_newperson_url = reverse('nomcom_private_nominate_newperson', kwargs={'year': self.year})
        self.add_questionnaire_url = reverse('nomcom_private_questionnaire', kwargs={'year': self.year})
        self.private_feedback_url = reverse('nomcom_private_feedback', kwargs={'year': self.year})
        self.positions_url = reverse("nomcom_list_positions", kwargs={'year': self.year})        
        self.edit_position_url = reverse("nomcom_add_position", kwargs={'year': self.year})

        # public urls
        self.index_url = reverse('nomcom_year_index', kwargs={'year': self.year})
        self.requirements_url = reverse('nomcom_requirements', kwargs={'year': self.year})
        self.questionnaires_url = reverse('nomcom_questionnaires', kwargs={'year': self.year})
        self.public_feedback_url = reverse('nomcom_public_feedback', kwargs={'year': self.year})
        self.public_nominate_url = reverse('nomcom_public_nominate', kwargs={'year': self.year})
        self.public_nominate_newperson_url = reverse('nomcom_public_nominate_newperson', kwargs={'year': self.year})

    def tearDown(self):
        clean_test_public_keys_dir(self)

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
        self.client.logout()

    def create_nominees_for_states(self, base_state):
        cnominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)
        position = Position.objects.get(name='APP')
        nom_pos = NomineePosition.objects.create(position=position,
                                                          nominee=cnominee,
                                                          state=NomineePositionStateName.objects.get(slug=base_state))
        position = Position.objects.get(name='INT')
        NomineePosition.objects.create(position=position,
                                                          nominee=cnominee,
                                                          state=NomineePositionStateName.objects.get(slug=base_state))
        position = Position.objects.get(name='OAM')
        NomineePosition.objects.create(position=position,
                                                          nominee=cnominee,
                                                          state=NomineePositionStateName.objects.get(slug=base_state))
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


    def change_members(self, members):
        members_emails = u','.join(['%s%s' % (member, EMAIL_DOMAIN) for member in members])
        test_data = {'members': members_emails,
                     'stage': 1}
        # preview
        self.client.post(self.edit_members_url, test_data)

        hash = EditMembersFormPreview(EditMembersForm).security_hash(None, EditMembersForm(test_data))
        test_data.update({'hash': hash, 'stage': 2})

        # submit
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

        f = open(self.cert_file.name)
        response = self.client.post(self.edit_nomcom_url, {
            'public_key': f,
            'reminderdates_set-TOTAL_FORMS': q('input[name="reminderdates_set-TOTAL_FORMS"]').val(),
            'reminderdates_set-INITIAL_FORMS': q('input[name="reminderdates_set-INITIAL_FORMS"]').val(),
            'reminderdates_set-MAX_NUM_FORMS': q('input[name="reminderdates_set-MAX_NUM_FORMS"]').val(),
        })
        f.close()
        self.assertEqual(response.status_code, 200)

        nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')

        comments = u'Plain text. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        nomcom = get_nomcom_by_year(self.year)
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           comments=comments,
                                           type=FeedbackTypeName.objects.get(slug='nomina'))
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)

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
            content_type="",
            )
        msg.related_groups.add(nomcom)
        
        r = self.client.get(reverse('ietf.nomcom.views.announcements'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(("Messages from %s" % nomcom.time.year) in unicontent(r))
        self.assertTrue(nomcom.role_set.filter(name="chair")[0].person.email_address() in unicontent(r))
        self.assertTrue(msg.subject in unicontent(r))


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
        self.assertTrue('nominee' in outbox[-3]['To'])

        self.assertEqual('Nomination Information', outbox[-2]['Subject'])
        self.assertTrue('nomcomchair' in outbox[-2]['To'])

        self.assertEqual('Nomination receipt', outbox[-1]['Subject'])
        self.assertTrue('plain' in outbox[-1]['To'])
        self.assertTrue(u'Comments with accents äöå' in unicode(outbox[-1].get_payload(decode=True),"utf-8","replace"))

        # Nominate the same person for the same position again without asking for confirmation 

        messages_before = len(outbox)

        self.nominate_view(public=True)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertEqual('Nomination Information', outbox[-1]['Subject'])
        self.assertTrue('nomcomchair' in outbox[-1]['To'])

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
        self.assertTrue('secretariat' in outbox[-4]['To'])

        self.assertEqual('IETF Nomination Information', outbox[-3]['Subject'])
        self.assertTrue('nominee' in outbox[-3]['To'])

        self.assertEqual('Nomination Information', outbox[-2]['Subject'])
        self.assertTrue('nomcomchair' in outbox[-2]['To'])

        self.assertEqual('Nomination receipt', outbox[-1]['Subject'])
        self.assertTrue('plain' in outbox[-1]['To'])
        self.assertTrue(u'Comments with accents äöå' in unicode(outbox[-1].get_payload(decode=True),"utf-8","replace"))

        # Nominate the same person for the same position again without asking for confirmation 

        messages_before = len(outbox)

        self.nominate_view(public=True)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertEqual('Nomination Information', outbox[-1]['Subject'])
        self.assertTrue('nomcomchair' in outbox[-1]['To'])

    def test_private_nominate_newperson(self):
        self.access_member_url(self.private_nominate_url)
        return self.nominate_newperson_view(public=False)
        self.client.logout()

    def test_public_nominate_with_automatic_questionnaire(self):
        nomcom = get_nomcom_by_year(self.year)
        nomcom.send_questionnaire = True
        nomcom.save()
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)
        empty_outbox()
        self.nominate_view(public=True)
        self.assertEqual(len(outbox), 3)
        # test_public_nominate checks the other messages
        self.assertTrue('Questionnaire' in outbox[1]['Subject'])
        self.assertTrue('nominee@' in outbox[1]['To'])


    def nominate_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        searched_email = kwargs.pop('searched_email', None)
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
        if not searched_email:
            searched_email = Email.objects.filter(address=nominee_email).first() 
            if not searched_email:
                searched_email = EmailFactory(address=nominee_email,primary=True)
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
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#nominate-form")), 1)

        position = Position.objects.get(name=position_name)
        comments = u'Test nominate view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        candidate_phone = u'123456'

        test_data = {'searched_email': searched_email.pk,
                     'candidate_phone': candidate_phone,
                     'position': position.id,
                     'qualifications': comments,
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
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)
        Nomination.objects.get(position=position,
                               candidate_name=nominee.person.plain_name(),
                               candidate_email=searched_email.address,
                               candidate_phone=candidate_phone,
                               nominee=nominee,
                               comments=feedback,
                               nominator_email="%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))

    def nominate_newperson_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
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
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertEqual(len(q("#nominate-form")), 1)

        position = Position.objects.get(name=position_name)
        candidate_email = nominee_email
        candidate_name = u'nominee'
        comments = u'Test nominate view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        candidate_phone = u'123456'

        test_data = {'candidate_name': candidate_name,
                     'candidate_email': candidate_email,
                     'candidate_phone': candidate_phone,
                     'position': position.id,
                     'qualifications': comments,
                     'confirmation': confirmation}
        if not public:
            test_data['nominator_email'] = nominator_email

        response = self.client.post(nominate_url, test_data,follow=True)
        self.assertTrue(response.redirect_chain)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertContains(response, "alert-success")

        # check objects
        email = Email.objects.get(address=candidate_email)
        Person.objects.get(name=candidate_name, address=candidate_email)
        nominee = Nominee.objects.get(email=email)
        NomineePosition.objects.get(position=position, nominee=nominee)
        feedback = Feedback.objects.filter(positions__in=[position],
                                           nominees__in=[nominee],
                                           type=FeedbackTypeName.objects.get(slug='nomina')).latest('id')
        if public:
            self.assertEqual(feedback.author, nominator_email)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)
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
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
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
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(self.add_questionnaire_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "questionnnaireform")

        position = Position.objects.get(name=position_name)
        nominee = Nominee.objects.get(email__address=nominee_email)

        comments = u'Test add questionnaire view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'

        test_data = {'comments': comments,
                     'nominee': '%s_%s' % (position.id, nominee.id)}

        response = self.client.post(self.add_questionnaire_url, test_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert-success")

        ## check objects
        feedback = Feedback.objects.filter(positions__in=[position],
                                           nominees__in=[nominee],
                                           type=FeedbackTypeName.objects.get(slug='questio')).latest('id')

        ## to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)

    def test_public_feedback(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_feedback_url)

        empty_outbox()
        self.feedback_view(public=True,confirmation=True)
        # feedback_view does a nomination internally: there is a lot of email related to that - tested elsewhere
        # We're interested in the confirmation receipt here
        self.assertEqual(len(outbox),3)
        self.assertEqual('NomCom comment confirmation', outbox[2]['Subject'])
        self.assertTrue('plain' in outbox[2]['To'])
        self.assertTrue(u'Comments with accents äöå' in unicode(outbox[2].get_payload(decode=True),"utf-8","replace"))

        empty_outbox()
        self.feedback_view(public=True)
        self.assertEqual(len(outbox),1)
        self.assertFalse('confirmation' in outbox[0]['Subject'])

    def test_private_feedback(self):
        self.access_member_url(self.private_feedback_url)
        return self.feedback_view(public=False)

    def feedback_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
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
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(feedback_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "feedbackform")

        position = Position.objects.get(name=position_name)
        nominee = Nominee.objects.get(email__address=nominee_email)

        feedback_url += "?nominee=%d&position=%d" % (nominee.id, position.id)
        response = self.client.get(feedback_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "feedbackform")

        comments = u'Test feedback view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'

        test_data = {'comments': comments,
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
        self.assertEqual(response.status_code, 200)
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
        build_test_public_keys_dir(self)
        nomcom_test_data()
        self.nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)

    def tearDown(self):
        clean_test_public_keys_dir(self)

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
        build_test_public_keys_dir(self)

        nomcom_test_data()
        self.cert_file, self.privatekey_file = get_cert_files()

    def tearDown(self):
        clean_test_public_keys_dir(self)

    def test_encrypted_comments(self):

        nominee = Nominee.objects.get(email__person__user__username=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')
        nomcom = position.nomcom

        # save the cert file in tmp
        #nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        comments = u'Plain text. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.'
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           comments=comments,
                                           type=FeedbackTypeName.objects.get(slug='nomina'))
        feedback.positions.add(position)
        feedback.nominees.add(nominee)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments, comments, self.privatekey_file), True)

class ReminderTest(TestCase):

    def setUp(self):
        build_test_public_keys_dir(self)
        nomcom_test_data()
        self.nomcom = get_nomcom_by_year(NOMCOM_YEAR)
        self.cert_file, self.privatekey_file = get_cert_files()
        #self.nomcom.public_key.storage.location = tempfile.gettempdir()
        self.nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        gen = Position.objects.get(nomcom=self.nomcom,name='GEN')
        rai = Position.objects.get(nomcom=self.nomcom,name='RAI')
        iab = Position.objects.get(nomcom=self.nomcom,name='IAB')

        today = datetime.date.today()
        t_minus_3 = today - datetime.timedelta(days=3)
        t_minus_4 = today - datetime.timedelta(days=4)
        e1 = EmailFactory(address="nominee1@example.org",person=PersonFactory(name=u"Nominee 1"))
        e2 = EmailFactory(address="nominee2@example.org",person=PersonFactory(name=u"Nominee 2"))
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
                                           comments='some non-empty comments',
                                           type=FeedbackTypeName.objects.get(slug='questio'),
                                           user=User.objects.get(username=CHAIR_USER))
        feedback.positions.add(gen)
        feedback.nominees.add(n)

    def tearDown(self):
        clean_test_public_keys_dir(self)

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
        self.assertTrue('nominee1@example.org' in outbox[-1]['To'])
        self.assertTrue('please complete' in outbox[-1]['Subject'])
        self.assertTrue('nominee1@example.org' in outbox[-2]['To'])
        self.assertTrue('please accept' in outbox[-2]['Subject'])
        messages_before=len(outbox)
        self.nomcom.reminder_interval = 4
        self.nomcom.save()
        c.handle(None,None)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertTrue('nominee2@example.org' in outbox[-1]['To'])
        self.assertTrue('please accept' in outbox[-1]['Subject'])
     
    def test_remind_accept_view(self):
        url = reverse('nomcom_send_reminder_mail', kwargs={'year': NOMCOM_YEAR,'type':'accept'})
        login_testing_unauthorized(self, CHAIR_USER, url)
        messages_before=len(outbox)
        test_data = {'selected': [x.id for x in Nominee.objects.filter(nomcom=self.nomcom)]}
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(outbox), messages_before + 2)
        self.assertTrue('nominee1@' in outbox[-2]['To'])
        self.assertTrue('nominee2@' in outbox[-1]['To'])

    def test_remind_questionnaire_view(self):
        url = reverse('nomcom_send_reminder_mail', kwargs={'year': NOMCOM_YEAR,'type':'questionnaire'})
        login_testing_unauthorized(self, CHAIR_USER, url)
        messages_before=len(outbox)
        test_data = {'selected': [x.id for x in Nominee.objects.filter(nomcom=self.nomcom)]}
        response = self.client.post(url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(outbox), messages_before + 1)
        self.assertTrue('nominee1@' in outbox[-1]['To'])

class InactiveNomcomTests(TestCase):

    def setUp(self):
        build_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year(group__state_id='conclude'))
        self.plain_person = PersonFactory.create()
        self.chair = self.nc.group.role_set.filter(name='chair').first().person
        self.member = self.nc.group.role_set.filter(name='member').first().person

    def tearDown(self):
        clean_test_public_keys_dir(self)

    def test_feedback_closed(self):
        for view in ['nomcom_public_feedback', 'nomcom_private_feedback']:
            url = reverse(view, kwargs={'year': self.nc.year()})
            who = self.plain_person if 'public' in view else self.member
            login_testing_unauthorized(self, who.user.username, url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertTrue( '(Concluded)' in q('h1').text())
            self.assertTrue( 'closed' in q('#instructions').text())
            self.assertTrue( q('#nominees a') )
            self.assertFalse( q('#nominees a[href]') )
    
            url += "?nominee=%d&position=%d" % (self.nc.nominee_set.first().id, self.nc.nominee_set.first().nomineeposition_set.first().position.id)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertFalse( q('#feedbackform'))        
            
            empty_outbox()
            fb_before = self.nc.feedback_set.count()
            test_data = {'comments': u'Test feedback view. Comments with accents äöåÄÖÅ éáíóú âêîôû ü àèìòù.',
                         'nominator_email': self.plain_person.email_set.first().address,
                         'confirmation': True}
            response = self.client.post(url, test_data)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertTrue( 'closed' in q('#instructions').text())
            self.assertEqual( len(outbox), 0 )
            self.assertEqual( fb_before, self.nc.feedback_set.count() )

    def test_nominations_closed(self):
        for view in ['nomcom_public_nominate', 'nomcom_private_nominate']:
            url = reverse(view, kwargs={'year': self.nc.year() })
            who = self.plain_person if 'public' in view else self.member
            login_testing_unauthorized(self, who.user.username, url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            q = PyQuery(response.content)
            self.assertTrue( '(Concluded)' in q('h1').text())
            self.assertTrue( 'closed' in q('.alert-warning').text())

    def test_acceptance_closed(self):
        today = datetime.date.today().strftime('%Y%m%d')
	pid = self.nc.position_set.first().nomineeposition_set.first().id 
        url = reverse('nomcom_process_nomination_status', kwargs = {
                      'year' : self.nc.year(),
                      'nominee_position_id' : pid,
                      'state' : 'accepted',
                      'date' : today,
                      'hash' : get_hash_nominee_position(today,pid),
                     })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_can_view_but_cannot_edit_nomcom_settings(self):
        url = reverse('nomcom_edit_nomcom',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_classify_feedback(self):
        url = reverse('nomcom_view_feedback_pending',kwargs={'year':self.nc.year() })
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_modify_nominees(self):
        url = reverse('nomcom_private_index', kwargs={'year':self.nc.year()})
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
        self.assertTrue('not active' in q('.alert-warning').text() )

    def test_email_pasting_closed(self):
        url = reverse('nomcom_private_feedback_email', kwargs={'year':self.nc.year()})
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
        self.assertTrue('not active' in q('.alert-warning').text() )

    def test_questionnaire_entry_closed(self):
        url = reverse('nomcom_private_questionnaire', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#questionnaireform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue('not active' in q('.alert-warning').text() )
        
    def _test_send_reminders_closed(self,rtype):
        url = reverse('nomcom_send_reminder_mail', kwargs={'year':self.nc.year(),'type':rtype })
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#reminderform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue('not active' in q('.alert-warning').text() )

    def test_send_accept_reminders_closed(self):
        self._test_send_reminders_closed('accept')

    def test_send_questionnaire_reminders_closed(self):
        self._test_send_reminders_closed('questionnaire')

    def test_merge_closed(self):
        url = reverse('nomcom_private_merge', kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        q = PyQuery(response.content)
        self.assertFalse( q('#mergeform'))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertTrue('not active' in q('.alert-warning').text() )

    def test_cannot_edit_position(self):
        url = reverse('nomcom_edit_position',kwargs={'year':self.nc.year(),'position_id':self.nc.position_set.first().id})
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_add_position(self):
        url = reverse('nomcom_add_position',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        provide_private_key_to_test_client(self)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url,{})
        self.assertEqual(response.status_code, 403)

    def test_cannot_delete_position(self):
        url = reverse('nomcom_remove_position',kwargs={'year':self.nc.year(),'position_id':self.nc.position_set.first().id})
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
        url = reverse('nomcom_edit_template',kwargs={'year':self.nc.year(), 'template_id':template.id})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        q = PyQuery(response.content)
        self.assertFalse( q('#templateform') )

class FeedbackLastSeenTests(TestCase):

    def setUp(self):
        build_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year())
        self.author = PersonFactory.create().email_set.first().address
        self.member = self.nc.group.role_set.filter(name='member').first().person
        self.nominee = self.nc.nominee_set.first()
        self.position = self.nc.position_set.first()
        for type_id in ['comment','nomina','questio']:
            f = FeedbackFactory.create(author=self.author,nomcom=self.nc,type_id=type_id)
            f.positions.add(self.position)
            f.nominees.add(self.nominee)
        now = datetime.datetime.now() 
        self.hour_ago = now - datetime.timedelta(hours=1)
        self.half_hour_ago = now - datetime.timedelta(minutes=30)
        self.second_from_now = now + datetime.timedelta(seconds=1)

    def tearDown(self):
        clean_test_public_keys_dir(self)

    def test_feedback_index_badges(self):
        url = reverse('nomcom_view_feedback',kwargs={'year':self.nc.year()})
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

    def test_feedback_nominee_badges(self):
        url = reverse('nomcom_view_feedback_nominee',kwargs={'year':self.nc.year(),'nominee_id':self.nominee.id})
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

class NewActiveNomComTests(TestCase):

    def setUp(self):
        build_test_public_keys_dir(self)
        self.nc = NomComFactory.create(**nomcom_kwargs_for_year())
        self.chair = self.nc.group.role_set.filter(name='chair').first().person
        self.saved_days_to_expire_nomination_link = settings.DAYS_TO_EXPIRE_NOMINATION_LINK

    def tearDown(self):
        clean_test_public_keys_dir(self)
        settings.DAYS_TO_EXPIRE_NOMINATION_LINK = self.saved_days_to_expire_nomination_link

    def test_help(self):
        url = reverse('nomcom_chair_help',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self, self.chair.user.username, url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_accept_reject_nomination_edges(self):

        np = self.nc.nominee_set.first().nomineeposition_set.first()

        kwargs={'year':self.nc.year(),
                'nominee_position_id':np.id,
                'state':'accepted',
                'date':np.time.strftime("%Y%m%d"),
                'hash':get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id),
               }
        url = reverse('nomcom_process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertTrue('already was' in unicontent(response))

        settings.DAYS_TO_EXPIRE_NOMINATION_LINK = 2
        np.time = np.time - datetime.timedelta(days=3)
        np.save()
        kwargs['date'] = np.time.strftime("%Y%m%d")
        kwargs['hash'] = get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id)
        url = reverse('nomcom_process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertTrue('Link expired' in unicontent(response))

        kwargs['hash'] = 'bad'
        url = reverse('nomcom_process_nomination_status', kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code,403)
        self.assertTrue('Bad hash!' in unicontent(response))

    def test_accept_reject_nomination_comment(self):
        np = self.nc.nominee_set.first().nomineeposition_set.first()
        hash = get_hash_nominee_position(np.time.strftime("%Y%m%d"),np.id)
        url = reverse('nomcom_process_nomination_status',
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
        url = reverse('nomcom_private_key',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url,{'key':key})
        self.assertEqual(response.status_code,302)

    def test_email_pasting(self):
        url = reverse('nomcom_private_feedback_email',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        fb_count_before = Feedback.objects.count()
        response = self.client.post(url,{'email_text':"""To: rjsparks@nostrum.com
From: Robert Sparks <rjsparks@nostrum.com>
Subject: Junk message for feedback testing
Message-ID: <566F2FE5.1050401@nostrum.com>
Date: Mon, 14 Dec 2015 15:08:53 -0600
Content-Type: text/plain; charset=utf-8; format=flowed
Content-Transfer-Encoding: 7bit

Junk body for testing

"""})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Feedback.objects.count(),fb_count_before+1)

    def test_simple_feedback_pending(self):
        url = reverse('nomcom_view_feedback_pending',kwargs={'year':self.nc.year() })
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
        nominee = self.nc.nominee_set.first()
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
        url = reverse('nomcom_view_feedback_pending',kwargs={'year':self.nc.year() })
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
        nominee = self.nc.nominee_set.first()
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
        url=reverse('nomcom_view_feedback_unrelated',kwargs={'year':self.nc.year()})
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
        url=reverse('nomcom_list_templates',kwargs={'year':self.nc.year()})
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
        url=reverse('nomcom_edit_template',kwargs={'year':self.nc.year(),'template_id':template.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        response = self.client.post(url,{'content': 'more interesting test content'})
        self.assertEqual(response.status_code,302)
        template = DBTemplate.objects.get(id=template.id)
        self.assertEqual('more interesting test content',template.content)
        
    def test_list_positions(self):
        url = reverse('nomcom_list_positions',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)

    def test_remove_position(self):
        position = self.nc.position_set.filter(nomineeposition__isnull=False).first()
        f = FeedbackFactory(nomcom=self.nc)
        f.positions.add(position)
        url = reverse('nomcom_remove_position',kwargs={'year':self.nc.year(),'position_id':position.id})
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
        url = reverse('nomcom_remove_position',kwargs={'year':self.nc.year(),'position_id':no_such_position_id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_edit_position(self):
        position = self.nc.position_set.filter(is_open=True).first()
        url = reverse('nomcom_edit_position',kwargs={'year':self.nc.year(),'position_id':position.id})
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
        url = reverse('nomcom_edit_position',kwargs={'year':self.nc.year(),'position_id':no_such_position_id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_edit_nominee(self):
        nominee = self.nc.nominee_set.first()
        new_email = EmailFactory(person=nominee.person)
        url = reverse('nomcom_edit_nominee',kwargs={'year':self.nc.year(),'nominee_id':nominee.id})
        login_testing_unauthorized(self,self.chair.user.username,url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'nominee_email':new_email.address})
        self.assertEqual(response.status_code, 302)
        nominee = self.nc.nominee_set.first()
        self.assertEqual(nominee.email,new_email)

    def test_request_merge(self):
        nominee1, nominee2 = self.nc.nominee_set.all()[:2]
        url = reverse('nomcom_private_merge',kwargs={'year':self.nc.year()})
        login_testing_unauthorized(self,self.chair.user.username,url)
        empty_outbox()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url,{'primary_person':nominee1.person.pk,
                                         'duplicate_persons':[nominee1.person.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue('must not also be listed as a duplicate' in unicontent(response))
        response = self.client.post(url,{'primary_person':nominee1.person.pk,
                                         'duplicate_persons':[nominee2.person.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(outbox),1)
        self.assertTrue(all([str(x.person.pk) in unicode(outbox[0]) for x in [nominee1,nominee2]]))


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
        self.do_common_work(reverse('nomcom_send_reminder_mail',kwargs={'year':self.nc.year(),'type':'accept'}),True)
        # No nominations
        self.do_common_work(reverse('nomcom_private_nominate',kwargs={'year':self.nc.year()}),False)
        # No feedback
        self.do_common_work(reverse('nomcom_private_feedback',kwargs={'year':self.nc.year()}),False)
        # No feedback email
        self.do_common_work(reverse('nomcom_private_feedback_email',kwargs={'year':self.nc.year()}),False)
        # No questionnaire responses
        self.do_common_work(reverse('nomcom_private_questionnaire',kwargs={'year':self.nc.year()}),False)
        # Warn on edit nomcom
        self.do_common_work(reverse('nomcom_edit_nomcom',kwargs={'year':self.nc.year()}),True)

class MergePersonTests(TestCase):
    def setUp(self):
        build_test_public_keys_dir(self)
        self.nc = NomComFactory(**nomcom_kwargs_for_year())
        self.author = PersonFactory.create().email_set.first().address
        self.nominee1, self.nominee2 = self.nc.nominee_set.all()[:2]
        self.person1, self.person2 = self.nominee1.person, self.nominee2.person
        self.position = self.nc.position_set.first()
        for nominee in [self.nominee1, self.nominee2]:
            f = FeedbackFactory.create(author=self.author,nomcom=self.nc,type_id='nomina')
            f.positions.add(self.position)
            f.nominees.add(nominee)
        UserFactory(is_superuser=True)

    def tearDown(self):
        clean_test_public_keys_dir(self)

    def test_merge_person(self):
        person1, person2 = [nominee.person for nominee in self.nc.nominee_set.all()[:2]]
        stream = StringIO.StringIO() 
        
        self.assertEqual(self.nc.nominee_set.count(),4)
        self.assertEqual(self.nominee1.feedback_set.count(),1) 
        self.assertEqual(self.nominee2.feedback_set.count(),1) 
        merge_persons(person1,person2,stream)
        self.assertEqual(self.nc.nominee_set.count(),3)
        self.assertEqual(self.nc.nominee_set.get(pk=self.nominee2.pk).feedback_set.count(),2)
        self.assertFalse(self.nc.nominee_set.filter(pk=self.nominee1.pk).exists())
        
