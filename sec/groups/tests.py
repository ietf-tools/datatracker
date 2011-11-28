from django.core.urlresolvers import reverse
from django.test import TestCase
from sec.groups.models import *

class GroupsTest(TestCase):
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

    # ------- Test Search -------- #
    def test_search(self):
        "Test Search"
        group = IETFWG.objects.all()[0]
        url = reverse('groups_search')
        post_data = {'group_acronym':group.group_acronym.acronym,'submit':'Search'}
        response = self.client.post(url,post_data,REMOTE_USER='rcross')
        #assert False, response.content
        self.assertEquals(response.status_code, 200)
        self.failUnless(group.group_acronym.name in response.content)

    # ------- Test Add -------- #
    def test_add_button(self):
        url = reverse('groups_search')
        target = reverse('groups_add')
        post_data = {'submit':'Add'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        self.assertRedirects(response, target)

    def test_add_group_invalid(self):
        url = reverse('groups_add')
        post_data = {'group_acronym':'test',
		     'group_type':'2',
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)
        self.failUnless('This field is required' in response.content)
        
    def test_add_group_dupe(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_add')
        post_data = {'group_acronym':group.group_acronym.acronym,
		     'group_type':'2',
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)
        self.failUnless('This acronym already exists' in response.content)

    def test_add_group_success(self):
        url = reverse('groups_add')
        post_data = {'group_acronym':'test',
	             'group_name':'Test Group',
		     'group_type':'2',
		     'status':'1',
		     'primary_area':'934',
		     'primary_area_director':'139',
                     'awp-TOTAL_FORMS':'2',
                     'awp-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)

    # ------- Test View -------- #
    def test_view(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_view', kwargs={'id':group.group_acronym.acronym_id})
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

    # ------- Test Edit -------- #
    def test_edit_valid(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_edit', kwargs={'id':group.group_acronym.acronym_id})
        target = reverse('groups_view', kwargs={'id':group.group_acronym.acronym_id})
        post_data = {'acronym':group.group_acronym.acronym,
	             'name':group.group_acronym.name,
                     'ietfwg-0-group_acronym':group.group_acronym.acronym_id,
		     'ietfwg-0-status':group.status.status_id,
		     'ietfwg-0-group_type':group.group_type.group_type_id,
                     'ietfwg-0-start_date':group.start_date,
		     'ietfwg-0-primary_area':group.area_director.area.area_acronym.acronym_id,
		     'ietfwg-0-area_director':group.area_director.id,
                     'ietfwg-TOTAL_FORMS':'1',
                     'ietfwg-INITIAL_FORMS':'1',
                     'wgawp_set-TOTAL_FORMS':'2',
                     'wgawp_set-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        self.assertRedirects(response, target)
        self.failUnless('changed successfully' in response.content)

    def test_edit_invalid(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_edit', kwargs={'id':group.group_acronym.acronym_id})
        target = reverse('groups_view', kwargs={'id':group.group_acronym.acronym_id})
        post_data = {'acronym':group.group_acronym.acronym,
	             'name':group.group_acronym.name,
                     'ietfwg-0-group_acronym':group.group_acronym.acronym_id,
		     'ietfwg-0-status':group.status.status_id,
		     'ietfwg-0-group_type':group.group_type.group_type_id,
                     'ietfwg-0-start_date':'invalid date',
		     'ietfwg-0-primary_area':group.area_director.area.area_acronym.acronym_id,
		     'ietfwg-0-area_director':group.area_director.id,
                     'ietfwg-TOTAL_FORMS':'1',
                     'ietfwg-INITIAL_FORMS':'1',
                     'wgawp_set-TOTAL_FORMS':'2',
                     'wgawp_set-INITIAL_FORMS':'0',
                     'submit':'Save'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)
        self.failUnless('Enter a valid date' in response.content)

    # ------- Test People -------- #
    def test_people_delete(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_people_delete', kwargs={'id':group.group_acronym.acronym_id})
        target = reverse('groups_people', kwargs={'id':group.group_acronym.acronym_id})
        post_data = {'tag':'104557',
                     'table':'WGChair',
                     'submit':'Delete'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        self.assertRedirects(response, target)
        self.failUnless('deleted successfully' in response.content)

    def test_people_add(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_people', kwargs={'id':group.group_acronym.acronym_id})
        post_data = {'role_type':'WGChair',
                     'role_name':'Jon Peterson - jon.peterson@neustar.biz (104557)',
                     'group':'1744',
                     'submit':'Add'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        #print response.content
        self.assertRedirects(response, url)
        self.failUnless('added successfully' in response.content)
        
    # ------- Test Description -------- #
    def test_description(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_description', kwargs={'id':group.group_acronym.acronym_id})
        response = self.client.get(url,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)
        # must locate actual external group description file to pass this test
        self.failUnless('P2P systems' in response.content)

    # ------- Test Goals and Milestones -------- #
    def test_gm_edit(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_edit_gm', kwargs={'id':group.group_acronym.acronym_id})
        target = reverse('groups_view', kwargs={'id':group.group_acronym.acronym_id})
        post_data = {'goalmilestone-TOTAL_FORMS':'6',
                     'goalmilestone-INITIAL_FORMS':'1',
		     'goalmilestone-0-group_acronym':'1744',
		     'goalmilestone-0-id':'9839',
		     'goalmilestone-0-description':'Working Group Last Call for problem statement',
		     'goalmilestone-0-expected_due_date':'2009-04-30',
		     'goalmilestone-1-group_acronym':'1744',
		     'goalmilestone-1-id':'',
		     'goalmilestone-1-description':'This is a test goal',
		     'goalmilestone-1-expected_due_date':'2010-08-30',
                     'submit':'Save'}
        response = self.client.post(url,post_data,follow=True,REMOTE_USER='rcross')
        self.assertRedirects(response, target)

    def test_gm_view(self):
        group = IETFWG.objects.all()[0]
        url = reverse('groups_view_gm', kwargs={'id':group.group_acronym.acronym_id})
        response = self.client.get(url,REMOTE_USER='rcross')
        self.assertEquals(response.status_code, 200)
        self.failUnless('Working Group Last Call' in response.content)
