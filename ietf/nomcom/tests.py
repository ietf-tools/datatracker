import os
import tempfile

from django.conf import settings
from django.test import TestCase
from django.db import IntegrityError
from django.core.urlresolvers import reverse
from django.core.files import File

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.pipe import pipe
from ietf.nomcom.test_data import nomcom_test_data
from ietf.nomcom.models import NomineePosition, Position, Nominee, \
                               NomineePositionState, Feedback, FeedbackType


class NomcomViewsTest(TestCase):
    """Tests to create a new nomcom"""
    fixtures = ['names', 'nomcom_templates']

    def check_url_status(self, url, status):
        response = self.client.get(url)
        self.assertEqual(response.status_code, status)

    def setUp(self):
        nomcom_test_data()
        self.year = 2013

    def test_home_view(self):
        """Verify home view"""
        url = reverse('nomcom_index', kwargs={'year': self.year})
        self.check_url_status(url, 200)

    def test_nominate_view(self):
        """Verify nominate view"""
        url = reverse('nomcom_nominate', kwargs={'year': self.year})
        login_testing_unauthorized(self, 'kaligula', url)
        self.check_url_status(url, 200)

    def test_requirements_view(self):
        """Verify requirements view"""
        url = reverse('nomcom_requirements', kwargs={'year': self.year})
        self.check_url_status(url, 200)

    def test_questionnaires_view(self):
        """Verify questionnaires view"""
        url = reverse('nomcom_questionnaires', kwargs={'year': self.year})
        self.check_url_status(url, 200)

    def test_comments_view(self):
        """Verify comments view"""
        url = reverse('nomcom_comments', kwargs={'year': self.year})
        login_testing_unauthorized(self, 'plain', url)
        self.check_url_status(url, 200)


class NomineePositionStateSaveTest(TestCase):
    """Tests for the NomineePosition save override method"""
    fixtures = ['names', 'nomcom_templates']

    def setUp(self):
        nomcom_test_data()
        self.nominee = Nominee.objects.get(email__address="plain@example.com")

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

        nominee = Nominee.objects.get(email__address="plain@example.com")
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
