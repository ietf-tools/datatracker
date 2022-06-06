# Copyright The IETF Trust 2022, All Rights Reserved
from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase

from .person_filters import person_link


class PersonLinkTests(TestCase):
    # Tests of the person_link template tag. These assume it is implemented as an
    # inclusion tag.
    # TODO test that the template actually renders the data in the dict
    def test_person_link(self):
        person = PersonFactory()
        self.assertEqual(
            person_link(person),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'email': person.email_address(),
                'title': '',
                'class': '',
                'with_email': True,
            }
        )
        self.assertEqual(
            person_link(person, with_email=False),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'email': person.email_address(),
                'title': '',
                'class': '',
                'with_email': False,
            }
        )
        self.assertEqual(
            person_link(person, title='Random Title'),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'email': person.email_address(),
                'title': 'Random Title',
                'class': '',
                'with_email': True,
            }
        )
        self.assertEqual(
            # funny syntax because 'class' is a Python keyword
            person_link(person, **{'class': 'some-class'}),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'email': person.email_address(),
                'title': '',
                'class': 'some-class',
                'with_email': True,
            }
        )

    def test_invalid_person(self):
        """Generates correct context dict when input is invalid/missing"""
        self.assertEqual(person_link(None), {})
        self.assertEqual(person_link(''), {})
        self.assertEqual(person_link("** No value found for 'somevar' **"), {})
