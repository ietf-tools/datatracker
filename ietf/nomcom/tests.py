import os
import tempfile

from django.conf import settings
from django.test import TestCase
from django.db import IntegrityError
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.formtools.preview import security_hash

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.pipe import pipe

from ietf.nomcom.test_data import nomcom_test_data, COMMUNITY_USER, CHAIR_USER, \
                                  MEMBER_USER, SECRETARIAT_USER, EMAIL_DOMAIN
from ietf.nomcom.models import NomineePosition, Position, Nominee, \
                               NomineePositionState, Feedback, FeedbackType
from ietf.nomcom.forms import EditChairForm, EditMembersForm


class NomcomViewsTest(TestCase):
    """Tests to create a new nomcom"""
    fixtures = ['names', 'nomcom_templates']

    def check_url_status(self, url, status):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)

    def setUp(self):
        nomcom_test_data()
        self.year = 2013

        # private urls
        self.private_index_url = reverse('nomcom_private_index', kwargs={'year': self.year})
        self.private_merge_url = reverse('nomcom_private_merge', kwargs={'year': self.year})
        self.edit_members_url = reverse('nomcom_edit_members', kwargs={'year': self.year})
        self.edit_chair_url = reverse('nomcom_edit_chair', kwargs={'year': self.year})
        self.public_key_url = reverse('nomcom_edit_publickey', kwargs={'year': self.year})

        # public urls
        self.index_url = reverse('nomcom_index', kwargs={'year': self.year})
        self.requirements_url = reverse('nomcom_requirements', kwargs={'year': self.year})
        self.questionnaires_url = reverse('nomcom_questionnaires', kwargs={'year': self.year})
        self.comments_url = reverse('nomcom_comments', kwargs={'year': self.year})
        self.nominate_url = reverse('nomcom_nominate', kwargs={'year': self.year})

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
        # TODO: complete merge nominations
        self.access_chair_url(self.private_merge_url)
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
        self.check_url_status(self.public_key_url, 200)

        # revert edit nomcom chair
        login_testing_unauthorized(self, SECRETARIAT_USER, self.edit_chair_url)
        self.change_chair(CHAIR_USER)
        self.client.logout()

    def test_edit_publickey_view(self):
        """Verify edit publickey view"""
        # TODO: complete chage edit public key
        login_testing_unauthorized(self, COMMUNITY_USER, self.public_key_url)
        login_testing_unauthorized(self, CHAIR_USER, self.public_key_url)
        self.check_url_status(self.public_key_url, 200)
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

    def test_comments_view(self):
        """Verify comments view"""
        # TODO: comments view
        login_testing_unauthorized(self, COMMUNITY_USER, self.comments_url)
        self.check_url_status(self.comments_url, 200)
        self.client.logout()

    def test_nominate_view(self):
        """Verify nominate view"""
        # TODO: complete to do a nomination
        login_testing_unauthorized(self, COMMUNITY_USER, self.nominate_url)
        self.check_url_status(self.nominate_url, 200)
        self.client.logout()


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
        self.generate_cert()

    def generate_cert(self):
        """Function to generate cert"""
        config = """
                [ req ]
                distinguished_name = req_distinguished_name
                string_mask        = utf8only
                x509_extensions    = ss_v3_ca

                [ req_distinguished_name ]
                commonName           = Common Name (e.g., NomComYY)
                commonName_default  = NomCom12

                [ ss_v3_ca ]

                subjectKeyIdentifier = hash
                keyUsage = critical, digitalSignature, keyEncipherment, dataEncipherment
                basicConstraints = critical, CA:true
                subjectAltName = email:nomcom12@ietf.org
                extendedKeyUsage= emailProtection"""

        self.config_file = tempfile.NamedTemporaryFile(delete=False)
        self.privatekey_file = tempfile.NamedTemporaryFile(delete=False)
        self.cert_file = tempfile.NamedTemporaryFile(delete=False)

        self.config_file.write(config)
        self.config_file.close()

        command = "%s req -config %s -x509 -new -newkey rsa:2048 -sha256 -days 730 -nodes \
                   -keyout %s -out %s -batch"
        code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                           self.config_file.name,
                                           self.privatekey_file.name,
                                           self.cert_file.name))
        self.privatekey_file.close()
        self.cert_file.close()

    def test_encrypted_comments(self):

        nominee = Nominee.objects.get(email__person__name=COMMUNITY_USER)
        position = Position.objects.get(name='OAM')
        nomcom = position.nomcom

        # save the cert file in tmp
        nomcom.public_key.storage.location = tempfile.gettempdir()
        nomcom.public_key.save('cert', File(open(self.cert_file.name, 'r')))

        comments = 'plain text'
        feedback = Feedback.objects.create(position=position,
                                            nominee=nominee,
                                            comments=comments,
                                            type=FeedbackType.objects.get(slug='nomina'))

        # to check feedback comments are saved like enrypted data
        self.assertNotEqual(feedback.comments, comments)

        encrypted_file = tempfile.NamedTemporaryFile(delete=False)
        encrypted_file.write(feedback.comments)
        encrypted_file.close()

        # to decrypt comments was encryped and check they are equal to the plain comments
        decrypted_file = tempfile.NamedTemporaryFile(delete=False)
        command = "%s smime -decrypt -in %s -out %s -inkey %s"
        code, out, error = pipe(command % (settings.OPENSSL_COMMAND,
                                           encrypted_file.name,
                                           decrypted_file.name,
                                           self.privatekey_file.name))

        decrypted_file.close()
        encrypted_file.close()

        self.assertEqual(open(decrypted_file.name, 'r').read(), comments)

        # delete tmps
        os.unlink(self.config_file.name)
        os.unlink(self.privatekey_file.name)
        os.unlink(self.cert_file.name)
        os.unlink(encrypted_file.name)
        os.unlink(decrypted_file.name)
