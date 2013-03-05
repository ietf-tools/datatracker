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
from ietf.secr.groups.forms import RoleForm
from ietf.secr.sreq.forms import GroupSelectForm

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

# -------------------------------------------------
# AJAX Functions
# -------------------------------------------------
def ajax_get_roles(request, acronym):
    '''
    Ajax function which takes a group acronym and returns the
    roles for the group in the form of a table
    '''
    group = get_object_or_404(Group, acronym=acronym)
    
    return render_to_response('roles/roles.html', {
        'group': group,
        'roles': group.role_set.all()},
        RequestContext(request, {}),
    )
# --------------------------------------------------
# STANDARD VIEW FUNCTIONS
# --------------------------------------------------
def delete_role(request, acronym, id):
    """ 
    Handle deleting roles

    **Templates:**

    * none

    """
    role = get_object_or_404(Role, id=id)
    group = get_object_or_404(Group, acronym=acronym)

    # save group
    save_group_in_history(role.group)
                
    role.delete()
    
    messages.success(request, 'The entry was deleted successfully')
    url = reverse('roles') + '?group=%s' % group.acronym
    return HttpResponseRedirect(url)

def main(request):
    '''
    Main view for generic Roles App
    '''
    groups = Group.objects.filter(type__in=('sdo','ietf')).order_by('acronym')
    choices=build_choices(groups)
    choices.insert(0,('','------------'))
    group_form = GroupSelectForm(choices=choices)
    
    # prime form with random sdo group so all roles are available
    group = Group.objects.filter(type='sdo')[0]
    
    if request.method == 'POST':
        role_form = RoleForm(request.POST,group=group)
        if role_form.is_valid():
            name = role_form.cleaned_data['name']
            person = role_form.cleaned_data['person']
            email = role_form.cleaned_data['email']
            acronym = role_form.cleaned_data['group_acronym']
            
            group = Group.objects.get(acronym=acronym)
            
            # save group
            save_group_in_history(group)
                
            Role.objects.create(name=name,
                                person=person,
                                email=email,
                                group=group)

            messages.success(request, 'New %s added successfully!' % name)
            url = reverse('roles') + '?group=%s' % group.acronym
            return HttpResponseRedirect(url)
    
    else:
        role_form = RoleForm(initial={'name':'chair'},group=group)
        # accept get argument to select group if we're returning after a change
        if 'group' in request.GET:
            group_form = GroupSelectForm(choices=choices,initial={'group':request.GET['group']})
            
    return render_to_response('roles/main.html', {
        'group_form': group_form,
        'role_form': role_form},
        RequestContext(request, {}),
    )