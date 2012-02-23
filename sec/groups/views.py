from django.conf import settings
from django.contrib import messages
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
from ietf.group.models import GroupEvent, GroupURL, Role
from ietf.group.utils import save_group_in_history
from ietf.wginfo.views import fill_in_charter_info

from forms import *

import os
import datetime

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def add_legacy_fields(group):
    '''
    This function takes a Group object as input and adds legacy attributes:
    start_date,proposed_date,concluded_date,meeting_scheduled
    '''
    # it's possible there could be multiple records of a certain type in which case
    # we just return the latest record
    for event in group.groupevent_set.all().order_by('time'):
        if event.type == 'changed_state' and event.desc.startswith('Started'):
            group.start_date = event.time
        if event.type == 'changed_state' and event.desc.startswith('Concluded'):
            group.concluded_date = event.time
        if event.type == 'changed_state' and event.desc.startswith('Proposed'):
            group.proposed_date = event.time
    
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
    ''' 
    Add a new IETF or IRTF Group

    **Templates:**

    * ``groups/add.html``

    **Template Variables:**

    * form, awp_formset

    '''
    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2, can_delete=False)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups')
            return HttpResponseRedirect(url)

        form = GroupModelForm(request.POST)
        awp_formset = AWPFormSet(request.POST, prefix='awp')
        if form.is_valid() and awp_formset.is_valid():
            group = form.save()
            for form in awp_formset.forms:
                awp = form.save(commit=False)
                awp.group = group
                awp.save()

            # create GroupEvent(s)
            # always create started event
            GroupEvent.objects.create(group=group,
                                      type='changed_state',
                                      by=request.user.get_profile(),
                                      desc='Started group')
                                          
            if group.state.slug == 'proposed':
                GroupEvent.objects.create(group=group,
                                          type='changed_state',
                                          by=request.user.get_profile(),
                                          desc='Proposed group')
            
            messages.success(request, 'The Group was created successfully!')
            url = reverse('groups_view', kwargs={'acronym':group.acronym})
            return HttpResponseRedirect(url)
            
    else:
        form = GroupModelForm(initial={'state':'active','type':'wg'})
        awp_formset = AWPFormSet(prefix='awp')

    return render_to_response('groups/add.html', {
        'form': form,
        'awp_formset': awp_formset},
        RequestContext(request, {}),
    )

def delete_role(request, acronym, id):
    """ 
    Handle deleting roles for groups (chair, editor, advisor, secretary)

    **Templates:**

    * none

    Redirects to people page on success.

    """
    group = get_object_or_404(Group, acronym=acronym)
    role = get_object_or_404(Role, id=id)
    
    # save group
    save_group_in_history(group)
                
    role.delete()
    
    messages.success(request, 'The entry was deleted successfully')
    url = reverse('groups_people', kwargs={'acronym':acronym})
    return HttpResponseRedirect(url)

def description(request, acronym):
    """ 
    Edit IETF Group description

    **Templates:**

    * ``groups/description.html``

    **Template Variables:**

    * group, form 

    """

    group = get_object_or_404(Group, acronym=acronym)
    # TODO: does this need to use group.charter.name ???
    filename = os.path.join(settings.GROUP_DESCRIPTION_DIR,group.acronym + '.desc.txt')

    if request.method == 'POST':
        form = DescriptionForm(request.POST) 
        if request.POST['submit'] == "Cancel":
            url = reverse('groups_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
     
        if form.is_valid():
            description = form.cleaned_data['description'] 
            f = open(filename,'w')
            f.write(description)
            f.close()

            messages.success(request, 'The Group Description was changed successfully')
            url = reverse('groups_view', kwargs={'acronym':acronym})
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

def edit(request, acronym):
    """ 
    Edit Group details

    **Templates:**

    * ``groups/edit.html``

    **Template Variables:**

    * group, form, awp_formset

    """

    group = get_object_or_404(Group, acronym=acronym)
    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)

        form = GroupModelForm(request.POST, instance=group)
        awp_formset = AWPFormSet(request.POST, instance=group)
        if form.is_valid() and awp_formset.is_valid():
            
            if form.changed_data:
                state = form.cleaned_data['state']
                
                # save group
                save_group_in_history(group)
                
                form.save()
                awp_formset.save()
                
                # create appropriate GroupEvent
                if 'state' in form.changed_data:
                    if state.slug == 'proposed':
                        GroupEvent.objects.create(group=group,
                                                  type='changed_state',
                                                  by=request.user.get_profile(),
                                                  desc='Proposed group')
                    elif state.slug == 'concluded':
                        GroupEvent.objects.create(group=group,
                                                  type='changed_state',
                                                  by=request.user.get_profile(),
                                                  desc='Concluded group')
                    form.changed_data.remove('state')
                    
                # if anything else was changed
                if form.changed_data:
                    GroupEvent.objects.create(group=group,
                                              type='info_changed',
                                              by=request.user.get_profile())
                
                messages.success(request, 'The Group was changed successfully')
            
            url = reverse('groups_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
            
    else:
        form = GroupModelForm(instance=group)
        awp_formset = AWPFormSet(instance=group)

    return render_to_response('groups/edit.html', {
        'group': group,
        'awp_formset': awp_formset,
        'form': form},
        RequestContext(request, {}),
    )

def edit_gm(request, acronym):
    """ 
    Edit IETF Group Goal and Milestone details

    **Templates:**

    * ``groups/edit_gm.html``

    **Template Variables:**

    * group, formset 

    """

    group = get_object_or_404(Group, acronym=acronym)
    GMFormset = inlineformset_factory(Group, GroupMilestone, form=GroupMilestoneForm, can_delete=True, extra=5)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)

        formset = GMFormset(request.POST, instance=group, prefix='goalmilestone')
        if formset.is_valid():
            formset.save()
            messages.success(request, 'The Goals Milestones were changed successfully')
            url = reverse('groups_view', kwargs={'acronym':acronym})
            return HttpResponseRedirect(url)
    else:
        formset = GMFormset(instance=group, prefix='goalmilestone')
        
    return render_to_response('groups/edit_gm.html', {
        'group': group,
        'formset': formset},
        RequestContext(request, {}),
    )

def people(request, acronym):
    """ 
    Edit Group Roles (Chairs, Secretary, etc)

    **Templates:**

    * ``groups/people.html``

    **Template Variables:**

    * form, group

    """

    group = get_object_or_404(Group, acronym=acronym)
    
    if request.method == 'POST':
        # we need to pass group for form validation
        form = RoleForm(request.POST,group=group)
        if form.is_valid():
            name = form.cleaned_data['name']
            person = form.cleaned_data['person']
            email = form.cleaned_data['email']
            
            # save group
            save_group_in_history(group)
                
            Role.objects.create(name=name,
                                person=person,
                                email=email,
                                group=group)

            messages.success(request, 'New %s added successfully!' % name)
            url = reverse('groups_people', kwargs={'acronym':group.acronym})
            return HttpResponseRedirect(url)
    else:
        form = RoleForm(initial={'name':'chair'},group=group)

    return render_to_response('groups/people.html', {
        'form':form,
        'group':group},
        RequestContext(request, {}),
    )

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
                kwargs['parent'] = primary_area
            if state:
                kwargs['state'] = state
            if type:
                kwargs['type'] = type
            else:
                #kwargs['type__in'] = ['wg','ag','team']
                kwargs['type__in'] = ['wg','rg']
            
            if meeting_scheduled == 'YES':
                kwargs['session__meeting__number'] = CURRENT_MEETING.number
            # perform query
            if kwargs:
                if meeting_scheduled == 'NO':
                    qs = Group.objects.filter(**kwargs).exclude(session__meeting__number=CURRENT_MEETING.number).distinct()
                else:
                    qs = Group.objects.filter(**kwargs).distinct()
            else:
                qs = Group.objects.all()
            results = qs.order_by('acronym')
            
            # if there's just one result go straight to view
            if len(results) == 1:
                url = reverse('groups_view', kwargs={'acronym':results[0].acronym})
                return HttpResponseRedirect(url)
            
    # process GET argument to support link from area app 
    elif 'primary_area' in request.GET:
        area = request.GET.get('primary_area','')
        results = Group.objects.filter(parent__id=area,type='wg',state__in=('bof','active','proposed')).order_by('name')
        form = SearchForm({'primary_area':area,'state':'','type':'wg'})
    else:
        form = SearchForm(initial={'state':'active','type':'wg'})

    # loop through results and tack on meeting_scheduled because it is no longer an
    # attribute of the meeting model
    for result in results:
        add_legacy_fields(result)
            
    return render_to_response('groups/search.html', {
        'results': results,
        'form': form},
        RequestContext(request, {}),
    )

def view(request, acronym):
    """ 
    View IETF Group details

    **Templates:**

    * ``groups/view.html``

    **Template Variables:**

    * group

    """

    group = get_object_or_404(Group, acronym=acronym)
    
    add_legacy_fields(group)
    
    return render_to_response('groups/view.html', {
        'group': group},
        RequestContext(request, {}),
    )

def view_gm(request, acronym):
    """ 
    View IETF Group Goals and Milestones details

    **Templates:**

    * ``groups/view_gm.html``

    **Template Variables:**

    * group

    """

    group = get_object_or_404(Group, acronym=acronym)

    return render_to_response('groups/view_gm.html', {
        'group': group},
        RequestContext(request, {}),
    )
