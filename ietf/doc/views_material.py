# views for managing group materials (slides, ...)
import os
import datetime
import re

from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden, Http404
from django.utils.html import mark_safe
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, DocTypeName, DocEvent, State
from ietf.doc.models import NewRevisionDocEvent, save_document_in_history
from ietf.doc.utils import add_state_change_event, check_common_doc_name_rules
from ietf.group.models import Group
from ietf.group.utils import can_manage_materials
from ietf.meeting.models import Session

@login_required
def choose_material_type(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    if not group.features.has_materials:
        raise Http404

    return render(request, 'doc/material/choose_material_type.html', {
        'group': group,
        'material_types': DocTypeName.objects.filter(slug__in=group.features.material_types),
    })

class UploadMaterialForm(forms.Form):
    title = forms.CharField(max_length=Document._meta.get_field("title").max_length)
    name = forms.CharField(max_length=Document._meta.get_field("name").max_length)
    abstract = forms.CharField(max_length=Document._meta.get_field("abstract").max_length,widget=forms.Textarea)
    state = forms.ModelChoiceField(State.objects.all(), empty_label=None)
    material = forms.FileField(label='File')

    def __init__(self, doc_type, action, group, doc, *args, **kwargs):
        super(UploadMaterialForm, self).__init__(*args, **kwargs)

        self.fields["state"].queryset = self.fields["state"].queryset.filter(type=doc_type)

        self.doc_type = doc_type
        self.action = action
        self.group = group

        if action == "new":
            self.fields["state"].widget = forms.HiddenInput()
            self.fields["state"].queryset = self.fields["state"].queryset.filter(slug="active")
            self.fields["state"].initial = self.fields["state"].queryset[0].pk
            self.fields["name"].initial = u"%s-%s-" % (doc_type.slug, group.acronym)
        else:
            del self.fields["name"]

            self.fields["title"].initial = doc.title
            self.fields["abstract"].initial = doc.abstract
            self.fields["state"].initial = doc.get_state().pk if doc.get_state() else None
            if doc.get_state_slug() == "deleted":
                self.fields["state"].help_text = "Note: If you wish to revise this document, you may wish to change the state so it's not deleted."

            if action in ["title","state","abstract"]:
                for fieldname in ["title","state","material","abstract"]: 
                    if fieldname != action:
                        del self.fields[fieldname]

    def clean_name(self):
        name = self.cleaned_data["name"].strip().rstrip("-")

        check_common_doc_name_rules(name)

        if not re.search("^%s-%s-[a-z0-9]+" % (self.doc_type.slug, self.group.acronym), name):
            raise forms.ValidationError("The name must start with %s-%s- followed by descriptive dash-separated words." % (self.doc_type.slug, self.group.acronym))

        existing = Document.objects.filter(type=self.doc_type, name=name)
        if existing:
            url = urlreverse("material_edit", kwargs={ 'name': existing[0].name, 'action': 'revise' })
            raise forms.ValidationError(mark_safe("Can't upload: %s with name %s already exists. Choose another title and name for what you're uploading or <a href=\"%s\">revise the existing %s</a>." % (self.doc_type.name, name, url, name)))

        return name

@login_required
def edit_material(request, name=None, acronym=None, action=None, doc_type=None):
    # the materials process is not very developed, so at the moment we
    # handle everything through the same view/form

    if action == "new":
        group = get_object_or_404(Group, acronym=acronym)
        if not group.features.has_materials:
            raise Http404

        doc = None
        document_type = get_object_or_404(DocTypeName, slug=doc_type)
    else:
        doc = get_object_or_404(Document, name=name)
        group = doc.group
        document_type = doc.type

    if not can_manage_materials(request.user, group):
        return HttpResponseForbidden("You don't have permission to access this view")

    if request.method == 'POST':
        form = UploadMaterialForm(document_type, action, group, doc, request.POST, request.FILES)

        if form.is_valid():
            if action == "new":
                doc = Document()
                doc.type = document_type
                doc.group = group
                doc.rev = "00"
                doc.name = form.cleaned_data["name"]
                prev_rev = None
            else:
                save_document_in_history(doc)
                prev_rev = doc.rev

            prev_title = doc.title
            prev_state = doc.get_state()

            if "title" in form.cleaned_data:
                doc.title = form.cleaned_data["title"]

            if "abstract" in form.cleaned_data:
                doc.abstract = form.cleaned_data["abstract"]

            doc.time = datetime.datetime.now()

            if "material" in form.fields:
                if action != "new":
                    doc.rev = "%02d" % (int(doc.rev) + 1)

                f = form.cleaned_data["material"]
                file_ext = os.path.splitext(f.name)[1]

                with open(os.path.join(doc.get_file_path(), doc.name + "-" + doc.rev + file_ext), 'wb+') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)

            doc.save()

            if action == "new":
                DocAlias.objects.get_or_create(name=doc.name, document=doc)

            if prev_rev != doc.rev:
                e = NewRevisionDocEvent(type="new_revision", doc=doc, rev=doc.rev)
                e.time = doc.time
                e.by = request.user.person
                e.desc = "New version available: <b>%s-%s</b>" % (doc.name, doc.rev)
                e.save()
                
            if prev_title != doc.title:
                e = DocEvent(doc=doc, by=request.user.person, type='changed_document')
                e.desc = u"Changed title to <b>%s</b>" % doc.title
                if prev_title:
                    e.desc += u" from %s" % prev_title
                e.time = doc.time
                e.save()

            if "state" in form.cleaned_data and form.cleaned_data["state"] != prev_state:
                doc.set_state(form.cleaned_data["state"])
                add_state_change_event(doc, request.user.person, prev_state, form.cleaned_data["state"])

            return redirect("doc_view", name=doc.name)
    else:
        form = UploadMaterialForm(document_type, action, group, doc)

    return render(request, 'doc/material/edit_material.html', {
        'group': group,
        'form': form,
        'action': action,
        'document_type': document_type,
        'doc_name': doc.name if doc else "",
    })

class MaterialVersionForm(forms.Form):

    version = forms.ChoiceField(required=False,
                                label='Which version of this document will be presented at this session')

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices')
        super(MaterialVersionForm,self).__init__(*args,**kwargs)
        self.fields['version'].choices = choices

def get_upcoming_manageable_sessions(user, doc, acronym=None, date=None, seq=None, week_day = None):

    # Find all the sessions for meetings that haven't ended that the user could affect
    # This motif is also in Document.future_presentations - it would be nice to consolodate it somehow

    candidate_sessions = Session.objects.exclude(status__in=['canceled','disappr','notmeet','deleted']).filter(meeting__date__gte=datetime.date.today()-datetime.timedelta(days=15))
    refined_candidates = [ sess for sess in candidate_sessions if sess.meeting.end_date()>=datetime.date.today()]

    if acronym:
        refined_candidates = [ sess for sess in refined_candidates if sess.group.acronym==acronym]

    if date:
        if len(date)==15:
            start = datetime.datetime.strptime(date,"%Y-%m-%d-%H%M")
            refined_candidates = [ sess for sess in refined_candidates if sess.timeslotassignments.filter(schedule=sess.meeting.agenda,timeslot__time=start) ]
        else:
            start = datetime.datetime.strptime(date,"%Y-%m-%d").date()
            end = start+datetime.timedelta(days=1)
            refined_candidates = [ sess for sess in refined_candidates if sess.timeslotassignments.filter(schedule=sess.meeting.agenda,timeslot__time__range=(start,end)) ]

    if week_day:
        try:
            dow = ['sun','mon','tue','wed','thu','fri','sat'].index(week_day.lower()[:3]) + 1
        except ValueError:
            raise Http404
        refined_candidates = [ sess for sess in refined_candidates if sess.timeslotassignments.filter(schedule=sess.meeting.agenda,timeslot__time__week_day=dow) ]

    changeable_sessions = [ sess for sess in refined_candidates if can_manage_materials(user, sess.group) ]

    if not changeable_sessions:
        raise Http404

    for sess in changeable_sessions:
        sess.has_presentation = bool(sess.sessionpresentation_set.filter(document=doc))
        if sess.has_presentation:
            sess.version = sess.sessionpresentation_set.get(document=doc).rev

    # Since Python 2.2 sorts are stable, so this series results in a list sorted first by whether
    # the session has any presentations, then by the meeting 'number', then by session's group 
    # acronym, then by scheduled time (or the time of the session request if the session isn't 
    # scheduled).
    
    def time_sort_key(session):
        official_sessions = session.timeslotassignments.filter(schedule=session.meeting.agenda)
        if official_sessions:
            return official_sessions.first().timeslot.time
        else:
            return session.requested

    time_sorted = sorted(changeable_sessions,key=time_sort_key)
    acronym_sorted = sorted(time_sorted,key=lambda x: x.group.acronym)
    meeting_sorted = sorted(acronym_sorted,key=lambda x: x.meeting.number)
    sorted_sessions = sorted(meeting_sorted,key=lambda x: '0' if x.has_presentation else '1')
    
    if seq:
        iseq = int(seq) - 1
        if not iseq in range(0,len(sorted_sessions)):
            raise Http404
        else:
            sorted_sessions = [sorted_sessions[iseq]]

    return sorted_sessions

@login_required
def edit_material_presentations(request, name, acronym=None, date=None, seq=None, week_day=None):

    doc = get_object_or_404(Document, name=name)
    if not (doc.type_id=='slides' and doc.get_state('slides').slug=='active'):
        raise Http404

    group = doc.group
    if not (group.features.has_materials and can_manage_materials(request.user,group)):
        raise Http404

    sorted_sessions = get_upcoming_manageable_sessions(request.user, doc, acronym, date, seq, week_day)

    if len(sorted_sessions)!=1:
        raise Http404

    session = sorted_sessions[0]
    choices = [('notpresented','Not Presented')]
    choices.extend([(x,x) for x in doc.docevent_set.filter(type='new_revision').values_list('newrevisiondocevent__rev',flat=True)])
    initial = {'version' : session.version if hasattr(session,'version') else 'notpresented'}

    if request.method == 'POST':
        form = MaterialVersionForm(request.POST,choices=choices)
        if form.is_valid():
            new_selection = form.cleaned_data['version']
            if initial['version'] != new_selection:
                if initial['version'] == 'notpresented':
                    doc.sessionpresentation_set.create(session=session,rev=new_selection)
                    c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
                    c.desc = "Added version %s to session: %s" % (new_selection,session)
                    c.save()
                elif new_selection == 'notpresented':
                    doc.sessionpresentation_set.filter(session=session).delete()
                    c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
                    c.desc = "Removed from session: %s" % (session)
                    c.save()
                else:
                    doc.sessionpresentation_set.filter(session=session).update(rev=new_selection)
                    c = DocEvent(type="added_comment", doc=doc, by=request.user.person)
                    c.desc = "Revision for session %s changed to  %s" % (session,new_selection)
                    c.save()
            return redirect('doc_view',name=doc.name)
    else:
        form = MaterialVersionForm(choices=choices,initial=initial)

    return render(request, 'doc/material/edit_material_presentations.html', {
        'session': session,
        'doc': doc,
        'form': form,
        })

@login_required
def material_presentations(request, name, acronym=None, date=None, seq=None, week_day=None):

    doc = get_object_or_404(Document, name=name)
    if not (doc.type_id=='slides' and doc.get_state('slides').slug=='active'):
        raise Http404

    group = doc.group
    if not (group.features.has_materials and can_manage_materials(request.user,group)):
        raise Http404

    sorted_sessions = get_upcoming_manageable_sessions(request.user, doc, acronym, date, seq, week_day)

    #for index,session in enumerate(sorted_sessions):
    #    session.sequence = index+1

    return render(request, 'doc/material/material_presentations.html', {
        'sessions' : sorted_sessions,
        'doc': doc,
        'date': date,
        'week_day': week_day,
        })
