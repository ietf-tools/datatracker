from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson

from ietf.group.models import Group, GroupEvent, GroupURL, Role
from ietf.group.utils import save_group_in_history
from ietf.name.models import RoleName
from ietf.person.models import Person, Email
from forms import *

import re
 
# --------------------------------------------------
# AJAX FUNCTIONS
# --------------------------------------------------
def getpeople(request):
    """
    Ajax function to find people.  Takes one or two terms (ignores rest) and
    returns JSON format response: first name, last name, primary email, tag
    """
    result = []
    term = request.GET.get('term','')

    qs = Person.objects.filter(name__icontains=term)
    for item in qs:
        full = '%s - (%s)' % (item.name,item.id)
        result.append(full)
        
    return HttpResponse(simplejson.dumps(result), mimetype='application/javascript')
    
def getemails(request):
    """
    Ajax function to get emails for given Person Id.  Used for adding Area ADs.
    returns JSON format response: [{id:email, value:email},...]
    """
    
    results=[]
    id = request.GET.get('id','')
    person = Person.objects.get(id=id)
    for item in person.email_set.filter(active=True):
        d = {'id': item.address, 'value': item.address}
        results.append(d)
        
    return HttpResponse(simplejson.dumps(results), mimetype='application/javascript')
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------

def add(request):
    """ 
    Add a new IETF Area

    **Templates:**

    * ``areas/add.html``

    **Template Variables:**

    * area_form

    """
    AWPFormSet = formset_factory(AWPAddModelForm, extra=2)
    if request.method == 'POST':
        area_form = AddAreaModelForm(request.POST)
        awp_formset = AWPFormSet(request.POST, prefix='awp')
        if area_form.is_valid() and awp_formset.is_valid():
            area = area_form.save()
            
            #save groupevent 'started' record
            start_date = area_form.cleaned_data.get('start_date')
            login = request.user.get_profile()
            group_event = GroupEvent(group=area,time=start_date,type='started',by=login)
            group_event.save()
            
            # save AWPs
            for item in awp_formset.cleaned_data:
                if item.get('url', 0):
                    group_url = GroupURL(group=area,name=item['name'],url=item['url'])
                    group_url.save()

            messages.success(request, 'The Area was created successfully!')
            url = reverse('areas')
            return HttpResponseRedirect(url)
    else:
        # display initial forms
        area_form = AddAreaModelForm()
        awp_formset = AWPFormSet(prefix='awp')

    return render_to_response('areas/add.html', {
        'area_form': area_form,
        'awp_formset': awp_formset},
        RequestContext(request, {}),
    )

def edit(request, name):
    """ 
    Edit IETF Areas 

    **Templates:**

    * ``areas/edit.html``

    **Template Variables:**

    * acronym, area_formset, awp_formset, acronym_form 

    """
    area = get_object_or_404(Group, acronym=name, type='area')

    AWPFormSet = inlineformset_factory(Group, GroupURL, form=AWPForm, max_num=2)
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Save':
            form = AreaForm(request.POST, instance=area)
            awp_formset = AWPFormSet(request.POST, instance=area)
            if form.is_valid() and awp_formset.is_valid():
                state = form.cleaned_data['state']
                
                # save group
                save_group_in_history(area)
                
                new_area = form.save()
                new_area.time = datetime.datetime.now()
                new_area.save()
                awp_formset.save()
                
                # create appropriate GroupEvent
                if 'state' in form.changed_data:
                    ChangeStateGroupEvent.objects.create(group=new_area,
                                                         type='changed_state',
                                                         by=request.user.get_profile(),
                                                         state=state,
                                                         time=new_area.time)
                    form.changed_data.remove('state')
                    
                # if anything else was changed
                if form.changed_data:
                    GroupEvent.objects.create(group=new_area,
                                              type='info_changed',
                                              by=request.user.get_profile(),
                                              time=new_area.time)
                
                messages.success(request, 'The Area entry was changed successfully')
                url = reverse('areas_view', kwargs={'name':name})
                return HttpResponseRedirect(url)
        else:
            url = reverse('areas_view', kwargs={'name':name})
            return HttpResponseRedirect(url)
    else:
        form = AreaForm(instance=area)
        awp_formset = AWPFormSet(instance=area)

    return render_to_response('areas/edit.html', {
        'area': area,
        'form': form,
        'awp_formset': awp_formset,
        },
        RequestContext(request,{}),
    )

def list_areas(request):
    """ 
    List IETF Areas 

    **Templates:**

    * ``areas/list.html``

    **Template Variables:**

    * results 

    """

    results = Group.objects.filter(type="area").order_by('name')
    
    return render_to_response('areas/list.html', {
        'results': results},
        RequestContext(request, {}),
    )

def people(request, name):
    """ 
    Edit People associated with Areas, Area Directors.
    
    # Legacy ------------------
    When a new Director is first added they get a user_level of 4, read-only.
    Then, when Director is made active (Enable Voting) user_level = 1.
    
    # New ---------------------
    First Director's are assigned the Role 'pre-ad' Incoming Area director
    Then they get 'ad' role
    
    **Templates:**

    * ``areas/people.html``

    **Template Variables:**

    * directors, area

    """
    area = get_object_or_404(Group, type='area', acronym=name)

    if request.method == 'POST':
        if request.POST.get('submit', '') == "Add":
            form = AreaDirectorForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                person = form.cleaned_data['ad_name']

                # save group
                save_group_in_history(area)
                
                # create role
                Role.objects.create(name_id='pre-ad',group=area,email=email,person=person)
                
                messages.success(request, 'New Area Director added successfully!')
                url = reverse('areas_view', kwargs={'name':name})
                return HttpResponseRedirect(url)
    else:
        form = AreaDirectorForm()

    directors = area.role_set.filter(name__slug__in=('ad','pre-ad'))
    return render_to_response('areas/people.html', {
        'area': area,
        'form': form,
        'directors': directors},
        RequestContext(request, {}),
    )

def modify(request, name):
    """ 
    Handle state changes of Area Directors (enable voting, retire)
    # Legacy --------------------------
    Enable Voting actions
    - user_level = 1
    - create TelechatUser object
    Per requirements, the Retire button shall perform the following DB updates
    - update iesg_login row, user_level = 2 (per Matt Feb 7, 2011)
    - remove telechat_user row (to revoke voting rights)
    - update IETFWG(groups) set area_director = TBD 
    - remove area_director row
    # New ------------------------------
    Enable Voting: change Role from 'pre-ad' to 'ad'
    Retire: save in history, delete role record, set group assn to TBD

    **Templates:**

    * none

    Redirects to view page on success.
    """

    area = get_object_or_404(Group, type='area', acronym=name)

    # should only get here with POST method
    if request.method == 'POST':
        # setup common request variables
        tag = request.POST.get('tag', '')
        person = Person.objects.get(id=tag)
        
        # save group
        save_group_in_history(area)
                
        # handle retire request
        if request.POST.get('submit', '') == "Retire":
            role = Role.objects.get(group=area,name__in=('ad','pre-ad'),person=person)
            role.delete()
            
            # update groups that have this AD as primary AD
            for group in Group.objects.filter(ad=person,type='wg',state__in=('active','bof')):
                group.ad = None
                group.save()
            
            messages.success(request, 'The Area Director has been retired successfully!')

        # handle voting request
        if request.POST.get('submit', '') == "Enable Voting":
            role = Role.objects.get(group=area,name__slug='pre-ad',person=person)
            role.name_id = 'ad'
            role.save()
            
            messages.success(request, 'Voting rights have been granted successfully!')

        url = reverse('areas_view', kwargs={'name':name})
        return HttpResponseRedirect(url)

def view(request, name):
    """ 
    View Area information.

    **Templates:**

    * ``areas/view.html``

    **Template Variables:**

    * area, directors

    """
    area = get_object_or_404(Group, type='area', acronym=name)
    try:
        area.start_date = area.groupevent_set.order_by('time')[0].time
        area.concluded_date = area.groupevent_set.get(type='concluded').time
    except GroupEvent.DoesNotExist:
        pass
    directors = area.role_set.filter(name__slug__in=('ad','pre-ad'))
    
    return render_to_response('areas/view.html', {
        'area': area,
        'directors': directors},
        RequestContext(request, {}),
    )
