from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Max
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson

from ietf.group.models import Group, GroupHistory, Role, RoleHistory
from ietf.group.utils import save_group_in_history
from sec.groups.forms import RoleForm
from sec.sreq.forms import GroupSelectForm

from forms import *
import re
import datetime

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def build_choices(queryset):
    '''
    This function takes a queryset (or list) of Groups and builds a list of tuples for use 
    as choices in a select widget.  Using acronym for both value and label.
    '''
    choices = [ (g.acronym,g.acronym) for g in queryset ]
    return sorted(choices, key=lambda choices: choices[1])
    
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------

def chair(request, type):
    """ 
    View IETF/IAB/NOMCOM Chair history.  Assign a new Chair. 

    **Templates:**

    * ``roles/ietf.html``

    **Template Variables:**

    * chairs, type

    """
    group = get_object_or_404(Group, acronym=type)
    chairs = []
    roles = Role.objects.filter(group=group,name__slug='chair')
    
    if request.method == 'POST':
        # handle adding a new director 
        if request.POST.get('submit', '') == "Add":
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
                url = reverse('roles_chair', kwargs={'type':type})
                return HttpResponseRedirect(url)
            
    else:
        form = RoleForm(initial={'name':'chair'},group=group)

    return render_to_response('roles/chairs.html', {
        'form': form,
        'type': type,
        'roles': roles,
        'group': group,
        'chairs': chairs},
        RequestContext(request, {}),
    )

def delete_role(request, type, id):
    """ 
    Handle deleting roles for groups (chair, editor, advisor, secretary)

    **Templates:**

    * none

    Redirects to people page on success.

    """
    role = get_object_or_404(Role, id=id)

    # save group
    save_group_in_history(role.group)
                
    role.delete()
    
    messages.success(request, 'The entry was deleted successfully')
    url = reverse('roles')
    return HttpResponseRedirect(url)
    
def liaisons(request):
    """ 
    View Liaison members, add or delete a member 

    **Templates:**

    * ``roles/liaisons.html``

    **Template Variables:**

    * liaisons 

    """
    '''
    if request.method == 'POST':
        # handle adding a new Liaison 
        if request.POST.get('submit', '') == "Add":
            form = LiaisonForm(request.POST)
            if form.is_valid():
                affiliation = request.POST.get('affiliation', '')
                name = request.POST.get('liaison_name', '')
                # get person record
                m = re.search(r'\((\d+)\)', name)
                tag = m.group(1)
                person = PersonOrOrgInfo.objects.get(person_or_org_tag=tag)
                liaison = LiaisonsMembers(person=person,affiliation=affiliation)
                liaison.save()
                
                messages.success(request, 'The Liaison was added successfully!')
                url = reverse('roles_liaisons')
                return HttpResponseRedirect(url)

        # handle deleting a Liaison 
        if request.POST.get('submit', '') == "Delete":
            tag = request.POST.get('liaison-tag', '')
            try:
                liaison = LiaisonsMembers.objects.get(person=tag)
            except:
                # use ERROR message level once upgraded to Django 1.2
                messages.error(request, 'Error locating liaisons record.')
                url = reverse('roles_liaisons')
                return HttpResponseRedirect(url)

            liaison.delete()
            messages.success(request, 'The liaison was deleted successfully')
            form = LiaisonForm()
    else:
        form = LiaisonForm()

    liaisons = LiaisonsMembers.objects.all()
    '''
    liaisons = None
    form = None
    return render_to_response('roles/liaisons.html', {
        'form': form,
        'liaisons': liaisons},
        RequestContext(request, {}),
    )

def main(request):
    '''
    Main view for generic Roles App
    '''
    groups = Group.objects.filter(type='sdo').order_by('acronym')
    group_form = GroupSelectForm(choices=build_choices(groups))
    
    return render_to_response('roles/main.html', {
        'group_form': group_form},
        RequestContext(request, {}),
    )