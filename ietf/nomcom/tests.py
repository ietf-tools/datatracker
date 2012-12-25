from django.test import TestCase
from django.db import IntegrityError
from django.core.urlresolvers import reverse

from ietf.utils.test_utils import login_testing_unauthorized
from ietf.nomcom.test_data import nomcom_test_data
from ietf.nomcom.models import NomineePosition, Position, Nominee, NomineePositionState


class NomcomTest(TestCase):
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
