from django.conf import settings
#from django.contrib import messages
from session_messages import create_message
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.core.exceptions import ObjectDoesNotExist
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson

from sec.utils.meeting import CURRENT_MEETING
from redesign.group.models import GroupEvent, GroupURL
from ietf.wginfo.views import fill_in_charter_info

from forms import *

import os
import datetime

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def add_legacy_fields(group):
    """
    This function takes a Group object as input and adds legacy attributes:
    start_date,proposed_date,concluded_date,dormant_date,meeting_scheduled
    """
    for event in group.groupevent_set.all():
        if event.type == 'started':
            group.start_date = event.time
        if event.type == 'concluded':
            group.concluded_date = event.time
        if event.type == 'proposed':
            group.proposed_date = event.time
        if event.type == 'dormant':
            group.dormant_date = event.time
    
    if group.session_set.filter(meeting__number=CURRENT_MEETING.number):
        group.meeting_scheduled = 'YES'
    else:
        group.meeting_scheduled = 'NO'
        
    # add roles
    fill_in_charter_info(group)
# -------------------------------------------------
# AJAX Functions
# -------------------------------------------------
'''
def get_ads(request):
    """ AJAX function which takes a URL parameter, "area" and returns the area directors
    in the form of a list of dictionaries with "id" and "value" keys(in json format).  
    Used to populate select options. 
    """

    results=[]
    area = request.GET.get('area','')
    qs = AreaDirector.objects.filter(area=area)
    for item in qs:
        d = {'id': item.id, 'value': item.person.first_name + ' ' + item.person.last_name}
        results.append(d)

    return HttpResponse(simplejson.dumps(results), mimetype='application/javascript')
'''
# -------------------------------------------------
# Standard View Functions
# -------------------------------------------------

def add(request):
    """ 
    Add a new IETF Group..

    **Templates:**

    * ``groups/add.html``

    **Template Variables:**

    * form, awp_formset

    """
    pass
'''    
    AWPFormSet = formset_factory(AWPAddForm, extra=2)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sec.groups.views.search')
            return HttpResponseRedirect(url)

        form = NewGroupForm(request.POST)
        awp_formset = AWPFormSet(request.POST, prefix='awp')
        if form.is_valid():
            # get form data
            acronym = form.cleaned_data['group_acronym']
            name = form.cleaned_data['group_name']
            type = form.cleaned_data['group_type']
            status = form.cleaned_data['status']
            area = form.cleaned_data['primary_area']
            area_director = form.cleaned_data['primary_area_director']
            # convert IDs to objects
            status_obj = WGStatus.objects.get(status_id=status)
            type_obj = WGType.objects.get(group_type_id=type)
            area_director_obj = AreaDirector.objects.get(id=area_director)
            area_obj = Area.objects.get(area_acronym=area)
            # save new Acronym 
            acronym_obj = Acronym(acronym=acronym,name=name)
            acronym_obj.save()
            # save new Group 
            pdate = form.cleaned_data['proposed_date']
            if type == '2' and not pdate:
                pdate = datetime.date.today().isoformat() 
            group_obj = IETFWG(
                group_acronym = acronym_obj,
                group_type = type_obj,
                status = status_obj,
		proposed_date = pdate,
		area_director = area_director_obj,
		meeting_scheduled = form.cleaned_data['meeting_scheduled'],
		email_address = form.cleaned_data['email_address'],
		email_subscribe = form.cleaned_data['email_subscribe'],
		email_keyword = form.cleaned_data['email_keyword'],
		email_archive = form.cleaned_data['email_archive'],
		comments = form.cleaned_data['comments'])
            group_obj.save()
            # create AreaGroup record
            area_group_obj = AreaGroup(group=group_obj,area=area_obj)
            area_group_obj.save()
            # save Additional Web Pages
            for item in awp_formset.cleaned_data:
                if item.get('url', 0):
                    awp_obj = WGAWP(name=acronym_obj,url=item['url'],description=item['description'])
                    awp_obj.save()

            messages.success(request, 'The Group was created successfully!')
            url = reverse('sec.groups.views.view', kwargs={'id':group_obj.group_acronym.acronym_id})
            return HttpResponseRedirect(url)

        else:
            # if primary area director was selected we need special logic to retain when displaying errors
            # we first need to check that 'primary_area_director' is in the posted data, if nothing was
            # selected it won't be there
            if 'primary_area_director' in request.POST:
		ad = request.POST['primary_area_director']
		area = request.POST['primary_area']
		ad_choices = [(ad.id, ad.person.first_name + ' ' + ad.person.last_name) for ad in AreaDirector.objects.filter(area=area)]
		form.fields['primary_area_director'].widget.choices = ad_choices
		form.fields['primary_area_director'].initial = ad
                
    else:
        # display initial form, default to 'PWG' type
        form = NewGroupForm(initial={'group_type': 2})
        awp_formset = AWPFormSet(prefix='awp')

    return render_to_response('groups/add.html', {
        'form': form,
        'awp_formset': awp_formset},
        RequestContext(request, {}),
    )

def delete(request, id):
    """ 
    Handle deleting roles for groups (chair, editor, advisor, secretary)

    **Templates:**

    * none

    Redirects to people page on success.

    """

    group = get_object_or_404(IETFWG, group_acronym=id)

    if request.method == 'POST':
        # delete a role
        if request.POST.get('submit', '') == "Delete":
            table = request.POST.get('table', '')
            tag = request.POST.get('tag', '')
            obj = get_model('core',table)
            instance = obj.objects.get(person=tag,group_acronym=group.group_acronym)
            instance.delete()
            messages.success(request, 'The entry was deleted successfully')

    url = reverse('sec.groups.views.people', kwargs={'id':id})
    return HttpResponseRedirect(url)

'''
def description(request, name):
    """ 
    Edit IETF Group description

    **Templates:**

    * ``groups/description.html``

    **Template Variables:**

    * group, form 

    """

    group = get_object_or_404(Group, acronym=name)
    # TODO: does this need to use group.charter.name ???
    filename = os.path.join(settings.GROUP_DESCRIPTION_DIR,group.acronym + '.desc.txt')

    if request.method == 'POST':
        form = DescriptionForm(request.POST) 
        if request.POST['submit'] == "Cancel":
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)
     
        if form.is_valid():
            description = form.cleaned_data['description'] 
            try:
                f = open(filename,'w')
                f.write(description)
                f.close()
            except IOError, e:
                return render_to_response('groups/error.html', { 'error': e},) 

            create_message(request, 'The Group Description was changed successfully')
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)
    else:
        if os.path.isfile(filename):
            f = open(filename,'r')
            value = f.read()
            f.close()
        else:
            value = 'Description file not found: %s.\nType new description here.' % filename 

        data = { 'description': value }
        form = DescriptionForm(data)

    return render_to_response('groups/description.html', {
        'group': group,
        'form': form},
        RequestContext(request, {}),
    )

def edit(request, name):
    """ 
    Edit IETF Group details

    **Templates:**

    * ``groups/edit.html``

    **Template Variables:**

    * form, awp_formset

    """

    group = get_object_or_404(Group, acronym=name)

    #GroupFormset = inlineformset_factory(Acronym, IETFWG, form=EditForm, can_delete=False, extra=0)
    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)

        form = GroupModelForm(request.POST, instance=acronym)
        awp_formset = AWPFormSet(request.POST, instance=acronym)
        if form.is_valid() and awp_formset.is_valid():
            form.save()
            awp_formset.save()
            # if the area was changed we need to change the AreaGroup record
            if 'primary_area' in group_formset.forms[0].changed_data:
                area = Area.objects.get(area_acronym=group_formset.forms[0].cleaned_data.get('primary_area'))
                obj, created = AreaGroup.objects.get_or_create(group=group,defaults={'area':area})
                if not created:
                    obj.area = area
                    obj.save()
            create_message(request, 'The Group was changed successfully')
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)
        else:
            # reset ad options based on submitted primary area
            primary_area = request.POST.get('ietfwg-0-primary_area','')
            if primary_area:
                group_formset.forms[0].fields['area_director'].choices = [(ad.id, "%s %s" % (ad.person.first_name, ad.person.last_name)) for ad in AreaDirector.objects.filter(area=primary_area)]
            
    else:
        #acronym_form = AcronymForm(instance=acronym)
        #group_formset = GroupFormset(instance=acronym)
        form = GroupModelForm(instance=group)
        awp_formset = AWPFormSet(instance=group)
        # preset extra field primary_area 
        
        # some groups, mostly concluded ones, are not associated with an area via the areagroup
        # table.  In this case add blank option to primary area
        area = group.parent
        if area == None:
            forms.fields['primary_area'].widget.choices = SEARCH_AREA_CHOICES
        else:
            #form.initial['primary_area']=group.parent.acronym
            form.fields['ad'].choices = [(ad.id, ad.name) for ad in group.parent.role_set.filter(name__name="Area Director")]

    return render_to_response('groups/edit.html', {
        'group': group,
        'awp_formset': awp_formset,
        'form': form},
        RequestContext(request, {}),
    )
'''
def edit_gm(request, id):
    """ 
    Edit IETF Group Goal and Milestone details

    **Templates:**

    * ``groups/edit_gm.html``

    **Template Variables:**

    * group, formset 

    """

    group = get_object_or_404(IETFWG, group_acronym=id)
    GMFormset = inlineformset_factory(IETFWG, GoalMilestone, form=GoalMilestoneForm, can_delete=True, extra=5)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sec.groups.views.view', kwargs={'id':id})
            return HttpResponseRedirect(url)

        formset = GMFormset(request.POST, instance=group, prefix='goalmilestone')
        if formset.is_valid():
            formset.save()
            messages.success(request, 'The Goals Milestones were changed successfully')
            url = reverse('sec.groups.views.view', kwargs={'id':id})
            return HttpResponseRedirect(url)
    else:
        formset = GMFormset(instance=group, prefix='goalmilestone')

    return render_to_response('groups/edit_gm.html', {
        'group': group,
        'formset': formset},
        RequestContext(request, {}),
    )

def grouplist(request, id):
    """ 
    List IETF Groups, id=group acronym 

    **Templates:**

    * ``groups/list.html``

    **Template Variables:**

    * groups 

    """

    groups = IETFWG.objects.filter(group_acronym__acronym_id=id)

    return render_to_response('groups/list.html', {
        'groups': groups},
        RequestContext(request, {}),
    )

def people(request, id):
    """ 
    Edit People associated with Groups, Chairs

    **Templates:**

    * ``groups/people.html``

    **Template Variables:**

    * driver, form, group

    """

    group = get_object_or_404(IETFWG, group_acronym=id)
    # dictionaries to produce template forms
    driver = [
        {'title':'Chairperson(s)','data':group.wgchair_set.all(),'table':'WGChair'},
        {'title':'Document Editor(s)','data':group.wgeditor_set.all(),'table':'WGEditor'},
        {'title':'Technical Advisor(s)','data':group.wgtechadvisor_set.all(),'table':'WGTechAdvisor'},
        {'title':'Secretary(ies)','data':group.wgsecretary_set.all(),'table':'WGSecretary'}]

    if request.method == 'POST':
        # handle adding a new role 
        if request.POST.get('submit', '') == "Add":
            form = GroupRoleForm(request.POST)
            if form.is_valid():
                name = request.POST.get('role_name', '')
                type = request.POST.get('role_type', '')
                person = get_person(name)
                # make sure ad entry doesn't already exist

                # because the various roles all have the same fields to initialize
                # we can use a generic object create call here
                role_model = get_model('core', type)
                obj = role_model(person=person, group_acronym=group)
                obj.save()

                messages.success(request, 'New %s added successfully!' % type)
                url = reverse('sec.groups.views.people', kwargs={'id':str(group.group_acronym.acronym_id)})
                return HttpResponseRedirect(url)
    else:
        # set hidden group field so we have this info for form validations
        form = GroupRoleForm(initial={'group':id})

    return render_to_response('groups/people.html', {
        'driver': driver,
        'group': group,
        'form': form},
        RequestContext(request, {}),
    )

'''
def search(request):
    """ 
    Search IETF Groups

    **Templates:**

    * ``groups/search.html``

    **Template Variables:**

    * form, results

    """
    results = []
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if request.POST['submit'] == 'Add':
            url = reverse('groups_add')
            return HttpResponseRedirect(url)
        
        if form.is_valid():
            kwargs = {} 
            group_acronym = form.cleaned_data['group_acronym']
            group_name = form.cleaned_data['group_name']
            primary_area = form.cleaned_data['primary_area']
            meeting_scheduled = form.cleaned_data['meeting_scheduled']
            state = form.cleaned_data['state']
            type = form.cleaned_data['type'] 
            # construct seach query
            if group_acronym:
                kwargs['acronym__istartswith'] = group_acronym
            if group_name:
                kwargs['name__istartswith'] = group_name
            if primary_area:
                kwargs['parent__acronym'] = primary_area
            if state:
                kwargs['state'] = state
            if type:
                kwargs['type'] = type
            else:
                kwargs['type__in'] = ['wg','ag','team']
            if meeting_scheduled == 'YES':
                kwargs['session__meeting__number'] = CURRENT_MEETING.number
            # perform query
            if kwargs:
                if meeting_scheduled == "NO":
                    qs = Group.objects.filter(**kwargs).exclude(session__meeting__number=CURRENT_MEETING.number)
                else:
                    qs = Group.objects.filter(**kwargs)
            else:
                qs = Group.objects.all()
            results = qs.order_by('acronym')
    # define GET argument to support link from area app 
    elif 'primary_area' in request.GET:
        area = request.GET.get('primary_area','')
        results = Group.objects.filter(parent__acronym=area,state='active').order_by('name')
        form = SearchForm({'primary_area':area})
    else:
        # have status default to active
        form = SearchForm(initial={'state':'active'})

    # loop through results and tack on meeting_scheduled because it is no longer an
    # attribute of the meeting model
    for result in results:
        add_legacy_fields(result)
            
    return render_to_response('groups/search.html', {
        'results': results,
        'form': form},
        RequestContext(request, {}),
    )

def view(request, name):
    """ 
    View IETF Group details

    **Templates:**

    * ``groups/view.html``

    **Template Variables:**

    * group

    """

    group = get_object_or_404(Group, acronym=name)
    
    # add on legacy fields
    add_legacy_fields(group)
    
    return render_to_response('groups/view.html', {
        'group': group},
        RequestContext(request, {}),
    )
'''

def view_gm(request, id):
    """ 
    View IETF Group Goals and Milestones details

    **Templates:**

    * ``groups/view_gm.html``

    **Template Variables:**

    * group

    """

    group = get_object_or_404(IETFWG, group_acronym=id)

    return render_to_response('groups/view_gm.html', {
        'group': group},
        RequestContext(request, {}),
    )
'''
