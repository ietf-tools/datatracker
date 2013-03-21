import os
import tempfile

from django.test import TestCase
from django.db import IntegrityError
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.formtools.preview import security_hash

from ietf.utils.test_utils import login_testing_unauthorized


from ietf.person.models import Email, Person

from ietf.nomcom.test_data import nomcom_test_data, generate_cert, check_comments, \
                                  COMMUNITY_USER, CHAIR_USER, \
                                  MEMBER_USER, SECRETARIAT_USER, EMAIL_DOMAIN, NOMCOM_YEAR
from ietf.nomcom.models import NomineePosition, Position, Nominee, \
                               NomineePositionState, Feedback, FeedbackType, \
                               Nomination
from ietf.nomcom.forms import EditChairForm, EditMembersForm
from ietf.nomcom.utils import get_nomcom_by_year


class NomcomViewsTest(TestCase):
    """Tests to create a new nomcom"""
    fixtures = ['names', 'nomcom_templates']

    def check_url_status(self, url, status):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)

    def setUp(self):
        nomcom_test_data()
        self.cert_file, self.privatekey_file = generate_cert()
        self.year = NOMCOM_YEAR

        # private urls
        self.private_index_url = reverse('nomcom_private_index', kwargs={'year': self.year})
        self.private_merge_url = reverse('nomcom_private_merge', kwargs={'year': self.year})
        self.edit_members_url = reverse('nomcom_edit_members', kwargs={'year': self.year})
        self.edit_chair_url = reverse('nomcom_edit_chair', kwargs={'year': self.year})
        self.edit_nomcom_url = reverse('nomcom_edit_nomcom', kwargs={'year': self.year})
        self.private_nominate_url = reverse('nomcom_private_nominate', kwargs={'year': self.year})
        self.private_feedback_url = reverse('nomcom_private_feedback', kwargs={'year': self.year})

        # public urls
        self.index_url = reverse('nomcom_index', kwargs={'year': self.year})
        self.requirements_url = reverse('nomcom_requirements', kwargs={'year': self.year})
        self.questionnaires_url = reverse('nomcom_questionnaires', kwargs={'year': self.year})
        self.public_feedback_url = reverse('nomcom_public_feedback', kwargs={'year': self.year})
        self.public_nominate_url = reverse('nomcom_public_nominate', kwargs={'year': self.year})

    def access_member_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        self.check_url_status(url, 200)
        self.client.logout()
        login_testing_unauthorized(self, MEMBER_USER, url)
        self.check_url_status(url, 200)

    def access_chair_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, MEMBER_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        self.check_url_status(url, 200)

    def access_secretariat_url(self, url):
        login_testing_unauthorized(self, COMMUNITY_USER, url)
        login_testing_unauthorized(self, CHAIR_USER, url)
        login_testing_unauthorized(self, SECRETARIAT_USER, url)
        self.check_url_status(url, 200)

    def test_private_index_view(self):
        """Verify private home view"""
        self.access_member_url(self.private_index_url)
        self.client.logout()

    def test_private_merge_view(self):
        """Verify private merge view"""

        # do nominations
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)
        self.nominate_view(public=True, nominee_email=u'nominee@example.com',
                           position='IAOC')
        self.nominate_view(public=True, nominee_email=u'nominee2@example.com',
                           position='IAOC')
        self.nominate_view(public=True, nominee_email=u'nominee3@example.com',
                           position='IAB')
        self.nominate_view(public=True, nominee_email=u'nominee4@example.com',
                           position='TSV')

        self.client.logout()

        # merge nominations
        self.access_chair_url(self.private_merge_url)

        test_data = {"secondary_emails": "nominee@example.com, nominee2@example.com",
                     "primary_email": "nominee@example.com"}
        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-error")

        test_data = {"primary_email": "nominee@example.com",
                     "secondary_emails": ""}
        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-error")

        test_data = {"primary_email": "",
                     "secondary_emails": "nominee@example.com"}
        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-error")

        test_data = {"primary_email": "unknown@example.com",
                     "secondary_emails": "nominee@example.com"}
        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-error")

        test_data = {"primary_email": "nominee@example.com",
                     "secondary_emails": "unknown@example.com"}
        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-error")

        test_data = {"secondary_emails": """nominee2@example.com,
                                            nominee3@example.com,
                                            nominee4@example.com""",
                     "primary_email": "nominee@example.com"}

        response = self.client.post(self.private_merge_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-success")

        self.assertEqual(Nominee.objects.filter(email__address='nominee2@example.com',
                                                duplicated__isnull=False).count(), 1)
        self.assertEqual(Nominee.objects.filter(email__address='nominee3@example.com',
                                                duplicated__isnull=False).count(), 1)
        self.assertEqual(Nominee.objects.filter(email__address='nominee4@example.com',
                                                duplicated__isnull=False).count(), 1)

        nominee = Nominee.objects.get(email__address='nominee@example.com')
        self.assertEqual(Nomination.objects.filter(nominee=nominee).count(), 4)
        self.assertEqual(Feedback.objects.filter(nominee=nominee).count(), 4)
        self.assertEqual(NomineePosition.objects.filter(nominee=nominee).count(), 3)

        self.client.logout()

    def change_members(self, members):
        members_emails = u','.join(['%s%s' % (member, EMAIL_DOMAIN) for member in members])
        test_data = {'members': members_emails,
                     'stage': 1}
        # preview
        self.client.post(self.edit_members_url, test_data)

        hash = security_hash(None, EditMembersForm(test_data))
        test_data.update({'hash': hash, 'stage': 2})

        # submit
        self.client.post(self.edit_members_url, test_data)

    def test_edit_members_view(self):
        """Verify edit member view"""
        self.access_chair_url(self.edit_members_url)
        self.change_members([CHAIR_USER, COMMUNITY_USER])

        # check member actions
        self.client.login(remote_user=COMMUNITY_USER)
        self.check_url_status(self.private_index_url, 200)

        # revert edit nomcom members
        login_testing_unauthorized(self, CHAIR_USER, self.edit_members_url)
        self.change_members([CHAIR_USER])
        self.client.login(remote_user=COMMUNITY_USER)
        self.check_url_status(self.private_index_url, 403)

        self.client.logout()

    def change_chair(self, user):
        test_data = {'chair': '%s%s' % (user, EMAIL_DOMAIN),
                     'stage': 1}
        # preview
        self.client.post(self.edit_chair_url, test_data)

        hash = security_hash(None, EditChairForm(test_data))
        test_data.update({'hash': hash, 'stage': 2})

        # submit
        self.client.post(self.edit_chair_url, test_data)

    def test_edit_chair_view(self):
        """Verify edit chair view"""
        self.access_secretariat_url(self.edit_chair_url)
        self.change_chair(COMMUNITY_USER)

        # check chair actions
        self.client.login(remote_user=COMMUNITY_USER)
        self.check_url_status(self.edit_members_url, 200)
        self.check_url_status(self.edit_nomcom_url, 200)

        # revert edit nomcom chair
        login_testing_unauthorized(self, SECRETARIAT_USER, self.edit_chair_url)
        self.change_chair(CHAIR_USER)
        self.client.logout()

    def test_edit_nomcom_view(self):
        """Verify edit nomcom view"""
        login_testing_unauthorized(self, COMMUNITY_USER, self.edit_nomcom_url)
        login_testing_unauthorized(self, CHAIR_USER, self.edit_nomcom_url)
        self.check_url_status(self.edit_nomcom_url, 200)
        f = open(self.cert_file.name)
        response = self.client.post(self.edit_nomcom_url, {'public_key': f})
        f.close()
        self.assertEqual(response.status_code, 200)

        nominee = Nominee.objects.get(email__person__name=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')

        comments = 'plain text'
        nomcom = get_nomcom_by_year(self.year)
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           nominee=nominee,
                                           comments=comments,
                                           type=FeedbackType.objects.get(slug='nomina'))
        feedback.positions.add(position)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments,
                                        comments,
                                        self.privatekey_file), True)

        self.client.logout()

    def test_index_view(self):
        """Verify home view"""
        self.check_url_status(self.index_url, 200)

    def test_requirements_view(self):
        """Verify requirements view"""
        self.check_url_status(self.requirements_url, 200)

    def test_questionnaires_view(self):
        """Verify questionnaires view"""
        self.check_url_status(self.questionnaires_url, 200)

    def test_public_feedback(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_feedback_url)
        return self.feedback_view(public=True)
        self.client.logout()

    def test_private_feedback(self):
        self.access_member_url(self.private_feedback_url)
        return self.feedback_view(public=False)
        self.client.logout()

    def feedback_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
        position_name = kwargs.pop('position', 'IAOC')

        if public:
            nominate_url = self.public_feedback_url
        else:
            nominate_url = self.private_feedback_url

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            self.assertNotContains(response, "feedbackform")

        # save the cert file in tmp
        nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "feedbackform")

    def test_public_nominate(self):
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_nominate_url)
        return self.nominate_view(public=True)
        self.client.logout()

    def test_private_nominate(self):
        self.access_member_url(self.private_nominate_url)
        return self.nominate_view(public=False)
        self.client.logout()

    def nominate_view(self, *args, **kwargs):
        public = kwargs.pop('public', True)
        nominee_email = kwargs.pop('nominee_email', u'nominee@example.com')
        position_name = kwargs.pop('position', 'IAOC')

        if public:
            nominate_url = self.public_nominate_url
        else:
            nominate_url = self.private_nominate_url
        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)

        nomcom = get_nomcom_by_year(self.year)
        if not nomcom.public_key:
            self.assertNotContains(response, "nominateform")

        # save the cert file in tmp
        nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        response = self.client.get(nominate_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nominateform")

        position = Position.objects.get(name=position_name)
        candidate_email = nominee_email
        candidate_name = u'nominee'
        comments = 'test nominate view'
        candidate_phone = u'123456'

        test_data = {'candidate_name': candidate_name,
                     'candidate_email': candidate_email,
                     'candidate_phone': candidate_phone,
                     'position': position.id,
                     'comments': comments}
        if not public:
            test_data['nominator_email'] = "%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN)

        response = self.client.post(nominate_url, test_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "info-message-success")

        # check objects
        email = Email.objects.get(address=candidate_email)
        Person.objects.get(name=candidate_name, address=candidate_email)
        nominee = Nominee.objects.get(email=email)
        NomineePosition.objects.get(position=position, nominee=nominee)
        feedback = Feedback.objects.get(positions__in=[position],
                                        nominee=nominee,
                                        type=FeedbackType.objects.get(slug='nomina'),
                                        author="%s%s" % (COMMUNITY_USER, EMAIL_DOMAIN))

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


class NomineePositionStateSaveTest(TestCase):
    """Tests for the NomineePosition save override method"""
    fixtures = ['names', 'nomcom_templates']

    def setUp(self):
        nomcom_test_data()
        self.nominee = Nominee.objects.get(email__person__name=COMMUNITY_USER)

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
                                                          state=NomineePositionState.objects.get(slug='accepted'))
        self.assertEqual(nominee_position.state.slug, 'accepted')

    def test_nomine_position_unique(self):
        """Verify nomine and position are unique together"""
        position = Position.objects.get(name='OAM')
        NomineePosition.objects.create(position=position,
                                       nominee=self.nominee)
        nominee_position = NomineePosition(position=position, nominee=self.nominee)

        self.assertRaises(IntegrityError, nominee_position.save)


class FeedbackTest(TestCase):
    fixtures = ['names', 'nomcom_templates']

    def setUp(self):
        nomcom_test_data()
        self.cert_file, self.privatekey_file = generate_cert()

    def test_encrypted_comments(self):

        nominee = Nominee.objects.get(email__person__name=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')
        nomcom = position.nomcom

        # save the cert file in tmp
        nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        comments = 'plain text'
        feedback = Feedback.objects.create(nomcom=nomcom,
                                           nominee=nominee,
                                           comments=comments,
                                           type=FeedbackType.objects.get(slug='nomina'))
        feedback.positions.add(position)

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        self.assertEqual(check_comments(feedback.comments,
                                        comments,
                                        self.privatekey_file), True)

        os.unlink(self.privatekey_file.name)
        os.unlink(self.cert_file.name)
