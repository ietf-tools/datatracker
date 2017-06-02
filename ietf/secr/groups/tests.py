# -*- coding: utf-8 -*-
from django.urls import reverse
from ietf.utils.test_utils import TestCase
from ietf.group.models import Group
from ietf.secr.groups.forms import get_parent_group_choices
from ietf.group.factories import GroupFactory
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data
import debug                            # pyflakes:ignore

class GroupsTest(TestCase):
    def test_get_parent_group_choices(self):
        make_test_data()
        choices = get_parent_group_choices()
        area = Group.objects.filter(type='area',state='active').first()
        self.assertEqual(choices[0][1][0][0],area.id)

    # ------- Test Search -------- #
    def test_search(self):
        "Test Search"
        make_test_data()
        group = Group.objects.all()[0]
        url = reverse('ietf.secr.groups.views.search')
        post_data = {'group_acronym':group.acronym,'submit':'Search'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        #assert False, response.content
        self.assertEqual(response.status_code, 200)
        self.failUnless(group.acronym in response.content)

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
        self.assertEqual(response.status_code, 200)
        self.failUnless('This field is required' in response.content)

    def test_add_group_dupe(self):
        make_test_data()
        group = Group.objects.all()[0]
        area = Group.objects.filter(type='area')[0]
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
        #print response.content
        self.assertEqual(response.status_code, 200)
        self.failUnless('Group with this Acronym already exists' in response.content)

    def test_add_group_success(self):
        make_test_data()
        area = Group.objects.filter(type='area')[0]
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

    # ------- Test View -------- #
    def test_view(self):
        make_test_data()
        group = Group.objects.all()[0]
        url = reverse('ietf.secr.groups.views.view', kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    # ------- Test Edit -------- #
    def test_edit_valid(self):
        make_test_data()
        group = Group.objects.filter(acronym='mars')[0]
        area = Group.objects.filter(acronym='farfut')[0]
        ad = Person.objects.get(name='Areað Irector')        
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
        self.failUnless('changed successfully' in response.content)

    def test_edit_non_wg_group(self):
        make_test_data()
        parent_sdo = GroupFactory.create(type_id='sdo',state_id='active')
        child_sdo = GroupFactory.create(type_id='sdo',state_id='active',parent=parent_sdo)
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
        self.failUnless('changed successfully' in response.content)

    # ------- Test People -------- #
    def test_people_delete(self):
        make_test_data()
        group = Group.objects.filter(acronym='mars')[0]
        role = group.role_set.all()[0]
        url = reverse('ietf.secr.groups.views.delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('ietf.secr.groups.views.people', kwargs={'acronym':group.acronym})
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.get(url,follow=True)
        self.assertRedirects(response, target)
        self.failUnless('deleted successfully' in response.content)

    def test_people_add(self):
        make_test_data()
        person = Person.objects.get(name='Areað Irector')
        group = Group.objects.filter(acronym='mars')[0]
        url = reverse('ietf.secr.groups.views.people', kwargs={'acronym':group.acronym})
        post_data = {'group_acronym':group.acronym,
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        self.client.login(username="secretary", password="secretary+password")
        response = self.client.post(url,post_data,follow=True)
        self.assertRedirects(response, url)
        self.failUnless('added successfully' in response.content)
