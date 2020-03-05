# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse
from ietf.utils.test_utils import TestCase

from ietf.group.factories import GroupFactory, RoleFactory
from ietf.person.models import Person

import debug                            # pyflakes:ignore

SECR_USER='secretary'

class SecrRolesMainTestCase(TestCase):

    def setUp(self):
        GroupFactory(type_id='sdo') # need this for the RoleForm initialization

    def test_main(self):
        "Main Test"
        url = reverse('ietf.secr.roles.views.main')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_roles_delete(self):
        role = RoleFactory(name_id='chair',group__acronym='mars')
        group = role.group
        id = role.id
        url = reverse('ietf.secr.roles.views.delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('ietf.secr.roles.views.main')
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, target)
        self.assertFalse(group.role_set.filter(id=id))
        
    def test_roles_add(self):
        person = Person.objects.get(name='Areað Irector')
        group = GroupFactory()
        url = reverse('ietf.secr.roles.views.main')
        target = reverse('ietf.secr.roles.views.main') + '?group=%s' % group.acronym
        post_data = {'group_acronym':group.acronym,
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, target)
        self.assertContains(response, 'added successfully')

    def test_roles_add_no_group(self):
        person = Person.objects.get(name='Areað Irector')
        url = reverse('ietf.secr.roles.views.main')
        post_data = {'group_acronym':'',
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You must select a group')
