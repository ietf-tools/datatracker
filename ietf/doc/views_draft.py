# Copyright The IETF Trust 2010-2023, All Rights Reserved
# -*- coding: utf-8 -*-


# changing state and metadata on Internet-Drafts

import datetime
import os
import glob
import shutil

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.forms.utils import ErrorList
from django.template.defaultfilters import pluralize
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, RelatedDocument, State,
    StateType, DocEvent, ConsensusDocEvent, TelechatDocEvent, WriteupDocEvent, StateDocEvent,
    IanaExpertDocEvent, IESG_SUBSTATE_TAGS)
from ietf.doc.mails import ( email_pulled_from_rfc_queue, email_resurrect_requested,
    email_resurrection_completed, email_state_changed, email_stream_changed,
    email_stream_state_changed, email_stream_tags_changed, extra_automation_headers,
    generate_publication_request, email_adopted, email_intended_status_changed,
    email_iesg_processing_document, email_ad_approved_doc,
    email_iana_expert_review_state_changed )
from ietf.doc.utils import ( add_state_change_event, can_adopt_draft, can_unadopt_draft,
    get_tags_for_stream_id, nice_consensus, update_action_holders,
    update_reminder, update_telechat, make_notify_changed_event, get_initial_notify,
    set_replaces_for_document, default_consensus, tags_suffix, can_edit_docextresources,
    update_doc_extresources )
from ietf.doc.lastcall import request_last_call
from ietf.doc.fields import SearchableDocumentsField
from ietf.doc.forms import ExtResourceForm
from ietf.group.models import Group, Role, GroupFeatures
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, is_authorized_in_doc_stream, user_is_person
from ietf.ietfauth.utils import role_required, can_request_rfc_publication
from ietf.mailtrigger.utils import gather_address_lists
from ietf.message.models import Message
from ietf.name.models import IntendedStdLevelName, DocTagName, StreamName
from ietf.person.fields import SearchableEmailField
from ietf.person.models import Person, Email
from ietf.utils.mail import send_mail, send_mail_message, on_behalf_of
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils import log
from ietf.utils.fields import ModelMultipleChoiceField
from ietf.utils.response import permission_denied
from ietf.utils.timezone import datetime_today, DEADLINE_TZINFO


class ChangeStateForm(forms.Form):
    state = forms.ModelChoiceField(State.objects.filter(used=True, type="draft-iesg"), empty_label=None, required=True)
    substate = forms.ModelChoiceField(DocTagName.objects.filter(slug__in=IESG_SUBSTATE_TAGS), required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False, strip=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if not has_role(user, "Secretariat"):
            self.fields["state"].queryset = self.fields["state"].queryset.exclude(slug="ann")

    def clean(self):
        retclean = self.cleaned_data
        state = self.cleaned_data.get('state', '(None)')
        tag = self.cleaned_data.get('substate','')
        comment = self.cleaned_data['comment'].strip() # pyflakes:ignore
        doc = get_object_or_404(Document, name=self.docname)
        prev = doc.get_state("draft-iesg")
    
        # tag handling is a bit awkward since the UI still works
        # as if IESG tags are a substate
        prev_tag = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        prev_tag = prev_tag[0] if prev_tag else None

        if state == prev and tag == prev_tag:
            self._errors['comment'] = ErrorList(['State not changed. Comments entered will be lost with no state change. Please go back and use the Add Comment feature on the history tab to add comments without changing state.'])

        if state != '(None)' and state.slug == 'idexists' and tag:
            self._errors['substate'] = ErrorList(['Clear substate before setting the document to the idexists state.'])

        return retclean

@role_required('Area Director','Secretariat')
def change_state(request, name):
    """Change IESG state of Internet-Draft, notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(Document, name=name)

    # Steer ADs towards "Begin IESG Processing"
    if doc.get_state_slug("draft-iesg")=="idexists" and not has_role(request.user,"Secretariat"):
        raise Http404

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStateForm(request.POST, user=request.user)
        form.docname=name

        if form.is_valid():
            new_state = form.cleaned_data['state']
            prev_state = doc.get_state("draft-iesg")

            tag = form.cleaned_data['substate']
            comment = form.cleaned_data['comment'].strip()

            msg = ""

            # tag handling is a bit awkward since the UI still works
            # as if IESG tags are a substate
            prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
            new_tags = [tag] if tag else []
            if new_state != prev_state or set(new_tags) != set(prev_tags):
                doc.set_state(new_state)

                doc.tags.remove(*prev_tags)
                doc.tags.add(*new_tags)

                events = []


                e = add_state_change_event(doc, login, prev_state, new_state,
                                           prev_tags=prev_tags, new_tags=new_tags)

                msg += "%s changed:\n\nNew State: %s\n\n"%(e.state_type.label, new_state.name + tags_suffix(new_tags))
                if prev_state:
                    msg += "(The previous state was %s)\n\n"%(prev_state.name + tags_suffix(prev_tags))
                
                events.append(e)

                e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
                if e:
                    events.append(e)

                if comment:
                    c = DocEvent(type="added_comment")
                    c.doc = doc
                    c.rev = doc.rev
                    c.by = login
                    c.desc = comment
                    c.save()

                    msg += c.desc + "\n"

                    events.append(c)

                doc.save_with_history(events)

                email_state_changed(request, doc, msg,'doc_state_edited')
                
                if new_state.slug == "approved" and new_tags == [] and has_role(request.user, "Area Director"):
                                        email_ad_approved_doc(request, doc, comment)

                if prev_state and prev_state.slug in ("ann", "rfcqueue") and new_state.slug not in ("rfcqueue", "pub"):
                    email_pulled_from_rfc_queue(request, doc, comment, prev_state, new_state)

                if new_state.slug in ("iesg-eva", "lc"):
                    if not doc.get_state_slug("draft-iana-review"):
                        doc.set_state(State.objects.get(used=True, type="draft-iana-review", slug="need-rev"))

                if new_state.slug == "lc-req":
                    request_last_call(request, doc)

                    return render(request, 'doc/draft/last_call_requested.html',
                                              dict(doc=doc,
                                                   url=doc.get_absolute_url()))

                if new_state.slug == "idexists" and doc.stream:
                    msg = "Note that this document is still in the %s stream. Please ensure the stream state settings make sense, or consider removing the document from the stream." % doc.stream.name
                    messages.info(request, msg)
                
            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        state = doc.get_state("draft-iesg")
        t = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        form = ChangeStateForm(initial=dict(state=state.pk if state else None,
                                            substate=t[0].pk if t else None),
                               user=request.user)
        form.docname=name

    state = doc.get_state("draft-iesg")
    next_states = state.next_states.all() if state else None
    prev_state = None

    hists = doc.history_set.exclude(states=doc.get_state("draft-iesg")).order_by('-time')[:1]
    if hists:
        prev_state = hists[0].get_state("draft-iesg")

    to_iesg_eval = None
    if not doc.latest_event(type="sent_ballot_announcement"):
        if next_states and next_states.filter(slug="iesg-eva"):
            to_iesg_eval = State.objects.get(used=True, type="draft-iesg", slug="iesg-eva")
            next_states = next_states.exclude(slug="iesg-eva")

    return render(request, 'doc/draft/change_state.html',
                              dict(form=form,
                                   doc=doc,
                                   state=state,
                                   prev_state=prev_state,
                                   next_states=next_states,
                                   to_iesg_eval=to_iesg_eval))

class AddIanaExpertsCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea, strip=False)

@role_required('Secretariat', 'IANA')
def add_iana_experts_comment(request, name):
    doc = get_object_or_404(Document, name = name)
    if request.method == 'POST':
        form = AddIanaExpertsCommentForm(request.POST)
        if form.is_valid():
            IanaExpertDocEvent.objects.create(doc=doc, rev=doc.rev, by=request.user.person, type="comment", desc=form.cleaned_data['comment'])
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = AddIanaExpertsCommentForm()

    return render(request, 'doc/draft/add_iana_experts_comment.html', dict(form=form, doc=doc))


class ChangeIanaStateForm(forms.Form):
    state = forms.ModelChoiceField(State.objects.all(), required=False)

    def __init__(self, state_type, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        choices = State.objects.filter(used=True, type=state_type).order_by("order").values_list("pk", "name")
        self.fields['state'].choices = [("", "-------")] + list(choices)


@role_required('Secretariat', 'IANA')
def change_iana_state(request, name, state_type):
    """Change IANA review state of Internet-Draft. Normally, this is done via
    automatic sync, but this form allows one to set it manually."""
    doc = get_object_or_404(Document, name=name)

    state_type = doc.type_id + "-" + state_type

    prev_state = doc.get_state(state_type)

    if request.method == 'POST':
        form = ChangeIanaStateForm(state_type, request.POST)
        if form.is_valid():
            new_state = form.cleaned_data['state']

            if new_state != prev_state:
                doc.set_state(new_state)

                events = [add_state_change_event(doc, request.user.person, prev_state, new_state)]

                doc.save_with_history(events)

                if state_type == 'draft-iana-experts':
                    email_iana_expert_review_state_changed(request, events)

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        form = ChangeIanaStateForm(state_type, initial=dict(state=prev_state.pk if prev_state else None))

    return render(request, 'doc/draft/change_iana_state.html',
                              dict(form=form,
                                   doc=doc))


    
class ChangeStreamForm(forms.Form):
    stream = forms.ModelChoiceField(StreamName.objects.exclude(slug="legacy"), required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False, strip=False)

@login_required
def change_stream(request, name):
    """Change the stream of a Document of type 'draft', notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(Document, name=name)
    if not doc.type_id=='draft':
        raise Http404

    if not (has_role(request.user, ("Area Director", "Secretariat")) or
            (request.user.is_authenticated and
             Role.objects.filter(name="chair",
                                 group__acronym__in=StreamName.objects.values_list("slug", flat=True),
                                 person__user=request.user))):
        permission_denied(request, "You do not have permission to view this page")

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStreamForm(request.POST)
        if form.is_valid():
            new_stream = form.cleaned_data['stream']
            comment = form.cleaned_data['comment'].strip()
            old_stream = doc.stream

            if new_stream != old_stream:
                if new_stream and new_stream.slug and new_stream.slug == "irtf":
                    if not doc.notify:
                        doc.notify = "irsg@irtf.org"
                    elif "irsg@irtf.org" not in doc.notify:
                        doc.notify += ", irsg@irtf.org"

                doc.stream = new_stream
                doc.group = Group.objects.get(type="individ")

                events = []

                e = DocEvent(doc=doc, rev=doc.rev, by=login, type='changed_document')
                e.desc = "Stream changed to <b>%s</b> from %s"% (new_stream, old_stream or "None")
                e.save()

                events.append(e)

                if comment:
                    c = DocEvent(doc=doc, rev=doc.rev, by=login, type="added_comment")
                    c.desc = comment
                    c.save()
                    events.append(c)

                doc.save_with_history(events)

                msg = "\n".join(e.desc for e in events)

                email_stream_changed(request, doc, old_stream, new_stream, msg)

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        stream = doc.stream
        form = ChangeStreamForm(initial=dict(stream=stream))

    return render(request, 'doc/draft/change_stream.html',
                              dict(form=form,
                                   doc=doc,
                                   ))

class ReplacesForm(forms.Form):
    replaces = SearchableDocumentsField(required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False, strip=False)

    def __init__(self, *args, **kwargs):
        self.doc = kwargs.pop('doc')
        super(ReplacesForm, self).__init__(*args, **kwargs)
        self.initial['replaces'] = self.doc.related_that_doc("replaces")

    def clean_replaces(self):
        for d in self.cleaned_data['replaces']:
            if d == self.doc:
                raise forms.ValidationError("An Internet-Draft can't replace itself")
            if d.type_id == "draft" and d.get_state_slug() == "rfc":
                raise forms.ValidationError("An Internet-Draft can't replace an RFC")
        return self.cleaned_data['replaces']

def replaces(request, name):
    """Change 'replaces' set of a Document of type 'draft' , notifying parties 
       as necessary and logging the change as a comment."""
    doc = get_object_or_404(Document, name=name)
    if doc.type_id != 'draft':
        raise Http404
    if not (has_role(request.user, ("Secretariat", "Area Director", "WG Chair", "RG Chair", "WG Secretary", "RG Secretary"))
            or is_authorized_in_doc_stream(request.user, doc)):
        permission_denied(request, "You do not have the necessary permissions to view this page.")

    if request.method == 'POST':
        form = ReplacesForm(request.POST, doc=doc)
        if form.is_valid():
            new_replaces = set(form.cleaned_data['replaces'])
            comment = form.cleaned_data['comment'].strip()
            old_replaces = set(doc.related_that_doc("replaces"))
            by = request.user.person

            if new_replaces != old_replaces:
                events = set_replaces_for_document(request, doc, new_replaces, by=by,
                                                   email_subject="%s replacement status updated by %s" % (doc.name, by),
                                                   comment=comment)

                doc.save_with_history(events)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = ReplacesForm(doc=doc)
    return render(request, 'doc/draft/change_replaces.html',
                  dict(form=form,
                       doc=doc,
                   ))

class SuggestedReplacesForm(forms.Form):
    replaces = ModelMultipleChoiceField(queryset=Document.objects.all(),
                                        label="Suggestions", required=False, widget=forms.CheckboxSelectMultiple,
                                        help_text="Select only the documents that are replaced by this document")
    comment = forms.CharField(label="Optional comment", widget=forms.Textarea, required=False, strip=False)

    def __init__(self, suggested, *args, **kwargs):
        super(SuggestedReplacesForm, self).__init__(*args, **kwargs)
        pks = [d.pk for d in suggested]
        self.fields["replaces"].initial = pks
        self.fields["replaces"].queryset = self.fields["replaces"].queryset.filter(pk__in=pks)
        self.fields["replaces"].choices = [(d.pk, d.name) for d in suggested]

def review_possibly_replaces(request, name):
    doc = get_object_or_404(Document, name=name)
    if doc.type_id != 'draft':
        raise Http404
    if not (has_role(request.user, ("Secretariat", "Area Director"))
            or is_authorized_in_doc_stream(request.user, doc)):
        permission_denied(request, "You do not have the necessary permissions to view this page")

    suggested = list(doc.related_that_doc("possibly-replaces"))
    if not suggested:
        raise Http404

    if request.method == 'POST':
        form = SuggestedReplacesForm(suggested, request.POST)
        if form.is_valid():
            replaces = set(form.cleaned_data['replaces'])
            old_replaces = set(doc.related_that_doc("replaces"))
            new_replaces = old_replaces.union(replaces)

            comment = form.cleaned_data['comment'].strip()
            by = request.user.person

            events = []

            # all suggestions reviewed, so get rid of them
            events.append(DocEvent.objects.create(doc=doc, rev=doc.rev, by=by, type="reviewed_suggested_replaces",
                                                  desc="Reviewed suggested replacement relationships: %s" % ", ".join(d.name for d in suggested)))
            RelatedDocument.objects.filter(source=doc, target__in=suggested,relationship__slug='possibly-replaces').delete()

            if new_replaces != old_replaces:
                events.extend(set_replaces_for_document(request, doc, new_replaces, by=by,
                                                        email_subject="%s replacement status updated by %s" % (doc.name, by),
                                                        comment=comment))

            if comment:
                events.append(DocEvent.objects.create(doc=doc, rev=doc.rev, by=by, type="added_comment", desc=comment))

            doc.save_with_history(events)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = SuggestedReplacesForm(suggested)

    return render(request, 'doc/draft/review_possibly_replaces.html',
                  dict(form=form,
                       doc=doc,
                   ))


class ChangeIntentionForm(forms.Form):
    intended_std_level = forms.ModelChoiceField(IntendedStdLevelName.objects.filter(used=True), empty_label="(None)", required=True, label="Intended RFC status")
    comment = forms.CharField(widget=forms.Textarea, required=False, strip=False)

def change_intention(request, name):
    """Change the intended publication status of a Document of type 'draft' , notifying parties 
       as necessary and logging the change as a comment."""
    doc = get_object_or_404(Document, name=name)
    if doc.type_id != 'draft':
        raise Http404

    if not (has_role(request.user, ("Secretariat", "Area Director"))
            or is_authorized_in_doc_stream(request.user, doc)):
        permission_denied(request, "You do not have the necessary permissions to view this page.")

    if request.method == 'POST':
        form = ChangeIntentionForm(request.POST)
        if form.is_valid():
            new_level = form.cleaned_data['intended_std_level']
            comment = form.cleaned_data['comment'].strip()
            old_level = doc.intended_std_level

            set_intended_status_level(request=request, doc=doc, new_level=new_level, old_level=old_level, comment=comment)

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        intended_std_level = doc.intended_std_level
        form = ChangeIntentionForm(initial=dict(intended_std_level=intended_std_level))

    return render(request, 'doc/draft/change_intended_status.html',
                              dict(form=form,
                                   doc=doc,
                                   ))


def to_iesg(request,name):
    """ Submit an IETF stream document to the IESG for publication """ 
    doc = get_object_or_404(Document, name=name, stream='ietf')

    if doc.get_state_slug('draft') == "expired" or doc.get_state_slug('draft-iesg') == 'pub-req' :
        raise Http404

    if not is_authorized_in_doc_stream(request.user, doc):
        raise Http404
    
    target_state={
        'iesg' : State.objects.get(type='draft-iesg',slug='pub-req'),
        'wg'   : State.objects.get(type='draft-stream-ietf',slug='sub-pub'),
    }

    target_map={ 
        'draft-iesg'        : 'iesg',
        'draft-stream-ietf' : 'wg'
    }

    warn={}
    if not doc.intended_std_level:
        warn['intended_std_level'] = True
    if not doc.shepherd:
        warn['shepherd'] = True
    shepherd_writeup = doc.latest_event(WriteupDocEvent, type="changed_protocol_writeup")
    if not shepherd_writeup:
        warn['shepherd_writeup'] = True
    tags = doc.tags.filter(slug__in=get_tags_for_stream_id(doc.stream_id))
    if tags:
        warn['tags'] = True
    notify = doc.notify
    if not notify:
        notify = get_initial_notify(doc)
    ad = doc.ad or getattr(doc.group.ad_role(),'person',None)

    if request.method == 'POST':

        if request.POST.get("confirm", ""): 
            by = request.user.person

            events = []
            def doc_event(type, by, doc, desc):
                return DocEvent.objects.create(type=type, by=by, doc=doc, rev=doc.rev, desc=desc)

            if doc.get_state_slug("draft-iesg") == "idexists":
                events.append(doc_event("started_iesg_process", by, doc, f"Document is now in IESG state <b>{target_state['iesg'].name}</b>"))

            # do this first, so AD becomes action holder
            if not doc.ad == ad :
                doc.ad = ad
                events.append(doc_event("changed_document", by, doc, f"Responsible AD changed to {doc.ad}"))

            for state_type in ['draft-iesg','draft-stream-ietf']:
                prev_state=doc.get_state(state_type)
                new_state = target_state[target_map[state_type]]
                if not prev_state==new_state:
                    doc.set_state(new_state)
                    e = update_action_holders(doc, prev_state, new_state)
                    if e:
                        events.append(e)
                    events.append(add_state_change_event(doc=doc,by=by,prev_state=prev_state,new_state=new_state))

            if not doc.notify == notify :
                doc.notify = notify
                events.append(doc_event("changed_document", by, doc, f"State Change Notice email list changed to {doc.notify}"))

            # Get the last available writeup
            previous_writeup = doc.latest_event(WriteupDocEvent,type="changed_protocol_writeup")
            if previous_writeup != None:
                events.append(doc_event("changed_document", by, doc, previous_writeup.text))

            doc.save_with_history(events)

            addrs= gather_address_lists('pubreq_iesg',doc=doc)
            extra = {}
            extra['Cc'] = addrs.cc
            send_mail(request=request,
                      to = addrs.to,
                      frm = on_behalf_of(by.formatted_email()),
                      subject = "Publication has been requested for %s-%s" % (doc.name,doc.rev),
                      template = "doc/submit_to_iesg_email.txt",
                      context = dict(doc=doc,by=by,url="%s%s"%(settings.IDTRACKER_BASE_URL,doc.get_absolute_url()),),
                      extra = extra)

        return HttpResponseRedirect(doc.get_absolute_url())

    return render(request, 'doc/submit_to_iesg.html',
                              dict(doc=doc,
                                   warn=warn,
                                   target_state=target_state,
                                   ad=ad,
                                   shepherd_writeup=shepherd_writeup,
                                   tags=tags,
                                   notify=notify,
                                  ))

class EditInfoForm(forms.Form):
    intended_std_level = forms.ModelChoiceField(
        IntendedStdLevelName.objects.filter(used=True),
        empty_label="(None)",
        required=True,
        label="Intended RFC status",
    )
    area = forms.ModelChoiceField(
        Group.objects.filter(type="area", state="active"),
        empty_label="(None - individual submission)",
        required=False,
        label="Assigned to area",
    )
    ad = forms.ModelChoiceField(
        Person.objects.filter(
            role__name="ad", role__group__state="active", role__group__type="area"
        ).order_by("name"),
        label="Responsible AD",
        empty_label="(None)",
        required=True,
    )
    notify = forms.CharField(
        widget=forms.Textarea,
        max_length=1023,
        label="Notice emails",
        help_text="Separate email addresses with commas.",
        required=False,
    )
    telechat_date = forms.TypedChoiceField(
        coerce=lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date(),
        empty_value=None,
        required=False,
        widget=forms.Select(attrs={"onchange": "make_bold()"}),
    )
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get("ad")
        choices = self.fields["ad"].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields["ad"].choices = list(choices) + [
                ("", "-------"),
                (ad_pk, Person.objects.get(pk=ad_pk).plain_name()),
            ]

        # telechat choices
        dates = [d.date for d in TelechatDate.objects.active().order_by("date")]
        init = kwargs["initial"]["telechat_date"]
        if init and init not in dates:
            dates.insert(0, init)

        self.fields["telechat_date"].choices = [("", "(not on agenda)")] + [
            (d, d.strftime("%Y-%m-%d")) for d in dates
        ]

        # returning item is rendered non-standard
        self.standard_fields = [
            x for x in self.visible_fields() if x.name not in ("returning_item",)
        ]


@role_required("Area Director", "Secretariat")
def edit_info(request, name):
    """Edit various Internet-Draft attributes, notifying parties as
    necessary and logging changes as document events."""
    doc = get_object_or_404(Document, name=name)
    if doc.get_state_slug() == "expired":
        raise Http404

    new_document = False
    # FIXME: should probably receive "new document" as argument to view instead of this
    if doc.get_state_slug("draft-iesg") == "idexists":
        new_document = True
        doc.notify = get_initial_notify(doc)

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    initial_telechat_date = e.telechat_date if e else None
    initial_returning_item = bool(e and e.returning_item)

    if request.method == "POST":
        form = EditInfoForm(
            request.POST,
            initial=dict(ad=doc.ad_id, telechat_date=initial_telechat_date),
        )
        if form.is_valid():
            by = request.user.person
            pubreq_state = State.objects.get(type="draft-iesg", slug="pub-req")

            r = form.cleaned_data
            events = []

            if new_document:
                doc.set_state(pubreq_state)

                # Is setting the WG state here too much of a hidden side-effect?
                if (
                    doc.stream
                    and doc.stream.slug == "ietf"
                    and doc.group
                    and doc.group.type_id == "wg"
                ):
                    submitted_state = State.objects.get(
                        type="draft-stream-ietf", slug="sub-pub"
                    )
                    doc.set_state(submitted_state)
                    e = DocEvent()
                    e.type = "changed_document"
                    e.by = by
                    e.doc = doc
                    e.rev = doc.rev
                    e.desc = "Working group state set to %s" % submitted_state.name
                    e.save()
                    events.append(e)

                replaces = Document.objects.filter(
                    targets_related__source=doc,
                    targets_related__relationship="replaces",
                )
                if replaces:
                    # this should perhaps be somewhere else, e.g. the
                    # place where the replace relationship is established?
                    e = DocEvent()
                    e.type = "added_comment"
                    e.by = Person.objects.get(name="(System)")
                    e.doc = doc
                    e.rev = doc.rev
                    e.desc = (
                        'Earlier history may be found in the Comment Log for <a href="%s">%s</a>'
                        % (replaces[0], replaces[0].get_absolute_url())
                    )
                    e.save()
                    events.append(e)

                e = DocEvent()
                e.type = "started_iesg_process"
                e.by = by
                e.doc = doc
                e.rev = doc.rev
                e.desc = (
                    "Document is now in IESG state <b>%s</b>"
                    % doc.get_state("draft-iesg").name
                )
                e.save()
                events.append(e)

            changes = []

            def desc(attr, new, old):
                entry = "%(attr)s changed to <b>%(new)s</b> from <b>%(old)s</b>"
                if new_document:
                    entry = "%(attr)s changed to <b>%(new)s</b>"

                return entry % dict(attr=attr, new=new, old=old)

            def diff(attr, name):
                v = getattr(doc, attr)
                if r[attr] != v:
                    changes.append(desc(name, r[attr], v))
                    setattr(doc, attr, r[attr])

            # update the attributes, keeping track of what we're doing
            diff("intended_std_level", "Intended Status")
            diff("ad", "Responsible AD")
            diff("notify", "State Change Notice email list")

            if doc.group.type_id in ("individ", "area"):
                if not r["area"]:
                    r["area"] = Group.objects.get(type="individ")

                if r["area"] != doc.group:
                    if r["area"].type_id == "area":
                        changes.append("Assigned to <b>%s</b>" % r["area"].name)
                    else:
                        changes.append("No longer assigned to any area")
                    doc.group = r["area"]

            for c in changes:
                events.append(
                    DocEvent.objects.create(
                        doc=doc, rev=doc.rev, by=by, desc=c, type="changed_document"
                    )
                )

            # Todo - chase this
            e = update_telechat(
                request, doc, by, r["telechat_date"], r["returning_item"]
            )
            if e:
                events.append(e)

            doc.save_with_history(events)

            if new_document:
                # If we created a new doc, update the action holders as though it
                # started in idexists and moved to pub-req. Do this
                # after the doc has been updated so, e.g., doc.ad is set.
                update_action_holders(
                    doc,
                    State.objects.get(type="draft-iesg", slug="idexists"),
                    pubreq_state,
                )

            if changes:
                email_iesg_processing_document(request, doc, changes)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        init = dict(
            intended_std_level=doc.intended_std_level_id,
            area=doc.group_id,
            ad=doc.ad_id,
            notify=doc.notify,
            telechat_date=initial_telechat_date,
            returning_item=initial_returning_item,
        )

        form = EditInfoForm(initial=init)

    # optionally filter out some fields
    if doc.group.type_id not in ("individ", "area"):
        form.standard_fields = [x for x in form.standard_fields if x.name != "area"]

    return render(
        request,
        "doc/draft/edit_info.html",
        dict(
            doc=doc,
            form=form,
            user=request.user,
            ballot_issued=doc.latest_event(type="sent_ballot_announcement"),
        ),
    )

@role_required('Area Director','Secretariat')
def request_resurrect(request, name):
    """Request resurrect of expired Internet-Draft."""
    doc = get_object_or_404(Document, name=name)
    if doc.get_state_slug() != "expired":
        raise Http404

    if request.method == 'POST':
        by = request.user.person

        email_resurrect_requested(request, doc, by)
        
        e = DocEvent(doc=doc, rev=doc.rev, by=by)
        e.type = "requested_resurrect"
        e.desc = "Resurrection was requested"
        e.save()
        
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render(request, 'doc/draft/request_resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()))

@role_required('Secretariat')
def resurrect(request, name):
    """Resurrect expired Internet-Draft."""
    doc = get_object_or_404(Document, name=name)
    if doc.get_state_slug() != "expired":
        raise Http404

    resurrect_requested_by = None
    e = doc.latest_event(type__in=('requested_resurrect', "completed_resurrect"))
    if e and e.type == 'requested_resurrect':
        resurrect_requested_by = e.by

    if request.method == 'POST':
        if resurrect_requested_by:
            email_resurrection_completed(request, doc, requester=resurrect_requested_by)

        events = []
        e = DocEvent(doc=doc, rev=doc.rev, by=request.user.person)
        e.type = "completed_resurrect"
        e.desc = "Resurrection was completed"
        e.save()
        events.append(e)

        doc.set_state(State.objects.get(used=True, type="draft", slug="active"))
        doc.expires = timezone.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)
        doc.save_with_history(events)

        restore_draft_file(request, doc)

        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render(request, 'doc/draft/resurrect.html',
                              dict(doc=doc,
                                   resurrect_requested_by=resurrect_requested_by,
                                   back_url=doc.get_absolute_url()))


def restore_draft_file(request, draft):
    '''restore latest revision document file from archive'''
    basename = '{}-{}'.format(draft.name, draft.rev)
    files = glob.glob(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, basename) + '.*')
    log.log("Resurrecting %s.  Moving files:" % draft.name)
    for file in files:
        try:
            # ghostlinkd would keep this in the combined all archive since it would
            # be sourced from a different place. But when ghostlinkd is removed, nothing
            # new is needed here - the file will already exist in the combined archive
            shutil.move(file, settings.INTERNET_DRAFT_PATH)
            log.log("  Moved file %s to %s" % (file, settings.INTERNET_DRAFT_PATH))
        except shutil.Error as ex:
            messages.warning(request, 'There was an error restoring the Internet-Draft file: {} ({})'.format(file, ex))
            log.log("  Exception %s when attempting to move %s" % (ex, file))


class ShepherdWriteupUploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Shepherd writeup", help_text="Edit the shepherd writeup.", required=False, strip=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file.", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])


@login_required
def edit_shepherd_writeup(request, name):
    """Change this document's shepherd writeup"""
    doc = get_object_or_404(Document, type="draft", name=name)

    can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
    can_edit_shepherd_writeup = (
        can_edit_stream_info
        or (doc.shepherd and user_is_person(request.user, doc.shepherd.person))
        or has_role(request.user, ["Area Director"])
    )

    if not can_edit_shepherd_writeup:
        permission_denied(
            request, "You do not have the necessary permissions to view this page"
        )

    login = request.user.person

    if request.method == "POST":
        if "submit_response" in request.POST:
            form = ShepherdWriteupUploadForm(request.POST, request.FILES)
            if form.is_valid():

                from_file = form.cleaned_data["txt"]
                if from_file:
                    writeup = from_file
                else:
                    writeup = form.cleaned_data["content"]
                e = WriteupDocEvent(
                    doc=doc, rev=doc.rev, by=login, type="changed_protocol_writeup"
                )

                # Add the shepherd writeup to description,
                # if the document is in submitted for publication state
                stream_state = doc.get_state("draft-stream-%s" % doc.stream_id)
                iesg_state = doc.get_state("draft-iesg")
                if iesg_state or (stream_state and stream_state.slug == "sub-pub"):
                    e.desc = writeup
                else:
                    e.desc = "Changed document writeup"

                e.text = writeup
                e.save()

                return redirect("ietf.doc.views_doc.document_main", name=doc.name)

        elif "reset_text" in request.POST:
            if not doc.group.type.slug or doc.group.type.slug != "wg":
                generate_type = "individ"
            else:
                generate_type = "group"           
            init = {
                "content": render_to_string(
                    "doc/shepherd_writeup.txt",
                    dict(
                        doc=doc,
                        type=generate_type,
                        stream=doc.stream.slug,
                        group=doc.group.type.slug,
                    ),
                )
            }
            form = ShepherdWriteupUploadForm(initial=init)

        # Protect against handcrufted malicious posts
        else:
            form = None

    else:
        form = None

    if not form:
        init = {"content": ""}

        previous_writeup = doc.latest_event(
            WriteupDocEvent, type="changed_protocol_writeup"
        )
        if previous_writeup:
            init["content"] = previous_writeup.text
        else:
            if not doc.group.type.slug or doc.group.type.slug != "wg":
                generate_type = "individ"
            else:
                generate_type = "group"
            init["content"] = render_to_string(
                "doc/shepherd_writeup.txt",
                dict(
                    doc=doc,
                    type=generate_type,
                    stream=doc.stream.slug,
                    group=doc.group.type.slug,
                ),
            )
        form = ShepherdWriteupUploadForm(initial=init)

    return render(
        request,
        "doc/draft/change_shepherd_writeup.html",
        {
            "form": form,
            "doc": doc,
        },
    )


class ShepherdForm(forms.Form):
    shepherd = SearchableEmailField(required=False, only_users=True)

def edit_shepherd(request, name):
    """Change the shepherd for a Document"""
    # TODO - this shouldn't be type="draft" specific
    doc = get_object_or_404(Document, type="draft", name=name)

    can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
    if not can_edit_stream_info:
        permission_denied(request, "You do not have the necessary permissions to view this page.")

    if request.method == 'POST':
        form = ShepherdForm(request.POST)
        if form.is_valid():

            if form.cleaned_data['shepherd'] != doc.shepherd:
                events = []

                doc.shepherd = form.cleaned_data['shepherd']
                if doc.shepherd and not doc.shepherd.origin:
                    doc.shepherd.origin = 'shepherd: %s' % doc.name
                    doc.shepherd.save()

                c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
                c.desc = "Document shepherd changed to "+ (doc.shepherd.person.name if doc.shepherd else "(None)")
                c.save()
                events.append(c)
    
                if doc.shepherd and (doc.shepherd.address not in doc.notify):
                    addrs = doc.notify
                    if addrs:
                        addrs += ', '
                    addrs += doc.shepherd.address
                    c = make_notify_changed_event(request, doc, request.user.person, addrs, c.time)
                    c.desc += " because the document shepherd was set"
                    c.save()
                    events.append(c)
                    doc.notify = addrs
    
                doc.save_with_history(events)

            else:
                messages.info(request,"The selected shepherd was already assigned - no changes have been made.")

            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        form = ShepherdForm(initial={ "shepherd": doc.shepherd_id })

    return render(request, 'doc/change_shepherd.html', {
        'form': form,
        'doc': doc,
    })

class ChangeShepherdEmailForm(forms.Form):
    shepherd = forms.ModelChoiceField(queryset=Email.objects.all(), label="Shepherd email", empty_label=None)

    def __init__(self, *args, **kwargs):
        super(ChangeShepherdEmailForm, self).__init__(*args, **kwargs)
        self.fields["shepherd"].queryset = self.fields["shepherd"].queryset.filter(person__email=self.initial["shepherd"]).distinct()
    
def change_shepherd_email(request, name):
    """Change the shepherd email address for a Document"""
    doc = get_object_or_404(Document, name=name)

    if not doc.shepherd:
        raise Http404

    can_edit_stream_info = is_authorized_in_doc_stream(request.user, doc)
    is_shepherd = user_is_person(request.user, doc.shepherd and doc.shepherd.person)
    if not can_edit_stream_info and not is_shepherd:
        permission_denied(request, "You do not have the necessary permissions to view this page")

    initial = { "shepherd": doc.shepherd_id }
    if request.method == 'POST':
        form = ChangeShepherdEmailForm(request.POST, initial=initial)
        if form.is_valid():
            if form.cleaned_data['shepherd'] != doc.shepherd:
                doc.shepherd = form.cleaned_data['shepherd']

                events = []
                c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
                c.desc = "Document shepherd email changed"
                c.save()
                events.append(c)

                doc.save_with_history(events)
            else:
                messages.info(request,"The selected shepherd address was already assigned - no changes have been made.")

            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        form = ChangeShepherdEmailForm(initial=initial)

    return render(request, 'doc/change_shepherd_email.html', {
        'form': form,
        'doc': doc,
    })

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(
        Person.objects.filter(
            role__name__in=("ad", "pre-ad"),
            role__group__state="active",
            role__group__type="area",
        ).order_by('name'),
        label="Shepherding AD",
        empty_label="(None)",
        required=False,
    )

    def __init__(self, doc, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.doc = doc
        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

    def clean_ad(self):
        ad = self.cleaned_data['ad']
        state = self.doc.get_state('draft-iesg')
        if not ad:
            if state.slug not in ['idexists','dead']:
                raise forms.ValidationError("Internet-Drafts in state %s must have an assigned AD." % state)
        return ad

@role_required("Area Director", "Secretariat")
def edit_ad(request, name):
    """Change the shepherding Area Director for this draft."""

    doc = get_object_or_404(Document, type="draft", name=name)

    if request.method == 'POST':
        form = AdForm(doc, request.POST)
        if form.is_valid():
            new_ad = form.cleaned_data['ad']
            if new_ad != doc.ad:
                doc.ad = new_ad

                c = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=request.user.person)
                c.desc = "Shepherding AD changed to "+doc.ad.name if doc.ad else "None"
                c.save()

                doc.save_with_history([c])
    
            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        init = { "ad" : doc.ad_id }
        form = AdForm(doc, initial=init)

    return render(request, 'doc/draft/change_ad.html',
                    {'form':   form,
                     'doc': doc,
                    },
                 )

class ConsensusForm(forms.Form):
    consensus = forms.ChoiceField(choices=(("Unknown", "Unknown"), ("Yes", "Yes"), ("No", "No")),
                  required=True, label="When published as an RFC, should the consensus boilerplate be included?")

def edit_consensus(request, name):
    """When this draft is published as an RFC, should it include the consensus boilerplate or not."""

    doc = get_object_or_404(Document, type="draft", name=name)

    if not (has_role(request.user, ("Secretariat", "Area Director"))
            or is_authorized_in_doc_stream(request.user, doc)):
        permission_denied(request, "You do not have the necessary permissions to view this page.")

    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
    prev_consensus = e.consensus if e else default_consensus(doc)

    if request.method == 'POST':
        form = ConsensusForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["consensus"] != prev_consensus:
                e = ConsensusDocEvent(doc=doc, rev=doc.rev, type="changed_consensus", by=request.user.person)
                e.consensus = {"Unknown":None,"Yes":True,"No":False}[form.cleaned_data["consensus"]]
                if not e.consensus and doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
                    permission_denied(request, "BCPs and Standards Track documents must include the consensus boilerplate.")

                e.desc = "Changed consensus to <b>%s</b> from %s" % (nice_consensus(e.consensus),
                                                                     nice_consensus(prev_consensus))

                e.save()

            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        form = ConsensusForm(initial=dict(consensus=nice_consensus(prev_consensus)))

    return render(request, 'doc/draft/change_consensus.html',
                              {'form': form,
                               'doc': doc,
                              },
                          )


def edit_doc_extresources(request, name):
    doc = get_object_or_404(Document, name=name)

    if not can_edit_docextresources(request.user, doc):
        permission_denied(request, "You do not have the necessary permissions to view this page.")

    if request.method == 'POST':
        form = ExtResourceForm(request.POST)
        if form.is_valid():
            if update_doc_extresources(doc, form.cleaned_data['resources'], by=request.user.person):
                messages.success(request,"Document resources updated.")
            else:
                messages.info(request,"No change in Document resources.")
            return redirect('ietf.doc.views_doc.document_main', name=doc.name)
    else:
        form = ExtResourceForm(initial={'resources': doc.docextresource_set.all()})

    info = "Valid tags:<br><br> %s" % ', '.join(form.valid_resource_tags())
    # May need to explain the tags more - probably more reason to move to a formset.
    title = "Additional document resources"
    return render(request, 'doc/edit_field.html',dict(doc=doc, form=form, title=title, info=info) )


def request_publication(request, name):
    """Request publication by RFC Editor for a document which hasn't
    been through the IESG ballot process."""

    class PublicationForm(forms.Form):
        subject = forms.CharField(max_length=200, required=True)
        body = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    doc = get_object_or_404(Document, type="draft", name=name, stream__in=("iab", "ise", "irtf", "editorial"))

    if not can_request_rfc_publication(request.user, doc):
        permission_denied(request, "You do not have the necessary permissions to view this page.")
 
    consensus_event = doc.latest_event(ConsensusDocEvent, type="changed_consensus")

    m = Message()
    m.frm = request.user.person.formatted_email()
    (m.to, m.cc) = gather_address_lists('pubreq_rfced',doc=doc).as_strings()
    m.by = request.user.person

    next_state = State.objects.get(used=True, type="draft-stream-%s" % doc.stream.slug, slug="rfc-edit")

    if request.method == 'POST' and not request.POST.get("reset"):
        form = PublicationForm(request.POST)
        if form.is_valid():
            events = []

            # start by notifying the RFC Editor
            import ietf.sync.rfceditor
            response, error = ietf.sync.rfceditor.post_approved_draft(settings.RFC_EDITOR_SYNC_NOTIFICATION_URL, doc.name)
            if error:
                return render(request, 'doc/draft/rfceditor_post_approved_draft_failed.html',
                                  dict(name=doc.name,
                                       response=response,
                                       error=error))

            m.subject = form.cleaned_data["subject"]
            m.body = form.cleaned_data["body"]
            m.save()

            if doc.group.acronym != "none":
                m.related_groups.set([doc.group])
            m.related_docs.set([doc])

            send_mail_message(request, m)

            # IANA copy
            (m.to, m.cc) = gather_address_lists('pubreq_rfced_iana',doc=doc).as_strings()
            send_mail_message(request, m, extra=extra_automation_headers(doc))

            e = DocEvent(doc=doc, type="requested_publication", rev=doc.rev, by=request.user.person)
            e.desc = "Sent request for publication to the RFC Editor"
            e.save()
            events.append(e)

            # change state
            prev_state = doc.get_state(next_state.type_id)
            if next_state != prev_state:
                doc.set_state(next_state)
                e = add_state_change_event(doc, request.user.person, prev_state, next_state)
                if e:
                    events.append(e)
                doc.save_with_history(events)

            return redirect('ietf.doc.views_doc.document_main', name=doc.name)

    else:
        if doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
            action = "Protocol Action"
        else:
            action = "Document Action"

        from ietf.doc.templatetags.mail_filters import std_level_prompt

        subject = "%s: '%s' to %s (%s-%s.txt)" % (action, doc.title, std_level_prompt(doc), doc.name, doc.rev)

        body = generate_publication_request(request, doc)

        form = PublicationForm(initial=dict(subject=subject,
                                            body=body))

    return render(request, 'doc/draft/request_publication.html',
                              dict(form=form,
                                   doc=doc,
                                   message=m,
                                   next_state=next_state,
                                   consensus_filled_in=(
                                       True if (doc.stream_id and doc.stream_id=='ietf')
                                       else (consensus_event != None and consensus_event.consensus != None)),
                               ),
                          )

class AdoptDraftForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(type__features__acts_like_wg=True, state="active")
        .order_by("-type", "acronym")
        .distinct(),
        required=True,
        empty_label=None,
    )
    newstate = forms.ModelChoiceField(
        queryset=State.objects.filter(
            type__in=[
                "draft-stream-ietf",
                "draft-stream-irtf",
                "draft-stream-editorial",
            ],
            used=True,
        ).exclude(slug__in=settings.GROUP_STATES_WITH_EXTRA_PROCESSING),
        required=True,
        label="State",
    )
    comment = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Comment",
        help_text="Optional comment explaining the reasons for the adoption.",
        strip=False,
    )
    weeks = forms.IntegerField(required=False, label="Expected weeks in adoption state")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(AdoptDraftForm, self).__init__(*args, **kwargs)

        docman_roles = {}
        for group_type in ("wg", "ag", "rg", "rag", "edwg"):
            docman_roles[group_type] = GroupFeatures.objects.get(
                type_id=group_type
            ).docman_roles

        state_types = set()
        if has_role(user, "Secretariat"):
            state_types.update(
                ["draft-stream-ietf", "draft-stream-irtf", "draft-stream-editorial"]
            )
        else:
            if has_role(user, "IRTF Chair") or any(
                [
                    Group.objects.filter(
                        type=type_id,
                        state="active",
                        role__person__user=user,
                        role__name__in=docman_roles[type_id],
                    ).exists()
                    for type_id in ("rg", "rag")
                ]
            ):
                state_types.add("draft-stream-irtf")
            if any(
                [
                    Group.objects.filter(
                        type=type_id,
                        state="active",
                        role__person__user=user,
                        role__name__in=docman_roles[type_id],
                    ).exists()
                    for type_id in ("wg", "ag")
                ]
            ):
                state_types.add("draft-stream-ietf")
            if Group.objects.filter(
                type="edwg",
                state="active",
                role__person__user=user,
                role__name__in=docman_roles["edwg"],
            ).exists():
                state_types.add("draft-stream-editorial")

        state_choices = State.objects.filter(type__in=state_types, used=True).exclude(
            slug__in=settings.GROUP_STATES_WITH_EXTRA_PROCESSING
        )

        if not has_role(user, "Secretariat"):
            allow_matching_groups = []
            if has_role(user, "IRTF Chair"):
                allow_matching_groups.append(Q(type__in=["rg", "rag"]))
            for type_id in docman_roles:
                allow_matching_groups.append(
                    Q(
                        role__person__user=user,
                        role__name__in=docman_roles[type_id],
                        type_id=type_id,
                    )
                )
            combined_query = Q(pk__in=[]) # Never use Q() here when following this pattern
            for query in allow_matching_groups:
                combined_query |= query
        
            self.fields["group"].queryset = self.fields["group"].queryset.filter(combined_query)

        self.fields["group"].choices = [
            (g.pk, "%s - %s" % (g.acronym, g.name))
            for g in self.fields["group"].queryset
        ]
        self.fields["newstate"].choices = [("", "-- Pick a state --")]
        self.fields["newstate"].choices.extend(
            [
                (x.pk, x.name + " (IETF)")
                for x in state_choices
                if x.type_id == "draft-stream-ietf"
            ]
        )
        self.fields["newstate"].choices.extend(
            [
                (x.pk, x.name + " (IRTF)")
                for x in state_choices
                if x.type_id == "draft-stream-irtf"
            ]
        )
        self.fields["newstate"].choices.extend(
            [
                (x.pk, x.name + " (Editorial)")
                for x in state_choices
                if x.type_id == "draft-stream-editorial"
            ]
        )

    def clean_newstate(self):
        group = self.cleaned_data["group"]
        newstate = self.cleaned_data["newstate"]

        ok_to_assign = (
            ("draft-stream-ietf", ("wg", "ag")),
            ("draft-stream-irtf", ("rg", "rag")),
            ("draft-stream-editorial", ("edwg",)),
        )
        ok = True
        for stream, types in ok_to_assign:
            if newstate.type_id == stream and group.type_id not in types:
                ok = False
                break
        if not ok:
            state_type_text = newstate.type_id.split("-")[-1].upper()
            group_type_text = {
                "wg": "IETF Working Group",
                "ag": "IETF Area Group",
                "rg": "IRTF Research Group",
                "rag": "IRTF Area Group",
                "edwg": "Editorial Stream Working Group",
            }[group.type_id]
            raise forms.ValidationError(
                f"Cannot assign {state_type_text} state to a {group_type_text}"
            )
        return newstate


@login_required
def adopt_draft(request, name):
    doc = get_object_or_404(Document, type="draft", name=name)
    if not can_adopt_draft(request.user, doc):
        permission_denied(request, "You don't have permission to access this page.")

    if request.method == 'POST':
        form = AdoptDraftForm(request.POST, user=request.user)

        if form.is_valid():
            # adopt
            by = request.user.person
            events = []

            group = form.cleaned_data["group"]
            if group.type.slug in ("rg", "rag"):
                new_stream = StreamName.objects.get(slug="irtf") 
            elif group.type.slug =="edwg":
                new_stream = StreamName.objects.get(slug="editorial")               
            else:
                new_stream = StreamName.objects.get(slug="ietf")                

            new_state = form.cleaned_data["newstate"]

            # stream
            if doc.stream != new_stream:
                e = DocEvent(type="changed_stream", doc=doc, rev=doc.rev, by=by)
                e.desc = "Changed stream to <b>%s</b>" % new_stream.name
                if doc.stream:
                    e.desc += " from %s" % doc.stream.name
                e.save()
                events.append(e)
                old_stream = doc.stream
                doc.stream = new_stream
                if old_stream != None:
                    email_stream_changed(request, doc, old_stream, new_stream)

                # Force intended std level here if stream isn't ietf
                if new_stream.slug != "ietf":
                    old_level = doc.intended_std_level
                    new_level = IntendedStdLevelName.objects.get(slug="inf", used=True)
                    set_intended_status_level(request=request, doc=doc, new_level=new_level, old_level=old_level, comment="")


            # group
            if group != doc.group:
                e = DocEvent(type="changed_group", doc=doc, rev=doc.rev, by=by)
                e.desc = "Changed group to <b>%s (%s)</b>" % (group.name, group.acronym.upper())
                if doc.group.type_id != "individ":
                    e.desc += " from %s (%s)" % (doc.group.name, doc.group.acronym.upper())
                e.save()
                events.append(e)
                doc.group = group

            new_notify = get_initial_notify(doc,extra=doc.notify)
            events.append(make_notify_changed_event(request, doc, by, new_notify))
            doc.notify = new_notify

            comment = form.cleaned_data["comment"].strip()

            # state
            prev_state = doc.get_state("draft-stream-%s" % doc.stream_id)
            if new_state != prev_state:
                doc.set_state(new_state)
                e = add_state_change_event(doc, by, prev_state, new_state)
                events.append(e)

                due_date = None
                if form.cleaned_data["weeks"] != None:
                    due_date = datetime_today(DEADLINE_TZINFO) + datetime.timedelta(weeks=form.cleaned_data["weeks"])

                update_reminder(doc, "stream-s", e, due_date)

                email_adopted(request, doc, prev_state, new_state, by, comment)

            # comment
            if comment:
                e = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=by)
                e.desc = comment
                e.save()
                events.append(e)

            doc.save_with_history(events)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = AdoptDraftForm(user=request.user)

    return render(request, 'doc/draft/adopt_draft.html',
                              {'doc': doc,
                               'form': form,
                              })

class ReleaseDraftForm(forms.Form):
    comment = forms.CharField(widget=forms.Textarea, required=False, label="Comment", help_text="Optional comment explaining the reasons for releasing the document." )

@login_required
def release_draft(request, name):
    doc = get_object_or_404(Document, type="draft", name=name)

    if doc.get_state_slug('draft-iesg') != 'idexists':
        raise Http404

    if not can_unadopt_draft(request.user, doc):
        permission_denied(request, "You don't have permission to access this page.")

    if request.method == 'POST':
        form = ReleaseDraftForm(request.POST)
        if form.is_valid():
            comment = form.cleaned_data["comment"]
            by = request.user.person
            events = []

            if doc.stream.slug == 'ise' or doc.group.type_id != 'individ':
                existing_tags = list(doc.tags.all())
                if existing_tags:
                    doc.tags.clear()
                    e = DocEvent(type="changed_document", doc=doc, rev=doc.rev, by=by)
                    l = []
                    l.append("Tag%s %s cleared." % (pluralize(existing_tags), ", ".join(t.name for t in existing_tags)))
                    e.desc = " ".join(l)
                    e.save()
                    events.append(e)
                    email_stream_tags_changed(request, doc, set(), existing_tags, by, comment)

                prev_state = doc.get_state("draft-stream-%s" % doc.stream_id)
                if prev_state:
                    doc.unset_state("draft-stream-%s" % doc.stream_id)
                    e = StateDocEvent(doc=doc, rev=doc.rev, by=by)
                    e.type = "changed_state"
                    e.state_type = (prev_state).type
                    e.state = None
                    e.desc = "State changed to <b>None</b> from %s" % prev_state.name 
                    e.save()
                    events.append(e)
                    email_state_changed(request,doc,e.desc)

                if doc.stream.slug != 'ise':
                    old_group = doc.group
                    doc.group = Group.objects.get(acronym='none')
                    e = DocEvent(type="changed_document", doc=doc, rev=doc.rev, by=by)
                    e.desc = "Document removed from group %s." % old_group.acronym.upper()

            if doc.stream:
                e = DocEvent(type="changed_stream", doc=doc, rev=doc.rev, by=by)
                e.desc = "Changed stream to <b>None</b> from %s" % doc.stream.name
                e.save()
                events.append(e)
                old_stream = doc.stream
                doc.stream = None
                email_stream_changed(request, doc, old_stream, None)

            if comment:
                e = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=by)
                e.desc = comment
                e.save()
                events.append(e)

            doc.save_with_history(events)
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        form = ReleaseDraftForm()

    return render(request, 'doc/draft/release_draft.html', {'doc':doc, 'form':form })


class ChangeStreamStateForm(forms.Form):
    new_state = forms.ModelChoiceField(queryset=State.objects.filter(used=True), label='State' )
    weeks = forms.IntegerField(label='Expected weeks in state',required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional comment for the document history.", strip=False)
    tags = ModelMultipleChoiceField(queryset=DocTagName.objects.filter(used=True), widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, **kwargs):
        doc = kwargs.pop("doc")
        state_type = kwargs.pop("state_type")
        self.can_set_sub_pub = kwargs.pop("can_set_sub_pub")
        self.stream = kwargs.pop("stream")
        super(ChangeStreamStateForm, self).__init__(*args, **kwargs)

        f = self.fields["new_state"]
        f.queryset = f.queryset.filter(type=state_type)
        if doc.group:
            unused_states = doc.group.unused_states.values_list("pk", flat=True)
            f.queryset = f.queryset.exclude(pk__in=unused_states)
        f.label = state_type.label
        if self.stream.slug == 'ietf':
            if self.can_set_sub_pub:
                f.help_text = "Only select 'Submitted to IESG for Publication' to correct errors. Use the document's main page to request publication."
            else:
                f.queryset = f.queryset.exclude(slug='sub-pub')
                f.help_text = "You may not set the 'Submitted to IESG for Publication' using this form - Use the document's main page to request publication."

        f = self.fields['tags']
        f.queryset = f.queryset.filter(slug__in=get_tags_for_stream_id(doc.stream_id))
        if doc.group:
            unused_tags = doc.group.unused_tags.values_list("pk", flat=True)
            f.queryset = f.queryset.exclude(pk__in=unused_tags)

    def clean_new_state(self):
        new_state = self.cleaned_data.get('new_state')
        if new_state.slug=='sub-pub' and not self.can_set_sub_pub:
            raise forms.ValidationError('You may not set the %s state using this form. Use the "Submit to IESG for publication" button on the document\'s main page instead. If that button does not appear, the document may already have IESG state. Ask your Area Director or the Secretariat for help.'%new_state.name)
        return new_state
         

def next_states_for_stream_state(doc, state_type, current_state):
    # find next states
    next_states = []
    if current_state:
        next_states = current_state.next_states.all()

        if doc.stream_id == "ietf" and doc.group:
            transitions = doc.group.groupstatetransitions_set.filter(state=current_state)
            if transitions:
                next_states = transitions[0].next_states.all()
    else:
        # return the initial state
        states = State.objects.filter(used=True, type=state_type).order_by('order')
        if states:
            next_states = states[:1]

    if doc.group:
        unused_states = doc.group.unused_states.values_list("pk", flat=True)
        next_states = [n for n in next_states if n.pk not in unused_states]

    return next_states

@login_required
def change_stream_state(request, name, state_type):
    doc = get_object_or_404(Document, type="draft", name=name)
    if not doc.stream:
        raise Http404

    state_type = get_object_or_404(StateType, slug=state_type)

    if not is_authorized_in_doc_stream(request.user, doc):
        permission_denied(request, "You don't have permission to access this page.")

    prev_state = doc.get_state(state_type.slug)
    next_states = next_states_for_stream_state(doc, state_type, prev_state)

    can_set_sub_pub = has_role(request.user,('Secretariat','Area Director')) or (prev_state and prev_state.slug=='sub-pub')

    if request.method == 'POST':
        form = ChangeStreamStateForm(request.POST, doc=doc, state_type=state_type,can_set_sub_pub=can_set_sub_pub,stream=doc.stream)
        if form.is_valid():
            by = request.user.person
            events = []

            comment = form.cleaned_data["comment"].strip()

            # state
            new_state = form.cleaned_data["new_state"]
            if new_state != prev_state:
                doc.set_state(new_state)
                e = add_state_change_event(doc, by, prev_state, new_state)
                events.append(e)

                due_date = None
                if form.cleaned_data["weeks"] != None:
                    due_date = datetime_today(DEADLINE_TZINFO) + datetime.timedelta(weeks=form.cleaned_data["weeks"])

                update_reminder(doc, "stream-s", e, due_date)

                email_stream_state_changed(request, doc, prev_state, new_state, by, comment)

            # tags
            existing_tags = set(doc.tags.all())
            new_tags = set(form.cleaned_data["tags"])

            if existing_tags != new_tags:
                doc.tags.clear()
                doc.tags.set(new_tags)

                e = DocEvent(type="changed_document", doc=doc, rev=doc.rev, by=by)
                added_tags = new_tags - existing_tags
                removed_tags = existing_tags - new_tags
                l = []
                if added_tags:
                    l.append("Tag%s %s set." % (pluralize(added_tags), ", ".join(t.name for t in added_tags)))
                if removed_tags:
                    l.append("Tag%s %s cleared." % (pluralize(removed_tags), ", ".join(t.name for t in removed_tags)))
                e.desc = " ".join(l)
                e.save()
                events.append(e)

                email_stream_tags_changed(request, doc, added_tags, removed_tags, by, comment)

            # comment
            if comment:
                e = DocEvent(type="added_comment", doc=doc, rev=doc.rev, by=by)
                e.desc = comment
                e.save()
                events.append(e)

            if events:
                doc.save_with_history(events)
                return HttpResponseRedirect(doc.get_absolute_url())
            else:
                form.add_error(None, "No change in state or tags found, and no comment provided -- nothing to do.")
    else:
        form = ChangeStreamStateForm(initial=dict(new_state=prev_state.pk if prev_state else None, tags= doc.tags.all()),
                                     doc=doc, state_type=state_type, can_set_sub_pub = can_set_sub_pub,stream = doc.stream)

    milestones = doc.groupmilestone_set.all()


    return render(request, "doc/draft/change_stream_state.html",
                              {"doc": doc,
                               "form": form,
                               "milestones": milestones,
                               "state_type": state_type,
                               "next_states": next_states,
                              })

# This should be in ietf.doc.utils, but placing it there brings a circular import issue with ietf.doc.mail
def set_intended_status_level(request, doc, new_level, old_level, comment):
    if new_level != old_level:
        doc.intended_std_level = new_level

        events = []
        e = DocEvent(doc=doc, rev=doc.rev, by=request.user.person, type='changed_document')
        e.desc = "Intended Status changed to <b>%s</b> from %s"% (new_level,old_level) 
        e.save()
        events.append(e)

        if comment:
            c = DocEvent(doc=doc, rev=doc.rev, by=request.user.person, type="added_comment")
            c.desc = comment
            c.save()
            events.append(c)

        de = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
        prev_consensus = de and de.consensus
        if not prev_consensus and doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
            ce = ConsensusDocEvent(doc=doc, rev=doc.rev, by=request.user.person, type="changed_consensus")
            ce.consensus = True
            ce.desc = "Changed consensus to <b>%s</b> from %s" % (nice_consensus(True),
                                                                    nice_consensus(prev_consensus))
            ce.save()
            events.append(ce)

        doc.save_with_history(events)

        msg = "\n".join(e.desc for e in events)

        email_intended_status_changed(request, doc, msg)
