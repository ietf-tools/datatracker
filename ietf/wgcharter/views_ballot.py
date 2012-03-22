# ballot management (voting, commenting, writeups, ...) for Area
# Directors and Secretariat

import re, os
from datetime import datetime, date, time, timedelta
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.core.urlresolvers import reverse as urlreverse
from django.template.loader import render_to_string
from django.template import RequestContext
from django import forms
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from ietf.utils.mail import send_mail_text, send_mail_preformatted
from ietf.ietfauth.decorators import has_role, role_required
from ietf.wgcharter.mails import email_secretariat, generate_ballot_writeup, generate_issue_ballot_mail
from ietf.wgcharter.utils import *
from ietf.group.models import Group, GroupHistory, GroupEvent
from ietf.group.utils import save_group_in_history
from ietf.name.models import GroupBallotPositionName, GroupStateName
from ietf.doc.models import *

def default_action_text(wg, charter, user, action):
    e = WriteupDocEvent(doc=charter, by=user)
    e.by = user
    e.type = "changed_action_announcement"
    e.desc = "WG action text was changed"

    info = {}
    info['chairs'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Chair")]
    info['secr'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Secr")]
    info['techadv'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Techadv")]
    info['ad'] = {'name': wg.ad.plain_name(), 'email': wg.ad.role_email("ad").address } if wg.ad else None,
    info['list'] = wg.list_email if wg.list_email else None,
    info['list_subscribe'] = str(wg.list_subscribe) if wg.list_subscribe else None,
    info['list_archive'] = str(wg.list_archive) if wg.list_archive else None,

    filename = os.path.join(settings.CHARTER_PATH, 'charter-ietf-%s-%s.txt' % (wg.acronym, wg.charter.rev))
    try:
        charter_text = open(filename, 'r')
        info['charter_txt'] = charter_text.read()
    except IOError:
        info['charter_txt'] = "Error: couldn't read charter text"

        e.text = render_to_string("wgcharter/action_text.txt",
                                  dict(wg=wg,
                                       charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                       action_type=action,
                                       info=info,
                                       ))

        e.save()
        return e

def default_review_text(wg, charter, user):
    e = WriteupDocEvent(doc=charter, by=user)
    e.by = user
    e.type = "changed_review_announcement"
    e.desc = "WG review text was changed"
    info = {}
    info['chairs'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Chair")]
    info['secr'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Secr")]
    info['techadv'] = [{ 'name': x.person.plain_name(), 'email': x.email.address} for x in wg.role_set.filter(name="Techadv")]
    info['ad'] = {'name': wg.ad.plain_name(), 'email': wg.ad.role_email("ad").address } if wg.ad else None,
    info['list'] = wg.list_email if wg.list_email else None,
    info['list_subscribe'] = wg.list_subscribe if wg.list_subscribe else None,
    info['list_archive'] = wg.list_archive if wg.list_archive else None,

    info['bydate'] = (date.today() + timedelta(weeks=1)).isoformat()

    filename = os.path.join(settings.CHARTER_PATH, 'charter-ietf-%s-%s.txt' % (wg.acronym, wg.charter.rev))
    try:
        charter_text = open(filename, 'r')
        info['charter_txt'] = charter_text.read()
    except IOError:
        info['charter_txt'] = "Error: couldn't read charter text"

        e.text = render_to_string("wgcharter/review_text.txt",
                                  dict(wg=wg,
                                       charter_url=settings.IDTRACKER_BASE_URL + charter.get_absolute_url(),
                                       info=info,
                                       review_type="new" if wg.state_id == "proposed" else "recharter",
                                       )
                                  )
        e.save()
        return e

BALLOT_CHOICES = (("yes", "Yes"),
                  ("no", "No"),
                  ("block", "Block"),
                  ("abstain", "Abstain"),
                  ("", "No Record"),
                  )

def position_to_ballot_choice(position):
    for v, label in BALLOT_CHOICES:
        if v and getattr(position, v):
            return v
    return ""

def position_label(position_value):
    return dict(BALLOT_CHOICES).get(position_value, "")

class EditPositionForm(forms.Form):
    position = forms.ModelChoiceField(queryset=GroupBallotPositionName.objects.all(), widget=forms.RadioSelect, initial="norecord", required=True)
    block_comment = forms.CharField(required=False, label="Blocking comment", widget=forms.Textarea)
    comment = forms.CharField(required=False, widget=forms.Textarea)
    return_to_url = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_blocking(self):
        entered_blocking = self.cleaned_data["block_comment"]
        entered_pos = self.cleaned_data["position"]
        if entered_pos.slug == "block" and not entered_blocking:
            raise forms.ValidationError("You must enter a non-empty blocking comment")
        return entered_blocking

@role_required('Area Director','Secretariat')
def edit_position(request, name):
    """Vote and edit comments on Charter as Area Director."""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_edit_position', name=wglist[0].group.acronym)
        else:
            raise Http404

    charter = set_or_create_charter(wg)
    started_process = charter.latest_event(type="started_iesg_process")
    if not started_process:
        raise Http404

    ad = login = request.user.get_profile()

    if 'HTTP_REFERER' in request.META:
        return_to_url = request.META['HTTP_REFERER']
    else:
        return_to_url = charter.get_absolute_url()

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not has_role(request.user, "Area Director"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404()
        from ietf.person.models import Person
        ad = get_object_or_404(Person, pk=ad_id)

    old_pos = charter.latest_event(GroupBallotPositionDocEvent, type="changed_ballot_position", ad=ad, time__gte=started_process.time)

    if request.method == 'POST':
        form = EditPositionForm(request.POST)
        if form.is_valid():
            
            # save the vote
            clean = form.cleaned_data

            if clean['return_to_url']:
                return_to_url = clean['return_to_url']

            pos = GroupBallotPositionDocEvent(doc=charter, by=login)
            pos.type = "changed_ballot_position"
            pos.ad = ad
            pos.pos = clean["position"]
            pos.comment = clean["comment"].strip()
            pos.comment_time = old_pos.comment_time if old_pos else None
            pos.block_comment = clean["block_comment"].strip() if pos.pos_id == "block" else ""
            pos.block_comment_time = old_pos.block_comment_time if old_pos else None

            changes = []
            added_events = []
            # possibly add discuss/comment comments to history trail
            # so it's easy to see
            old_comment = old_pos.comment if old_pos else ""
            if pos.comment != old_comment:
                pos.comment_time = pos.time
                changes.append("comment")

                if pos.comment:
                    e = DocEvent(doc=charter)
                    e.by = ad # otherwise we can't see who's saying it
                    e.type = "added_comment"
                    e.desc = "[Ballot comment]\n" + pos.comment
                    added_events.append(e)

            old_block_comment = old_pos.block_comment if old_pos else ""
            if pos.block_comment != old_block_comment:
                pos.block_comment_time = pos.time
                changes.append("block_comment")

                if pos.block_comment:
                    e = DocEvent(doc=charter, by=login)
                    e.by = ad # otherwise we can't see who's saying it
                    e.type = "added_comment"
                    e.desc = "[Ballot blocking comment]\n" + pos.block_comment
                    added_events.append(e)

            # figure out a description
            if not old_pos and pos.pos.slug != "norecord":
                pos.desc = u"[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.name)
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
                    e.save() # save them after the position is saved to get later id
                    
                charter.time = pos.time
                charter.save()

            if request.POST.get("send_mail"):
                qstr = "?return_to_url=%s" % return_to_url
                if request.GET.get('ad'):
                    qstr += "&ad=%s" % request.GET.get('ad')
                return HttpResponseRedirect(urlreverse("wg_send_ballot_comment", kwargs=dict(name=wg.acronym)) + qstr)
            else:
                return HttpResponseRedirect(return_to_url)
    else:
        initial = {}
        if old_pos:
            initial['position'] = old_pos.pos.slug
            initial['block_comment'] = old_pos.block_comment
            initial['comment'] = old_pos.comment
            
        if return_to_url:
            initial['return_to_url'] = return_to_url
            
        form = EditPositionForm(initial=initial)

    return render_to_response('wgcharter/edit_position.html',
                              dict(charter=charter,
                                   wg=wg,
                                   form=form,
                                   ad=ad,
                                   return_to_url=return_to_url,
                                   old_pos=old_pos,
                                   ),
                              context_instance=RequestContext(request))

@role_required('Area Director','Secretariat')
def send_ballot_comment(request, name):
    """Email Charter ballot comment for area director."""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_send_ballot_comment', name=wglist[0].group.acronym)
        else:
            raise Http404

    charter = set_or_create_charter(wg)
    started_process = charter.latest_event(type="started_iesg_process")
    if not started_process:
        raise Http404()

    ad = login = request.user.get_profile()

    return_to_url = request.GET.get('return_to_url')
    if not return_to_url:
        return_to_url = charter.get_absolute_url()

    if 'HTTP_REFERER' in request.META:
        back_url = request.META['HTTP_REFERER']
    else:
        back_url = charter.get_absolute_url()

    # if we're in the Secretariat, we can select an AD to act as stand-in for
    if not has_role(request.user, "Area Director"):
        ad_id = request.GET.get('ad')
        if not ad_id:
            raise Http404()
        from ietf.person.models import Person
        ad = get_object_or_404(Person, pk=ad_id)

    pos = charter.latest_event(GroupBallotPositionDocEvent, type="changed_ballot_position", ad=ad, time__gte=started_process.time)
    if not pos:
        raise Http404()
    
    subj = []
    d = ""
    if pos.pos_id == "block" and pos.block_comment:
        d = pos.block_comment
        subj.append("BLOCKING COMMENT")
    c = ""
    if pos.comment:
        c = pos.comment
        subj.append("COMMENT")

    ad_name_genitive = ad.plain_name() + "'" if ad.plain_name().endswith('s') else ad.plain_name() + "'s"
    subject = "%s %s on %s" % (ad_name_genitive, pos.pos.name if pos.pos else "No Position", charter.name + "-" + charter.rev)
    if subj:
        subject += ": (with %s)" % " and ".join(subj)

    body = render_to_string("wgcharter/ballot_comment_mail.txt",
                            dict(block_comment=d, comment=c, ad=ad.plain_name(), charter=charter, pos=pos.pos))
    frm = ad.formatted_email()
    to = "The IESG <iesg@ietf.org>"
    
    if request.method == 'POST':
        cc = [x.strip() for x in request.POST.get("cc", "").split(',') if x.strip()]
        send_mail_text(request, to, frm, subject, body, cc=", ".join(cc))
        
        return HttpResponseRedirect(return_to_url)
    
    return render_to_response('wgcharter/send_ballot_comment.html',
                              dict(charter=charter,
                                   subject=subject,
                                   body=body,
                                   frm=frm,
                                   to=to,
                                   ad=ad,
                                   can_send=d or c,
                                   back_url=back_url,
                                   ),
                              context_instance=RequestContext(request))

class AnnouncementTextForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, required=True)

    def clean_announcement_text(self):
        return self.cleaned_data["announcement_text"].replace("\r", "")

@role_required('Area Director','Secretariat')
def announcement_text(request, name, ann):
    """Editing of announcement text"""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_announcement_text', name=wglist[0].group.acronym)
        else:
            raise Http404

    charter = set_or_create_charter(wg)

    login = request.user.get_profile()

    if ann == "action":
        existing = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    elif ann == "review":
        existing = charter.latest_event(WriteupDocEvent, type="changed_review_announcement")
    if not existing:
        if ann == "action":
            if next_approved_revision(wg.charter.rev) == "01":
                existing = default_action_text(wg, charter, login, "Formed")
            else:
                existing = default_action_text(wg, charter, login, "Rechartered")
        elif ann == "review":
            existing = default_review_text(wg, charter, login)

    form = AnnouncementTextForm(initial=dict(announcement_text=existing.text))

    if request.method == 'POST':
        form = AnnouncementTextForm(request.POST)
        if "save_text" in request.POST and form.is_valid():
            t = form.cleaned_data['announcement_text']
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, by=login)
                e.by = login
                e.type = "changed_%s_announcement" % ann
                e.desc = "WG %s text was changed" % ann
                e.text = t
                e.save()
                
                charter.time = e.time
                charter.save()
            return redirect('doc_writeup', name=charter.name)

        if "regenerate_text" in request.POST:
            if ann == "action":
                if next_approved_revision(wg.charter.rev) == "01":
                    e = default_action_text(wg, charter, login, "Formed")
                else:
                    e = default_action_text(wg, charter, login, "Rechartered")
            elif ann == "review":
                e = default_review_text(wg, charter, login)
            # make sure form has the updated text
            form = AnnouncementTextForm(initial=dict(announcement_text=e.text))

        if "send_text" in request.POST and form.is_valid():
            msg = form.cleaned_data['announcement_text']
            import email
            parsed_msg = email.message_from_string(msg.encode("utf-8"))

            send_mail_text(request, parsed_msg["To"],
                           parsed_msg["From"], parsed_msg["Subject"],
                           parsed_msg.get_payload())
            return redirect('doc_writeup', name=charter.name)

    return render_to_response('wgcharter/announcement_text.html',
                              dict(charter=charter,
                                   announcement=ann,
                                   back_url=charter.get_absolute_url(),
                                   announcement_text_form=form,
                                   ),
                              context_instance=RequestContext(request))

class BallotWriteupForm(forms.Form):
    ballot_writeup = forms.CharField(widget=forms.Textarea, required=True)

    def clean_ballot_writeup(self):
        return self.cleaned_data["ballot_writeup"].replace("\r", "")
        
@role_required('Area Director','Secretariat')
def ballot_writeupnotes(request, name):
    """Editing of ballot write-up and notes"""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_ballot_writeupnotes', name=wglist[0].group.acronym)
        else:
            raise Http404

    charter = set_or_create_charter(wg)

    started_process = charter.latest_event(type="started_iesg_process")
    if not started_process:
        raise Http404()

    login = request.user.get_profile()

    approval = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    
    existing = charter.latest_event(WriteupDocEvent, type="changed_ballot_writeup_text")
    if not existing:
        existing = generate_ballot_writeup(request, charter)

    reissue = charter.latest_event(DocEvent, type="sent_ballot_announcement")
        
    form = BallotWriteupForm(initial=dict(ballot_writeup=existing.text))

    if request.method == 'POST' and "save_ballot_writeup" in request.POST or "issue_ballot" in request.POST:
        form = BallotWriteupForm(request.POST)
        if form.is_valid():
            t = form.cleaned_data["ballot_writeup"]
            if t != existing.text:
                e = WriteupDocEvent(doc=charter, by=login)
                e.by = login
                e.type = "changed_ballot_writeup_text"
                e.desc = "Ballot writeup was changed"
                e.text = t
                e.save()

            if "issue_ballot" in request.POST and approval:
                if has_role(request.user, "Area Director") and not charter.latest_event(GroupBallotPositionDocEvent, ad=login, time__gte=started_process.time):
                    # sending the ballot counts as a yes
                    pos = GroupBallotPositionDocEvent(doc=charter, by=login)
                    pos.type = "changed_ballot_position"
                    pos.ad = login
                    pos.pos_id = "yes"
                    pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.ad.plain_name())
                    pos.save()

                msg = generate_issue_ballot_mail(request, charter)
                send_mail_preformatted(request, msg)

                e = DocEvent(doc=charter, by=login)
                e.by = login
                e.type = "sent_ballot_announcement"
                e.desc = "Ballot has been issued"
                e.save()

                return render_to_response('wgcharter/ballot_issued.html',
                                          dict(charter=charter,
                                               back_url=charter.get_absolute_url()),
                                          context_instance=RequestContext(request))
                        

    return render_to_response('wgcharter/ballot_writeupnotes.html',
                              dict(charter=charter,
                                   back_url=charter.get_absolute_url(),
                                   ballot_issued=bool(charter.latest_event(type="sent_ballot_announcement")),
                                   ballot_writeup_form=form,
                                   reissue=reissue,
                                   approval=approval,
                                   ),
                              context_instance=RequestContext(request))

@role_required('Secretariat')
def approve_ballot(request, name):
    """Approve ballot, changing state, copying charter"""
    try:
        wg = Group.objects.get(acronym=name)
    except ObjectDoesNotExist:
        wglist = GroupHistory.objects.filter(acronym=name)
        if wglist:
            return redirect('wg_approve_ballot', name=wglist[0].group.acronym)
        else:
            raise Http404

    charter = set_or_create_charter(wg)

    login = request.user.get_profile()

    e = charter.latest_event(WriteupDocEvent, type="changed_action_announcement")
    if not e:
        if next_approved_revision(wg.charter.rev) == "01":
            announcement= default_action_text(wg, charter, login, "Formed").text
        else:
            announcement = default_action_text(wg, charter, login, "Rechartered").text
    else:
        announcement = e.text

    if request.method == 'POST':
        new_state = GroupStateName.objects.get(slug="active")
        new_charter_state = State.objects.get(type="charter", slug="approved")

        save_document_in_history(charter)
        save_group_in_history(wg)

        prev_state = wg.state
        prev_charter_state = charter.get_state()
        wg.state = new_state
        charter.set_state(new_charter_state)

        e = DocEvent(doc=charter, by=login)
        e.type = "iesg_approved"
        e.desc = "IESG has approved the charter"
        e.save()
        
        change_description = e.desc + " and WG state has been changed to %s" % new_state.name
        
        e = log_state_changed(request, charter, login, prev_state)
        
        wg.time = e.time
        wg.save()

        ch = get_charter_for_revision(wg.charter, wg.charter.rev)

        filename = os.path.join(charter.get_file_path(), ch.name+"-"+ch.rev+".txt")
        try:
            source = open(filename, 'rb')
            raw_content = source.read()

            new_filename = os.path.join(charter.get_file_path(), 'charter-ietf-%s-%s.txt' % (wg.acronym, next_approved_revision(ch.rev)))
            destination = open(new_filename, 'wb+')
            destination.write(raw_content)
            destination.close()
        except IOError:
            raise Http404("Charter text %s" % filename)

        charter.rev = next_approved_revision(charter.rev)
        charter.save()
        
        email_secretariat(request, wg, "state-%s" % new_charter_state.slug, change_description)

        # send announcement
        send_mail_preformatted(request, announcement)

        return HttpResponseRedirect(charter.get_absolute_url())
    
    return render_to_response('wgcharter/approve_ballot.html',
                              dict(charter=charter,
                                   announcement=announcement,
                                   wg=wg),
                              context_instance=RequestContext(request))

