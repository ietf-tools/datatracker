# ballot management (voting, commenting, writeups, ...) for Area
# Directors and Secretariat

import re, os
from datetime import datetime, date, time, timedelta
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse as urlreverse
from django.template.loader import render_to_string
from django.template import RequestContext
from django import forms
from django.utils.html import strip_tags
from django.conf import settings

from ietf.utils.mail import send_mail_text, send_mail_preformatted
from ietf.ietfauth.decorators import group_required
from ietf.idtracker.templatetags.ietf_filters import in_group
from ietf.ietfauth.decorators import has_role
from ietf.idtracker.models import *
from ietf.iesg.models import *
from ietf.ipr.models import IprDetail
from ietf.ipr.search import iprs_from_docs
from ietf.idrfc.mails import *
from ietf.idrfc.utils import *
from ietf.idrfc.lastcall import request_last_call
from ietf.idrfc.idrfc_wrapper import BallotWrapper

from redesign.doc.models import *
from redesign.name.models import BallotPositionName


BALLOT_CHOICES = (("yes", "Yes"),
                  ("noobj", "No Objection"),
                  ("discuss", "Discuss"),
                  ("abstain", "Abstain"),
                  ("recuse", "Recuse"),
                  ("", "No Record"),
                  )

def position_to_ballot_choice(position):
    for v, label in BALLOT_CHOICES:
        if v and getattr(position, v):
            return v
    return ""

def position_label(position_value):
    return dict(BALLOT_CHOICES).get(position_value, "")

def get_ballot_info(ballot, area_director):
    pos = Position.objects.filter(ballot=ballot, ad=area_director)
    pos = pos[0] if pos else None
    
    discuss = IESGDiscuss.objects.filter(ballot=ballot, ad=area_director)
    discuss = discuss[0] if discuss else None
    
    comment = IESGComment.objects.filter(ballot=ballot, ad=area_director)
    comment = comment[0] if comment else None
    
    return (pos, discuss, comment)

class EditPositionForm(forms.Form):
    position = forms.ChoiceField(choices=BALLOT_CHOICES, widget=forms.RadioSelect, required=False)
    discuss_text = forms.CharField(required=False, widget=forms.Textarea)
    comment_text = forms.CharField(required=False, widget=forms.Textarea)
    return_to_url = forms.CharField(required=False, widget=forms.HiddenInput)
    def clean_discuss_text(self):
       entered_discuss = self.cleaned_data["discuss_text"]
       entered_pos = self.cleaned_data["position"]
       if entered_pos == "discuss" and not entered_discuss:
         print "Raising discuss ",entered_pos," ",entered_discuss
         raise forms.ValidationError("You must enter a non-empty discuss")
       return entered_discuss

@group_required('Area_Director','Secretariat')
def edit_position(request, name):
    """Vote and edit discuss and comment on Internet Draft as Area Director."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    ad = login = IESGLogin.objects.get(login_name=request.user.username)

    if 'HTTP_REFERER' in request.META:
      return_to_url = request.META['HTTP_REFERER']
    else:
      return_to_url = doc.idinternal.get_absolute_url()


    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not in_group(request.user, "Area_Director"):
        ad_username = request.GET.get('ad')
        if not ad_username:
            raise Http404()
        ad = get_object_or_404(IESGLogin, login_name=ad_username)

    pos, discuss, comment = get_ballot_info(doc.idinternal.ballot, ad)

    if request.method == 'POST':
        form = EditPositionForm(request.POST)
        if form.is_valid():
             # save the vote
            clean = form.cleaned_data

            if clean['return_to_url']:
              return_to_url = clean['return_to_url']

            vote = clean['position']
            if pos:
                # mark discuss as cleared (quirk from old system)
                if pos.discuss:
                    pos.discuss = -1
            else:
                pos = Position(ballot=doc.idinternal.ballot, ad=ad)
                pos.discuss = 0
                
            old_vote = position_to_ballot_choice(pos)
            
            pos.yes = pos.noobj = pos.abstain = pos.recuse = 0
            if vote:
                setattr(pos, vote, 1)

            if pos.id:
                if vote:
                    pos.save()
                else:
                    pos.delete()
                if vote != old_vote:
                    add_document_comment(request, doc, "[Ballot Position Update] Position for %s has been changed to %s from %s" % (pos.ad, position_label(vote), position_label(old_vote)))
            elif vote:
                pos.save()
                add_document_comment(request, doc, "[Ballot Position Update] New position, %s, has been recorded" % position_label(vote))

            # save discuss
            if (discuss and clean['discuss_text'] != discuss.text) or (clean['discuss_text'] and not discuss):
                if not discuss:
                    discuss = IESGDiscuss(ballot=doc.idinternal.ballot, ad=ad)

                discuss.text = clean['discuss_text']
                discuss.date = date.today()
                discuss.revision = doc.revision_display()
                discuss.active = True
                discuss.save()

                if discuss.text:
                    add_document_comment(request, doc, discuss.text,
                                         ballot=DocumentComment.BALLOT_DISCUSS)

            if pos.discuss < 1:
                IESGDiscuss.objects.filter(ballot=doc.idinternal.ballot, ad=pos.ad).update(active=False)

            # similar for comment (could share code with discuss, but
            # it's maybe better to coalesce them in the model instead
            # than doing a clever hack here)
            if (comment and clean['comment_text'] != comment.text) or (clean['comment_text'] and not comment):
                if not comment:
                    comment = IESGComment(ballot=doc.idinternal.ballot, ad=ad)

                comment.text = clean['comment_text']
                comment.date = date.today()
                comment.revision = doc.revision_display()
                comment.active = True
                comment.save()

                if comment.text:
                    add_document_comment(request, doc, comment.text,
                                         ballot=DocumentComment.BALLOT_COMMENT)
            
            doc.idinternal.event_date = date.today()
            doc.idinternal.save()

            if request.POST.get("send_mail"):
                qstr = "?return_to_url=%s" % return_to_url
                if request.GET.get('ad'):
                    qstr += "&ad=%s" % request.GET.get('ad')
                return HttpResponseRedirect(urlreverse("doc_send_ballot_comment", kwargs=dict(name=doc.filename)) + qstr)
            else:
              if request.POST.get("Defer"):
                  return HttpResponseRedirect(urlreverse("doc_defer_ballot", kwargs=dict(name=doc)))
              else:
                  if request.POST.get("Undefer"):
                      return HttpResponseRedirect(urlreverse("doc_undefer_ballot", kwargs=dict(name=doc)))
                  else:
                      return HttpResponseRedirect(return_to_url)
    else:
        initial = {}
        if pos:
            initial['position'] = position_to_ballot_choice(pos)

        if discuss:
            initial['discuss_text'] = discuss.text

        if comment:
            initial['comment_text'] = comment.text

        if return_to_url:
            initial['return_to_url'] = return_to_url
            
        form = EditPositionForm(initial=initial)
  

    return render_to_response('idrfc/edit_position.html',
                              dict(doc=doc,
                                   form=form,
                                   discuss=discuss,
                                   comment=comment,
                                   ad=ad,
                                   return_to_url=return_to_url,
                                   ballot=BallotWrapper(doc.idinternal)
                                   ),
                              context_instance=RequestContext(request))

class EditPositionFormREDESIGN(forms.Form):
    position = forms.ModelChoiceField(queryset=BallotPositionName.objects.all(), widget=forms.RadioSelect, initial="norecord", required=True)
    discuss = forms.CharField(required=False, widget=forms.Textarea)
    comment = forms.CharField(required=False, widget=forms.Textarea)
    return_to_url = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_discuss(self):
       entered_discuss = self.cleaned_data["discuss"]
       entered_pos = self.cleaned_data["position"]
       if entered_pos.slug == "discuss" and not entered_discuss:
           raise forms.ValidationError("You must enter a non-empty discuss")
       return entered_discuss

@group_required('Area_Director','Secretariat')
def edit_positionREDESIGN(request, name):
    """Vote and edit discuss and comment on Internet Draft as Area Director."""
    doc = get_object_or_404(Document, docalias__name=name)
    started_process = doc.latest_event(type="started_iesg_process")
    if not doc.get_state("draft-iesg") or not started_process:
        raise Http404()

    ad = login = request.user.get_profile()

    if 'HTTP_REFERER' in request.META:
        return_to_url = request.META['HTTP_REFERER']
    else:
        return_to_url = doc.get_absolute_url()

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not has_role(request.user, "Area Director"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404()
        from person.models import Person
        ad = get_object_or_404(Person, pk=ad_id)

    old_pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=ad, time__gte=started_process.time)

    if request.method == 'POST':
        form = EditPositionForm(request.POST)
        if form.is_valid():
 
            # save the vote
            clean = form.cleaned_data

            if clean['return_to_url']:
              return_to_url = clean['return_to_url']

            pos = BallotPositionDocEvent(doc=doc, by=login)
            pos.type = "changed_ballot_position"
            pos.ad = ad
            pos.pos = clean["position"]
            pos.comment = clean["comment"].strip()
            pos.comment_time = old_pos.comment_time if old_pos else None
            pos.discuss = clean["discuss"].strip()
            pos.discuss_time = old_pos.discuss_time if old_pos else None

            changes = []
            added_events = []
            # possibly add discuss/comment comments to history trail
            # so it's easy to see
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

                if pos.discuss:
                    e = DocEvent(doc=doc, by=login)
                    e.by = ad # otherwise we can't see who's saying it
                    e.type = "added_comment"
                    e.desc = "[Ballot discuss]\n" + pos.discuss
                    added_events.append(e)

            # figure out a description
            if not old_pos and pos.pos.slug != "norecord":
                pos.desc = u"[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.name)
            elif old_pos and pos.pos != old_pos.pos:
                pos.desc = "[Ballot Position Update] Position for %s has been changed to %s from %s" % (pos.ad.name, pos.pos.name, old_pos.pos.name)

            if not pos.desc and changes:
                pos.desc = u"Ballot %s text updated for %s" % (u" and ".join(changes), ad.name)

            # only add new event if we actually got a change
            if pos.desc:
                if login != ad:
                    pos.desc += u" by %s" % login.name

                pos.save()

                for e in added_events:
                    e.save() # save them after the position is saved to get later id
                        
            if request.POST.get("send_mail"):
                qstr = "?return_to_url=%s" % return_to_url
                if request.GET.get('ad'):
                    qstr += "&ad=%s" % request.GET.get('ad')
                return HttpResponseRedirect(urlreverse("doc_send_ballot_comment", kwargs=dict(name=doc.name)) + qstr)
            elif request.POST.get("Defer"):
                return HttpResponseRedirect(urlreverse("doc_defer_ballot", kwargs=dict(name=doc)))
            elif request.POST.get("Undefer"):
                return HttpResponseRedirect(urlreverse("doc_undefer_ballot", kwargs=dict(name=doc)))
            else:
                return HttpResponseRedirect(return_to_url)
    else:
        initial = {}
        if old_pos:
            initial['position'] = old_pos.pos.slug
            initial['discuss'] = old_pos.discuss
            initial['comment'] = old_pos.comment
            
        if return_to_url:
            initial['return_to_url'] = return_to_url
            
        form = EditPositionForm(initial=initial)

    ballot_deferred = None
    if doc.get_state_slug("draft-iesg") == "defer":
        ballot_deferred = doc.latest_event(type="changed_document", desc__startswith="State changed to <b>IESG Evaluation - Defer</b>")

    return render_to_response('idrfc/edit_positionREDESIGN.html',
                              dict(doc=doc,
                                   form=form,
                                   ad=ad,
                                   return_to_url=return_to_url,
                                   old_pos=old_pos,
                                   ballot_deferred=ballot_deferred,
                                   ),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    edit_position = edit_positionREDESIGN
    EditPositionForm = EditPositionFormREDESIGN


@group_required('Area_Director','Secretariat')
def send_ballot_comment(request, name):
    """Email Internet Draft ballot discuss/comment for area director."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    ad = login = IESGLogin.objects.get(login_name=request.user.username)

    return_to_url = request.GET.get('return_to_url')
    if not return_to_url:
        return_to_url = doc.idinternal.get_absolute_url()

    if 'HTTP_REFERER' in request.META:
      back_url = request.META['HTTP_REFERER']
    else:
      back_url = doc.idinternal.get_absolute_url()



    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not in_group(request.user, "Area_Director"):
        ad_username = request.GET.get('ad')
        if not ad_username:
            raise Http404()
        ad = get_object_or_404(IESGLogin, login_name=ad_username)

    pos, discuss, comment = get_ballot_info(doc.idinternal.ballot, ad)
    
    subj = []
    d = ""
    if pos and pos.discuss == 1 and discuss and discuss.text:
        d = discuss.text
        subj.append("DISCUSS")
    c = ""
    if comment and comment.text:
        c = comment.text
        subj.append("COMMENT")


    ad_name = str(ad)
    ad_name_genitive = ad_name + "'" if ad_name.endswith('s') else ad_name + "'s"
    subject = "%s %s on %s" % (ad_name_genitive, pos.name() if pos else "No Position" , doc.filename + '-' + doc.revision_display())
    if subj:
      subject += ": (with "+" and ".join(subj)+")"
 
    body = render_to_string("idrfc/ballot_comment_mail.txt",
                            dict(discuss=d, comment=c, ad=ad, doc=doc, pos=pos))
    frm = u"%s <%s>" % ad.person.email()
    to = "The IESG <iesg@ietf.org>"
        
    if request.method == 'POST':
        cc = [x.strip() for x in request.POST.get("cc", "").split(',') if x.strip()]
        if request.POST.get("cc_state_change") and doc.idinternal.state_change_notice_to:
            cc.extend(doc.idinternal.state_change_notice_to.split(','))

        send_mail_text(request, to, frm, subject, body, cc=", ".join(cc))
            
        return HttpResponseRedirect(return_to_url)
  
    return render_to_response('idrfc/send_ballot_comment.html',
                              dict(doc=doc,
                                   subject=subject,
                                   body=body,
                                   frm=frm,
                                   to=to,
                                   ad=ad,
                                   can_send=d or c,
                                   back_url=back_url,
                                  ),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def send_ballot_commentREDESIGN(request, name):
    """Email Internet Draft ballot discuss/comment for area director."""
    doc = get_object_or_404(Document, docalias__name=name)
    started_process = doc.latest_event(type="started_iesg_process")
    if not started_process:
        raise Http404()

    ad = login = request.user.get_profile()

    return_to_url = request.GET.get('return_to_url')
    if not return_to_url:
        return_to_url = doc.get_absolute_url()

    if 'HTTP_REFERER' in request.META:
        back_url = request.META['HTTP_REFERER']
    else:
        back_url = doc.get_absolute_url()

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not has_role(request.user, "Area Director"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404()
        from person.models import Person
        ad = get_object_or_404(Person, pk=ad_id)

    pos = doc.latest_event(BallotPositionDocEvent, type="changed_ballot_position", ad=ad, time__gte=started_process.time)
    if not pos:
        raise Http404()
    
    subj = []
    d = ""
    if pos.pos == "discuss" and pos.discuss:
        d = pos.discuss
        subj.append("DISCUSS")
    c = ""
    if pos.comment:
        c = pos.comment
        subj.append("COMMENT")

    ad_name_genitive = ad.name + "'" if ad.name.endswith('s') else ad.name + "'s"
    subject = "%s %s on %s" % (ad_name_genitive, pos.pos.name if pos.pos else "No Position", doc.name + "-" + doc.rev)
    if subj:
        subject += ": (with %s)" % " and ".join(subj)

    doc.filename = doc.name # compatibility attributes
    doc.revision_display = doc.rev
    body = render_to_string("idrfc/ballot_comment_mail.txt",
                            dict(discuss=d, comment=c, ad=ad.name, doc=doc, pos=pos.pos))
    frm = ad.formatted_email()
    to = "The IESG <iesg@ietf.org>"
        
    if request.method == 'POST':
        cc = [x.strip() for x in request.POST.get("cc", "").split(',') if x.strip()]
        if request.POST.get("cc_state_change") and doc.notify:
            cc.extend(doc.notify.split(','))

        send_mail_text(request, to, frm, subject, body, cc=", ".join(cc))
            
        return HttpResponseRedirect(return_to_url)
  
    return render_to_response('idrfc/send_ballot_commentREDESIGN.html',
                              dict(doc=doc,
                                   subject=subject,
                                   body=body,
                                   frm=frm,
                                   to=to,
                                   ad=ad,
                                   can_send=d or c,
                                   back_url=back_url,
                                  ),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    send_ballot_comment = send_ballot_commentREDESIGN


@group_required('Area_Director','Secretariat')
def defer_ballot(request, name):
    """Signal post-pone of Internet Draft ballot, notifying relevant parties."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)
    telechat_date = TelechatDates.objects.all()[0].date2

    if request.method == 'POST':
        doc.idinternal.ballot.defer = True
        doc.idinternal.ballot.defer_by = login
        doc.idinternal.ballot.defer_date = date.today()
        doc.idinternal.ballot.save()
        
        doc.idinternal.change_state(IDState.objects.get(document_state_id=IDState.IESG_EVALUATION_DEFER), None)
        doc.idinternal.agenda = True
        doc.idinternal.telechat_date = telechat_date
        doc.idinternal.event_date = date.today()
        doc.idinternal.save()

        email_ballot_deferred(request, doc, login, telechat_date)
        
        log_state_changed(request, doc, login)

        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/defer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def defer_ballotREDESIGN(request, name):
    """Signal post-pone of Internet Draft ballot, notifying relevant parties."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()
    telechat_date = TelechatDates.objects.all()[0].date2

    if request.method == 'POST':
        save_document_in_history(doc)

        prev = doc.get_state("draft-iesg")
        doc.set_state(State.objects.get(type="draft-iesg", slug='defer'))
        e = log_state_changed(request, doc, login, prev)
        
        doc.time = e.time
        doc.save()

        email_state_changed(request, doc, e.desc)

        update_telechat(request, doc, login, telechat_date)
        email_ballot_deferred(request, doc, login.name, telechat_date)

        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/defer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    defer_ballot = defer_ballotREDESIGN

@group_required('Area_Director','Secretariat')
def undefer_ballot(request, name):
    """Delete deferral of Internet Draft ballot."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)
    telechat_date = TelechatDates.objects.all()[0].date1
    
    if request.method == 'POST':
        doc.idinternal.ballot.defer = False
        doc.idinternal.ballot.save()
        
        doc.idinternal.change_state(IDState.objects.get(document_state_id=IDState.IESG_EVALUATION), None)
        doc.idinternal.telechat_date = telechat_date
        doc.idinternal.event_date = date.today()
        doc.idinternal.save()

        log_state_changed(request, doc, login)
        
        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/undefer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.idinternal.get_absolute_url()),
                              context_instance=RequestContext(request))

@group_required('Area_Director','Secretariat')
def undefer_ballotREDESIGN(request, name):
    """Delete deferral of Internet Draft ballot."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()
    telechat_date = TelechatDates.objects.all()[0].date1
    
    if request.method == 'POST':
        save_document_in_history(doc)

        prev = doc.get_state("draft-iesg")
        doc.set_state(State.objects.get(type="draft-iesg", slug='iesg-eva'))
        e = log_state_changed(request, doc, login, prev)
        
        doc.time = e.time
        doc.save()

        email_state_changed(request, doc, e.desc)
        
        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/undefer_ballot.html',
                              dict(doc=doc,
                                   telechat_date=telechat_date,
                                   back_url=doc.get_absolute_url()),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    undefer_ballot = undefer_ballotREDESIGN


class LastCallTextForm(forms.ModelForm):
    def clean_last_call_text(self):
        lines = self.cleaned_data["last_call_text"].split("\r\n")
        for l, next in zip(lines, lines[1:]):
            if l.startswith('Subject:') and next.strip():
                raise forms.ValidationError("Subject line appears to have a line break, please make sure there is no line breaks in the subject line and that it is followed by an empty line.")
        
        return self.cleaned_data["last_call_text"].replace("\r", "")
    
    class Meta:
        model = BallotInfo
        fields = ["last_call_text"]

class BallotWriteupForm(forms.ModelForm):
    class Meta:
        model = BallotInfo
        fields = ["ballot_writeup"]

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
class ApprovalTextForm(forms.ModelForm):
    class Meta:
        model = BallotInfo
        fields = ["approval_text"]

    def clean_approval_text(self):
        return self.cleaned_data["approval_text"].replace("\r", "")

@group_required('Area_Director','Secretariat')
def lastcalltext(request, name):
    """Editing of the last call text"""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    try:
        ballot = doc.idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = generate_ballot(request, doc)

    last_call_form = LastCallTextForm(instance=ballot)

    if request.method == 'POST':
        if "save_last_call_text" in request.POST or "send_last_call_request" in request.POST:
            last_call_form = LastCallTextForm(request.POST, instance=ballot)
            if last_call_form.is_valid():
                ballot.last_call_text = last_call_form.cleaned_data["last_call_text"]
		add_document_comment(request, doc, "Last Call text changed")
                ballot.save()

                if "send_last_call_request" in request.POST:
                    doc.idinternal.change_state(IDState.objects.get(document_state_id=IDState.LAST_CALL_REQUESTED), None)
                    
                    change = log_state_changed(request, doc, login)
                    email_owner(request, doc, doc.idinternal.job_owner, login, change)
                    request_last_call(request, doc)

                    doc.idinternal.event_date = date.today()
                    doc.idinternal.save()
                    
                    return render_to_response('idrfc/last_call_requested.html',
                                              dict(doc=doc),
                                              context_instance=RequestContext(request))
        
        if "regenerate_last_call_text" in request.POST:
            ballot.last_call_text = generate_last_call_announcement(request, doc)
            ballot.save()

            # make sure form has the updated text
            last_call_form = LastCallTextForm(instance=ballot)

        doc.idinternal.event_date = date.today()
        doc.idinternal.save()

    can_request_last_call = doc.idinternal.cur_state_id < 27
    can_make_last_call = doc.idinternal.cur_state_id < 20
    can_announce = doc.idinternal.cur_state_id > 19
    docs_with_invalid_status = [d.document().file_tag() for d in doc.idinternal.ballot_set() if "None" in d.document().intended_status.intended_status or "Request" in d.document().intended_status.intended_status]
    need_intended_status = ", ".join(docs_with_invalid_status)

    return render_to_response('idrfc/ballot_lastcalltext.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url(),
                                   ballot=ballot,
                                   last_call_form=last_call_form,
                                   can_request_last_call=can_request_last_call,
                                   can_make_last_call=can_make_last_call,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))


class LastCallTextFormREDESIGN(forms.Form):
    last_call_text = forms.CharField(widget=forms.Textarea, required=True)
    
    def clean_last_call_text(self):
        lines = self.cleaned_data["last_call_text"].split("\r\n")
        for l, next in zip(lines, lines[1:]):
            if l.startswith('Subject:') and next.strip():
                raise forms.ValidationError("Subject line appears to have a line break, please make sure there is no line breaks in the subject line and that it is followed by an empty line.")
        
        return self.cleaned_data["last_call_text"].replace("\r", "")

@group_required('Area_Director','Secretariat')
def lastcalltextREDESIGN(request, name):
    """Editing of the last call text"""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()

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

                    prev = doc.get_state("draft-iesg")
                    doc.set_state(State.objects.get(type="draft-iesg", slug='lc-req'))
                    e = log_state_changed(request, doc, login, prev)
                    
                    doc.time = e.time
                    doc.save()

                    email_state_changed(request, doc, e.desc)
                    email_owner(request, doc, doc.ad, login, e.desc)

                    request_last_call(request, doc)
                    
                    return render_to_response('idrfc/last_call_requested.html',
                                              dict(doc=doc),
                                              context_instance=RequestContext(request))
        
        if "regenerate_last_call_text" in request.POST:
            e = generate_last_call_announcement(request, doc)
            
            # make sure form has the updated text
            form = LastCallTextForm(initial=dict(last_call_text=e.text))


    s = doc.get_state("draft-iesg")
    can_request_last_call = s.order < 27
    can_make_last_call = s.order < 20
    can_announce = s.order > 19
    
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('idrfc/ballot_lastcalltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   last_call_form=form,
                                   can_request_last_call=can_request_last_call,
                                   can_make_last_call=can_make_last_call,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    LastCallTextForm = LastCallTextFormREDESIGN
    lastcalltext = lastcalltextREDESIGN


@group_required('Area_Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    try:
        ballot = doc.idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = generate_ballot(request, doc)

    ballot_writeup_form = BallotWriteupForm(instance=ballot)

    if request.method == 'POST':

        if "save_ballot_writeup" in request.POST:
            ballot_writeup_form = BallotWriteupForm(request.POST, instance=ballot)
            if ballot_writeup_form.is_valid():
                ballot.ballot_writeup = ballot_writeup_form.cleaned_data["ballot_writeup"]
		add_document_comment(request, doc, "Ballot writeup text changed")
                ballot.save()

        if "issue_ballot" in request.POST:
            ballot_writeup_form = BallotWriteupForm(request.POST, instance=ballot)
            approval_text_form = ApprovalTextForm(request.POST, instance=ballot)            
            if ballot_writeup_form.is_valid() and approval_text_form.is_valid():
                ballot.ballot_writeup = ballot_writeup_form.cleaned_data["ballot_writeup"]
                ballot.approval_text = approval_text_form.cleaned_data["approval_text"]
                ballot.active = True
                ballot.ballot_issued = True
                ballot.save()

                if not Position.objects.filter(ballot=ballot, ad=login):
                    pos = Position()
                    pos.ballot = ballot
                    pos.ad = login
                    pos.yes = 1
                    pos.noobj = pos.abstain = pos.approve = pos.discuss = pos.recuse = 0
                    pos.save()

                msg = generate_issue_ballot_mail(request, doc)
                send_mail_preformatted(request, msg)

                email_iana(request, doc, 'drafts-eval@icann.org', msg)
                
                doc.b_sent_date = date.today()
                doc.save()

                add_document_comment(request, doc, "Ballot has been issued")
                    
                doc.idinternal.event_date = date.today()
                doc.idinternal.save()
                    
                return render_to_response('idrfc/ballot_issued.html',
                                          dict(doc=doc,
                                               back_url=doc.idinternal.get_absolute_url()),
                                          context_instance=RequestContext(request))
                

        doc.idinternal.event_date = date.today()
        doc.idinternal.save()

    docs_with_invalid_status = [d.document().file_tag() for d in doc.idinternal.ballot_set() if "None" in d.document().intended_status.intended_status or "Request" in d.document().intended_status.intended_status]
    need_intended_status = ", ".join(docs_with_invalid_status)

    return render_to_response('idrfc/ballot_writeupnotes.html',
                              dict(doc=doc,
                                   ballot=ballot,
                                   ballot_writeup_form=ballot_writeup_form,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

class BallotWriteupFormREDESIGN(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
@group_required('Area_Director','Secretariat')
def ballot_writeupnotesREDESIGN(request, name):
    """Editing of ballot write-up and notes"""
    doc = get_object_or_404(Document, docalias__name=name)
    started_process = doc.latest_event(type="started_iesg_process")
    if not started_process:
        raise Http404()

    login = request.user.get_profile()

    approval = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    
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

            if "issue_ballot" in request.POST and approval:
                if has_role(request.user, "Area Director") and not doc.latest_event(BallotPositionDocEvent, ad=login, time__gte=started_process.time):
                    # sending the ballot counts as a yes
                    pos = BallotPositionDocEvent(doc=doc, by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = login
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.name)
                    pos.save()

                msg = generate_issue_ballot_mail(request, doc)
                send_mail_preformatted(request, msg)

                email_iana(request, doc, 'drafts-eval@icann.org', msg)

                e = DocEvent(doc=doc, by=login)
                e.by = login
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been issued by %s" % login.name
                e.save()

                return render_to_response('idrfc/ballot_issued.html',
                                          dict(doc=doc,
                                               back_url=doc.get_absolute_url()),
                                          context_instance=RequestContext(request))
                        

    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('idrfc/ballot_writeupnotesREDESIGN.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   ballot_issued=bool(doc.latest_event(type="sent_ballot_announcement")),
                                   ballot_writeup_form=form,
                                   need_intended_status=need_intended_status,
                                   approval=approval,
                                   ),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    BallotWriteupForm = BallotWriteupFormREDESIGN
    ballot_writeupnotes = ballot_writeupnotesREDESIGN


@group_required('Area_Director','Secretariat')
def ballot_approvaltext(request, name):
    """Editing of approval text"""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    try:
        ballot = doc.idinternal.ballot
    except BallotInfo.DoesNotExist:
        ballot = generate_ballot(request, doc)

    approval_text_form = ApprovalTextForm(instance=ballot)

    if request.method == 'POST':

        if "save_approval_text" in request.POST:
            approval_text_form = ApprovalTextForm(request.POST, instance=ballot)            
            if approval_text_form.is_valid():
                ballot.approval_text = approval_text_form.cleaned_data["approval_text"]
		add_document_comment(request, doc, "Approval announcement text changed")
                ballot.save()
                
        if "regenerate_approval_text" in request.POST:
            ballot.approval_text = generate_approval_mail(request, doc)
	    add_document_comment(request, doc, "Approval announcement text regenerated")
            ballot.save()

            # make sure form has the updated text
            approval_text_form = ApprovalTextForm(instance=ballot)
            
        doc.idinternal.event_date = date.today()
        doc.idinternal.save()

    can_announce = doc.idinternal.cur_state_id > 19
    docs_with_invalid_status = [d.document().file_tag() for d in doc.idinternal.ballot_set() if "None" in d.document().intended_status.intended_status or "Request" in d.document().intended_status.intended_status]
    need_intended_status = ", ".join(docs_with_invalid_status)

    return render_to_response('idrfc/ballot_approvaltext.html',
                              dict(doc=doc,
                                   back_url=doc.idinternal.get_absolute_url(),
                                   ballot=ballot,
                                   approval_text_form=approval_text_form,
                                   can_announce=can_announce,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

class ApprovalTextFormREDESIGN(forms.Form):
    approval_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_approval_text(self):
        return self.cleaned_data["approval_text"].replace("\r", "")

@group_required('Area_Director','Secretariat')
def ballot_approvaltextREDESIGN(request, name):
    """Editing of approval text"""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()

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
            form = ApprovalTextForm(initial=dict(approval_text=existing.text))

    can_announce = doc.get_state("draft-iesg").order > 19
    need_intended_status = ""
    if not doc.intended_std_level:
        need_intended_status = doc.file_tag()

    return render_to_response('idrfc/ballot_approvaltext.html',
                              dict(doc=doc,
                                   back_url=doc.get_absolute_url(),
                                   approval_text_form=form,
                                   can_announce=can_announce,
                                   need_intended_status=need_intended_status,
                                   ),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    ApprovalTextForm = ApprovalTextFormREDESIGN
    ballot_approvaltext = ballot_approvaltextREDESIGN

@group_required('Secretariat')
def approve_ballot(request, name):
    """Approve ballot, sending out announcement, changing state."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    ballot = doc.idinternal.ballot

    if "To: RFC Editor" in ballot.approval_text:
        action = "to_rfc_editor"
    elif "NOT be published" in ballot.approval_text:
        action = "do_not_publish"
    else:
        action = "to_announcement_list"

    announcement = ballot.approval_text + "\n\n" + ballot.ballot_writeup
        
    if request.method == 'POST':
        for i in doc.idinternal.ballot_set():
            if action == "do_not_publish":
                new_state = IDState.DEAD
            else:
                new_state = IDState.APPROVED_ANNOUNCEMENT_SENT

            i.change_state(IDState.objects.get(document_state_id=new_state), None)

            if action == "do_not_publish":
                i.dnp = True
                i.dnp_date = date.today()
                i.noproblem = False

            if action == "to_rfc_editor":
                i.noproblem = True
            
            i.event_date = date.today()
            i.save()

            i.document().b_approve_date = date.today()
            i.document().save()
            
            if action == "do_not_publish":
                comment = "Do Not Publish note has been sent to RFC Editor"
            else:
                comment = "IESG has approved"
                
            comment += " and state has been changed to %s" % i.cur_state.state
            add_document_comment(request, i.document(), comment)
            email_owner(request, i.document(), i.job_owner, login, comment)
            email_state_changed(request, i.document(), strip_tags(comment))

        send_mail_preformatted(request, announcement)

        ballot.an_sent = True
        ballot.an_sent_date = date.today()
        ballot.an_sent_by = login
        ballot.save()

        if action == "to_announcement_list":
            email_iana(request, doc, "drafts-approval@icann.org", announcement)

        return HttpResponseRedirect(doc.idinternal.get_absolute_url())
  
    return render_to_response('idrfc/approve_ballot.html',
                              dict(doc=doc,
                                   action=action,
                                   announcement=announcement),
                              context_instance=RequestContext(request))

@group_required('Secretariat')
def approve_ballotREDESIGN(request, name):
    """Approve ballot, sending out announcement, changing state."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_approval_text")
    if not e:
        e = generate_approval_mail(request, doc)
    approval_text = e.text

    e = doc.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not e:
        e = generate_ballot_writeup(request, doc)
    ballot_writeup = e.text
    
    if "NOT be published" in approval_text:
        action = "do_not_publish"
    elif "To: RFC Editor" in approval_text:
        action = "to_rfc_editor"
    else:
        action = "to_announcement_list"

    announcement = approval_text + "\n\n" + ballot_writeup
        
    if request.method == 'POST':
        if action == "do_not_publish":
            new_state = State.objects.get(type="draft-iesg", slug="dead")
        else:
            new_state = State.objects.get(type="draft-iesg", slug="ann")

        # fixup document
        save_document_in_history(doc)

        prev = doc.get_state("draft-iesg")
        doc.set_state(new_state)

        e = DocEvent(doc=doc, by=login)
        if action == "do_not_publish":
            e.type = "iesg_disapproved"
            e.desc = "Do Not Publish note has been sent to RFC Editor"
        else:
            e.type = "iesg_approved"
            e.desc = "IESG has approved the document"

        e.save()
        
        change_description = e.desc + " and state has been changed to %s" % doc.get_state("draft-iesg").name
        
        e = log_state_changed(request, doc, login, prev)
                    
        doc.time = e.time
        doc.save()

        email_state_changed(request, doc, change_description)
        email_owner(request, doc, doc.ad, login, change_description)

        # send announcement
        send_mail_preformatted(request, announcement)

        if action == "to_announcement_list":
            email_iana(request, doc, "drafts-approval@icann.org", announcement)

        return HttpResponseRedirect(doc.get_absolute_url())
  
    return render_to_response('idrfc/approve_ballot.html',
                              dict(doc=doc,
                                   action=action,
                                   announcement=announcement),
                              context_instance=RequestContext(request))

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    approve_ballot = approve_ballotREDESIGN


class MakeLastCallForm(forms.Form):
    last_call_sent_date = forms.DateField(required=True)
    last_call_expiration_date = forms.DateField(required=True)

@group_required('Secretariat')
def make_last_call(request, name):
    """Make last call for Internet Draft, sending out announcement."""
    doc = get_object_or_404(InternetDraft, filename=name)
    if not doc.idinternal:
        raise Http404()

    login = IESGLogin.objects.get(login_name=request.user.username)

    ballot = doc.idinternal.ballot
    docs = [i.document() for i in doc.idinternal.ballot_set()]
    
    announcement = ballot.last_call_text

    if request.method == 'POST':
        form = MakeLastCallForm(request.POST)
        if form.is_valid():
            send_mail_preformatted(request, announcement)
            email_iana(request, doc, "drafts-lastcall@icann.org", announcement)

            doc.idinternal.change_state(IDState.objects.get(document_state_id=IDState.IN_LAST_CALL), None)
            doc.idinternal.event_date = date.today()
            doc.idinternal.save()
                
            log_state_changed(request, doc, login)
            
            doc.lc_sent_date = form.cleaned_data['last_call_sent_date']
            doc.lc_expiration_date = form.cleaned_data['last_call_expiration_date']
            doc.save()
            
            comment = "Last call has been made for %s ballot and state has been changed to %s" % (doc.filename, doc.idinternal.cur_state.state)
            email_owner(request, doc, doc.idinternal.job_owner, login, comment)
            
            return HttpResponseRedirect(doc.idinternal.get_absolute_url())
    else:
        initial = {}
        initial["last_call_sent_date"] = date.today()
        expire_days = 14
        if doc.group_id == Acronym.INDIVIDUAL_SUBMITTER:
            expire_days = 28

        initial["last_call_expiration_date"] = date.today() + timedelta(days=expire_days)
        
        form = MakeLastCallForm(initial=initial)
  
    return render_to_response('idrfc/make_last_call.html',
                              dict(doc=doc,
                                   docs=docs,
                                   form=form),
                              context_instance=RequestContext(request))


@group_required('Secretariat')
def make_last_callREDESIGN(request, name):
    """Make last call for Internet Draft, sending out announcement."""
    doc = get_object_or_404(Document, docalias__name=name)
    if not doc.get_state("draft-iesg"):
        raise Http404()

    login = request.user.get_profile()

    e = doc.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not e:
        e = generate_last_call_announcement(request, doc)
    announcement = e.text

    if request.method == 'POST':
        form = MakeLastCallForm(request.POST)
        if form.is_valid():
            send_mail_preformatted(request, announcement)
            email_iana(request, doc, "drafts-lastcall@icann.org", announcement)

            save_document_in_history(doc)

            prev = doc.get_state("draft-iesg")
            doc.set_state(State.objects.get(type="draft-iesg", slug='lc'))
            e = log_state_changed(request, doc, login, prev)
                    
            doc.time = e.time
            doc.save()

            change_description = "Last call has been made for %s and state has been changed to %s" % (doc.name, doc.get_state("draft-iesg").name)
            email_state_changed(request, doc, change_description)
            email_owner(request, doc, doc.ad, login, change_description)
            
            e = LastCallDocEvent(doc=doc, by=login)
            e.type = "sent_last_call"
            e.desc = "Last call sent by %s" % login.name
            if form.cleaned_data['last_call_sent_date'] != e.time.date():
                e.time = datetime.datetime.combine(form.cleaned_data['last_call_sent_date'], e.time.time())
            e.expires = form.cleaned_data['last_call_expiration_date']
            e.save()
            
            return HttpResponseRedirect(doc.get_absolute_url())
    else:
        initial = {}
        initial["last_call_sent_date"] = date.today()
        expire_days = 14
        if doc.group.type_id == "individ":
            expire_days = 28

        initial["last_call_expiration_date"] = date.today() + timedelta(days=expire_days)
        
        form = MakeLastCallForm(initial=initial)
  
    return render_to_response('idrfc/make_last_callREDESIGN.html',
                              dict(doc=doc,
                                   form=form),
                              context_instance=RequestContext(request))


if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    make_last_call = make_last_callREDESIGN
