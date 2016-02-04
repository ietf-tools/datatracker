# ballot management (voting, commenting, writeups, ...) for Area
# Directors and Secretariat

import datetime, json

from django.http import HttpResponseForbidden, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse as urlreverse
from django.template.loader import render_to_string
from django.template import RequestContext
from django import forms
from django.conf import settings

import debug                            # pyflakes:ignore

from ietf.doc.models import ( Document, State, DocEvent, BallotDocEvent, BallotPositionDocEvent,
    BallotType, LastCallDocEvent, WriteupDocEvent, save_document_in_history, IESG_SUBSTATE_TAGS )
from ietf.doc.utils import ( add_state_change_event, close_ballot, close_open_ballots,
    create_ballot_if_not_open, update_telechat )
from ietf.doc.mails import ( email_ballot_deferred, email_ballot_undeferred, 
    extra_automation_headers, generate_last_call_announcement, 
    generate_issue_ballot_mail, generate_ballot_writeup, generate_ballot_rfceditornote,
    generate_approval_mail )
from ietf.doc.lastcall import request_last_call
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, role_required
from ietf.message.utils import infer_message
from ietf.name.models import BallotPositionName
from ietf.person.models import Person
from ietf.utils.mail import send_mail_text, send_mail_preformatted
from ietf.mailtrigger.utils import gather_address_lists
from ietf.mailtrigger.forms import CcSelectForm

BALLOT_CHOICES = (("yes", "Yes"),
                  ("noobj", "No Objection"),
                  ("discuss", "Discuss"),
                  ("abstain", "Abstain"),
                  ("recuse", "Recuse"),
                  ("", "No Record"),
                  )

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def do_undefer_ballot(request, doc):
    '''
    Helper function to perform undefer of ballot.  Takes the Request object, for use in 
    logging, and the Document object.
    '''
    login = request.user.person
    telechat_date = TelechatDate.objects.active().order_by("date")[0].date
    save_document_in_history(doc)

    new_state = doc.get_state()
    prev_tags = new_tags = []

    if doc.type_id == 'draft':
        new_state = State.objects.get(used=True, type="draft-iesg", slug='iesg-eva')
        prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
    elif doc.type_id in ['conflrev','statchg']:
        new_state = State.objects.get(used=True, type=doc.type_id, slug='iesgeval')

    prev_state = doc.get_state(new_state.type_id if new_state else None)

    doc.set_state(new_state)
    doc.tags.remove(*prev_tags)

    e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
    
    doc.time = (e and e.time) or datetime.datetime.now()
    doc.save()

    update_telechat(request, doc, login, telechat_date)
    email_ballot_undeferred(request, doc, login.plain_name(), telechat_date)
    
def position_to_ballot_choice(position):
    for v, label in BALLOT_CHOICES:
        if v and getattr(position, v):
            return v
    return ""

def position_label(position_value):
    return dict(BALLOT_CHOICES).get(position_value, "")

# -------------------------------------------------
class EditPositionForm(forms.Form):
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.all(), widget=forms.RadioSelect, initial="norecord", required=True)
    discuss = forms.CharField(required=False, widget=forms.Textarea)
    comment = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        ballot_type = kwargs.pop("ballot_type")
        super(EditPositionForm, self).__init__(*args, **kwargs)
        self.fields['position'].queryset = ballot_type.positions.order_by('order')

    def clean_discuss(self):
       entered_discuss = self.cleaned_data["discuss"]
       entered_pos = self.cleaned_data.get("position", "norecord")
       if entered_pos.blocking and not entered_discuss:
           raise forms.ValidationError("You must enter a non-empty discuss")
       return entered_discuss

@role_required('Area Director','Secretariat')
def edit_position(request, name, ballot_id):
    """Vote and edit discuss and comment on document as Area Director."""
    doc = get_object_or_404(Document, docalias__name=name)
    ballot = get_object_or_404(BallotDocEvent, type="created_ballot", pk=ballot_id, doc=doc)

    ad = login = request.user.person

    if 'ballot_edit_return_point' in request.session:
        return_to_url = request.session['ballot_edit_return_point']
    else:
        return_to_url = urlreverse("doc_ballot", kwargs=dict(name=doc.name, ballot_id=ballot_id))

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if has_role(request.user, "Secretariat"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404
        ad = get_object_or_404(Person, pk=ad_id)

    old_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=ad, ballot=ballot)

    if request.method == 'POST':
        if not has_role(request.user, "Secretariat") and not ad.role_set.filter(name="ad", group__type="area", group__state="active"):
            # prevent pre-ADs from voting
            return HttpResponseForbidden("Must be a proper Area Director in an active area to cast ballot")
        
        form = EditPositionForm(request.POST, ballot_type=ballot.ballot_type)
        if form.is_valid():
            # save the vote
            clean = form.cleaned_data

            pos = BallotPositionDocEvent(doc=doc, by=login)
            pos.type = "changed_ballot_position"
            pos.ballot = ballot
            pos.ad = ad
            pos.pos = clean["position"]
            pos.comment = clean["comment"].rstrip()
            pos.comment_time = old_pos.comment_time if old_pos else None
            pos.discuss = clean["discuss"].rstrip()
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
                    e = DocEvent(doc=doc)
                    e.by = ad # otherwise we can't see who's saying it
                    e.type = "added_comment"
                    e.desc = "[Ballot comment]\n" + pos.comment
                    added_events.append(e)

            old_discuss = old_pos.discuss if old_pos else ""
            if pos.discuss != old_discuss:
                pos.discuss_time = pos.time
                changes.append("discuss")

                if pos.pos.blocking:
                    e = DocEvent(doc=doc, by=login)
                    e.by = ad # otherwise we can't see who's saying it
                    e.type = "added_comment"
                    e.desc = "[Ballot %s]\n" % pos.pos.name.lower()
                    e.desc += pos.discuss
                    added_events.append(e)

            # figure out a description
            if not old_pos and pos.pos.slug != "norecord":
                pos.desc = u"[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.plain_name())
            elif old_pos and pos.pos != old_pos.pos:
                pos.desc = "[Ballot Position Update] Position for %s has been changed to %s from %s" % (pos.ad.plain_name(), pos.pos.name, old_pos.pos.name)

            if not pos.desc and changes:
                pos.desc = u"Ballot %s text updated for %s" % (u" and ".join(changes), ad.plain_name())

            # only add new event if we actually got a change
            if pos.desc:
                if login != ad:
                    pos.desc += u" by %s" % login.plain_name()

                pos.save()

                for e in added_events:
                    e.save() # save them after the position is saved to get later id for sorting order
                        
            if request.POST.get("send_mail"):
                qstr=""
                if request.GET.get('ad'):
                    qstr += "?ad=%s" % request.GET.get('ad')
                return HttpResponseRedirect(urlreverse("doc_send_ballot_comment", kwargs=dict(name=doc.name, ballot_id=ballot_id)) + qstr)
            elif request.POST.get("Defer"):
                return redirect("doc_defer_ballot", name=doc)
            elif request.POST.get("Undefer"):
                return redirect("doc_undefer_ballot", name=doc)
            else:
                return HttpResponseRedirect(return_to_url)
    else:
        initial = {}
        if old_pos:
            initial['position'] = old_pos.pos.slug
            initial['discuss'] = old_pos.discuss
            initial['comment'] = old_pos.comment
            
        form = EditPositionForm(initial=initial, ballot_type=ballot.ballot_type)

    blocking_positions = dict((p.pk, p.name) for p in form.fields["position"].queryset.all() if p.blocking)

    ballot_deferred = doc.active_defer_event()

    return render_to_response('doc/ballot/edit_position.html',
                              dict(doc=doc,
                                   form=form,
                                   ad=ad,
                                   return_to_url=return_to_url,
                                   old_pos=old_pos,
                                   ballot_deferred=ballot_deferred,
                                   ballot = ballot,
                                   show_discuss_text=old_pos and old_pos.pos.blocking,
                                   blocking_positions=json.dumps(blocking_positions),
                                   ),
                              context_instance=RequestContext(request))


@role_required('Area Director','Secretariat')
def send_ballot_comment(request, name, ballot_id):
    """Email document ballot position discuss/comment for Area Director."""
    doc = get_object_or_404(Document, docalias__name=name)
    ballot = get_object_or_404(BallotDocEvent, type="created_ballot", pk=ballot_id, doc=doc)

    ad = request.user.person

    if 'ballot_edit_return_point' in request.session:
        return_to_url = request.session['ballot_edit_return_point']
    else:
        return_to_url = urlreverse("doc_ballot", kwargs=dict(name=doc.name, ballot_id=ballot_id))

    if 'HTTP_REFERER' in request.META:
        back_url = request.META['HTTP_REFERER']
    else:
        back_url = urlreverse("doc_ballot", kwargs=dict(name=doc.name, ballot_id=ballot_id))

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not has_role(request.user, "Area Director"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404
        ad = get_object_or_404(Person, pk=ad_id)

    pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=ad, ballot=ballot)
    if not pos:
        raise Http404

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

    ad_name_genitive = ad.plain_name() + "'" if ad.plain_name().endswith('s') else ad.plain_name() + "'s"
    subject = "%s %s on %s" % (ad_name_genitive, pos.pos.name if pos.pos else "No Position", doc.name + "-" + doc.rev)
    if subj:
        subject += ": (with %s)" % " and ".join(subj)

    body = render_to_string("doc/ballot/ballot_comment_mail.txt",
                            dict(discuss=d,
                                 comment=c,
                                 ad=ad.plain_name(),
                                 doc=doc,
                                 pos=pos.pos,
                                 blocking_name=blocking_name,
                                 settings=settings))
    frm = ad.role_email("ad").formatted_email()
    
    addrs = gather_address_lists('ballot_saved',doc=doc)
        
    if request.method == 'POST':
        cc = []
        cc_select_form = CcSelectForm(data=request.POST,mailtrigger_slug='ballot_saved',mailtrigger_context={'doc':doc})
        if cc_select_form.is_valid():
            cc.extend(cc_select_form.get_selected_addresses())
        extra_cc = [x.strip() for x in request.POST.get("extra_cc","").split(',') if x.strip()]
        if extra_cc:
            cc.extend(extra_cc)

        send_mail_text(request, addrs.to, frm, subject, body, cc=u", ".join(cc))
            
        return HttpResponseRedirect(return_to_url)

    else: 

        cc_select_form = CcSelectForm(mailtrigger_slug='ballot_saved',mailtrigger_context={'doc':doc})
  
    return render_to_response('doc/ballot/send_ballot_comment.html',
                              dict(doc=doc,
                                   subject=subject,
                                   body=body,
                                   frm=frm,
                                   to=addrs.as_strings().to,
                                   ad=ad,
                                   can_send=d or c,
                                   back_url=back_url,
                                   cc_select_form = cc_select_form,
                                  ),
                              context_instance=RequestContext(request))

@role_required('Secretariat')
def clear_ballot(request, name):
    """Clear all positions and discusses on every open ballot for a document."""
    doc = get_object_or_404(Document, name=name)
    if request.method == 'POST':
        by = request.user.person
        for t in BallotType.objects.filter(doc_type=doc.type_id):
            close_ballot(doc, by, t.slug)
            create_ballot_if_not_open(doc, by, t.slug)
        if doc.get_state('draft-iesg').slug == 'defer':
            do_undefer_ballot(request,doc)
        return redirect("doc_view", name=doc.name)

    return render_to_response('doc/ballot/clear_ballot.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

@role_required('Area Director','Secretariat')
def defer_ballot(request, name):
    """Signal post-pone of ballot, notifying relevant parties."""
    doc = get_object_or_404(Document, docalias__name=name)
    if doc.type_id not in ('draft','conflrev','statchg'):
        raise Http404
    interesting_state = dict(draft='draft-iesg',conflrev='conflrev',statchg='statchg')
    state = doc.get_state(interesting_state[doc.type_id])
    if not state or state.slug=='defer' or not doc.telechat_date():
        raise Http404

    login = request.user.person
    telechat_date = TelechatDate.objects.active().order_by("date")[1].date

    if request.method == 'POST':
        save_document_in_history(doc)

        new_state = doc.get_state()
        prev_tags = new_tags = []

        if doc.type_id == 'draft':
            new_state = State.objects.get(used=True, type="draft-iesg", slug='defer')
            prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
        elif doc.type_id in ['conflrev','statchg']:
            new_state = State.objects.get(used=True, type=doc.type_id, slug='defer')

        prev_state = doc.get_state(new_state.type_id if new_state else None)

        doc.set_state(new_state)
        doc.tags.remove(*prev_tags)

        e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)
        
        doc.time = (e and e.time) or datetime.datetime.now()
        doc.save()

        update_telechat(request, doc, login, telechat_date)
        email_ballot_deferred(request, doc, login.plain_name(), telechat_date)

        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('doc/ballot/defer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

@role_required('Area Director','Secretariat')
def undefer_ballot(request, name):
    """undo deferral of ballot ballot."""
    doc = get_object_or_404(Document, docalias__name=name)
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
  
    return render_to_response('doc/ballot/undefer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

class LastCallTextForm(forms.Form):
    last_call_text = forms.CharField(widget=forms.Textarea, required=True)
    
    def clean_last_call_text(self):
        lines = self.cleaned_data["last_call_text"].split("\r\n")
        for l, next in zip(lines, lines[1:]):
            if l.startswith('Subject:') and next.strip():
                raise forms.ValidationError("Subject line appears to have a line break, please make sure there is no line breaks in the subject line and that it is followed by an empty line.")
        
        return self.cleaned_data["last_call_text"].replace("\r", "")


@role_required('Area Director','Secretariat')
def lastcalltext(request, name):
    """Editing of the last call text"""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not existing:
        existing = generate_last_call_announcement(request, doc)
        
    form = LastCallTextForm(initial=dict(last_call_text=existing.text))

    if request.method == 'POST':
        if "save_last_call_text" in request.POST or "send_last_call_request" in request.POST:
            form = LastCallTextForm(request.POST)
            if form.is_valid():
                t = form.cleaned_data['last_call_text']
                if t != existing.text:
                    e = WriteupDocEvent(doc=doc, by=login)
                    e.by = login
                    e.type = "changed_last_call_text"
                    e.desc = "Last call announcement was changed"
                    e.text = t
                    e.save()
                
                if "send_last_call_request" in request.POST:
                    save_document_in_history(doc)

                    prev_state = doc.get_state("draft-iesg")
                    new_state = State.objects.get(used=True, type="draft-iesg", slug='lc-req')

                    prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)

                    doc.set_state(new_state)
                    doc.tags.remove(*prev_tags)

                    e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=[])

                    doc.time = (e and e.time) or datetime.datetime.now()
                    doc.save()

                    request_last_call(request, doc)
                    
                    return render_to_response('doc/draft/last_call_requested.html',
                                              dict(doc=doc),
                                              context_instance=RequestContext(request))
        
        if "regenerate_last_call_text" in request.POST:
            e = generate_last_call_announcement(request, doc)
            
            # make sure form has the updated text
            form = LastCallTextForm(initial=dict(last_call_text=e.text))


    s = doc.get_state("draft-iesg")
    can_request_last_call = s.order < 27
    can_make_last_call = s.order < 20
    
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('doc/ballot/lastcalltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   last_call_form=form,
                                   can_request_last_call=can_request_last_call,
                                   can_make_last_call=can_make_last_call,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

class BallotWriteupForm(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
@role_required('Area Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    doc = get_object_or_404(Document, docalias__name=name)

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not existing:
        existing = generate_ballot_writeup(request, doc)
        
    form = BallotWriteupForm(initial=dict(ballot_writeup=existing.text))

    if request.method == 'POST' and "save_ballot_writeup" in request.POST or "issue_ballot" in request.POST:
        form = BallotWriteupForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["ballot_writeup"]
            if t != existing.text:
                e = WriteupDocEvent(doc=doc, by=login)
                e.by = login
                e.type = "changed_ballot_writeup_text"
                e.desc = "Ballot writeup was changed"
                e.text = t
                e.save()

            if "issue_ballot" in request.POST:
                create_ballot_if_not_open(doc, login, "approve")
                ballot = doc.latest_event(BallotDocEvent, type="created_ballot")

                if has_role(request.user, "Area Director") and not doc.latest_event(BallotPositionDocEvent, ad=login, ballot=ballot):
                    # sending the ballot counts as a yes
                    pos = BallotPositionDocEvent(doc=doc, by=login)
                    pos.ballot = ballot
                    pos.type = "changed_ballot_position"
                    pos.ad = login
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.plain_name())
                    pos.save()

                    # Consider mailing this position to 'ballot_saved'

                approval = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
                if not approval:
                    approval = generate_approval_mail(request, doc)

                msg = generate_issue_ballot_mail(request, doc, ballot)

                addrs = gather_address_lists('ballot_issued',doc=doc).as_strings()
                override = {'To':addrs.to}
                if addrs.cc:
                    override['CC'] = addrs.cc
                send_mail_preformatted(request, msg, override=override)

                addrs = gather_address_lists('ballot_issued_iana',doc=doc).as_strings()
                override={ "To": "IANA <%s>"%settings.IANA_EVAL_EMAIL, "Bcc": None , "Reply-To": None}
                if addrs.cc:
                    override['CC'] = addrs.cc
                send_mail_preformatted(request, msg, extra=extra_automation_headers(doc),
                                       override={ "To": "IANA <%s>"%settings.IANA_EVAL_EMAIL, "CC": None, "Bcc": None , "Reply-To": None})

                e = DocEvent(doc=doc, by=login)
                e.by = login
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been issued"
                e.save()

                return render_to_response('doc/ballot/ballot_issued.html',
                                          dict(doc=doc,
                                               back_url=doc.get_absolute_url()),
                                          context_instance=RequestContext(request))
                        

    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('doc/ballot/writeupnotes.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   ballot_issued=bool(doc.latest_event(type="sent_ballot_announcement")),
                                   ballot_writeup_form=form,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

class BallotRfcEditorNoteForm(forms.Form):
    rfc_editor_note = forms.CharField(widget=forms.Textarea, label="RFC Editor Note", required=True)

    def clean_rfc_editor_note(self):
        return self.cleaned_data["rfc_editor_note"].replace("\r", "")
        
@role_required('Area Director','Secretariat')
def ballot_rfceditornote(request, name):
    """Editing of RFC Editor Note in the ballot"""
    doc = get_object_or_404(Document, docalias__name=name)

    login = request.user.person


        
    existing = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
    if not existing or (existing.text == ""):
        existing = generate_ballot_rfceditornote(request, doc)

    form = BallotRfcEditorNoteForm(auto_id=False, initial=dict(rfc_editor_note=existing.text))

    if request.method == 'POST' and "save_ballot_rfceditornote" in request.POST:
        form = BallotRfcEditorNoteForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["rfc_editor_note"]
            if t != existing.text:
                e = WriteupDocEvent(doc=doc, by=login)
                e.by = login
                e.type = "changed_rfc_editor_note_text"
                e.desc = "RFC Editor Note was changed"
                e.text = t.rstrip()
                e.save()

    if request.method == 'POST' and "clear_ballot_rfceditornote" in request.POST:
        e = WriteupDocEvent(doc=doc, by=login)
        e.by = login
        e.type = "changed_rfc_editor_note_text"
        e.desc = "RFC Editor Note was cleared"
        e.text = ""
        e.save()

        # make sure form shows a blank RFC Editor Note
        form = BallotRfcEditorNoteForm(initial=dict(rfc_editor_note=" "))

    return render_to_response('doc/ballot/rfceditornote.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   ballot_rfceditornote_form=form,
                                   ),
                              context_instance=RequestContext(request))

class ApprovalTextForm(forms.Form):
    approval_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_approval_text(self):
        return self.cleaned_data["approval_text"].replace("\r", "")

@role_required('Area Director','Secretariat')
def ballot_approvaltext(request, name):
    """Editing of approval text"""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    existing = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    if not existing:
        existing = generate_approval_mail(request, doc)

    form = ApprovalTextForm(initial=dict(approval_text=existing.text))

    if request.method == 'POST':
        if "save_approval_text" in request.POST:
            form = ApprovalTextForm(request.POST)
            if form.is_valid():
                t = form.cleaned_data['approval_text']
                if t != existing.text:
                    e = WriteupDocEvent(doc=doc, by=login)
                    e.by = login
                    e.type = "changed_ballot_approval_text"
                    e.desc = "Ballot approval text was changed"
                    e.text = t
                    e.save()
                
        if "regenerate_approval_text" in request.POST:
            e = generate_approval_mail(request, doc)

            # make sure form has the updated text
            form = ApprovalTextForm(initial=dict(approval_text=e.text))

    can_announce = doc.get_state("draft-iesg").order > 19
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('doc/ballot/approvaltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   approval_text_form=form,
                                   can_announce=can_announce,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

@role_required('Secretariat')
def approve_ballot(request, name):
    """Approve ballot, sending out announcement, changing state."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404

    login = request.user.person

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    if not e:
        e = generate_approval_mail(request, doc)
    approval_text = e.text

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not e:
        e = generate_ballot_writeup(request, doc)
    ballot_writeup = e.text

    error_duplicate_rfc_editor_note = False
    e = doc.latest_event(WriteupDocEvent, type="changed_rfc_editor_note_text")
    if e and (e.text != ""):
        if "RFC Editor Note" in ballot_writeup:
            error_duplicate_rfc_editor_note = True
        ballot_writeup += "\n\n" + e.text

    if error_duplicate_rfc_editor_note:
        return render_to_response('doc/draft/rfceditor_note_duplicate_error.html',
                                  dict(doc=doc),
                                  context_instance=RequestContext(request))

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

        if new_state.slug == "ann" and new_state.slug != prev_state.slug and not request.REQUEST.get("skiprfceditorpost"):
            # start by notifying the RFC Editor
            import ietf.sync.rfceditor
            response, error = ietf.sync.rfceditor.post_approved_draft(settings.RFC_EDITOR_SYNC_NOTIFICATION_URL, doc.name)
            if error:
                return render_to_response('doc/draft/rfceditor_post_approved_draft_failed.html',
                                  dict(name=doc.name,
                                       response=response,
                                       error=error),
                                  context_instance=RequestContext(request))

        save_document_in_history(doc)

        doc.set_state(new_state)
        doc.tags.remove(*prev_tags)
        
        # fixup document
        close_open_ballots(doc, login)

        e = DocEvent(doc=doc, by=login)
        if action == "do_not_publish":
            e.type = "iesg_disapproved"
            e.desc = "Do Not Publish note has been sent to the RFC Editor"
        else:
            e.type = "iesg_approved"
            e.desc = "IESG has approved the document"

        e.save()
        
        e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=[])

        doc.time = (e and e.time) or datetime.datetime.now()
        doc.save()

        # send announcement

        send_mail_preformatted(request, announcement)

        if action == "to_announcement_list":
            addrs = gather_address_lists('ballot_approved_ietf_stream_iana').as_strings(compact=False)
            send_mail_preformatted(request, announcement, extra=extra_automation_headers(doc),
                                   override={ "To": addrs.to, "CC": addrs.cc, "Bcc": None, "Reply-To": None})

        msg = infer_message(announcement)
        msg.by = login
        msg.save()
        msg.related_docs.add(doc)

        return HttpResponseRedirect(doc.get_absolute_url())

    return render_to_response('doc/ballot/approve_ballot.html',
                              dict(doc=doc,
                                   action=action,
                                   announcement=announcement),
                              context_instance=RequestContext(request))


class MakeLastCallForm(forms.Form):
    last_call_sent_date = forms.DateField(required=True)
    last_call_expiration_date = forms.DateField(required=True)

@role_required('Secretariat')
def make_last_call(request, name):
    """Make last call for Internet Draft, sending out announcement."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not (doc.get_state("draft-iesg") or doc.get_state("statchg")):
        raise Http404

    login = request.user.person

    e = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not e:
        if doc.type.slug != 'draft':
            raise Http404
        e = generate_last_call_announcement(request, doc)
    announcement = e.text

    if request.method == 'POST':
        form = MakeLastCallForm(request.POST)
        if form.is_valid():
            send_mail_preformatted(request, announcement)
            if doc.type.slug == 'draft':
                addrs = gather_address_lists('last_call_issued_iana',doc=doc).as_strings(compact=False)
                send_mail_preformatted(request, announcement, extra=extra_automation_headers(doc),
                                       override={ "To": addrs.to, "CC": addrs.cc, "Bcc": None, "Reply-To": None})

            msg = infer_message(announcement)
            msg.by = login
            msg.save()
            msg.related_docs.add(doc)

            save_document_in_history(doc)

            new_state = doc.get_state()
            prev_tags = new_tags = []

            if doc.type.slug == 'draft':
                new_state = State.objects.get(used=True, type="draft-iesg", slug='lc')
                prev_tags = doc.tags.filter(slug__in=IESG_SUBSTATE_TAGS)
            elif doc.type.slug == 'statchg':
                new_state = State.objects.get(used=True, type="statchg", slug='in-lc')

            prev_state = doc.get_state(new_state.type_id)

            doc.set_state(new_state)
            doc.tags.remove(*prev_tags)

            e = add_state_change_event(doc, login, prev_state, new_state, prev_tags=prev_tags, new_tags=new_tags)

            doc.time = (e and e.time) or datetime.datetime.now()
            doc.save()

            e = LastCallDocEvent(doc=doc, by=login)
            e.type = "sent_last_call"
            e.desc = "The following Last Call announcement was sent out:<br><br>"
            e.desc += announcement

            if form.cleaned_data['last_call_sent_date'] != e.time.date():
                e.time = datetime.datetime.combine(form.cleaned_data['last_call_sent_date'], e.time.time())
            e.expires = form.cleaned_data['last_call_expiration_date']
            e.save()

            # update IANA Review state
            if doc.type.slug == 'draft':
                prev_state = doc.get_state("draft-iana-review")
                if not prev_state:
                    next_state = State.objects.get(used=True, type="draft-iana-review", slug="need-rev")
                    doc.set_state(next_state)
                    add_state_change_event(doc, login, prev_state, next_state)

            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        initial = {}
        initial["last_call_sent_date"] = datetime.date.today()
        if doc.type.slug == 'draft':
            # This logic is repeated in the code that edits last call text - why?
            expire_days = 14
            if doc.group.type_id in ("individ", "area"):
                expire_days = 28
            templ = 'doc/draft/make_last_call.html'
        else:
            expire_days=28
            templ = 'doc/status_change/make_last_call.html'

        initial["last_call_expiration_date"] = datetime.date.today() + datetime.timedelta(days=expire_days)
        
        form = MakeLastCallForm(initial=initial)
  
    return render_to_response(templ,
                              dict(doc=doc,
                                   form=form,
                                   announcement=announcement,
                                  ),
                              context_instance=RequestContext(request))
