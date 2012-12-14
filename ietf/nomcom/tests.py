from django.test import TestCase
from django.db import IntegrityError

from ietf.nomcom.test_data import nomcom_test_data
from ietf.nomcom.models import NomineePosition, Position, Nominee, NomineePositionState


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
