from django.contrib import messages
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.forms.models import inlineformset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import urlencode
from django.urls import reverse

from ietf.ietfauth.utils import role_required
from ietf.person.models import Person, Email, Alias
from ietf.person.utils import merge_users
from ietf.secr.rolodex.forms import EditPersonForm, EmailForm, NameForm, NewPersonForm, SearchForm


# ---------------------------------------
# Views 
# ---------------------------------------

@role_required('Secretariat')
def add(request):
    """ 
    Add contact information.

    **Templates:**

    * ``rolodex/add.html``

    **Template Variables:**

    * form
    * results: the list of similar names to allow user to check for dupes
    * name: the new name that is submitted

    """
    results = []
    name = None
    if request.method == 'POST':
        form = NameForm(request.POST)
        if form.is_valid():
            # search to see if contact already exists
            name = form.cleaned_data['name']
            results = Alias.objects.filter(name=name)
            if not results:
                params = dict(name=name)
                url = reverse('ietf.secr.rolodex.views.add_proceed')
                url = url + '?' + urlencode(params)
                return redirect(url)

    else:
        form = NameForm()

    return render(request, 'rolodex/add.html', {
        'form': form,
        'results': results,
        'name': name},
    )

@role_required('Secretariat')
def add_proceed(request):
    """ 
    Add contact information. (2nd page, allows entry of address, phone and email records)

    **Templates:**

    * ``rolodex/add_proceeed.html``

    **Template Variables:**

    * name: new contact name
    * form

    """
    if 'name' in request.GET:
        name = request.GET.get('name')
    elif 'name' in request.POST:
        name = request.POST.get('name')
    else:
        name = ''

    if request.method == 'POST' and request.POST.get('submit') == 'Submit':
        form = NewPersonForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            # save person here
            person = form.save()

            # save email
            Email.objects.create(address=email,
                                 person=person,
                                 origin=request.user.username,
                             )

            # in theory a user record could exist which wasn't associated with a Person
            try:
                user = User.objects.create_user(email, email)
            except IntegrityError:
                user = User.objects.get(username=email)
                
            person.user = user
            person.save()
            
            messages.success(request, 'The Rolodex entry was added successfully')
            return redirect('ietf.secr.rolodex.views.view', id=person.id)
    else:
        form = NewPersonForm(initial={'name':name,'ascii':name})

    return render(request, 'rolodex/add_proceed.html', {
        'name': name,
        'form': form},
    )

@role_required('Secretariat')
def delete(request, id):
    """ 
    Delete contact information.
    Note: access to this view was disabled per Glen 3-16-10.

    **Templates:**

    * ``rolodex/delete.html``

    **Template Variables:**

    * person

    """
    person = get_object_or_404(Person, id=id)

    if request.method == 'POST':
        if request.POST.get('post', '') == "yes":
            
            # Django does cascading delete (deletes all objects with foreign
            # keys to this object).  Since this isn't what we want, ie. you don't
            # want to delete a group which has a foreign key, "ad" to this person.
            # Django 1.3 has a way to override, on_delete
            #person.delete()
            
            messages.warning(request, 'This feature is disabled')
            return redirect('ietf.secr.rolodex.views.search')

    return render(request, 'rolodex/delete.html', { 'person': person}, )
    
@role_required('Secretariat')
def edit(request, id):
    """ 
    Edit contact information.  Address, Email and Phone records are provided as inlineformsets.

    **Templates:**

    * ``rolodex/edit.html``

    **Template Variables:**

    * person, person_form, email_formset

    """
    person = get_object_or_404(Person, id=id)

    EmailFormset = inlineformset_factory(Person, Email, form=EmailForm, can_delete=False, extra=0)
  
    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.secr.rolodex.views.view', id=id)

        person_form = EditPersonForm(request.POST, instance=person)
        email_formset = EmailFormset(request.POST, instance=person, prefix='email')
        if person_form.is_valid() and email_formset.is_valid():
            # handle aliases
            for field in ('name','ascii','ascii_short'):
                if field in person_form.changed_data:
                    person.alias_set.filter(name=getattr(person,field)).delete()
                    alias = person_form.cleaned_data[field]
                    if alias:
                        Alias.objects.get_or_create(person=person,name=alias)
                    
            person_form.save()
            email_formset.save()
            
            if 'user' in person_form.changed_data and person_form.initial['user']:
                try:
                    source = User.objects.get(username=person_form.initial['user'])
                    merge_users(source, person_form.cleaned_data['user'])
                    source.is_active = False
                    source.save()
                except User.DoesNotExist:
                    pass

            messages.success(request, 'The Rolodex entry was changed successfully')
            return redirect('ietf.secr.rolodex.views.view', id=id)

    else:
        person_form = EditPersonForm(instance=person)
        # if any inlineformsets will be empty, need to initialize with extra=1
        # this is because the javascript for adding new forms requires a first one to copy
        if not person.email_set.all():
            EmailFormset.extra = 1
        # initialize formsets
        email_formset = EmailFormset(instance=person, prefix='email')
            
    return render(request, 'rolodex/edit.html', {
        'person': person,
        'person_form': person_form, 
        'email_formset': email_formset},
    )

@role_required('Secretariat')
def search(request):
    """ 
    Search Person by any combination of name, email or tag.  email matches
    any substring, if tag is provided only exact tag matches are returned.

    **Templates:**

    * ``rolodex/search.html``

    **Template Variables:**

    * results: list of dictionaries of search results (first_name, last_name, tag, email, company
    * form: the search form
    * not_found: contains text "No record found" if search results are empty

    """
    results = []
    not_found = ''
    if request.method == 'POST':
        form = SearchForm(request.POST)
        if form.is_valid():
            kwargs = {}
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            id = form.cleaned_data['id']
            if name:
                kwargs['name__icontains'] = name
            if email:
                #kwargs['email__address__istartswith'] = email
                kwargs['person__email__address__istartswith'] = email
            if id:
                kwargs['person__id'] = id
            # perform query
            if kwargs:
                qs = Alias.objects.filter(**kwargs).distinct()
                
            results = qs.order_by('name')
            
            # if there's just one result go straight to view
            if len(results) == 1:
                return redirect('ietf.secr.rolodex.views.view', id=results[0].person.id)

            if not results:
                not_found = 'No record found' 
    else:
        form = SearchForm()
    
    return render(request, 'rolodex/search.html', {
        'results' : results,
        'form': form,
        'not_found': not_found},
    )

@role_required('Secretariat')
def view(request, id):
    """ 
    View contact information.

    **Templates:**

    * ``rolodex/view.html``

    **Template Variables:**

    * person

    """
    person = get_object_or_404(Person, id=id)
    
    # must filter for active emails only
    person.emails = person.email_set.filter(active=True)
    roles = person.role_set.all().order_by('name__name','group__acronym')
    
    return render(request, 'rolodex/view.html', {
        'person': person,
        'roles': roles},
    )

