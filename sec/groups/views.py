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
    start_date,proposed_date,concluded_date,dormant_date,meeting_scheduled
    '''
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
    ''' 
    Add a new IETF Group..

    **Templates:**

    * ``groups/add.html``

    **Template Variables:**

    * form, awp_formset

    '''
    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups_search')
            return HttpResponseRedirect(url)

        form = GroupModelForm(request.POST)
        awp_formset = AWPFormSet(request.POST, prefix='awp')
        if form.is_valid() and awp_formset.is_valid():
            group = form.save()
            for form in awp_formset.forms:
                awp = form.save(commit=False)
                awp.group = group
                awp.save()

            # create GroupEvent
            if group.state.slug == 'proposed':
                GroupEvent.objects.create(group=group,
                                          type='proposed',
                                          by=request.user.get_profile())
            else:
                GroupEvent.objects.create(group=group,
                                          type='started',
                                          by=request.user.get_profile())
            
            messages.success(request, 'The Group was created successfully!')
            url = reverse('groups_view', kwargs={'name':group.acronym})
            return HttpResponseRedirect(url)
            
    else:
        # display initial form, default to 'PWG' type
        form = GroupModelForm()
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

            messages.success(request, 'The Group Description was changed successfully')
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
    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)

        form = GroupModelForm(request.POST, instance=group)
        awp_formset = AWPFormSet(request.POST, instance=group)
        if form.is_valid() and awp_formset.is_valid():
            
            if form.changed_data:    
                # save group in history
                
                form.save()
                awp_formset.save()
                
                # create GroupEvent
                
                messages.success(request, 'The Group was changed successfully')
            
            url = reverse('groups_view', kwargs={'name':name})
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

def edit_gm(request, name):
    """ 
    Edit IETF Group Goal and Milestone details

    **Templates:**

    * ``groups/edit_gm.html``

    **Template Variables:**

    * group, formset 

    """

    group = get_object_or_404(Group, acronym=name)
    GMFormset = inlineformset_factory(Group, GroupMilestone, form=GroupMilestoneForm, can_delete=True, extra=5)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            url = reverse('sec.groups.views.view', kwargs={'id':id})
            return HttpResponseRedirect(url)

        formset = GMFormset(request.POST, instance=group, prefix='goalmilestone')
        if formset.is_valid():
            formset.save()
            messages.success(request, 'The Goals Milestones were changed successfully')
            url = reverse('groups_view', kwargs={'name':name})
            return HttpResponseRedirect(url)
    else:
        formset = GMFormset(instance=group, prefix='goalmilestone')
        pass
        
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

def people(request, name):
    """ 
    Edit People associated with Groups, Chairs

    **Templates:**

    * ``groups/people.html``

    **Template Variables:**

    * driver, form, group

    """

    group = get_object_or_404(Group, acronym=name)
    
    RoleFormSet = inlineformset_factory(Group, Role, form=RoleForm, extra=2)
    
    if request.method == 'POST':
        formset = RoleFormSet(request.POST,instance=group)
        if formset.is_valid():
            formset.save()

            messages.success(request, 'New %s added successfully!' % type)
            url = reverse('groups_people', kwargs={'name':group.acronym})
            return HttpResponseRedirect(url)
    else:
        formset = RoleFormSet(instance=group)

    return render_to_response('groups/people.html', {
        'formset':formset,
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
            
            # if there's just one result go straight to view
            if len(results) == 1:
                url = reverse('groups_view', kwargs={'name':results[0].acronym})
                return HttpResponseRedirect(url)
            
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

def view_gm(request, name):
    """ 
    View IETF Group Goals and Milestones details

    **Templates:**

    * ``groups/view_gm.html``

    **Template Variables:**

    * group

    """

    group = get_object_or_404(Group, acronym=name)
    #assert False, group.groupmilestone_set.all()

    return render_to_response('groups/view_gm.html', {
        'group': group},
        RequestContext(request, {}),
    )
