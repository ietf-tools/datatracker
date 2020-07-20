import json
 
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

from ietf.group.models import Group, GroupEvent, Role
from ietf.group.utils import save_group_in_history
from ietf.ietfauth.utils import role_required
from ietf.person.models import Person
from ietf.secr.areas.forms import AreaDirectorForm

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
        
    return HttpResponse(json.dumps(result), content_type='application/javascript')
    
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
        
    return HttpResponse(json.dumps(results), content_type='application/javascript')
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------


@role_required('Secretariat')
def list_areas(request):
    """ 
    List IETF Areas 

    **Templates:**

    * ``areas/list.html``

    **Template Variables:**

    * results 

    """

    results = Group.objects.filter(type="area").order_by('name')
    
    return render(request, 'areas/list.html', { 'results': results} )

@role_required('Secretariat')
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
                
                if not email.origin or email.origin == person.user.username:
                    email.origin = "role: %s %s" % (area.acronym, 'pre-ad')
                    email.save()

                messages.success(request, 'New Area Director added successfully!')
                return redirect('ietf.secr.areas.views.view', name=name)
    else:
        form = AreaDirectorForm()

    directors = area.role_set.filter(name__slug__in=('ad','pre-ad'))
    return render(request, 'areas/people.html', {
        'area': area,
        'form': form,
        'directors': directors},
    )

@role_required('Secretariat')
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
            Role.objects.filter(name__in=('ad','pre-ad'),person=person,group__type='wg',group__state__in=('active','bof')).delete()
            
            messages.success(request, 'The Area Director has been retired successfully!')

        # handle voting request
        if request.POST.get('submit', '') == "Enable Voting":
            role = Role.objects.get(group=area,name__slug='pre-ad',person=person)
            role.name_id = 'ad'
            role.save()
            
            messages.success(request, 'Voting rights have been granted successfully!')

        return redirect('ietf.secr.areas.views.view', name=name)

@role_required('Secretariat')
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
    
    return render(request, 'areas/view.html', {
        'area': area,
        'directors': directors},
    )
