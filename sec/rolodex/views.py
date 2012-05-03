from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms.formsets import formset_factory
from django.forms.models import inlineformset_factory, modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from ietf.person.models import Person, Email, Alias

from forms import *

# ---------------------------------------
# Views 
# ---------------------------------------

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
            request.session['post_data'] = request.POST
            
            # search to see if contact already exists
            name = form.cleaned_data['name']
            results = Person.objects.filter(name=name)
            if not results:
                return HttpResponseRedirect('../add-proceed/')

    else:
        form = NameForm()

    return render_to_response('rolodex/add.html', {
        'form': form,
        'results': results,
        'name': name},
        RequestContext(request, {}),
    )

def add_proceed(request):
    """ 
    Add contact information. (2nd page, allows entry of address, phone and email records)

    **Templates:**

    * ``rolodex/add_proceeed.html``

    **Template Variables:**

    * name: new contact name
    * form

    """
    # if we get to this page from the add page, as expected, the session will have post_data.
    if request.session['post_data']:
        post_data = request.session['post_data']
    else:
        messages.error('ERROR: unable to save session data (enable cookies)')
        url = reverse('rolodex_add')
        return HttpResponseRedirect(url)
    
    name = post_data['name']

    if request.method == 'POST':
        form = NewPersonForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            # save person here
            person = form.save()

            # save email
            Email.objects.create(address=email,
                                 person=person)

            # in theory a user record could exist which wasn't associated with a Person
            try:
                user = User.objects.create_user(email, email)
            except IntegrityError:
                user = User.objects.get(username=email)
                
            person.user = user
            person.save()
            
            # create the Alias
            Alias.objects.create(person=person,name=name)
            if person.ascii != person.name:
                Alias.objects.create(person=person,name=person.ascii)
            
            messages.success(request, 'The Rolodex entry was added successfully')
            url = reverse('rolodex_view', kwargs={'id': person.id})
            return HttpResponseRedirect(url)
    else:
        form = NewPersonForm(initial={'name':name,'ascii':name})

    return render_to_response('rolodex/add_proceed.html', {
        'name': name,
        'form': form},
        RequestContext(request, {}),
    )

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
            url = reverse('rolodex')
            return HttpResponseRedirect(url)

    return render_to_response('rolodex/delete.html', {
        'person': person},
        RequestContext(request, {}),
    )
    
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
            url = reverse('rolodex_view', kwargs={'id':id})
            return HttpResponseRedirect(url)

        person_form = EditPersonForm(request.POST, instance=person)
        email_formset = EmailFormset(request.POST, instance=person, prefix='email')
        if person_form.is_valid() and email_formset.is_valid():
            # handle aliases
            for field in ('name','ascii','ascii_short'):
                if field in person_form.changed_data:
                    person.alias_set.filter(name=getattr(person,field)).delete()
                    Alias.objects.get_or_create(person=person,name=person_form.cleaned_data[field])
                    
            person_form.save()
            email_formset.save()
            
            # add new names to alias
            
            messages.success(request, 'The Rolodex entry was changed successfully')
            url = reverse('rolodex_view', kwargs={'id': id})
            return HttpResponseRedirect(url)

    else:
        person_form = EditPersonForm(instance=person)
        # if any inlineformsets will be empty, need to initialize with extra=1
        # this is because the javascript for adding new forms requires a first one to copy
        if not person.email_set.all():
            EmailFormset.extra = 1
        # initialize formsets
        email_formset = EmailFormset(instance=person, prefix='email')
            
    return render_to_response('rolodex/edit.html', {
        'person': person,
        'person_form': person_form, 
        'email_formset': email_formset},
        RequestContext(request, {}),
    )

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
                #kwargs['id'] = id
                kwargs['person__id'] = id
            # perform query
            if kwargs:
                #qs = Person.objects.filter(**kwargs)
                qs = Alias.objects.filter(**kwargs).distinct()
                
            results = qs.order_by('name')
            
            # if there's just one result go straight to view
            if len(results) == 1:
                url = reverse('rolodex_view', kwargs={'id':results[0].person.id})
                return HttpResponseRedirect(url)
                
            if not results:
                not_found = 'No record found' 
    else:
        form = SearchForm()
    
    return render_to_response('rolodex/search.html', {
        'results' : results,
        'form': form,
        'not_found': not_found},
        RequestContext(request, {}),
    )

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
    
    return render_to_response('rolodex/view.html', {
        'person': person},
        RequestContext(request, {}),
    )

