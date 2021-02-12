from django.contrib import messages
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect

from ietf.group.models import Group, GroupEvent, Role
from ietf.group.utils import save_group_in_history, get_charter_text
from ietf.ietfauth.utils import role_required
from ietf.person.models import Person
from ietf.secr.groups.forms import RoleForm, SearchForm
from ietf.secr.utils.meeting import get_current_meeting
from ietf.liaisons.views import contacts_from_roles

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
    query = GroupEvent.objects.filter(group=group, type="changed_state").order_by('time')
    proposed = query.filter(changestategroupevent__state="proposed")
    meeting = get_current_meeting()

    if proposed:
        group.proposed_date = proposed[0].time
    active = query.filter(changestategroupevent__state="active")
    if active:
        group.start_date = active[0].time
    concluded = query.filter(changestategroupevent__state="conclude")
    if concluded:
        group.concluded_date = concluded[0].time

    if group.session_set.filter(meeting__number=meeting.number):
        group.meeting_scheduled = 'YES'
    else:
        group.meeting_scheduled = 'NO'

    group.chairs = group.role_set.filter(name="chair")
    group.techadvisors = group.role_set.filter(name="techadv")
    group.editors = group.role_set.filter(name="editor")
    group.secretaries = group.role_set.filter(name="secr")
    # Note: liaison_contacts is now a dict instead of a model instance with fields. In
    # templates, the dict can still be accessed using '.contacts' and .cc_contacts', though.
    group.liaison_contacts = dict(
        contacts=contacts_from_roles(group.role_set.filter(name='liaison_contact')),
        cc_contacts=contacts_from_roles(group.role_set.filter(name='liaison_cc_contact')),
    )

    #fill_in_charter_info(group)

#--------------------------------------------------
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

    return HttpResponse(json.dumps(results), content_type='application/javascript')
'''
# -------------------------------------------------
# Standard View Functions
# -------------------------------------------------



@role_required('Secretariat')
def blue_dot(request):
    '''
    This is a report view.  It returns a text/plain listing of working group chairs.
    '''
    people = Person.objects.filter(role__name__slug='chair',
                                   role__group__type='wg',
                                   role__group__state__slug__in=('active','bof','proposed')).distinct()
    chairs = []
    for person in people:
        parts = person.name_parts()
        groups = [ r.group.acronym for r in person.role_set.filter(name__slug='chair',
                                                                   group__type='wg',
                                                                   group__state__slug__in=('active','bof','proposed')) ]
        entry = {'name':'%s, %s' % (parts[3], parts[1]),
                 'groups': ', '.join(groups)}
        chairs.append(entry)

    # sort the list
    sorted_chairs = sorted(chairs, key = lambda a: a['name'])

    return render(request, 'groups/blue_dot_report.txt', { 'chairs':sorted_chairs },
        content_type="text/plain; charset=%s"%settings.DEFAULT_CHARSET,
    )

@role_required('Secretariat')
def charter(request, acronym):
    """
    View Group Charter

    **Templates:**

    * ``groups/charter.html``

    **Template Variables:**

    * group, charter_text

    """

    group = get_object_or_404(Group, acronym=acronym)
    # TODO: get_charter_text() should be updated to return None
    if group.charter:
        charter_text = get_charter_text(group)
    else:
        charter_text = ''

    return render(request, 'groups/charter.html', {
        'group': group,
        'charter_text': charter_text},
    )

@role_required('Secretariat')
def delete_role(request, acronym, id):
    """
    Handle deleting roles for groups (chair, editor, advisor, secretary)

    **Templates:**

    * none

    Redirects to people page on success.

    """
    group = get_object_or_404(Group, acronym=acronym)
    role = get_object_or_404(Role, id=id)
    
    if request.method == 'POST' and request.POST['post'] == 'yes':
        # save group
        save_group_in_history(group)

        role.delete()
        messages.success(request, 'The entry was deleted successfully')
        return redirect('ietf.secr.groups.views.people', acronym=acronym)

    return render(request, 'confirm_delete.html', {'object': role})


@role_required('Secretariat')
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

            if not email.origin or email.origin == person.user.username:
                email.origin = "role: %s %s" % (group.acronym, name.slug)
                email.save()

            messages.success(request, 'New %s added successfully!' % name)
            return redirect('ietf.secr.groups.views.people', acronym=group.acronym)
    else:
        form = RoleForm(initial={'name':'chair', 'group_acronym':group.acronym}, group=group)

    return render(request, 'groups/people.html', {
        'form':form,
        'group':group},
    )

@role_required('Secretariat')
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

        if form.is_valid():
            kwargs = {}
            group_acronym = form.cleaned_data['group_acronym']
            group_name = form.cleaned_data['group_name']
            primary_area = form.cleaned_data['primary_area']
            meeting_scheduled = form.cleaned_data['meeting_scheduled']
            state = form.cleaned_data['state']
            type = form.cleaned_data['type']
            meeting = get_current_meeting()

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
            #else:
            #    kwargs['type__in'] = ('wg','rg','ietf','ag','sdo','team')

            if meeting_scheduled == 'YES':
                kwargs['session__meeting__number'] = meeting.number
            # perform query
            if kwargs:
                if meeting_scheduled == 'NO':
                    qs = Group.objects.filter(**kwargs).exclude(session__meeting__number=meeting.number).distinct()
                else:
                    qs = Group.objects.filter(**kwargs).distinct()
            else:
                qs = Group.objects.all()
            results = qs.order_by('acronym')

            # if there's just one result go straight to view
            if len(results) == 1:
                return redirect('ietf.secr.groups.views.view', acronym=results[0].acronym)

    # process GET argument to support link from area app
    elif 'primary_area' in request.GET:
        area = request.GET.get('primary_area','')
        results = Group.objects.filter(parent__id=area,type='wg',state__in=('bof','active','proposed')).order_by('name')
        form = SearchForm({'primary_area':area,'state':'','type':'wg'})
    else:
        form = SearchForm(initial={'state':'active'})

    # loop through results and tack on meeting_scheduled because it is no longer an
    # attribute of the meeting model
    for result in results:
        add_legacy_fields(result)

    return render(request, 'groups/search.html', {
        'results': results,
        'form': form},
    )

@role_required('Secretariat')
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

    return render(request, 'groups/view.html', { 'group': group } )

