# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from ietf.utils.test_utils import TestCase

from ietf.group.models import Group
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data

import debug                            # pyflakes:ignore

SECR_USER='secretary'

def augment_data():
    # need this for the RoleForm intialization
    Group.objects.create(acronym='dummy',name='Dummy Group',type_id='sdo')

class MainTestCase(TestCase):
    def test_main(self):
        "Main Test"
        augment_data()
        url = reverse('roles')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_roles_delete(self):
        make_test_data()
        augment_data()
        group = Group.objects.filter(acronym='mars')[0]
        role = group.role_set.all()[0]
        url = reverse('roles_delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('roles') + '?group=%s' % group.acronym
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url,follow=True)
        self.assertRedirects(response, target)
        self.failUnless('deleted successfully' in response.content)

    def test_roles_add(self):
        make_test_data()
        augment_data()
        person = Person.objects.get(name='Areað Irector')
        group = Group.objects.filter(acronym='mars')[0]
        url = reverse('roles')
        target = reverse('roles') + '?group=%s' % group.acronym
        post_data = {'group_acronym':group.acronym,
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, target)
        self.failUnless('added successfully' in response.content)

