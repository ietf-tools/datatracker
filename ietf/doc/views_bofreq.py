# Copyright The IETF Trust 2021 All Rights Reserved

import debug    # pyflakes:ignore

import io 

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.utils.html import escape

from ietf.doc.mails import (email_bofreq_title_changed, email_bofreq_editors_changed, 
    email_bofreq_new_revision, email_bofreq_responsible_changed)
from ietf.doc.models import (Document, DocEvent, NewRevisionDocEvent, 
    BofreqEditorDocEvent, BofreqResponsibleDocEvent, State)
from ietf.doc.utils import add_state_change_event
from ietf.doc.utils_bofreq import bofreq_editors, bofreq_responsible
from ietf.ietfauth.utils import has_role, role_required
from ietf.person.fields import SearchablePersonsField
from ietf.person.models import Person
from ietf.utils import markdown
from ietf.utils.response import permission_denied
from ietf.utils.text import xslugify
from ietf.utils.textupload import get_cleaned_text_file_content


def bof_requests(request):
    reqs = Document.objects.filter(type_id='bofreq')
    for req in reqs:
        req.latest_revision_event = req.latest_event(NewRevisionDocEvent)
        req.responsible = bofreq_responsible(req)
        req.editors = bofreq_editors(req)
    sorted_reqs = sorted(sorted(reqs, key=lambda doc: doc.latest_revision_event.time, reverse=True), key=lambda doc: doc.get_state().order)
    return render(request, 'doc/bofreq/bof_requests.html',dict(reqs=sorted_reqs))


class BofreqUploadForm(forms.Form):
    ACTIONS = [
        ("enter", "Enter content directly"),
        ("upload", "Upload content from file"),
    ]
    bofreq_submission = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)
    bofreq_file = forms.FileField(label="Markdown source file to upload", required=False)
    bofreq_content = forms.CharField(widget=forms.Textarea(attrs={'rows':30}), required=False, strip=False)

    def clean(self):
        def require_field(f):
            if not self.cleaned_data.get(f):
                self.add_error(f, forms.ValidationError("You must fill in this field."))
                return False
            else:
                return True

        submission_method = self.cleaned_data.get("bofreq_submission")
        content = ''
        if submission_method == "enter":
            if require_field("bofreq_content"):
                content = self.cleaned_data["bofreq_content"].replace("\r", "")
                default_content = render_to_string('doc/bofreq/bofreq_template.md', {'settings': settings})
                if content==default_content:
                    raise forms.ValidationError('The example content may not be saved. Edit it as instructed to document this BOF request.')
        elif submission_method == "upload":
            if require_field("bofreq_file"):
                content = get_cleaned_text_file_content(self.cleaned_data["bofreq_file"])
        try:
            _ = markdown.markdown(content)
        except Exception as e:
           raise forms.ValidationError(f'Markdown processing failed: {e}')



@login_required
def submit(request, name):
    bofreq = get_object_or_404(Document, type="bofreq", name=name)
    previous_editors = bofreq_editors(bofreq)
    state_id = bofreq.get_state_slug('bofreq')
    if not (has_role(request.user,('Secretariat', 'Area Director', 'IAB')) or (state_id=='proposed' and request.user.person in previous_editors)):
        permission_denied(request,"You do not have permission to upload a new revision of this BOF Request")

    if request.method == 'POST':
        form = BofreqUploadForm(request.POST, request.FILES)
        if form.is_valid():
            bofreq.rev = "%02d" % (int(bofreq.rev)+1) 
            e = NewRevisionDocEvent.objects.create(
                type="new_revision",
                doc=bofreq,
                by=request.user.person,
                rev=bofreq.rev,
                desc='New revision available',
                time=bofreq.time,
            )
            bofreq.save_with_history([e])
            bofreq_submission = form.cleaned_data['bofreq_submission']
            if bofreq_submission == "upload":
                content = get_cleaned_text_file_content(form.cleaned_data["bofreq_file"])
            else:
                content = form.cleaned_data['bofreq_content']
            with io.open(bofreq.get_file_name(), 'w', encoding='utf-8') as destination:
                destination.write(content)
            bofreq.store_str(bofreq.get_base_name(), content)
            email_bofreq_new_revision(request, bofreq)
            return redirect('ietf.doc.views_doc.document_main', name=bofreq.name)

    else:
        init = {'bofreq_content':bofreq.text_or_error(),
                'bofreq_submission':'enter',
               }
        form = BofreqUploadForm(initial=init)
    return render(request, 'doc/bofreq/upload_content.html',
                            {'form':form,'doc':bofreq})

class NewBofreqForm(BofreqUploadForm):
    title = forms.CharField(max_length=255)
    field_order = ['title','bofreq_submission','bofreq_file','bofreq_content']

    def __init__(self, requester, *args, **kwargs):
        self._requester = requester
        super().__init__(*args, **kwargs)

    def name_from_title(self, title):
        requester_slug = xslugify(self._requester.last_name())
        title_slug = xslugify(title)
        name = f'bofreq-{requester_slug[:64]}-{title_slug[:128]}'
        return name.replace('_', '-')

    def clean_title(self):
        title = self.cleaned_data['title']
        name = self.name_from_title(title)
        if name == self.name_from_title(''):
            raise forms.ValidationError('The filename derived from this title is empty. Please include a few descriptive words using ascii or numeric characters') 
        if Document.objects.filter(name=name).exists():
            raise forms.ValidationError('This title produces a filename already used by an existing BOF request')
        return title

@login_required
def new_bof_request(request):

    if request.method == 'POST':
        form = NewBofreqForm(request.user.person, request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            name = form.name_from_title(title)
            bofreq = Document.objects.create(
                type_id='bofreq',
                name = name,
                title = title,
                abstract = '',
                rev = '00',
            )
            bofreq.set_state(State.objects.get(type_id='bofreq',slug='proposed'))
            e1 = NewRevisionDocEvent.objects.create(
                type="new_revision",
                doc=bofreq,
                by=request.user.person,
                rev=bofreq.rev,
                desc='New revision available',
                time=bofreq.time,
            )
            e2 = BofreqEditorDocEvent.objects.create(
                type="changed_editors",
                doc=bofreq,
                rev=bofreq.rev,
                by=request.user.person,
                desc= f'Editors changed to {request.user.person.name}',
            )
            e2.editors.set([request.user.person])
            bofreq.save_with_history([e1,e2])
            bofreq_submission = form.cleaned_data['bofreq_submission']
            if bofreq_submission == "upload":
                content = get_cleaned_text_file_content(form.cleaned_data["bofreq_file"])
            else:
                content = form.cleaned_data['bofreq_content']
            with io.open(bofreq.get_file_name(), 'w', encoding='utf-8') as destination:
                destination.write(content)
            bofreq.store_str(bofreq.get_base_name(), content)
            email_bofreq_new_revision(request, bofreq)
            return redirect('ietf.doc.views_doc.document_main', name=bofreq.name)

    else:
        init = {'bofreq_content':escape(render_to_string('doc/bofreq/bofreq_template.md',{'settings': settings})),
                'bofreq_submission':'enter',
               }
        form = NewBofreqForm(request.user.person, initial=init)
    return render(request, 'doc/bofreq/new_bofreq.html',
                            {'form':form})  


class ChangeEditorsForm(forms.Form):
    editors = SearchablePersonsField(required=False)


@login_required
def change_editors(request, name):
    bofreq = get_object_or_404(Document, type="bofreq", name=name)
    previous_editors = bofreq_editors(bofreq)
    state_id = bofreq.get_state_slug('bofreq')
    if not (has_role(request.user,('Secretariat', 'Area Director', 'IAB')) or (state_id=='proposed' and request.user.person in previous_editors)):
        permission_denied(request,"You do not have permission to change this document's editors")

    if request.method == 'POST':
        form = ChangeEditorsForm(request.POST)
        if form.is_valid():
            new_editors = form.cleaned_data['editors']
            if set(new_editors) != set(previous_editors):
                e = BofreqEditorDocEvent(type="changed_editors", doc=bofreq, rev=bofreq.rev, by=request.user.person)
                e.desc = f'Editors changed to {", ".join([p.name for p in new_editors])}'
                e.save()
                e.editors.set(new_editors)
                bofreq.save_with_history([e])
                email_bofreq_editors_changed(request, bofreq, previous_editors)
            return redirect("ietf.doc.views_doc.document_main", name=bofreq.name)
    else:
        init = { "editors" : previous_editors }
        form = ChangeEditorsForm(initial=init)
    titletext = bofreq.get_base_name()
    return render(request, 'doc/bofreq/change_editors.html',
                              {'form': form,
                               'doc': bofreq,
                               'titletext' : titletext,
                              },
                          )


class ChangeResponsibleForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The queryset in extra_prefetch finds users for whom has_role(u, 'Area Director') or
        # has_role(u, 'IAB') is True. It needs to match the queries in the has_role() method.
        # Disable ajax requests because the SearchablePersonsField cannot enforce the queryset filter.
        self.fields['responsible'] = SearchablePersonsField(
            required=False,
            extra_prefetch=Person.objects.filter(
                Q(role__name='member', role__group__acronym='iab')
                | Q(role__name__in=('pre-ad', 'ad'), role__group__type='area', role__group__state='active')
            ).distinct(),
            disable_ajax=True,  # only use the prefetched options
            min_search_length=0,  # do not require typing to display options
        )

    def clean_responsible(self):
        responsible = self.cleaned_data['responsible']
        not_leadership = list()
        for person in responsible:
            if not has_role(person.user, ('Area Director', 'IAB')):
                not_leadership.append(person)
        if not_leadership:
            raise forms.ValidationError('Only current IAB and IESG members are allowed. Please remove: '+', '.join([person.plain_name() for person in not_leadership]))
        return responsible


@login_required
def change_responsible(request,name):
    if not has_role(request.user,('Secretariat', 'Area Director', 'IAB')):
        permission_denied(request,"You do not have permission to change this document's responsible leadership")
    bofreq = get_object_or_404(Document, type="bofreq", name=name)
    previous_responsible = bofreq_responsible(bofreq)

    if request.method == 'POST':
        form = ChangeResponsibleForm(request.POST)
        if form.is_valid():
            new_responsible = form.cleaned_data['responsible']
            if set(new_responsible) != set(previous_responsible):
                e = BofreqResponsibleDocEvent(type="changed_responsible", doc=bofreq, rev=bofreq.rev, by=request.user.person)
                e.desc = f'Responsible leadership changed to {", ".join([p.name for p in new_responsible])}'
                e.save()
                e.responsible.set(new_responsible)
                bofreq.save_with_history([e])
                email_bofreq_responsible_changed(request, bofreq, previous_responsible)
            return redirect("ietf.doc.views_doc.document_main", name=bofreq.name)
    else:
        init = { "responsible" : previous_responsible }
        form = ChangeResponsibleForm(initial=init)
    titletext = bofreq.get_base_name()
    return render(request, 'doc/bofreq/change_responsible.html',
                              {'form': form,
                               'doc': bofreq,
                               'titletext' : titletext,
                              },
                          )


class ChangeTitleForm(forms.Form):
    title = forms.CharField(max_length=255, label="Title", required=True)

@login_required
def edit_title(request, name):
    bofreq = get_object_or_404(Document, type="bofreq", name=name)
    editors = bofreq_editors(bofreq)
    state_id = bofreq.get_state_slug('bofreq')
    if not (has_role(request.user,('Secretariat', 'Area Director', 'IAB')) or (state_id=='proposed' and request.user.person in editors)):
        permission_denied(request, "You do not have permission to edit this document's title")

    if request.method == 'POST':
        form = ChangeTitleForm(request.POST)
        if form.is_valid():

            bofreq.title = form.cleaned_data['title']

            c = DocEvent(type="added_comment", doc=bofreq, rev=bofreq.rev, by=request.user.person)
            c.desc = "Title changed to '%s'"%bofreq.title
            c.save()

            bofreq.save_with_history([c])
            email_bofreq_title_changed(request, bofreq)

            return redirect("ietf.doc.views_doc.document_main", name=bofreq.name)

    else:
        init = { "title" : bofreq.title }
        form = ChangeTitleForm(initial=init)

    titletext = bofreq.get_base_name()
    return render(request, 'doc/change_title.html',
                              {'form': form,
                               'doc': bofreq,
                               'titletext' : titletext,
                              },
                          )


class ChangeStateForm(forms.Form):
    new_state = forms.ModelChoiceField(State.objects.filter(type="bofreq", used=True), label="BOF Request State", empty_label=None, required=True)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the state change history entry.", required=False, strip=False)


@role_required('Area Director', 'Secretariat', 'IAB')
def change_state(request, name, option=None):
    bofreq = get_object_or_404(Document, type="bofreq", name=name)

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        if form.is_valid():
            clean = form.cleaned_data
            new_state = clean['new_state']
            comment = clean['comment'].rstrip()

            if comment:
                c = DocEvent(type="added_comment", doc=bofreq, rev=bofreq.rev, by=login)
                c.desc = comment
                c.save()

            prev_state = bofreq.get_state()
            if new_state != prev_state:
                bofreq.set_state(new_state)
                events = []
                events.append(add_state_change_event(bofreq, login, prev_state, new_state))
                bofreq.save_with_history(events)

            return redirect('ietf.doc.views_doc.document_main', name=bofreq.name)
    else:
        s = bofreq.get_state()
        init = dict(new_state=s.pk if s else None)
        form = ChangeStateForm(initial=init)

    return render(request, 'doc/change_state.html',
                              dict(form=form,
                                   doc=bofreq,
                                   login=login,
                                   help_url=urlreverse('ietf.doc.views_help.state_help', kwargs=dict(type="bofreq")),
                                   ))
