# Copyright The IETF Trust 2012-2023, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import os
from pathlib import Path

from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import escape

import debug                            # pyflakes:ignore

from ietf.doc.models import ( BallotDocEvent, BallotPositionDocEvent, DocEvent,
    Document, NewRevisionDocEvent, State )
from ietf.doc.utils import ( add_state_change_event, close_open_ballots,
    create_ballot_if_not_open, update_telechat )
from ietf.doc.mails import email_iana, email_ad_approved_conflict_review
from ietf.doc.forms import AdForm 
from ietf.group.models import Role, Group
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, role_required, is_authorized_in_doc_stream
from ietf.name.models import DocTagName
from ietf.person.models import Person
from ietf.utils import log
from ietf.utils.mail import send_mail_preformatted
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.mailtrigger.utils import gather_address_lists

class ChangeStateForm(forms.Form):
    review_state = forms.ModelChoiceField(State.objects.filter(used=True, type="conflrev"), label="Conflict review state", empty_label=None, required=True)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the review history.", required=False, strip=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if not has_role(user, "Secretariat"):
            self.fields["review_state"].queryset = self.fields["review_state"].queryset.exclude(slug__in=("appr-reqnopub-sent","appr-noprob-sent"))

@role_required("Area Director", "Secretariat")
def change_state(request, name, option=None):
    """Change state of an IESG review for IETF conflicts in other stream's documents, notifying parties as necessary
    and logging the change as a comment."""
    review = get_object_or_404(Document, type="conflrev", name=name)

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStateForm(request.POST, user=request.user)
        if form.is_valid():
            clean = form.cleaned_data
            new_state = clean['review_state']
            comment = clean['comment'].rstrip()

            if comment:
                c = DocEvent(type="added_comment", doc=review, rev=review.rev, by=login)
                c.desc = comment
                c.save()

            prev_state = review.get_state()
            if new_state != prev_state:
                events = []

                review.set_state(new_state)
                events.append(add_state_change_event(review, login, prev_state, new_state))

                review.save_with_history(events)

                if new_state.slug == "iesgeval":
                    e = create_ballot_if_not_open(request, review, login, "conflrev") # pyflakes:ignore
                    ballot = review.latest_event(BallotDocEvent, type="created_ballot")
                    log.assertion('ballot == e')
                    if has_role(request.user, "Area Director") and not review.latest_event(BallotPositionDocEvent, balloter=login, ballot=ballot, type="changed_ballot_position"):

                        # The AD putting a conflict review into iesgeval who doesn't already have a position is saying "yes"
                        pos = BallotPositionDocEvent(doc=review, rev=review.rev, by=login)
                        pos.ballot = ballot
                        pos.type = "changed_ballot_position"
                        pos.balloter = login
                        pos.pos_id = "yes"
                        pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.balloter.plain_name())
                        pos.save()
                        # Consider mailing that position to 'iesg_ballot_saved'
                    send_conflict_eval_email(request,review)
                elif (new_state.slug in ("appr-reqnopub-pend", "appr-noprob-pend")
                      and has_role(request.user, "Area Director")):
                    if new_state.slug == "appr-noprob-pend":
                        ok_to_publish = True
                    else:
                        ok_to_publish = False
                    email_ad_approved_conflict_review(request,
                                                      review,
                                                      ok_to_publish)

                if new_state.slug in ["appr-reqnopub-sent", "appr-noprob-sent", "withdraw", "dead"]:
                    doc = review.related_that_doc("conflrev")[0]
                    update_stream_state(doc, login, 'chair-w' if doc.stream_id=='irtf' else 'ise-rev', 'iesg-com')

            return redirect('ietf.doc.views_doc.document_main', name=review.name)
    else:
        s = review.get_state()
        init = dict(review_state=s.pk if s else None)
        form = ChangeStateForm(initial=init, user=request.user)

    return render(request, 'doc/change_state.html',
                              dict(form=form,
                                   doc=review,
                                   login=login,
                                   help_url=reverse('ietf.doc.views_help.state_help', kwargs=dict(type="conflict-review")),
                                   ))

def send_conflict_review_ad_changed_email(request, review, event):
    addrs = gather_address_lists('conflrev_ad_changed', doc=review).as_strings(compact=False)
    msg = render_to_string("doc/conflict_review/changed_ad.txt",
                           dict(frm = settings.DEFAULT_FROM_EMAIL,
                                 to = addrs.to,
                                 cc = addrs.cc,
                                 by = request.user.person,
                                 event = event,
                                 review = review,
                                 reviewed_doc = review.relateddocument_set.get(relationship__slug='conflrev').target,
                                 review_url = settings.IDTRACKER_BASE_URL+review.get_absolute_url(),
                               )
                          )
    send_mail_preformatted(request,msg)

                                
def send_conflict_review_started_email(request, review):
    addrs = gather_address_lists('conflrev_requested',doc=review).as_strings(compact=False)
    msg = render_to_string("doc/conflict_review/review_started.txt",
                            dict(frm = settings.DEFAULT_FROM_EMAIL,
                                 to = addrs.to,
                                 cc = addrs.cc,
                                 by = request.user.person,
                                 review = review,
                                 reviewed_doc = review.relateddocument_set.get(relationship__slug='conflrev').target,
                                 review_url = settings.IDTRACKER_BASE_URL+review.get_absolute_url(),
                                 )
                           )
    if not has_role(request.user,"Secretariat"):
        send_mail_preformatted(request,msg)

    addrs = gather_address_lists('conflrev_requested_iana',doc=review).as_strings(compact=False)
    email_iana(request, 
               review.relateddocument_set.get(relationship__slug='conflrev').target,
               addrs.to,
               msg,
               cc=addrs.cc)

def send_conflict_eval_email(request,review):
    msg = render_to_string("doc/eval_email.txt",
                            dict(doc=review,
                                 doc_url = settings.IDTRACKER_BASE_URL+review.get_absolute_url(),
                                 )
                           )
    addrs = gather_address_lists('iesg_ballot_issued',doc=review).as_strings()
    override = {'To':addrs.to}
    if addrs.cc:
        override['Cc']=addrs.cc
    send_mail_preformatted(request,msg,override=override)
    addrs = gather_address_lists('ballot_issued_iana',doc=review).as_strings()
    email_iana(request, 
               review.relateddocument_set.get(relationship__slug='conflrev').target,
               addrs.to,
               msg,
               addrs.cc)

class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Conflict review response", help_text="Edit the conflict review response.", required=False, strip=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file.", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

    def save(self, review):
        basename = f"{review.name}-{review.rev}.txt"
        filepath = Path(settings.CONFLICT_REVIEW_PATH) / basename
        with filepath.open('w', encoding='utf-8') as destination:
            if self.cleaned_data['txt']:
                content = self.cleaned_data['txt']
            else:
                content = self.cleaned_data['content']
            destination.write(content)
        ftp_filepath = Path(settings.FTP_DIR) / "conflict-reviews" / basename
        try:
            os.link(filepath, ftp_filepath) # Path.hardlink_to is not available until 3.10
        except IOError as e:
            log.log(
                "There was an error creating a hardlink at %s pointing to %s: %s"
                % (ftp_filepath, filepath, e)
            )
        review.store_str(basename, content)

#This is very close to submit on charter - can we get better reuse?
@role_required('Area Director','Secretariat')
def submit(request, name):
    review = get_object_or_404(Document, type="conflrev", name=name)

    login = request.user.person

    path = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (review.name, review.rev))
    not_uploaded_yet = review.rev == "00" and not os.path.exists(path)

    if not_uploaded_yet:
        # this case is special - the conflict review text document doesn't actually exist yet
        next_rev = review.rev
    else:
        next_rev = "%02d" % (int(review.rev)+1) 

    if request.method == 'POST':
        if "submit_response" in request.POST:
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                review.rev = next_rev

                events = []
                e = NewRevisionDocEvent(doc=review, by=login, type="new_revision")
                e.desc = "New version available: <b>%s-%s.txt</b>" % (review.name, review.rev)
                e.rev = review.rev
                e.save()
                events.append(e)
            
                # Save file on disk
                form.save(review)

                review.save_with_history(events)

                return redirect('ietf.doc.views_doc.document_main', name=review.name)

        elif "reset_text" in request.POST:

            init = { "content": escape(render_to_string("doc/conflict_review/review_choices.txt",dict()))}
            form = UploadForm(initial=init)

        # Protect against handcrufted malicious posts
        else:
            form = None

    else:
        form = None

    if not form:
        init = { "content": ""}

        if not_uploaded_yet:
            init["content"] = escape(render_to_string("doc/conflict_review/review_choices.txt",
                                                dict(),
                                              ))
        else:
            filename = os.path.join(settings.CONFLICT_REVIEW_PATH, '%s-%s.txt' % (review.name, review.rev))
            try:
                with io.open(filename, 'r') as f:
                    init["content"] = f.read()
            except IOError:
                pass

        form = UploadForm(initial=init)

    return render(request, 'doc/conflict_review/submit.html',
                              {'form': form,
                               'next_rev': next_rev,
                               'review' : review,
                               'conflictdoc' : review.relateddocument_set.get(relationship__slug='conflrev').target,
                              })

@role_required("Area Director", "Secretariat")
def edit_ad(request, name):
    """Change the shepherding Area Director for this review."""

    review = get_object_or_404(Document, type="conflrev", name=name)

    if request.method == 'POST':
        form = AdForm(request.POST)
        if form.is_valid():
            review.ad = form.cleaned_data['ad']

            c = DocEvent(type="added_comment", doc=review, rev=review.rev, by=request.user.person)
            c.desc = "Shepherding AD changed to "+review.ad.name
            c.save()

            review.save_with_history([c])
            send_conflict_review_ad_changed_email(request, review, c)

            return redirect('ietf.doc.views_doc.document_main', name=review.name)

    else:
        init = { "ad" : review.ad_id }
        form = AdForm(initial=init)

    
    conflictdoc = review.relateddocument_set.get(relationship__slug='conflrev').target
    titletext = 'the conflict review of %s-%s' % (conflictdoc.name,conflictdoc.rev)
    return render(request, 'doc/change_ad.html',
                              {'form': form,
                               'doc': review,
                               'titletext': titletext
                              },
                          )

def default_approval_text(review):

    current_text = review.text_or_error()      # pyflakes:ignore
    conflictdoc = review.relateddocument_set.get(relationship__slug='conflrev').target
    if conflictdoc.stream_id=='ise':
         receiver = 'Independent Submissions Editor'
    elif conflictdoc.stream_id=='irtf':
         receiver = 'IRTF'
    else:
         receiver = 'recipient'
    addrs = gather_address_lists('ballot_approved_conflrev',doc=review).as_strings(compact=False)
    text = render_to_string("doc/conflict_review/approval_text.txt",
                               dict(review=review,
                                    review_url = settings.IDTRACKER_BASE_URL+review.get_absolute_url(),
                                    conflictdoc = conflictdoc,
                                    conflictdoc_url = settings.IDTRACKER_BASE_URL+conflictdoc.get_absolute_url(),
                                    receiver=receiver,
                                    approved_review = current_text,
                                    to = addrs.to,
                                    cc = addrs.cc,
                                   )
                              )

    return text


class AnnouncementForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, label="IETF Conflict Review Announcement", help_text="Edit the announcement message.", required=True, strip=False)

@role_required("Secretariat")
def approve_conflict_review(request, name):
    """Approve this conflict review, setting the appropriate state and send the announcement to the right parties."""
    review = get_object_or_404(Document, type="conflrev", name=name)

    if review.get_state('conflrev').slug not in ('appr-reqnopub-pend','appr-noprob-pend'):
      raise Http404

    login = request.user.person

    if request.method == 'POST':

        form = AnnouncementForm(request.POST)

        if form.is_valid():
            prev_state = review.get_state()
            events = []

            new_state_slug = 'appr-reqnopub-sent' if prev_state.slug == 'appr-reqnopub-pend' else 'appr-noprob-sent'
            new_state = State.objects.get(used=True, type="conflrev", slug=new_state_slug)

            review.set_state(new_state)
            e = add_state_change_event(review, login, prev_state, new_state)
            events.append(e)

            close_open_ballots(review, login)

            e = DocEvent(doc=review, rev=review.rev, by=login)
            e.type = "iesg_approved"
            e.desc = "IESG has approved the conflict review response"
            e.save()
            events.append(e)

            review.save_with_history(events)

            # send announcement
            send_mail_preformatted(request, form.cleaned_data['announcement_text'])

            c = DocEvent(type="added_comment", doc=review, rev=review.rev, by=login)
            c.desc = "The following approval message was sent\n"+form.cleaned_data['announcement_text']
            c.save()

            doc = review.related_that_doc("conflrev")[0]
            update_stream_state(doc, login, 'chair-w' if doc.stream_id=='irtf' else 'ise-rev', 'iesg-com')

            return HttpResponseRedirect(review.get_absolute_url())

    else:

        init = { "announcement_text" : escape(default_approval_text(review)) }
        form = AnnouncementForm(initial=init)
    
    return render(request, 'doc/conflict_review/approve.html',
                              dict(
                                   review = review,
                                   conflictdoc = review.relateddocument_set.get(relationship__slug='conflrev').target,   
                                   form = form,
                                   ))

class SimpleStartReviewForm(forms.Form):
    notify = forms.CharField(
        widget=forms.Textarea,
        max_length=1023,
        label="Notice emails",
        help_text="Separate email addresses with commas.",
        required=False,
    )

class StartReviewForm(forms.Form):
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active",role__group__type='area').order_by('name'), 
                                label="Shepherding AD", empty_label="(None)", required=True)
    create_in_state = forms.ModelChoiceField(State.objects.filter(used=True, type="conflrev", slug__in=("needshep", "adrev")), empty_label=None, required=False)
    notify = forms.CharField(
        widget=forms.Textarea,
        max_length=1023,
        label="Notice emails",
        help_text="Separate email addresses with commas.",
        required=False,
    )
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False, widget=forms.Select(attrs={'onchange':'make_bold()'}))

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

        # telechat choices
        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        #init = kwargs['initial']['telechat_date']
        #if init and init not in dates:
        #    dates.insert(0, init)

        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]

@role_required("Secretariat","IRTF Chair","ISE")
def start_review(request, name):
    if has_role(request.user,"Secretariat"):
        return start_review_as_secretariat(request,name)
    else:
        return start_review_as_stream_owner(request,name)

def start_review_sanity_check(request, name):
    doc_to_review = get_object_or_404(Document, type="draft", name=name)

    if ( not doc_to_review.stream_id in ('ise','irtf') )  or ( not is_authorized_in_doc_stream(request.user,doc_to_review)):
        raise Http404

    # sanity check that there's not already a conflict review document for this document
    if [ rel.source for rel in doc_to_review.targets_related.filter(relationship='conflrev') ]:
        raise Http404

    return doc_to_review

def build_notify_addresses(doc_to_review):
    # Take care to do the right thing during ietf chair and stream owner transitions
    notify_addresses = []
    notify_addresses.extend([r.formatted_email() for r in Role.objects.filter(group__acronym=doc_to_review.stream.slug, name='chair')])
    notify_addresses.append("%s@%s" % (doc_to_review.name, settings.DRAFT_ALIAS_DOMAIN))
    return notify_addresses

def build_conflict_review_document(login, doc_to_review, ad, notify, create_in_state):
    if doc_to_review.name.startswith('draft-'):
        review_name = 'conflict-review-'+doc_to_review.name[6:]
    else:
        # This is a failsafe - and might be treated better as an error
        review_name = 'conflict-review-'+doc_to_review.name

    iesg_group = Group.objects.get(acronym='iesg')

    conflict_review = Document.objects.create(
        type_id="conflrev",
        title="IETF conflict review for %s" % doc_to_review.name,
        name=review_name,
        rev="00",
        ad=ad,
        notify=notify,
        stream_id='ietf',
        group=iesg_group,
    )
    conflict_review.set_state(create_in_state)
            
    conflict_review.relateddocument_set.create(target=doc_to_review, relationship_id='conflrev')

    c = DocEvent(type="added_comment", doc=conflict_review, rev=conflict_review.rev, by=login)
    c.desc = "IETF conflict review requested"
    c.save()

    c = DocEvent(type="added_comment", doc=doc_to_review, rev=doc_to_review.rev, by=login)
    # Is it really OK to put html tags into comment text?
    c.desc = 'IETF conflict review initiated - see <a href="%s">%s</a>' % (reverse('ietf.doc.views_doc.document_main', kwargs={'name':conflict_review.name}),conflict_review.name)
    c.save()

    return conflict_review

def start_review_as_secretariat(request, name):
    """Start the conflict review process, setting the initial shepherding AD, and possibly putting the review on a telechat."""

    doc_to_review = start_review_sanity_check(request, name)

    login = request.user.person

    if request.method == 'POST':
        form = StartReviewForm(request.POST)
        if form.is_valid():
            conflict_review = build_conflict_review_document(login = login,
                                                             doc_to_review = doc_to_review, 
                                                             ad = form.cleaned_data['ad'],
                                                             notify = form.cleaned_data['notify'],
                                                             create_in_state = form.cleaned_data['create_in_state']
                                                            )

            tc_date = form.cleaned_data['telechat_date']
            if tc_date:
                update_telechat(request, conflict_review, login, tc_date)

            send_conflict_review_started_email(request, conflict_review)

            update_stream_state(doc_to_review, login, 'iesg-rev')

            return HttpResponseRedirect(conflict_review.get_absolute_url())
    else: 
        notify_addresses = build_notify_addresses(doc_to_review)
        init = { 
                "ad" : Role.objects.filter(group__acronym='ietf',name='chair')[0].person.id,
                "notify" : ', '.join(notify_addresses),
               }
        form = StartReviewForm(initial=init)

    return render(request, 'doc/conflict_review/start.html',
                              {'form':   form,
                               'doc_to_review': doc_to_review,
                              },
                          )

def start_review_as_stream_owner(request, name):
    """Start the conflict review process using defaults for everything but notify and let the secretariat know"""

    doc_to_review = start_review_sanity_check(request, name)

    login = request.user.person

    if request.method == 'POST':
        form = SimpleStartReviewForm(request.POST)
        if form.is_valid():
            conflict_review = build_conflict_review_document(login = login,
                                                             doc_to_review = doc_to_review, 
                                                             ad = Role.objects.filter(group__acronym='ietf',name='chair')[0].person,
                                                             notify = form.cleaned_data['notify'],
                                                             create_in_state = State.objects.get(used=True,type='conflrev',slug='needshep')
                                                            )

            send_conflict_review_started_email(request, conflict_review)

            update_stream_state(doc_to_review, login, 'iesg-rev')

            return HttpResponseRedirect(conflict_review.get_absolute_url())
    else: 
        notify_addresses = build_notify_addresses(doc_to_review)
        
        init = { 
                "notify" : ', '.join(notify_addresses),
               }
        form = SimpleStartReviewForm(initial=init)

    return render(request, 'doc/conflict_review/start.html',
                              {'form':   form,
                               'doc_to_review': doc_to_review,
                              },
                          )

def update_stream_state(doc, by, state, tag=None):
    statetype = 'draft-stream-' + doc.stream_id
    prev_state = doc.get_state(statetype)
    new_state = State.objects.get(type_id=statetype, slug=state)
    if tag:
        prev_tags = set(doc.tags.all())
        new_tags = set(DocTagName.objects.filter(pk=tag))

    if new_state != prev_state:
        doc.set_state(new_state)
        events = []
        if tag:
            doc.tags.clear()
            doc.tags.set(new_tags)
            events.append(add_state_change_event(doc, by, prev_state, new_state, prev_tags, new_tags))
        else:
            events.append(add_state_change_event(doc, by, prev_state, new_state))
        doc.save_with_history(events)
