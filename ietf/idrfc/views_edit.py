# changing state and metadata and commenting on Internet Drafts for
# Area Directors and Secretariat

import re, os
from datetime import datetime, date, time, timedelta
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse as urlreverse
from django.template.loader import render_to_string
from django.template import RequestContext
from django import forms
from django.utils.html import strip_tags
from django.db.models import Max
from django.conf import settings
from django.forms.util import ErrorList

from ietf.utils.mail import send_mail_text, send_mail_message
from ietf.ietfauth.decorators import group_required
from ietf.idtracker.templatetags.ietf_filters import in_group
from ietf.ietfauth.decorators import has_role, role_required
from ietf.idtracker.models import *
from ietf.iesg.models import *
from ietf.idrfc.mails import *
from ietf.idrfc.utils import *
from ietf.idrfc.lastcall import request_last_call

from ietf.ietfworkflows.models import Stream
from ietf.ietfworkflows.utils import update_stream
from ietf.ietfworkflows.streams import get_stream_from_draft
from ietf.ietfworkflows.accounts import can_edit_state

from ietf.doc.models import *
from ietf.doc.utils import *
from ietf.name.models import IntendedStdLevelName, DocTagName, StreamName
from ietf.person.models import Person, Email
from ietf.message.models import Message
from ietf.idrfc.utils import log_state_changed

class ChangeStateForm(forms.Form):
    pass

@group_required('Area_Director','Secretariat')
def change_state(request, name):
    pass

IESG_SUBSTATE_TAGS = ('point', 'ad-f-up', 'need-rev', 'extpty')

class ChangeStateFormREDESIGN(forms.Form):
    state = forms.ModelChoiceField(State.objects.filter(used=True, type="draft-iesg"), empty_label=None, required=True)
    substate = forms.ModelChoiceField(DocTagName.objects.filter(slug__in=IESG_SUBSTATE_TAGS), required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        retclean = self.cleaned_data
        state = self.cleaned_data.get('state', '(None)')
        tag = self.cleaned_data.get('substate','')
        comment = self.cleaned_data['comment'].strip()
        doc = get_object_or_404(Document, docalias__name=self.docname)
        prev = doc.get_state("draft-iesg")
    
        # tag handling is a bit awkward since the UI still works
        # as if IESG tags are a substate
        prev_tag = doc.tags.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))
        prev_tag = prev_tag[0] if prev_tag else None

        if state == prev and tag == prev_tag:
            self._errors['comment'] = ErrorList([u'State not changed. Comments entered will be lost with no state change. Please go back and use the Add Comment feature on the history tab to add comments without changing state.'])
        return retclean

@group_required('Area_Director','Secretariat')
def change_stateREDESIGN(request, name):
    """Change state of Internet Draft, notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(Document, docalias__name=name)
    if (not doc.latest_event(type="started_iesg_process")) or doc.get_state_slug() == "expired":
        raise Http404()

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStateForm(request.POST)
        form.docname=name
        if form.is_valid():
            next_state = form.cleaned_data['state']
            prev_state = doc.get_state("draft-iesg")

            tag = form.cleaned_data['substate']
            comment = form.cleaned_data['comment'].strip()

            # tag handling is a bit awkward since the UI still works
            # as if IESG tags are a substate
            prev_tag = doc.tags.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))
            prev_tag = prev_tag[0] if prev_tag else None

            if next_state != prev_state or tag != prev_tag:
                save_document_in_history(doc)
                
                doc.set_state(next_state)

                if prev_tag:
                    doc.tags.remove(prev_tag)

                if tag:
                    doc.tags.add(tag)

                e = log_state_changed(request, doc, login, prev_state, prev_tag)

                if comment:
                    c = DocEvent(type="added_comment")
                    c.doc = doc
                    c.by = login
                    c.desc = comment
                    c.save()

                    e.desc += "<br>" + comment
                
                doc.time = e.time
                doc.save()

                email_state_changed(request, doc, e.desc)
                email_owner(request, doc, doc.ad, login, e.desc)


                if prev_state and prev_state.slug in ("ann", "rfcqueue") and next_state.slug not in ("rfcqueue", "pub"):
                    email_pulled_from_rfc_queue(request, doc, comment, prev_state, next_state)

                if next_state.slug in ("iesg-eva", "lc"):
                    if not doc.get_state_slug("draft-iana-review"):
                        doc.set_state(State.objects.get(used=True, type="draft-iana-review", slug="need-rev"))

                if next_state.slug == "lc-req":
                    request_last_call(request, doc)

                    return render_to_response('idrfc/last_call_requested.html',
                                              dict(doc=doc,
                                                   url=doc.get_absolute_url()),
                                              context_instance=RequestContext(request))
                
            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        state = doc.get_state("draft-iesg")
        t = doc.tags.filter(slug__in=('point', 'ad-f-up', 'need-rev', 'extpty'))
        form = ChangeStateForm(initial=dict(state=state.pk if state else None,
                                            substate=t[0].pk if t else None))
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

    return render_to_response('idrfc/change_stateREDESIGN.html',
                              dict(form=form,
                                   doc=doc,
                                   state=state,
                                   prev_state=prev_state,
                                   next_states=next_states,
                                   to_iesg_eval=to_iesg_eval),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    change_state = change_stateREDESIGN
    ChangeStateForm = ChangeStateFormREDESIGN

class ChangeIanaStateForm(forms.Form):
    state = forms.ModelChoiceField(State.objects.all(), required=False)

    def __init__(self, state_type, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        choices = State.objects.filter(used=True, type=state_type).order_by("order").values_list("pk", "name")
        self.fields['state'].choices = [("", "-------")] + list(choices)

@role_required('Secretariat', 'IANA')
def change_iana_state(request, name, state_type):
    """Change IANA review state of Internet Draft. Normally, this is done via
    automatic sync, but this form allows one to set it manually."""
    doc = get_object_or_404(Document, docalias__name=name)

    state_type = doc.type_id + "-" + state_type

    prev_state = doc.get_state(state_type)

    if request.method == 'POST':
        form = ChangeIanaStateForm(state_type, request.POST)
        if form.is_valid():
            next_state = form.cleaned_data['state']

            if next_state != prev_state:
                save_document_in_history(doc)
                
                doc.set_state(next_state)

                e = add_state_change_event(doc, request.user.get_profile(), prev_state, next_state)

                doc.time = e.time
                doc.save()

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        form = ChangeIanaStateForm(state_type, initial=dict(state=prev_state.pk if prev_state else None))

    return render_to_response('idrfc/change_iana_state.html',
                              dict(form=form,
                                   doc=doc),
                              context_instance=RequestContext(request))


    
class ChangeStreamForm(forms.Form):
    stream = forms.ModelChoiceField(StreamName.objects.exclude(slug="legacy"), required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False)

@group_required('Area_Director','Secretariat')
def change_stream(request, name):
    """Change the stream of a Document of type 'draft' , notifying parties as necessary
    and logging the change as a comment."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.type_id=='draft':
        raise Http404()

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeStreamForm(request.POST)
        if form.is_valid():
            new_stream = form.cleaned_data['stream']
            comment = form.cleaned_data['comment'].strip()
            old_stream = doc.stream

            if new_stream != old_stream:
                save_document_in_history(doc)
                
                doc.stream = new_stream

                e = DocEvent(doc=doc,by=login,type='changed_document')
                e.desc = u"Stream changed to <b>%s</b> from %s"% (new_stream,old_stream) 
                e.save()

                email_desc = e.desc

                if comment:
                    c = DocEvent(doc=doc,by=login,type="added_comment")
                    c.desc = comment
                    c.save()
                    email_desc += "\n"+c.desc
                
                doc.time = e.time
                doc.save()

                email_stream_changed(request, doc, old_stream, new_stream, email_desc)

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        stream = doc.stream
        form = ChangeStreamForm(initial=dict(stream=stream))

    return render_to_response('idrfc/change_stream.html',
                              dict(form=form,
                                   doc=doc,
                                   ),
                              context_instance=RequestContext(request))

class ChangeIntentionForm(forms.Form):
    intended_std_level = forms.ModelChoiceField(IntendedStdLevelName.objects.filter(used=True), empty_label="(None)", required=True, label="Intended RFC status")
    comment = forms.CharField(widget=forms.Textarea, required=False)

def change_intention(request, name):
    """Change the intended publication status of a Document of type 'draft' , notifying parties 
       as necessary and logging the change as a comment."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.type_id != 'draft':
        raise Http404

    if not can_edit_intended_std_level(doc, request.user):
        return HttpResponseForbidden("You do not have the necessary permissions to view this page")

    login = request.user.get_profile()

    if request.method == 'POST':
        form = ChangeIntentionForm(request.POST)
        if form.is_valid():
            new_level = form.cleaned_data['intended_std_level']
            comment = form.cleaned_data['comment'].strip()
            old_level = doc.intended_std_level

            if new_level != old_level:
                save_document_in_history(doc)
                
                doc.intended_std_level = new_level

                e = DocEvent(doc=doc,by=login,type='changed_document')
                e.desc = u"Intended Status changed to <b>%s</b> from %s"% (new_level,old_level) 
                e.save()

                email_desc = e.desc

                if comment:
                    c = DocEvent(doc=doc,by=login,type="added_comment")
                    c.desc = comment
                    c.save()
                    email_desc += "\n"+c.desc
                
                doc.time = e.time
                doc.save()

                email_owner(request, doc, doc.ad, login, email_desc)

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        intended_std_level = doc.intended_std_level
        form = ChangeIntentionForm(initial=dict(intended_std_level=intended_std_level))

    return render_to_response('idrfc/change_intended_status.html',
                              dict(form=form,
                                   doc=doc,
                                   ),
                              context_instance=RequestContext(request))

def dehtmlify_textarea_text(s):
    return s.replace("<br>", "\n").replace("<b>", "").replace("</b>", "").replace("  ", " ")

class EditInfoForm(forms.Form):
    pass

def get_initial_state_change_notice(doc):
    # set change state notice to something sensible
    receivers = []
    if doc.group_id == Acronym.INDIVIDUAL_SUBMITTER:
        for a in doc.authors.all():
            # maybe it would be more appropriate to use a.email() ?
            e = a.person.email()[1]
            if e:
                receivers.append(e)
    else:
        receivers.append("%s-chairs@%s" % (doc.group.acronym, settings.TOOLS_SERVER))
        for editor in doc.group.ietfwg.wgeditor_set.all():
            e = editor.person.email()[1]
            if e:
                receivers.append(e)

    receivers.append("%s@%s" % (doc.filename, settings.TOOLS_SERVER))
    return ", ".join(receivers)

def get_new_ballot_id():
    return IDInternal.objects.aggregate(Max('ballot'))['ballot__max'] + 1
    
@group_required('Area_Director','Secretariat')
def edit_info(request, name):
    pass

class EditInfoFormREDESIGN(forms.Form):
    intended_std_level = forms.ModelChoiceField(IntendedStdLevelName.objects.filter(used=True), empty_label="(None)", required=True, label="Intended RFC status")
    area = forms.ModelChoiceField(Group.objects.filter(type="area", state="active"), empty_label="(None - individual submission)", required=False, label="Assigned to area")
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active").order_by('name'), label="Responsible AD", empty_label="(None)", required=True)
    create_in_state = forms.ModelChoiceField(State.objects.filter(used=True, type="draft-iesg", slug__in=("pub-req", "watching")), empty_label=None, required=False)
    notify = forms.CharField(max_length=255, label="Notice emails", help_text="Separate email addresses with commas", required=False)
    note = forms.CharField(widget=forms.Textarea, label="IESG note", required=False)
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False, widget=forms.Select(attrs={'onchange':'make_bold()'}))
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]
        
        # telechat choices
        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        init = kwargs['initial']['telechat_date']
        if init and init not in dates:
            dates.insert(0, init)

        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]

        # returning item is rendered non-standard
        self.standard_fields = [x for x in self.visible_fields() if x.name not in ('returning_item',)]

    def clean_note(self):
        # note is stored munged in the database
        return self.cleaned_data['note'].replace('\n', '<br>').replace('\r', '').replace('  ', '&nbsp; ')


def get_initial_notify(doc):
    # set change state notice to something sensible
    receivers = []
    if doc.group.type_id in ("individ", "area"):
        for a in doc.authors.all():
            receivers.append(a.address)
    else:
        receivers.append("%s-chairs@%s" % (doc.group.acronym, settings.TOOLS_SERVER))
        for editor in Email.objects.filter(role__name="editor", role__group=doc.group):
            receivers.append(e.address)

    receivers.append("%s@%s" % (doc.name, settings.TOOLS_SERVER))
    return ", ".join(receivers)

@group_required('Area_Director','Secretariat')
def edit_infoREDESIGN(request, name):
    """Edit various Internet Draft attributes, notifying parties as
    necessary and logging changes as document events."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.get_state_slug() == "expired":
        raise Http404()

    login = request.user.get_profile()

    new_document = False
    if not doc.get_state("draft-iesg"): # FIXME: should probably receive "new document" as argument to view instead of this
        new_document = True
        doc.notify = get_initial_notify(doc)

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    initial_telechat_date = e.telechat_date if e else None
    initial_returning_item = bool(e and e.returning_item)

    if request.method == 'POST':
        form = EditInfoForm(request.POST,
                            initial=dict(ad=doc.ad_id,
                                         telechat_date=initial_telechat_date))
        if form.is_valid():
            save_document_in_history(doc)
            
            r = form.cleaned_data
            if new_document:
                doc.set_state(r['create_in_state'])

                # fix so Django doesn't barf in the diff below because these
                # fields can't be NULL
                doc.ad = r['ad']

                replaces = Document.objects.filter(docalias__relateddocument__source=doc, docalias__relateddocument__relationship="replaces")
                if replaces:
                    # this should perhaps be somewhere else, e.g. the
                    # place where the replace relationship is established?
                    e = DocEvent()
                    e.type = "added_comment"
                    e.by = Person.objects.get(name="(System)")
                    e.doc = doc
                    e.desc = "Earlier history may be found in the Comment Log for <a href=\"%s\">%s</a>" % (replaces[0], replaces[0].get_absolute_url())
                    e.save()

                e = DocEvent()
                e.type = "started_iesg_process"
                e.by = login
                e.doc = doc
                e.desc = "IESG process started in state <b>%s</b>" % doc.get_state("draft-iesg").name
                e.save()
                    
            orig_ad = doc.ad

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
            diff('intended_std_level', "Intended Status")
            diff('ad', "Responsible AD")
            diff('notify', "State Change Notice email list")

            if r['note'] != doc.note:
                if not r['note']:
                    if doc.note:
                        changes.append("Note field has been cleared")
                else:
                    if doc.note:
                        changes.append("Note changed to '%s'" % r['note'])
                    else:
                        changes.append("Note added '%s'" % r['note'])
                    
                doc.note = r['note']

            if doc.group.type_id in ("individ", "area"):
                if not r["area"]:
                    r["area"] = Group.objects.get(type="individ")

                if r["area"] != doc.group:
                    if r["area"].type_id == "area":
                        changes.append(u"Assigned to <b>%s</b>" % r["area"].name)
                    else:
                        changes.append(u"No longer assigned to any area")
                    doc.group = r["area"]

            for c in changes:
                e = DocEvent(doc=doc, by=login)
                e.desc = c
                e.type = "changed_document"
                e.save()

            update_telechat(request, doc, login,
                            r['telechat_date'], r['returning_item'])

            doc.time = datetime.datetime.now()

            if changes and not new_document:
                email_owner(request, doc, orig_ad, login, "\n".join(changes))
                
            doc.save()
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        init = dict(intended_std_level=doc.intended_std_level_id,
                    area=doc.group_id,
                    ad=doc.ad_id,
                    notify=doc.notify,
                    note=dehtmlify_textarea_text(doc.note),
                    telechat_date=initial_telechat_date,
                    returning_item=initial_returning_item,
                    )

        form = EditInfoForm(initial=init)

    # optionally filter out some fields
    if not new_document:
        form.standard_fields = [x for x in form.standard_fields if x.name != "create_in_state"]
    if doc.group.type_id not in ("individ", "area"):
        form.standard_fields = [x for x in form.standard_fields if x.name != "area"]

    return render_to_response('idrfc/edit_infoREDESIGN.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login,
                                   ballot_issued=doc.latest_event(type="sent_ballot_announcement")),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    EditInfoForm = EditInfoFormREDESIGN
    edit_info = edit_infoREDESIGN


@group_required('Area_Director','Secretariat')
def request_resurrect(request, name):
    """Request resurrect of expired Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if doc.status.status != "Expired":
        raise Http404()

    if not doc.idinternal:
        doc.idinternal = IDInternal(draft=doc, rfc_flag=type(doc) == Rfc)

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        email_resurrect_requested(request, doc, login)
        add_document_comment(request, doc, "Resurrection was requested")
        doc.idinternal.resurrect_requested_by = login
        doc.idinternal.save()
        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/request_resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def request_resurrectREDESIGN(request, name):
    """Request resurrect of expired Internet Draft."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.get_state_slug() != "expired":
        raise Http404()

    login = request.user.get_profile()

    if request.method == 'POST':
        email_resurrect_requested(request, doc, login)
        
        e = DocEvent(doc=doc, by=login)
        e.type = "requested_resurrect"
        e.desc = "Resurrection was requested"
        e.save()
        
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/request_resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     request_resurrect = request_resurrectREDESIGN

@group_required('Secretariat')
def resurrect(request, name):
    """Resurrect expired Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if doc.status.status != "Expired":
        raise Http404()

    if not doc.idinternal:
        doc.idinternal = IDInternal(draft=doc, rfc_flag=type(doc) == Rfc)

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        if doc.idinternal.resurrect_requested_by:
            email_resurrection_completed(request, doc)
        add_document_comment(request, doc, "Resurrection was completed")
        doc.idinternal.resurrect_requested_by = None
        doc.idinternal.event_date = date.today()
        doc.idinternal.save()
        doc.status = IDStatus.objects.get(status="Active")
        doc.save()
        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Secretariat')
def resurrectREDESIGN(request, name):
    """Resurrect expired Internet Draft."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.get_state_slug() != "expired":
        raise Http404()

    login = request.user.get_profile()

    if request.method == 'POST':
        save_document_in_history(doc)
        
        e = doc.latest_event(type__in=('requested_resurrect', "completed_resurrect"))
        if e and e.type == 'requested_resurrect':
            email_resurrection_completed(request, doc, requester=e.by)
            
        e = DocEvent(doc=doc, by=login)
        e.type = "completed_resurrect"
        e.desc = "Resurrection was completed"
        e.save()
        
        doc.set_state(State.objects.get(used=True, type="draft", slug="active"))
        doc.expires = datetime.datetime.now() + datetime.timedelta(settings.INTERNET_DRAFT_DAYS_TO_EXPIRE)
        doc.time = datetime.datetime.now()
        doc.save()
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/resurrect.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     resurrect = resurrectREDESIGN


class AddCommentForm(forms.Form):
    comment = forms.CharField(required=True, widget=forms.Textarea)

@group_required('Area_Director','Secretariat', 'IANA')
def add_comment(request, name):
    """Add comment to Internet Draft."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            add_document_comment(request, doc, c)
            email_owner(request, doc, doc.idinternal.job_owner, login,
                        "A new comment added by %s" % login)
            return HttpResponseRedirect(doc.idinternal.get_absolute_url())
    else:
        form = AddCommentForm()
  
    return render_to_response('idrfc/add_comment.html',
                              dict(doc=doc,
                                   form=form,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director', 'Secretariat', 'IANA', 'RFC Editor')
def add_commentREDESIGN(request, name):
    """Add comment to history of document."""
    doc = get_object_or_404(Document, docalias__name=name)

    login = request.user.get_profile()

    if request.method == 'POST':
        form = AddCommentForm(request.POST)
        if form.is_valid():
            c = form.cleaned_data['comment']
            
            e = DocEvent(doc=doc, by=login)
            e.type = "added_comment"
            e.desc = c
            e.save()

            if doc.type_id == "draft":
                email_owner(request, doc, doc.ad, login,
                            "A new comment added by %s" % login.name)
            return HttpResponseRedirect(urlreverse("doc_history", kwargs=dict(name=doc.name)))
    else:
        form = AddCommentForm()
  
    return render_to_response('idrfc/add_comment.html',
                              dict(doc=doc,
                                   form=form),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
     add_comment = add_commentREDESIGN

class NotifyForm(forms.Form):
    notify = forms.CharField(max_length=255, label="Notice emails", help_text="Separate email addresses with commas", required=False)


@group_required('Area_Director','Secretariat')
def edit_notices(request, name):
    """Change the set of email addresses document change notificaitions go to."""

    doc = get_object_or_404(Document, type="draft", name=name)

    if request.method == 'POST':

        if "save_addresses" in request.POST:
            form = NotifyForm(request.POST)
            if form.is_valid():

                doc.notify = form.cleaned_data['notify']
                doc.save()

                login = request.user.get_profile()
                c = DocEvent(type="added_comment", doc=doc, by=login)
                c.desc = "Notification list changed to : "+doc.notify
                c.save()

                return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))

        elif "regenerate_addresses" in request.POST:
            init = { "notify" : get_initial_notify(doc) }
            form = NotifyForm(initial=init)

        # Protect from handcrufted POST
        else:
            init = { "notify" : doc.notify }
            form = NotifyForm(initial=init)

    else:

        init = { "notify" : doc.notify }
        form = NotifyForm(initial=init)

    return render_to_response('idrfc/change_notify.html',
                              {'form':   form,
                               'doc': doc,
                              },
                              context_instance = RequestContext(request))

class TelechatForm(forms.Form):
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False)
    returning_item = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        init = kwargs['initial'].get("telechat_date")
        if init and init not in dates:
            dates.insert(0, init)

        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]
        

@group_required("Area Director", "Secretariat")
def telechat_date(request, name):
    doc = get_object_or_404(Document, type="draft", name=name)
    login = request.user.get_profile()

    e = doc.latest_event(TelechatDocEvent, type="scheduled_for_telechat")
    initial_returning_item = bool(e and e.returning_item)

    initial = dict(telechat_date=e.telechat_date if e else None,
                   returning_item = initial_returning_item,
                  )
    if request.method == "POST":
        form = TelechatForm(request.POST, initial=initial)

        if form.is_valid():
            update_telechat(request, doc, login, form.cleaned_data['telechat_date'],form.cleaned_data['returning_item'])
            return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))
    else:
        form = TelechatForm(initial=initial)

    return render_to_response('idrfc/edit_telechat_date.html',
                              dict(doc=doc,
                                   form=form,
                                   user=request.user,
                                   login=login),
                              context_instance=RequestContext(request))


class IESGNoteForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea, label="IESG note", required=False)

    def clean_note(self):
        # note is stored munged in the database
        return self.cleaned_data['note'].replace('\n', '<br>').replace('\r', '').replace('  ', '&nbsp; ')

@group_required("Area Director", "Secretariat")
def edit_iesg_note(request, name):
    doc = get_object_or_404(Document, type="draft", name=name)
    login = request.user.get_profile()

    initial = dict(note=dehtmlify_textarea_text(doc.note))

    if request.method == "POST":
        form = IESGNoteForm(request.POST, initial=initial)

        if form.is_valid():
            new_note = form.cleaned_data['note']
            if new_note != doc.note:
                if not new_note:
                    if doc.note:
                        log_message = "Note field has been cleared"
                else:
                    if doc.note:
                        log_message = "Note changed to '%s'" % new_note
                    else:
                        log_message = "Note added '%s'" % new_note

                doc.note = new_note
                doc.save()

                c = DocEvent(type="added_comment", doc=doc, by=login)
                c.desc = log_message
                c.save()

            return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))
    else:
        form = IESGNoteForm(initial=initial)

    return render_to_response('idrfc/edit_iesg_note.html',
                              dict(doc=doc,
                                   form=form,
                                   ),
                              context_instance=RequestContext(request))

class AdForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active").order_by('name'), 
                                label="Shepherding AD", empty_label="(None)", required=True)

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # if previous AD is now ex-AD, append that person to the list
        ad_pk = self.initial.get('ad')
        choices = self.fields['ad'].choices
        if ad_pk and ad_pk not in [pk for pk, name in choices]:
            self.fields['ad'].choices = list(choices) + [("", "-------"), (ad_pk, Person.objects.get(pk=ad_pk).plain_name())]

@group_required("Area Director", "Secretariat")
def edit_ad(request, name):
    """Change the shepherding Area Director for this draft."""

    doc = get_object_or_404(Document, type="draft", name=name)

    if request.method == 'POST':
        form = AdForm(request.POST)
        if form.is_valid():

            doc.ad = form.cleaned_data['ad']
            doc.save()
    
            login = request.user.get_profile()
            c = DocEvent(type="added_comment", doc=doc, by=login)
            c.desc = "Shepherding AD changed to "+doc.ad.name
            c.save()

            return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))

    else:
        init = { "ad" : doc.ad_id }
        form = AdForm(initial=init)

    return render_to_response('idrfc/change_ad.html',
                              {'form':   form,
                               'doc': doc,
                              },
                              context_instance = RequestContext(request))

class ConsensusForm(forms.Form):
    consensus = forms.ChoiceField(choices=(("", "Unknown"), ("Yes", "Yes"), ("No", "No")), required=True)

def edit_consensus(request, name):
    """Change whether the draft is a consensus document or not."""

    doc = get_object_or_404(Document, type="draft", name=name)

    if not can_edit_consensus(doc, request.user):
        return HttpResponseForbidden("You do not have the necessary permissions to view this page")

    e = doc.latest_event(ConsensusDocEvent, type="changed_consensus")
    prev_consensus = e and e.consensus

    if request.method == 'POST':
        form = ConsensusForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["consensus"] != bool(prev_consensus):
                e = ConsensusDocEvent(doc=doc, type="changed_consensus", by=request.user.get_profile())
                e.consensus = form.cleaned_data["consensus"] == "Yes"

                e.desc = "Changed consensus to <b>%s</b> from %s" % (nice_consensus(e.consensus),
                                                                     nice_consensus(prev_consensus))

                e.save()

            return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))

    else:
        form = ConsensusForm(initial=dict(consensus=nice_consensus(prev_consensus).replace("Unknown", "")))

    return render_to_response('idrfc/change_consensus.html',
                              {'form': form,
                               'doc': doc,
                              },
                              context_instance = RequestContext(request))

class PublicationForm(forms.Form):
    subject = forms.CharField(max_length=200, required=True)
    body = forms.CharField(widget=forms.Textarea, required=True)

def request_publication(request, name):
    """Request publication by RFC Editor for a document which hasn't
    been through the IESG ballot process."""

    doc = get_object_or_404(Document, type="draft", name=name, stream__in=("iab", "ise", "irtf"))

    if not can_edit_state(request.user, doc):
        return HttpResponseForbidden("You do not have the necessary permissions to view this page")

    m = Message()
    m.frm = request.user.get_profile().formatted_email()
    m.to = "RFC Editor <rfc-editor@rfc-editor.org>"
    m.by = request.user.get_profile()

    next_state = State.objects.get(used=True, type="draft-stream-%s" % doc.stream.slug, slug="rfc-edit")

    if request.method == 'POST' and not request.POST.get("reset"):
        form = PublicationForm(request.POST)
        if form.is_valid():
            m.subject = form.cleaned_data["subject"]
            m.body = form.cleaned_data["body"]
            m.save()

            if doc.group.acronym != "none":
                m.related_groups = [doc.group]
            m.related_docs = [doc]

            send_mail_message(request, m)

            # IANA copy
            m.to = "IANA <drafts-approval@icann.org>"
            send_mail_message(request, m, extra=extra_automation_headers(doc))

            e = DocEvent(doc=doc, type="requested_publication", by=request.user.get_profile())
            e.desc = "Sent request for publication to the RFC Editor"
            e.save()

            # change state
            prev_state = doc.get_state(next_state.type)

            doc.set_state(next_state)

            e = add_state_change_event(doc, request.user.get_profile(), prev_state, next_state)

            doc.time = e.time
            doc.save()

            return HttpResponseRedirect(urlreverse('doc_view', kwargs={'name': doc.name}))

    else:
        if doc.intended_std_level_id in ("std", "ds", "ps", "bcp"):
            action = "Protocol Action"
        else:
            action = "Document Action"

        from ietf.idrfc.templatetags.mail_filters import std_level_prompt

        subject = "%s: '%s' to %s (%s-%s.txt)" % (action, doc.title, std_level_prompt(doc), doc.name, doc.rev)

        body = generate_publication_request(request, doc)

        form = PublicationForm(initial=dict(subject=subject,
                                            body=body))

    return render_to_response('idrfc/request_publication.html',
                              dict(form=form,
                                   doc=doc,
                                   message=m,
                                   next_state=next_state,
                                   ),
                              context_instance = RequestContext(request))

