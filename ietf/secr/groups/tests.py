# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.urls import reverse
from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
from ietf.secr.groups.forms import get_parent_group_choices
from ietf.group.factories import GroupFactory, RoleFactory
from ietf.meeting.factories import MeetingFactory
from ietf.person.factories import PersonFactory
from ietf.person.models import Person
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

    # ------- Test Add -------- #
    def test_add_button(self):
        url = reverse('ietf.secr.groups.views.search')
        target = reverse('ietf.secr.groups.views.add')
        post_data = {'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, target)

    def test_add_group_invalid(self):
        url = reverse('ietf.secr.groups.views.add')
        post_data = {'acronym':'test',
                     'type':'wg',
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertContains(response, 'This field is required')

    def test_add_group_dupe(self):
        group = GroupFactory()
        area = GroupFactory(type_id='area')
        url = reverse('ietf.secr.groups.views.add')
        post_data = {'acronym':group.acronym,
                     'name':'Test Group',
                     'state':'active',
                     'type':'wg',
                     'parent':area.id,
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertContains(response, 'Group with this Acronym already exists')

    def test_add_group_success(self):
        area = GroupFactory(type_id='area')
        url = reverse('ietf.secr.groups.views.add')
        post_data = {'acronym':'test',
                     'name':'Test Group',
                     'type':'wg',
                     'status':'active',
                     'parent':area.id,
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertEqual(response.status_code, 200)

    def test_add_group_capital_acronym(self):
        area = GroupFactory(type_id='area')
        url = reverse('ietf.secr.groups.views.add')
        post_data = {'acronym':'TEST',
                     'name':'Test Group',
                     'type':'wg',
                     'status':'active',
                     'parent':area.id,
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Capital letters not allowed in group acronym')

    # ------- Test View -------- #
    def test_view(self):
        MeetingFactory(type_id='ietf')
        group = GroupFactory()
        url = reverse('ietf.secr.groups.views.view', kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ------- Test Edit -------- #
    def test_edit_valid(self):
        group = GroupFactory()
        area = GroupFactory(type_id='area')
        ad = Person.objects.get(name='Areað Irector')
        MeetingFactory(type_id='ietf')        
        url = reverse('ietf.secr.groups.views.edit', kwargs={'acronym':group.acronym})
        target = reverse('ietf.secr.groups.views.view', kwargs={'acronym':group.acronym})
        post_data = {'acronym':group.acronym,
                     'name':group.name,
                     'type':'wg',
                     'state':group.state_id,
                     'parent':area.id,
                     'ad':ad.id,
                     'groupurl_set-TOTAL_FORMS':'2',
                     'groupurl_set-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, target)
        self.assertContains(response, 'changed successfully')

    def test_edit_non_wg_group(self):
        parent_sdo = GroupFactory.create(type_id='sdo',state_id='active')
        child_sdo = GroupFactory.create(type_id='sdo',state_id='active',parent=parent_sdo)
        MeetingFactory(type_id='ietf')
        url = reverse('ietf.secr.groups.views.edit', kwargs={'acronym':child_sdo.acronym})
        target = reverse('ietf.secr.groups.views.view', kwargs={'acronym':child_sdo.acronym})
        post_data = {'acronym':child_sdo.acronym,
                     'name':'New Name',
                     'type':'sdo',
                     'state':child_sdo.state_id,
                     'parent':parent_sdo.id,
                     'ad':'',
                     'groupurl_set-TOTAL_FORMS':'2',
                     'groupurl_set-INITIAL_FORMS':'0',
                     'submit':'Save'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, target)
        self.assertContains(response, 'changed successfully')

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
