from django.core.urlresolvers import reverse
from django.test import TestCase
from ietf.group.models import Group
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data

SECR_USER='secretary'

class GroupsTest(TestCase):
    fixtures = ['names']
    """
    fixtures = [ 'acronym.json',
                 'area.json',
                 'areadirector',
                 'areagroup.json',
                 'goalmilestone',
                 'iesglogin.json',
                 'ietfwg',
                 'personororginfo.json',
                 'wgchair.json',
                 'wgstatus.json',
                 'wgtype.json' ]
    """
    # ------- Test Search -------- #
    def test_search(self):
        "Test Search"
        draft = make_test_data()
        group = Group.objects.all()[0]
        url = reverse('groups_search')
        post_data = {'group_acronym':group.acronym,'submit':'Search'}
        response = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        #assert False, response.content
        self.assertEquals(response.status_code, 200)
        self.failUnless(group.acronym in response.content)

    # ------- Test Add -------- #
    def test_add_button(self):
        url = reverse('groups_search')
        target = reverse('groups_add')
        post_data = {'submit':'Add'}
        response = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, target)

    def test_add_group_invalid(self):
        url = reverse('groups_add')
        post_data = {'acronym':'test',
                     'type':'wg',
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)
        self.failUnless('This field is required' in response.content)

    def test_add_group_dupe(self):
        draft = make_test_data()
        group = Group.objects.all()[0]
        area = Group.objects.filter(type='area')[0]
        url = reverse('groups_add')
        post_data = {'acronym':group.acronym,
                     'name':'Test Group',
                     'state':'active',
                     'type':'wg',
                     'parent':area.id,
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data, REMOTE_USER=SECR_USER)
        #print response.content
        self.assertEquals(response.status_code, 200)
        self.failUnless('Group with this Acronym already exists' in response.content)

    def test_add_group_success(self):
        draft = make_test_data()
        area = Group.objects.filter(type='area')[0]
        url = reverse('groups_add')
        post_data = {'acronym':'test',
                     'name':'Test Group',
                     'type':'wg',
                     'status':'active',
                     'parent':area.id,
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)

    # ------- Test View -------- #
    def test_view(self):
        draft = make_test_data()
        group = Group.objects.all()[0]
        url = reverse('groups_view', kwargs={'acronym':group.acronym})
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

    # ------- Test Edit -------- #
    def test_edit_valid(self):
        draft = make_test_data()
        group = Group.objects.filter(type='wg')[0]
        area = Group.objects.filter(type='area')[0]
        url = reverse('groups_edit', kwargs={'acronym':group.acronym})
        target = reverse('groups_view', kwargs={'acronym':group.acronym})
        post_data = {'acronym':group.acronym,
                     'name':group.name,
                     'type':'wg',
                     'state':group.state_id,
                     'parent':area.id,
                     'ad':3,
                     'groupurl_set-TOTAL_FORMS':'2',
                     'groupurl_set-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, target)
        self.failUnless('changed successfully' in response.content)

    # ------- Test People -------- #
    def test_people_delete(self):
        draft = make_test_data()
        group = Group.objects.filter(type='wg')[0]
        role = group.role_set.all()[0]
        url = reverse('groups_delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('groups_people', kwargs={'acronym':group.acronym})
        response = self.client.get(url,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, target)
        self.failUnless('deleted successfully' in response.content)

    def test_people_add(self):
        draft = make_test_data()
        person = Person.objects.get(name='Aread Irector')
        group = Group.objects.filter(type='wg')[0]
        url = reverse('groups_people', kwargs={'acronym':group.acronym})
        post_data = {'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        response = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, url)
        self.failUnless('added successfully' in response.content)
