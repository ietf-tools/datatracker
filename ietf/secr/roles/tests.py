from django.core.urlresolvers import reverse
from django.test import TestCase

from ietf.group.models import Group
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data

from pyquery import PyQuery

SECR_USER='secretary'

def augment_data():
        # need this for the RoleForm intialization
        Group.objects.create(acronym='dummy',name='Dummy Group',type_id='sdo')

class MainTestCase(TestCase):
    fixtures = ['names']
                
    def test_main(self):
        "Main Test"
        augment_data()
        url = reverse('roles')
        response = self.client.get(url, REMOTE_USER=SECR_USER)
        self.assertEquals(response.status_code, 200)

    def test_roles_delete(self):
        draft = make_test_data()
        augment_data()
        group = Group.objects.filter(type='wg')[0]
        role = group.role_set.all()[0]
        url = reverse('roles_delete_role', kwargs={'acronym':group.acronym,'id':role.id})
        target = reverse('roles') + '?group=%s' % group.acronym
        response = self.client.get(url,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, target)
        self.failUnless('deleted successfully' in response.content)

    def test_roles_add(self):
        draft = make_test_data()
        augment_data()
        person = Person.objects.get(name='Aread Irector')
        group = Group.objects.filter(type='wg')[0]
        url = reverse('roles')
        target = reverse('roles') + '?group=%s' % group.acronym
        post_data = {'group_acronym':group.acronym,
                     'name':'chair',
                     'person':'Joe Smith - (%s)' % person.id,
                     'email':person.email_set.all()[0].address,
                     'submit':'Add'}
        response = self.client.post(url,post_data,follow=True, REMOTE_USER=SECR_USER)
        self.assertRedirects(response, target)
        self.failUnless('added successfully' in response.content)

