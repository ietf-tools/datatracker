# Copyright The IETF Trust 2022, All Rights Reserved
from django.template.loader import render_to_string

from ietf.person.factories import PersonFactory
from ietf.utils.test_utils import TestCase

from .person_filters import person_link


class PersonLinkTests(TestCase):
    # Tests of the person_link template tag. These assume it is implemented as an
    # inclusion tag.
    def test_person_link(self):
        person = PersonFactory()
        self.assertEqual(
            person_link(person),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'titlepage_name': None,
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
                'titlepage_name': None,
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
                'titlepage_name': None,
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
                'titlepage_name': None,
                'email': person.email_address(),
                'title': '',
                'class': 'some-class',
                'with_email': True,
            }
        )
        self.assertEqual(
            person_link(person, titlepage_name='G. Surname'),
            {
                'name': person.name,
                'plain_name': person.plain_name(),
                'titlepage_name': 'G. Surname',
                'email': person.email_address(),
                'title': '',
                'class': '',
                'with_email': True,
            }
        )

    def test_person_link_renders(self):
        """Verifies person/person_link.html renders context dict values correctly."""
        person = PersonFactory()
        name = person.name
        email = person.email_address()
        base_context = {
            'name': name,
            'plain_name': person.plain_name(),
            'titlepage_name': None,
            'email': email,
            'title': '',
            'class': '',
            'with_email': True,
        }

        # Default: name is used as link text with default title attribute
        html = render_to_string('person/person_link.html', base_context)
        self.assertIn(f'>{name}</a>', html)
        self.assertIn(f'Datatracker profile of {name}', html)
        self.assertIn('bi-envelope', html)

        # titlepage_name overrides name as link text
        html = render_to_string('person/person_link.html', {**base_context, 'titlepage_name': 'G. Surname'})
        self.assertIn('>G. Surname</a>', html)
        self.assertNotIn(f'>{name}</a>', html)

        # with_email=False suppresses the envelope link
        html = render_to_string('person/person_link.html', {**base_context, 'with_email': False})
        self.assertNotIn('bi-envelope', html)

        # Custom title appears in the anchor title attribute
        html = render_to_string('person/person_link.html', {**base_context, 'title': 'Special Title'})
        self.assertIn('title="Special Title"', html)

        # Empty context (None person) renders (None)
        self.assertInHTML(
            '<span class="text-body-secondary">(None)</span>',
            render_to_string('person/person_link.html', {}),
        )

        # System email renders (System)
        self.assertInHTML(
            '<span class="text-body-secondary">(System)</span>',
            render_to_string('person/person_link.html', {'email': 'system@datatracker.ietf.org', 'name': ''}),
        )

    def test_invalid_person(self):
        """Generates correct context dict when input is invalid/missing"""
        self.assertEqual(person_link(None), {})
        self.assertEqual(person_link(''), {})
        self.assertEqual(person_link("** No value found for 'somevar' **"), {})
