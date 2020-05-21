from django.urls import reverse

import debug                            # pyflakes:ignore

from ietf.utils.test_utils import TestCase
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.person.factories import PersonFactory, UserFactory
from ietf.person.models import Person, User

SECR_USER='secretary'

class RolodexTestCase(TestCase):
    def test_main(self):
        "Main Test"
        url = reverse('ietf.secr.rolodex.views.search')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_view(self):
        "View Test"
        person = PersonFactory()
        url = reverse('ietf.secr.rolodex.views.view', kwargs={'id':person.id})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add(self):
        url = reverse('ietf.secr.rolodex.views.add')
        add_proceed_url = reverse('ietf.secr.rolodex.views.add_proceed') + '?name=Joe+Smith'
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'name':'Joe Smith'})
        self.assertRedirects(response, add_proceed_url)
        post_data = {
            'name': 'Joe Smith',
            'ascii': 'Joe Smith',
            'ascii_short': 'Joe S',
            'affiliation': 'IETF',
            'email': 'joes@example.com',
            'submit': 'Submit',
        }
        response = self.client.post(add_proceed_url, post_data)
        person = Person.objects.get(name='Joe Smith')
        view_url = reverse('ietf.secr.rolodex.views.view', kwargs={'id':person.pk})
        self.assertRedirects(response, view_url)

    def test_edit_replace_user(self):
        person = PersonFactory()
        email = person.email()
        user = UserFactory()
        group = GroupFactory(type_id='wg')
        role = RoleFactory(group=group,name_id='chair',person=person)
        url = reverse('ietf.secr.rolodex.views.edit', kwargs={'id':person.id})
        redirect_url = reverse('ietf.secr.rolodex.views.view', kwargs={'id':person.id})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        #debug.show('unicontent(response)')
        self.assertEqual(response.status_code, 200)
        post_data = {
            'name': person.name,
            'ascii': person.ascii,
            'ascii_short': person.ascii_short,
            'user': user.username,
            'email-0-person':person.pk,
            'email-0-address': email.address,
            'email-0-origin': email.origin,
            'email-1-person':person.pk,
            'email-1-address': 'name@example.com',
            'email-1-origin': 'role: %s %s' % (group.acronym, role.name.slug),
            'email-TOTAL_FORMS':2,
            'email-INITIAL_FORMS':1,
            'email-MIN_NUM_FORMS':0,
            'email-MAX_NUM_FORMS':1000,
            'submit': 'Submit',
        }
        original_user = person.user
        person_id = person.pk
        response = self.client.post(url, post_data, follow=True)
        person = Person.objects.get(id=person_id)
        original_user = User.objects.get(id=original_user.id)
        self.assertRedirects(response, redirect_url)
        self.assertEqual(person.user, user)
        self.assertTrue(not original_user.is_active)
