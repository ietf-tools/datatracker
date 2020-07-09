# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse
from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
from ietf.secr.groups.forms import get_parent_group_choices
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory
import debug                            # pyflakes:ignore

class GroupsTest(TestCase):
    def test_get_parent_group_choices(self):
        GroupFactory(type_id='area')
        choices = get_parent_group_choices()
        area = Group.objects.filter(type='area',state='active').first()
        # This is opaque. Can it be rewritten to be more self-documenting?
        self.assertEqual(choices[0][1][0][0],area.id)

    # ------- Test Search -------- #
    def test_search(self):
        "Test Search"
        MeetingFactory(type_id='ietf')
        group = GroupFactory()
        url = reverse('ietf.secr.groups.views.search')
        post_data = {'group_acronym':group.acronym,'submit':'Search'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertContains(response, group.acronym)

    # ------- Test View -------- #
    def test_view(self):
        MeetingFactory(type_id='ietf')
        group = GroupFactory()
        url = reverse('ietf.secr.groups.views.view', kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


    # ------- Test People -------- #
    def test_people_delete(self):
        role = RoleFactory(name_id='member')
        group = role.group
        id = role.id
        url = reverse('ietf.secr.groups.views.delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('ietf.secr.groups.views.people', kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'post':'yes'})
        self.assertRedirects(response, target)
        self.assertFalse(group.role_set.filter(id=id))

    def test_people_add(self):
        person = PersonFactory()
        group = GroupFactory()
        url = reverse('ietf.secr.groups.views.people', kwargs={'acronym':group.acronym})
        post_data = {'group_acronym':group.acronym,
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, url)
        self.assertContains(response, 'added successfully')
