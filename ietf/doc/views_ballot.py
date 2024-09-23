# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# ballot management (voting, commenting, writeups, ...) for Area
# Directors and Secretariat


import datetime, json

from django import forms
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.template.defaultfilters import striptags
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.views.decorators.csrf import csrf_exempt
from django.utils.html import escape
from urllib.parse import urlencode as urllib_urlencode

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, DocEvent, BallotDocEvent,
    IRSGBallotDocEvent, BallotPositionDocEvent, LastCallDocEvent, WriteupDocEvent,
    IESG_SUBSTATE_TAGS, RelatedDocument, BallotType )
from ietf.doc.utils import ( add_state_change_event, close_ballot, close_open_ballots,
    create_ballot_if_not_open, update_telechat, update_action_holders )
from ietf.doc.mails import ( email_ballot_deferred, email_ballot_undeferred, 
    extra_automation_headers, generate_last_call_announcement, 
    generate_issue_ballot_mail, generate_ballot_writeup, generate_ballot_rfceditornote,
    generate_approval_mail, email_irsg_ballot_closed, email_irsg_ballot_issued,
    email_rsab_ballot_issued, email_rsab_ballot_closed,
    email_lc_to_yang_doctors )
from ietf.doc.lastcall import request_last_call
from ietf.doc.templatetags.ietf_filters import can_ballot
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, role_required, is_authorized_in_doc_stream
from ietf.mailtrigger.utils import gather_address_lists
from ietf.mailtrigger.forms import CcSelectForm
from ietf.message.utils import infer_message
from ietf.name.models import BallotPositionName, DocTypeName
from ietf.person.models import Person
from ietf.utils.fields import ModelMultipleChoiceField
from ietf.utils.http import validate_return_to_path
from ietf.utils.mail import send_mail_text, send_mail_preformatted
from ietf.utils.decorators import require_api_key
from ietf.utils.response import permission_denied
from ietf.utils.timezone import date_today, datetime_from_date, DEADLINE_TZINFO


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def do_undefer_ballot(request, doc):
    '''
    Helper function to perform undefer of ballot.  Takes the Request object, for use in 
    logging, and the Document object.
    '''
    by = request.user.person
    telechat_date = TelechatDate.objects.active().order_by("date")[0].date

    new_state = doc.get_state()
    prev_tags = []
    new_tags = []

    if doc.type_id == 'draft':
        new_state = State.objects.get(used=True, type="draft-iesg", slug='iesg-eva')
        prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
    elif doc.type_id in ['conflrev','statchg']:
        new_state = State.objects.get(used=True, type=doc.type_id, slug='iesgeval')

    prev_state = doc.get_state(new_state.type_id if new_state else None)

    doc.set_state(new_state)
    doc.tags.remove(*prev_tags)

    events = []
    e = add_state_change_event(doc, by, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
    if e:
        events.append(e)
    e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
    if e:
        events.append(e)

    e = update_telechat(request, doc, by, telechat_date)
    if e:
        events.append(e)

    if events:
        doc.save_with_history(events)

    email_ballot_undeferred(request, doc, by.plain_name(), telechat_date)

# -------------------------------------------------
class EditPositionForm(forms.Form):
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.all(), widget=forms.RadioSelect, initial="norecord", required=True)
    discuss = forms.CharField(required=False, widget=forms.Textarea, strip=False)
    comment = forms.CharField(required=False, widget=forms.Textarea, strip=False)

    def __init__(self, *args, **kwargs):
        ballot_type = kwargs.pop("ballot_type")
        super(EditPositionForm, self).__init__(*args, **kwargs)
        self.fields['position'].queryset = ballot_type.positions.order_by('order')
        if ballot_type.positions.filter(blocking=True).exists():
            self.fields['discuss'].label = ballot_type.positions.get(blocking=True).name

    def clean_discuss(self):
       entered_discuss = self.cleaned_data["discuss"]
       entered_pos = self.cleaned_data.get("position", BallotPositionName.objects.get(slug="norecord"))
       if entered_pos.blocking and not entered_discuss:
           raise forms.ValidationError("You must enter a non-empty discuss")
       return entered_discuss

def save_position(form, doc, ballot, balloter, login=None, send_email=False):
    # save the vote
    if login is None:
        login = balloter
    clean = form.cleaned_data

    old_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", balloter=balloter, ballot=ballot)
    pos = BallotPositionDocEvent(doc=doc, rev=doc.rev, by=login)
    pos.type = "changed_ballot_position"
    pos.ballot = ballot
    pos.balloter = balloter
    pos.pos = clean["position"]
    pos.comment = clean["comment"].rstrip()
    pos.comment_time = old_pos.comment_time if old_pos else None
    pos.discuss = clean["discuss"].rstrip()
    pos.send_email = send_email
    if not pos.pos.blocking:
        pos.discuss = ""
    pos.discuss_time = old_pos.discuss_time if old_pos else None

    changes = []
    added_events = []
    # possibly add discuss/comment comments to history trail
    # so it's easy to see what's happened
    old_comment = old_pos.comment if old_pos else ""
    if pos.comment != old_comment:
        pos.comment_time = pos.time
        changes.append("comment")

        if pos.comment:
            e = DocEvent(doc=doc, rev=doc.rev, by=balloter)
            e.type = "added_comment"
            e.desc = "[Ballot comment]\n" + pos.comment

            added_events.append(e)

    old_discuss = old_pos.discuss if old_pos else ""
    if pos.discuss != old_discuss:
        pos.discuss_time = pos.time
        changes.append("discuss")

        if pos.pos.blocking:
            e = DocEvent(doc=doc, rev=doc.rev, by=balloter)
            e.type = "added_comment"
            e.desc = "[Ballot %s]\n" % pos.pos.name.lower()
            e.desc += pos.discuss
            added_events.append(e)

    # figure out a description
    if not old_pos and pos.pos.slug != "norecord":
        pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.balloter.plain_name())
    elif old_pos and pos.pos != old_pos.pos:
        pos.desc = "[Ballot Position Update] Position for %s has been changed to %s from %s" % (pos.balloter.plain_name(), pos.pos.name, old_pos.pos.name)

    if not pos.desc and changes:
        pos.desc = "Ballot %s text updated for %s" % (" and ".join(changes), balloter.plain_name())

    # only add new event if we actually got a change
    if pos.desc:
        if login != balloter:
            pos.desc += " by %s" % login.plain_name()

        pos.save()

        for e in added_events:
            e.save() # save them after the position is saved to get later id for sorting order

    return pos

@role_required("Area Director", "Secretariat", "IRSG Member", "RSAB Member")
def edit_position(request, name, ballot_id):
    """Vote and edit discuss and comment on document"""
    doc = get_object_or_404(Document, name=name)
    ballot = get_object_or_404(BallotDocEvent, type="created_ballot", pk=ballot_id, doc=doc)

    balloter = login = request.user.person

    try:
        return_to_url = parse_ballot_edit_return_point(request.GET.get('ballot_edit_return_point'), doc.name, ballot_id)
    except ValueError:
        return HttpResponseBadRequest('ballot_edit_return_point is invalid')
    
    # if we're in the Secretariat, we can select a balloter to act as stand-in for
    if has_role(request.user, "Secretariat"):
        balloter_id = request.GET.get('balloter')
        if not balloter_id:
            raise Http404
        balloter = get_object_or_404(Person, pk=balloter_id)

    if request.method == 'POST':
        old_pos = None
        if not has_role(request.user, "Secretariat") and not can_ballot(request.user, doc):
            # prevent pre-ADs from taking a position
            permission_denied(request, "Must be an active member (not a pre-AD for example) of the balloting body to take a position")
        
        form = EditPositionForm(request.POST, ballot_type=ballot.ballot_type)
        if form.is_valid():
            send_mail = True if request.POST.get("send_mail") else False
            save_position(form, doc, ballot, balloter, login, send_mail)

            if send_mail:
                query = {}
                if request.GET.get('balloter'):
                    query['balloter'] = request.GET.get('balloter')
                if request.GET.get('ballot_edit_return_point'):
                    query['ballot_edit_return_point'] = request.GET.get('ballot_edit_return_point')
                qstr = ""
                if len(query) > 0:
                    qstr = "?" + urllib_urlencode(query, safe='/')
                return HttpResponseRedirect(urlreverse('ietf.doc.views_ballot.send_ballot_comment', kwargs=dict(name=doc.name, ballot_id=ballot_id)) + qstr)
            elif request.POST.get("Defer") and doc.stream.slug != "irtf":
                return redirect('ietf.doc.views_ballot.defer_ballot', name=doc)
            elif request.POST.get("Undefer") and doc.stream.slug != "irtf":
                return redirect('ietf.doc.views_ballot.undefer_ballot', name=doc)
            else:
                return HttpResponseRedirect(return_to_url)
    else:
        initial = {}
        old_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", balloter=balloter, ballot=ballot)
        if old_pos:
            initial['position'] = old_pos.pos.slug
            initial['discuss'] = old_pos.discuss
            initial['comment'] = old_pos.comment
            
        form = EditPositionForm(initial=initial, ballot_type=ballot.ballot_type)

    blocking_positions = dict((p.pk, p.name) for p in form.fields["position"].queryset.all() if p.blocking)

    ballot_deferred = doc.active_defer_event()

    return render(request, 'doc/ballot/edit_position.html',
                              dict(doc=doc,
                                   form=form,
                                   balloter=balloter,
                                   return_to_url=return_to_url,
                                   old_pos=old_pos,
                                   ballot_deferred=ballot_deferred,
                                   ballot = ballot,
                                   show_discuss_text=old_pos and old_pos.pos.blocking,
                                   blocking_positions=json.dumps(blocking_positions),
                                   ))

@require_api_key
@role_required('Area Director')
@csrf_exempt
def api_set_position(request):
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
    if request.method == 'POST':
        ad = request.user.person
        name = request.POST.get('doc')
        if not name:
            return err(400, "Missing document name")
        try:
            doc = Document.objects.get(name=name)
        except Document.DoesNotExist:
            return err(400, "Document not found")
        position_names = BallotPositionName.objects.values_list('slug', flat=True)
        position = request.POST.get('position')
        if not position:
            return err(400, "Missing parameter: position, one of: %s " % ','.join(position_names))
        if not position in position_names:
            return err(400, "Bad position name, must be one of: %s " % ','.join(position_names))
        ballot = doc.active_ballot()
        if not ballot:
            return err(400, "No open ballot found")
        form = EditPositionForm(request.POST, ballot_type=ballot.ballot_type)
        if form.is_valid():
            pos = save_position(form, doc, ballot, ad, send_email=True)
        else:
            errors = form.errors
            summary = ','.join([ "%s: %s" % (f, striptags(errors[f])) for f in errors ])
            return err(400, "Form not valid: %s" % summary)
    else:
        return err(405, "Method not allowed")

    # send position email
    addrs, frm, subject, body = build_position_email(ad, doc, pos)
    send_mail_text(request, addrs.to, frm, subject, body, cc=addrs.cc)

    return HttpResponse("Done", status=200, content_type='text/plain')


def build_position_email(balloter, doc, pos):
    subj = []
    d = ""
    blocking_name = "DISCUSS"
    if pos.pos.blocking and pos.discuss:
        d = pos.discuss
        blocking_name = pos.pos.name.upper()
        subj.append(blocking_name)
    c = ""
    if pos.comment:
        c = pos.comment
        subj.append("COMMENT")

    balloter_name_genitive = balloter.plain_name() + "'" if balloter.plain_name().endswith('s') else balloter.plain_name() + "'s"
    subject = "%s %s on %s" % (balloter_name_genitive, pos.pos.name if pos.pos else "No Position", doc.name + "-" + doc.rev)
    if subj:
        subject += ": (with %s)" % " and ".join(subj)

    body = render_to_string("doc/ballot/ballot_comment_mail.txt",
                            dict(discuss=d,
                                 comment=c,
                                 balloter=balloter.plain_name(),
                                 doc=doc,
                                 pos=pos.pos,
                                 blocking_name=blocking_name,
                                 settings=settings))
    frm = balloter.role_email("ad").formatted_email()

    if doc.stream_id == "irtf":
        addrs = gather_address_lists('irsg_ballot_saved',doc=doc)
    elif doc.stream_id == "editorial":
        addrs = gather_address_lists('rsab_ballot_saved',doc=doc)
    else:
        addrs = gather_address_lists('iesg_ballot_saved',doc=doc)

    return addrs, frm, subject, body

@role_required('Area Director','Secretariat','IRSG Member', 'RSAB Member')
def send_ballot_comment(request, name, ballot_id):
    """Email document ballot position discuss/comment for Area Director."""
    doc = get_object_or_404(Document, name=name)
    ballot = get_object_or_404(BallotDocEvent, type="created_ballot", pk=ballot_id, doc=doc)

    if not has_role(request.user, 'Secretariat'):
        if any([
            doc.stream_id == 'ietf' and not has_role(request.user, 'Area Director'),
            doc.stream_id == 'irtf' and not has_role(request.user, 'IRSG Member'),
            doc.stream_id == 'editorial' and not has_role(request.user, 'RSAB Member'),
        ]):
            raise Http404

    balloter = request.user.person

    try:
        return_to_url = parse_ballot_edit_return_point(request.GET.get('ballot_edit_return_point'), doc.name, ballot_id)
    except ValueError:
        return HttpResponseBadRequest('ballot_edit_return_point is invalid')
    
    if 'HTTP_REFERER' in request.META:
        back_url = request.META['HTTP_REFERER']
    else:
        back_url = urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc.name, ballot_id=ballot_id))

    # if we're in the Secretariat, we can select a balloter (such as an AD) to act as stand-in for
    if has_role(request.user, "Secretariat"):
        balloter_id = request.GET.get('balloter')
        if not balloter_id:
            raise Http404
        balloter = get_object_or_404(Person, pk=balloter_id)

    pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", balloter=balloter, ballot=ballot)
    if not pos:
        raise Http404

    addrs, frm, subject, body = build_position_email(balloter, doc, pos)

    if doc.stream_id == 'irtf':
        mailtrigger_slug='irsg_ballot_saved'
    elif doc.stream_id == 'editorial':
        mailtrigger_slug='rsab_ballot_saved'
    else:
        mailtrigger_slug='iesg_ballot_saved'
        
    if request.method == 'POST':
        cc = []
        cc_select_form = CcSelectForm(data=request.POST,mailtrigger_slug=mailtrigger_slug,mailtrigger_context={'doc':doc})
        if cc_select_form.is_valid():
            cc.extend(cc_select_form.get_selected_addresses())
        extra_cc = [x.strip() for x in request.POST.get("extra_cc","").split(',') if x.strip()]
        if extra_cc:
            cc.extend(extra_cc)

        send_mail_text(request, addrs.to, frm, subject, body, cc=", ".join(cc))
            
        return HttpResponseRedirect(return_to_url)

    else: 

        cc_select_form = CcSelectForm(mailtrigger_slug=mailtrigger_slug,mailtrigger_context={'doc':doc})
  
        return render(request, 'doc/ballot/send_ballot_comment.html',
                      dict(doc=doc,
                          subject=subject,
                          body=body,
                          frm=frm,
                          to=addrs.as_strings().to,
                          balloter=balloter,
                          back_url=back_url,
                          cc_select_form = cc_select_form,
                      ))

@role_required('Area Director','Secretariat')
def clear_ballot(request, name, ballot_type_slug):
    """Clear all positions and discusses on every open ballot for a document."""
    doc = get_object_or_404(Document, name=name)
    # If there's no appropriate ballot type state, clearing would be an invalid action.
    # This will need to be updated if we ever allow defering IRTF ballots
    if ballot_type_slug == "approve":
        state_machine = "draft-iesg"
    elif ballot_type_slug in ["statchg","conflrev"]:
        state_machine = ballot_type_slug
    else:
        state_machine = None
    state_slug = state_machine and doc.get_state_slug(state_machine)
    if state_machine is None or state_slug is None:
        raise Http404
    if request.method == 'POST':
        by = request.user.person
        if close_ballot(doc, by, ballot_type_slug):
            create_ballot_if_not_open(request, doc, by, ballot_type_slug)
        if state_slug == "defer":
            do_undefer_ballot(request,doc)
        return redirect("ietf.doc.views_doc.document_main", name=doc.name)

    return render(request, 'doc/ballot/clear_ballot.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()))

@role_required('Area Director','Secretariat')
def defer_ballot(request, name):
    """Signal post-pone of ballot, notifying relevant parties."""
    doc = get_object_or_404(Document, name=name)
    if doc.type_id not in ('draft','conflrev','statchg'):
        raise Http404
    interesting_state = dict(draft='draft-iesg',conflrev='conflrev',statchg='statchg')
    state = doc.get_state(interesting_state[doc.type_id])
    if not state or state.slug=='defer' or not doc.telechat_date():
        raise Http404

    login = request.user.person
    telechat_date = TelechatDate.objects.active().order_by("date")[1].date

    if request.method == 'POST':
        new_state = doc.get_state()
        prev_tags = []
        new_tags = []

        if doc.type_id == 'draft':
            new_state = State.objects.get(used=True, type="draft-iesg", slug='defer')
            prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        elif doc.type_id in ['conflrev','statchg']:
            new_state = State.objects.get(used=True, type=doc.type_id, slug='defer')

        prev_state = doc.get_state(new_state.type_id if new_state else None)

        doc.set_state(new_state)
        doc.tags.remove(*prev_tags)

        events = []

        e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
        if e:
            events.append(e)
        e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
        if e:
            events.append(e)

        e = update_telechat(request, doc, login, telechat_date)
        if e:
            events.append(e)

        doc.save_with_history(events)

        email_ballot_deferred(request, doc, login.plain_name(), telechat_date)

        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render(request, 'doc/ballot/defer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()))

@role_required('Area Director','Secretariat')
def undefer_ballot(request, name):
    """undo deferral of ballot ballot."""
    doc = get_object_or_404(Document, name=name)
    if doc.type_id not in ('draft','conflrev','statchg'):
        raise Http404
    if doc.type_id == 'draft' and not doc.get_state("draft-iesg"):
        raise Http404
    interesting_state = dict(draft='draft-iesg',conflrev='conflrev',statchg='statchg')
    state = doc.get_state(interesting_state[doc.type_id]) 
    if not state or state.slug!='defer':
        raise Http404

    telechat_date = TelechatDate.objects.active().order_by("date")[0].date
    
    if request.method == 'POST':
        do_undefer_ballot(request,doc)
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render(request, 'doc/ballot/undefer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()))

class LastCallTextForm(forms.Form):
    last_call_text = forms.CharField(widget=forms.Textarea, required=True, strip=False)
    
    def clean_last_call_text(self):
        lines = self.cleaned_data["last_call_text"].split("\r\n")
        for l, next in zip(lines, lines[1:]):
            if l.startswith('Subject:') and next.strip():
                raise forms.ValidationError("Subject line appears to have a line break, please make sure there is no line breaks in the subject line and that it is followed by an empty line.")
        
        return self.cleaned_data["last_call_text"].replace("\r", "")


@role_required('Area Director','Secretariat')
def lastcalltext(request, name):
    """Editing of the last call text"""
    doc = get_object_or_404(Document, name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not existing:
        existing = generate_last_call_announcement(request, doc)
        
    form = LastCallTextForm(initial=dict(last_call_text=escape(existing.text)))

    if request.method == 'POST':
        if "save_last_call_text" in request.POST or "send_last_call_request" in request.POST:
            form = LastCallTextForm(request.POST)
            if form.is_valid():
                t = form.cleaned_data['last_call_text']
                if t != existing.text:
                    e = WriteupDocEvent(doc=doc, rev=doc.rev, by=login)
                    e.by = login
                    e.type = "changed_last_call_text"
                    e.desc = "Last call announcement was changed"
                    e.text = t
                    e.save()
                elif existing.pk == None:
                    existing.save()
                
                if "send_last_call_request" in request.POST:
                    prev_state = doc.get_state("draft-iesg")
                    new_state = State.objects.get(used=True, type="draft-iesg", slug='lc-req')

                    prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)

                    doc.set_state(new_state)
                    doc.tags.remove(*prev_tags)

                    events = []
                    e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
                    if e:
                        events.append(e)
                    e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
                    if e:
                        events.append(e)

                    if events:
                        doc.save_with_history(events)

                    request_last_call(request, doc)
                    
                    return render(request, 'doc/draft/last_call_requested.html',
                                              dict(doc=doc))
        
        if "regenerate_last_call_text" in request.POST:
            e = generate_last_call_announcement(request, doc)
            e.save()

            # make sure form has the updated text
            form = LastCallTextForm(initial=dict(last_call_text=escape(e.text)))


    s = doc.get_state("draft-iesg")
    can_request_last_call = s.order < 27
    can_make_last_call = s.order < 20
    
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render(request, 'doc/ballot/lastcalltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   last_call_form=form,
                                   can_request_last_call=can_request_last_call,
                                   can_make_last_call=can_make_last_call,
                                   need_intended_status=need_intended_status,
                                   ))

class BallotWriteupForm(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
@role_required('Area Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    doc = get_object_or_404(Document, name=name)
    prev_state = doc.get_state("draft-iesg")

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not existing:
        existing = generate_ballot_writeup(request, doc)
        
    form = BallotWriteupForm(initial=dict(ballot_writeup=escape(existing.text)))

    if request.method == 'POST' and "save_ballot_writeup" in request.POST or "issue_ballot" in request.POST:
        form = BallotWriteupForm(request.POST)
        if form.is_valid():
            if prev_state.slug in ['ann', 'approved', 'rfcqueue', 'pub']:
                ballot_already_approved = True
            else:
                ballot_already_approved = False

            t = form.cleaned_data["ballot_writeup"]
            if t != existing.text:
                e = WriteupDocEvent(doc=doc, rev=doc.rev, by=login)
                e.by = login
                e.type = "changed_ballot_writeup_text"
                e.desc = "Ballot writeup was changed"
                e.text = t
                e.save()
            elif existing.pk == None:
                existing.save()

            if "issue_ballot" in request.POST and not ballot_already_approved:
                if prev_state.slug in ['writeupw', 'goaheadw']:
                    new_state = State.objects.get(used=True, type="draft-iesg", slug='iesg-eva')
                    prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
                    doc.set_state(new_state)
                    doc.tags.remove(*prev_tags)

                    events = []
                    e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
                    if e:
                        events.append(e)
                    e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
                    if e:
                        events.append(e)
                    if events:
                        doc.save_with_history(events)

                if not ballot_already_approved:
                    e = create_ballot_if_not_open(request, doc, login, "approve") # pyflakes:ignore
                    ballot = doc.latest_event(BallotDocEvent, type="created_ballot")
                    if has_role(request.user, "Area Director") and not doc.latest_event(BallotPositionDocEvent, balloter=login, ballot=ballot):
                        # sending the ballot counts as a yes
                        pos = BallotPositionDocEvent(doc=doc, rev=doc.rev, by=login)
                        pos.ballot = ballot
                        pos.type = "changed_ballot_position"
                        pos.balloter = login
                        pos.pos_id = "yes"
                        pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.balloter.plain_name())
                        pos.save()

                        # Consider mailing this position to 'iesg_ballot_saved'

                    approval = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
                    if not approval:
                        approval = generate_approval_mail(request, doc)
                        approval.save()

                    msg = generate_issue_ballot_mail(request, doc, ballot)

                    addrs = gather_address_lists('iesg_ballot_issued',doc=doc).as_strings()
                    override = {'To':addrs.to}
                    if addrs.cc:
                        override['CC'] = addrs.cc
                    send_mail_preformatted(request, msg, override=override)

                    addrs = gather_address_lists('ballot_issued_iana',doc=doc).as_strings()
                    override={ "To": addrs.to, "Bcc": None , "Reply-To": [], "CC": addrs.cc or None }
                    send_mail_preformatted(request, msg, extra=extra_automation_headers(doc), override=override)

                    e = DocEvent(doc=doc, rev=doc.rev, by=login)
                    e.by = login
                    e.type = "sent_ballot_announcement"
                    e.desc = "Ballot has been issued"
                    e.save()

                    return render(request, 'doc/ballot/ballot_issued.html',
                                              dict(doc=doc,
                                                   back_url=doc.get_absolute_url()))

    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render(request, 'doc/ballot/writeupnotes.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   ballot_issued=bool(doc.latest_event(type="sent_ballot_announcement")),
                                   warn_lc = not doc.docevent_set.filter(lastcalldocevent__expires__date__lt=date_today(DEADLINE_TZINFO)).exists(),
                                   warn_unexpected_state= prev_state if bool(prev_state.slug in ['ad-eval', 'lc']) else None,
                                   ballot_writeup_form=form,
                                   need_intended_status=need_intended_status,
                                   ))

class BallotRfcEditorNoteForm(forms.Form):
    rfc_editor_note = forms.CharField(widget=forms.Textarea, label="RFC Editor Note", required=True, strip=False)

    def clean_rfc_editor_note(self):
        return self.cleaned_data["rfc_editor_note"].replace("\r", "")
        
@role_required('Area Director','Secretariat','IAB Chair','IRTF Chair','ISE')
def ballot_rfceditornote(request, name):
    """Editing of RFC Editor Note"""
    doc = get_object_or_404(Document, name=name)

    if not is_authorized_in_doc_stream(request.user, doc):
        permission_denied(request, "You do not have the necessary permissions to change the RFC Editor Note for this document")

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
    if not existing or (existing.text == ""):
        existing = generate_ballot_rfceditornote(request, doc)

    form = BallotRfcEditorNoteForm(auto_id=False, initial=dict(rfc_editor_note=escape(existing.text)))

    if request.method == 'POST' and "save_ballot_rfceditornote" in request.POST:
        form = BallotRfcEditorNoteForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["rfc_editor_note"]
            if t != existing.text:
                e = WriteupDocEvent(doc=doc, rev=doc.rev, by=login)
                e.by = login
                e.type = "changed_rfc_editor_note_text"
                e.desc = f"RFC Editor Note was changed to \n{t}"
                e.text = t.rstrip()
                e.save()

                if doc.get_state_slug('draft-iesg') in ['approved', 'ann', 'rfcqueue']:
                    (to, cc) = gather_address_lists('ballot_ednote_changed_late').as_strings()
                    msg = render_to_string(
                              'doc/ballot/ednote_changed_late.txt',
                              context = dict(
                                  to = to,
                                  cc = cc,
                                  event = e,
                                  settings = settings,
                              )
                          )
                    send_mail_preformatted(request, msg)
            return redirect('ietf.doc.views_doc.document_writeup', name=doc.name)

    if request.method == 'POST' and "clear_ballot_rfceditornote" in request.POST:
        e = WriteupDocEvent(doc=doc, rev=doc.rev, by=login)
        e.by = login
        e.type = "changed_rfc_editor_note_text"
        e.desc = "RFC Editor Note was cleared"
        e.text = ""
        e.save()

        # make sure form shows a blank RFC Editor Note
        form = BallotRfcEditorNoteForm(initial=dict(rfc_editor_note=" "))

    return render(request, 'doc/ballot/rfceditornote.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   ballot_rfceditornote_form=form,
                                   ))

class ApprovalTextForm(forms.Form):
    approval_text = forms.CharField(widget=forms.Textarea, required=True, strip=False)

    def clean_approval_text(self):
        return self.cleaned_data["approval_text"].replace("\r", "")

@role_required('Area Director','Secretariat')
def ballot_approvaltext(request, name):
    """Editing of approval text"""
    doc = get_object_or_404(Document, name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    if not existing:
        existing = generate_approval_mail(request, doc)

    form = ApprovalTextForm(initial=dict(approval_text=escape(existing.text)))

    if request.method == 'POST':
        if "save_approval_text" in request.POST:
            form = ApprovalTextForm(request.POST)
            if form.is_valid():
                t = form.cleaned_data['approval_text']
                if t != existing.text:
                    e = WriteupDocEvent(doc=doc, rev=doc.rev, by=login)
                    e.by = login
                    e.type = "changed_ballot_approval_text"
                    e.desc = "Ballot approval text was changed"
                    e.text = t
                    e.save()
                elif existing.pk == None:
                    existing.save()
                
        if "regenerate_approval_text" in request.POST:
            e = generate_approval_mail(request, doc)
            e.save()

            # make sure form has the updated text
            form = ApprovalTextForm(initial=dict(approval_text=escape(e.text)))

    can_announce = doc.get_state("draft-iesg").order > 19
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render(request, 'doc/ballot/approvaltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   approval_text_form=form,
                                   can_announce=can_announce,
                                   need_intended_status=need_intended_status,
                                   ))


@role_required('Secretariat')
def approve_ballot(request, name):
    """Approve ballot, sending out announcement, changing state."""
    doc = get_object_or_404(Document, name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    approval_mail_event = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    if not approval_mail_event:
        approval_mail_event = generate_approval_mail(request, doc)
    approval_text = approval_mail_event.text

    ballot_writeup_event = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not ballot_writeup_event:
        ballot_writeup_event = generate_ballot_writeup(request, doc)
    ballot_writeup = ballot_writeup_event.text

    error_duplicate_rfc_editor_note = False
    e = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
    if e and (e.text != ""):
        if "RFC Editor Note" in ballot_writeup:
            error_duplicate_rfc_editor_note = True
        ballot_writeup += "\n\n" + e.text

    if error_duplicate_rfc_editor_note:
        return render(request, 'doc/draft/rfceditor_note_duplicate_error.html', {'doc': doc})

    if "NOT be published" in approval_text:
        action = "do_not_publish"
    elif "To: RFC Editor" in approval_text:
        action = "to_rfc_editor"
    else:
        action = "to_announcement_list"

    # NOTE: according to Michelle Cotton <michelle.cotton@icann.org>
    # (as per 2011-10-24) IANA is scraping these messages for
    # information so would like to know beforehand if the format
    # changes
    announcement = approval_text + "\n\n" + ballot_writeup
        
    if request.method == 'POST':
        if action == "do_not_publish":
            new_state = State.objects.get(used=True, type="draft-iesg", slug="dead")
        else:
            new_state = State.objects.get(used=True, type="draft-iesg", slug="ann")

        prev_state = doc.get_state("draft-iesg")
        prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        events = []

        if approval_mail_event.pk == None:
            approval_mail_event.save()
        if ballot_writeup_event.pk == None:
            ballot_writeup_event.save()

        if new_state.slug == "ann" and new_state.slug != prev_state.slug:
            # start by notifying the RFC Editor
            import ietf.sync.rfceditor
            response, error = ietf.sync.rfceditor.post_approved_draft(settings.RFC_EDITOR_SYNC_NOTIFICATION_URL, doc.name)
            if error:
                return render(request, 'doc/draft/rfceditor_post_approved_draft_failed.html',
                              dict(name=doc.name,
                                   response=response,
                                   error=error))

        doc.set_state(new_state)
        doc.tags.remove(*prev_tags)
        
        # fixup document
        close_open_ballots(doc, login)

        e = DocEvent(doc=doc, rev=doc.rev, by=login)
        if action == "do_not_publish":
            e.type = "iesg_disapproved"
            e.desc = "Do Not Publish note has been sent to the RFC Editor"
        else:
            e.type = "iesg_approved"
            e.desc = "IESG has approved the document"
        e.save()
        events.append(e)

        e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
        if e:
            events.append(e)
        e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=[])
        if e:
            events.append(e)

        doc.save_with_history(events)

        # send announcement
        send_mail_preformatted(request, announcement)

        if action == "to_announcement_list":
            addrs = gather_address_lists('ballot_approved_ietf_stream_iana').as_strings(compact=False)
            send_mail_preformatted(request, announcement, extra=extra_automation_headers(doc),
                                   override={ "To": addrs.to, "CC": addrs.cc, "Bcc": None, "Reply-To": []})

        msg = infer_message(announcement)
        msg.by = login
        msg.save()
        msg.related_docs.add(doc)

        downrefs = [rel for rel in doc.relateddocument_set.all() if rel.is_downref() and not rel.is_approved_downref()]
        if not downrefs:
            return HttpResponseRedirect(doc.get_absolute_url())
        else:
            return HttpResponseRedirect(doc.get_absolute_url()+'edit/approvedownrefs/')

    return render(request, 'doc/ballot/approve_ballot.html',
                              dict(doc=doc,
                                   action=action,
                                   announcement=announcement))


class ApproveDownrefsForm(forms.Form):
    checkboxes = ModelMultipleChoiceField(
        widget = forms.CheckboxSelectMultiple,
        queryset =  RelatedDocument.objects.none(), )


    def __init__(self, queryset, *args, **kwargs):
        super(ApproveDownrefsForm, self).__init__(*args, **kwargs)
        self.fields['checkboxes'].queryset = queryset

    def clean(self):
        if 'checkboxes' not in self.cleaned_data:
            raise forms.ValidationError("No RFCs were selected")

@role_required('Secretariat')
def approve_downrefs(request, name):
    """Document ballot was just approved; add the checked downwared references to the downref registry."""
    doc = get_object_or_404(Document, name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    downrefs_to_rfc = [
        rel
        for rel in doc.relateddocument_set.all()
        if rel.is_downref()
        and not rel.is_approved_downref()
        and rel.target.type_id == "rfc"
    ]

    downrefs_to_rfc_qs = RelatedDocument.objects.filter(pk__in=[r.pk for r in downrefs_to_rfc])        

    last_call_text = doc.latest_event(WriteupDocEvent, type="changed_last_call_text").text.strip()

    if request.method == 'POST':
        form = ApproveDownrefsForm(downrefs_to_rfc_qs, request.POST)
        if form.is_valid():
            for rel in form.cleaned_data['checkboxes']:
                RelatedDocument.objects.create(source=rel.source,
                        target=rel.target, relationship_id='downref-approval')
                c = DocEvent(type="downref_approved", doc=rel.source,
                        rev=rel.source.rev, by=login)
                c.desc = "Downref to RFC %s approved by Last Call for %s-%s" % (
                    rel.target.rfc_number, rel.source, rel.source.rev)
                c.save()
                c = DocEvent(type="downref_approved", doc=rel.target,
                        rev=rel.target.rev, by=login)
                c.desc = "Downref to RFC %s approved by Last Call for %s-%s" % (
                    rel.target.rfc_number, rel.source, rel.source.rev)
                c.save()

            return HttpResponseRedirect(doc.get_absolute_url())

    else:
        form = ApproveDownrefsForm(downrefs_to_rfc_qs)

    return render(request, 'doc/ballot/approve_downrefs.html',
                            dict(doc=doc,
                                 approve_downrefs_form=form,
                                 last_call_text=last_call_text,
                                 downrefs_to_rfc=downrefs_to_rfc))


class MakeLastCallForm(forms.Form):
    last_call_sent_date = forms.DateField(required=True)
    last_call_expiration_date = forms.DateField(required=True)

@role_required('Secretariat')
def make_last_call(request, name):
    """Make last call for Internet-Draft, sending out announcement."""
    doc = get_object_or_404(Document, name=name)
    if not (doc.get_state("draft-iesg") or doc.get_state("statchg")):
        raise Http404

    login = request.user.person

    announcement_event = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not announcement_event:
        if doc.type_id != 'draft':
            raise Http404
        announcement_event = generate_last_call_announcement(request, doc)
    announcement = announcement_event.text

    if request.method == 'POST':
        form = MakeLastCallForm(request.POST)
        if form.is_valid():
            if announcement_event.pk == None:
                announcement_event.save()

            send_mail_preformatted(request, announcement)
            if doc.type.slug in ("draft", "statchg"):
                addrs = gather_address_lists('last_call_issued_iana',doc=doc).as_strings(compact=False)
                send_mail_preformatted(request, announcement, extra=extra_automation_headers(doc),
                                       override={ "To": addrs.to, "CC": addrs.cc, "Bcc": None, "Reply-To": []})

            msg = infer_message(announcement)
            msg.by = login
            msg.save()
            msg.related_docs.add(doc)

            new_state = doc.get_state()
            prev_tags = []
            new_tags = []
            events = []

            if doc.type.slug == 'draft':
                new_state = State.objects.get(used=True, type="draft-iesg", slug='lc')
                prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
            elif doc.type.slug == 'statchg':
                new_state = State.objects.get(used=True, type="statchg", slug='in-lc')

            prev_state = doc.get_state(new_state.type_id)

            doc.set_state(new_state)
            doc.tags.remove(*prev_tags)

            e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)
            e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)
            expiration_date = form.cleaned_data['last_call_expiration_date']
            e = LastCallDocEvent(doc=doc, rev=doc.rev, by=login)
            e.type = "sent_last_call"
            e.desc = "The following Last Call announcement was sent out (ends %s):<br><br>" % expiration_date
            e.desc += announcement

            e_production_time = e.time.astimezone(DEADLINE_TZINFO)
            if form.cleaned_data['last_call_sent_date'] != e_production_time.date():
                lcsd = form.cleaned_data['last_call_sent_date']
                e.time = e_production_time.replace(year=lcsd.year, month=lcsd.month, day=lcsd.day)  # preserves tzinfo
            e.expires = datetime_from_date(expiration_date, DEADLINE_TZINFO)
            e.save()
            events.append(e)

            # update IANA Review state
            if doc.type.slug == 'draft':
                prev_state = doc.get_state("draft-iana-review")
                if not prev_state:
                    next_state = State.objects.get(used=True, type="draft-iana-review", slug="need-rev")
                    doc.set_state(next_state)
                    e = add_state_change_event(doc, login, prev_state, next_state)
                    if e:
                        events.append(e)

            doc.save_with_history(events)

            sub = doc.submission()
            if sub and sub.has_yang():
                email_lc_to_yang_doctors(request, doc)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        initial = {}
        initial["last_call_sent_date"] = date_today()
        if doc.type.slug == 'draft':
            # This logic is repeated in the code that edits last call text - why?
            expire_days = 14
            if doc.group.type_id in ("individ", "area"):
                expire_days = 28
            templ = 'doc/draft/make_last_call.html'
        else:
            expire_days=28
            templ = 'doc/status_change/make_last_call.html'

        initial["last_call_expiration_date"] = date_today() + datetime.timedelta(days=expire_days)
        
        form = MakeLastCallForm(initial=initial)
  
    return render(request, templ,
                              dict(doc=doc,
                                   form=form,
                                   announcement=announcement,
                                  ))

@role_required('Secretariat', 'IRTF Chair')
def issue_irsg_ballot(request, name):
    doc = get_object_or_404(Document, name=name)
    if doc.stream.slug != "irtf" or doc.type != DocTypeName.objects.get(slug="draft"):
        raise Http404

    by = request.user.person
    fillerdate = date_today(DEADLINE_TZINFO) + datetime.timedelta(weeks=2)

    if request.method == 'POST':
        button = request.POST.get("irsg_button")
        if button == 'Yes':
            duedate = request.POST.get("duedate")
            e = IRSGBallotDocEvent(doc=doc, rev=doc.rev, by=request.user.person)
            if (duedate == None or duedate==""):
                duedate = str(fillerdate)
            e.duedate = datetime_from_date(datetime.datetime.strptime(duedate, '%Y-%m-%d'), DEADLINE_TZINFO)
            e.type = "created_ballot"
            e.desc = "Created IRSG Ballot"
            ballot_type = BallotType.objects.get(doc_type=doc.type, slug="irsg-approve")
            e.ballot_type = ballot_type
            e.save()
            new_state = doc.get_state()
            prev_tags = []
            new_tags = []

            email_irsg_ballot_issued(request, doc, ballot=e)  # Send notification email

            if doc.type_id == 'draft':
                new_state = State.objects.get(used=True, type="draft-stream-irtf", slug='irsgpoll')

            prev_state = doc.get_state(new_state.type_id if new_state else None)

            doc.set_state(new_state)
            doc.tags.remove(*prev_tags)

            events = []
            e = add_state_change_event(doc, by, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)
            e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)

            if events:
                doc.save_with_history(events)

        return HttpResponseRedirect(doc.get_absolute_url())
    else:
        templ = 'doc/ballot/irsg_ballot_approve.html'

        question = "Confirm issuing a ballot for " + name + "?"
        return render(request, templ, dict(doc=doc,
                                           question=question, fillerdate=fillerdate))

@role_required('Secretariat', 'IRTF Chair')
def close_irsg_ballot(request, name):
    doc = get_object_or_404(Document, name=name)
    if doc.stream.slug != "irtf" or doc.type != DocTypeName.objects.get(slug="draft"):
        raise Http404

    by = request.user.person

    if request.method == 'POST':
        button = request.POST.get("irsg_button")
        if button == 'Yes':
            ballot = close_ballot(doc, by, "irsg-approve")
            email_irsg_ballot_closed(request,
                                     doc=doc,
                                     ballot=IRSGBallotDocEvent.objects.get(pk=ballot.pk))

        return HttpResponseRedirect(doc.get_absolute_url())

    templ = 'doc/ballot/irsg_ballot_close.html'

    question = "Confirm closing the ballot for " + name + "?"
    return render(request, templ, dict(doc=doc,
                                       question=question))

def irsg_ballot_status(request):
    possible_docs = Document.objects.filter(docevent__ballotdocevent__irsgballotdocevent__isnull=False)
    docs = []
    for doc in possible_docs:
        if doc.ballot_open("irsg-approve"):
            ballot = doc.active_ballot()
            if ballot:
                doc.ballot = ballot
                doc.duedate=datetime.datetime.strftime(
                    ballot.irsgballotdocevent.duedate.astimezone(DEADLINE_TZINFO),
                    '%Y-%m-%d',
                )

            docs.append(doc)

    return render(request, 'doc/irsg_ballot_status.html', {'docs':docs})

@role_required('Secretariat', 'RSAB Chair')
def issue_rsab_ballot(request, name):
    doc = get_object_or_404(Document, name=name)
    if doc.stream.slug != "editorial" or doc.type != DocTypeName.objects.get(slug="draft"):
        raise Http404

    by = request.user.person

    if request.method == 'POST':
        button = request.POST.get("rsab_button") # TODO: Really? There's an irsg button? The templates should be generalized.
        if button == 'Yes':
            e = BallotDocEvent(doc=doc, rev=doc.rev, by=request.user.person)
            e.type = "created_ballot"
            e.desc = "Created RSAB Ballot"
            ballot_type = BallotType.objects.get(doc_type=doc.type, slug="rsab-approve")
            e.ballot_type = ballot_type
            e.save()
            new_state = doc.get_state()
            prev_tags = []
            new_tags = []

            email_rsab_ballot_issued(request, doc, ballot=e)  # Send notification email

            if doc.type_id == 'draft':
                new_state = State.objects.get(used=True, type="draft-stream-editorial", slug='rsabpoll')

            prev_state = doc.get_state(new_state.type_id if new_state else None)

            doc.set_state(new_state)
            doc.tags.remove(*prev_tags)

            events = []
            e = add_state_change_event(doc, by, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)
            e = update_action_holders(doc, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
            if e:
                events.append(e)

            if events:
                doc.save_with_history(events)

        return HttpResponseRedirect(doc.get_absolute_url())
    else:
        templ = 'doc/ballot/rsab_ballot_approve.html'

        question = "Confirm issuing a ballot for " + name + "?"
        return render(request, templ, dict(doc=doc, question=question))

@role_required('Secretariat', 'RSAB Chair')
def close_rsab_ballot(request, name):
    doc = get_object_or_404(Document, name=name)
    if doc.stream.slug != "editorial" or doc.type_id != "draft":
        raise Http404

    by = request.user.person

    if request.method == 'POST':
        button = request.POST.get("rsab_button")
        if button == 'Yes':
            ballot = close_ballot(doc, by, "rsab-approve")
            email_rsab_ballot_closed(
                request,
                doc=doc,
                ballot=BallotDocEvent.objects.get(pk=ballot.pk)
            )
        return HttpResponseRedirect(doc.get_absolute_url())
        
    templ = 'doc/ballot/rsab_ballot_close.html'
    question = "Confirm closing the ballot for " + name + "?"
    return render(request, templ, dict(doc=doc, question=question))

def rsab_ballot_status(request):
    possible_docs = Document.objects.filter(docevent__ballotdocevent__isnull=False)
    docs = []
    for doc in possible_docs:
        if doc.ballot_open("rsab-approve"):
            ballot = doc.active_ballot()
            if ballot:
                doc.ballot = ballot

            docs.append(doc)
    return render(request, 'doc/rsab_ballot_status.html', {'docs':docs}) 
    # Possible TODO: add a menu item to show this? Maybe only if you're in rsab or an rswg chair?
    # There will be so few of these that the general community would follow them from the rswg docs page.
    # Maybe the view isn't actually needed at all...


def parse_ballot_edit_return_point(path, doc_name, ballot_id):
    get_default_path = lambda: urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc_name, ballot_id=ballot_id))
    allowed_path_handlers = {
        "ietf.community.views.view_list",
        "ietf.doc.views_doc.document_ballot",
        "ietf.doc.views_doc.document_irsg_ballot",
        "ietf.doc.views_doc.document_rsab_ballot",
        "ietf.doc.views_ballot.irsg_ballot_status",
        "ietf.doc.views_ballot.rsab_ballot_status",
        "ietf.doc.views_search.search",
        "ietf.doc.views_search.docs_for_ad",
        "ietf.doc.views_search.drafts_in_last_call",
        "ietf.doc.views_search.recent_drafts",
        "ietf.group.views.chartering_groups",
        "ietf.group.views.group_documents",
        "ietf.group.views.stream_documents",
        "ietf.iesg.views.agenda",
        "ietf.iesg.views.agenda_documents",
        "ietf.iesg.views.discusses",
        "ietf.iesg.views.past_documents",
    }
    return validate_return_to_path(path, get_default_path, allowed_path_handlers)

