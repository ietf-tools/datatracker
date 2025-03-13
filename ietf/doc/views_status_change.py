# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import io
import os
from pathlib import Path
import re

from typing import Dict             # pyflakes:ignore

from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.encoding import force_str
from django.utils.html import escape

import debug                            # pyflakes:ignore
from ietf.doc.mails import email_ad_approved_status_change

from ietf.doc.models import ( Document, State, DocEvent, BallotDocEvent,
    BallotPositionDocEvent, NewRevisionDocEvent, WriteupDocEvent, STATUSCHANGE_RELATIONS )
from ietf.doc.forms import AdForm
from ietf.doc.lastcall import request_last_call
from ietf.doc.utils import add_state_change_event, update_telechat, close_open_ballots, create_ballot_if_not_open
from ietf.doc.views_ballot import LastCallTextForm
from ietf.group.models import Group
from ietf.iesg.models import TelechatDate
from ietf.ietfauth.utils import has_role, role_required
from ietf.mailtrigger.utils import gather_address_lists
from ietf.name.models import DocRelationshipName, StdLevelName
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.utils.mail import send_mail_preformatted
from ietf.utils.textupload import get_cleaned_text_file_content
from ietf.utils.timezone import date_today, DEADLINE_TZINFO


class ChangeStateForm(forms.Form):
    new_state = forms.ModelChoiceField(State.objects.filter(type="statchg", used=True), label="Status Change Evaluation State", empty_label=None, required=True)
    comment = forms.CharField(widget=forms.Textarea, help_text="Optional comment for the review history.", required=False, strip=False)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super(ChangeStateForm, self).__init__(*args, **kwargs)
        if not has_role(user, "Secretariat"):
            self.fields["new_state"].queryset = self.fields["new_state"].queryset.exclude(slug="appr-sent")


@role_required("Area Director", "Secretariat")
def change_state(request, name, option=None):
    """Change state of an status-change document, notifying parties as necessary
       and logging the change as a comment."""
    status_change = get_object_or_404(Document, type="statchg", name=name)

    login = request.user.person

    if request.method == 'POST':
        form = ChangeStateForm(request.POST, user=request.user)
        if form.is_valid():
            clean = form.cleaned_data
            new_state = clean['new_state']
            comment = clean['comment'].rstrip()

            if comment:
                c = DocEvent(type="added_comment", doc=status_change, rev=status_change.rev, by=login)
                c.desc = comment
                c.save()

            prev_state = status_change.get_state()
            if new_state != prev_state:
                status_change.set_state(new_state)
                events = []
                events.append(add_state_change_event(status_change, login, prev_state, new_state))
                status_change.save_with_history(events)

                if new_state.slug == "iesgeval":
                    e = create_ballot_if_not_open(request, status_change, login, "statchg", status_change.time) # pyflakes:ignore
                    ballot = status_change.latest_event(BallotDocEvent, type="created_ballot")
                    if has_role(request.user, "Area Director") and not status_change.latest_event(BallotPositionDocEvent, balloter=login, ballot=ballot, type="changed_ballot_position"):

                        # The AD putting a status change into iesgeval who doesn't already have a position is saying "yes"
                        pos = BallotPositionDocEvent(doc=status_change, rev=status_change.rev, by=login)
                        pos.ballot = ballot
                        pos.type = "changed_ballot_position"
                        pos.balloter = login
                        pos.pos_id = "yes"
                        pos.desc = "[Ballot Position Update] New position, %s, has been recorded for %s" % (pos.pos.name, pos.balloter.plain_name())
                        pos.save()

                    send_status_change_eval_email(request,status_change)


                if new_state.slug == "lc-req":
                    request_last_call(request, status_change)
                    return render(request, 'doc/draft/last_call_requested.html',
                                              dict(doc=status_change,
                                                   url = status_change.get_absolute_url(),
                                                  ))
                elif new_state.slug == 'appr-pend' and has_role(request.user, "Area Director"):
                    related_docs = status_change.relateddocument_set.filter(
                        relationship__slug__in=STATUSCHANGE_RELATIONS
                    )
                    related_doc_info = [
                        dict(title=rel_doc.target.title,
                             name=rel_doc.target.name,
                             newstatus=newstatus(rel_doc))
                        for rel_doc in related_docs
                    ]
                    email_ad_approved_status_change(
                        request,
                        status_change,
                        related_doc_info=related_doc_info,
                    )

            return redirect('ietf.doc.views_doc.document_main', name=status_change.name)
    else:
        s = status_change.get_state()
        init = dict(new_state=s.pk if s else None,
                    type='statchg',
                    label='Status Change Evaluation State',
                   )
        form = ChangeStateForm(initial=init, user=request.user)

    return render(request, 'doc/change_state.html',
                              dict(form=form,
                                   doc=status_change,
                                   login=login,
                                   help_url=reverse('ietf.doc.views_help.state_help', kwargs=dict(type="status-change")),
                                   ))

def send_status_change_eval_email(request,doc):
    for target in ('iesg_ballot_issued', 'ballot_issued_iana'):
        addrs = gather_address_lists(target,doc=doc).as_strings()
        msg = render_to_string("doc/eval_email.txt",
                                dict(doc=doc,
                                    doc_url = settings.IDTRACKER_BASE_URL+doc.get_absolute_url(),
                                    to = addrs.to,
                                    cc = addrs.cc
                                    )
                            )
        send_mail_preformatted(request,msg)

class UploadForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea, label="Status change text", help_text="Edit the status change text.", required=False, strip=False)
    txt = forms.FileField(label=".txt format", help_text="Or upload a .txt file.", required=False)

    def clean_content(self):
        return self.cleaned_data["content"].replace("\r", "")

    def clean_txt(self):
        return get_cleaned_text_file_content(self.cleaned_data["txt"])

    def save(self, doc):
        basename = f"{doc.name}-{doc.rev}.txt"
        filename = Path(settings.STATUS_CHANGE_PATH) / basename
        with io.open(filename, 'w', encoding='utf-8') as destination:
            if self.cleaned_data['txt']:
                content = self.cleaned_data['txt']
            else:
                content = self.cleaned_data['content']
            destination.write(content)
            doc.store_str(basename, content)
        try:
            ftp_filename = Path(settings.FTP_DIR) / "status-changes" / basename
            os.link(filename, ftp_filename) # Path.hardlink is not available until 3.10
        except IOError as ex:
            log(
                "There was an error creating a hardlink at %s pointing to %s: %s"
                % (ftp_filename, filename, ex)
            )

#This is very close to submit on charter - can we get better reuse?
@role_required('Area Director','Secretariat')
def submit(request, name):
    doc = get_object_or_404(Document, type="statchg", name=name)

    login = request.user.person

    path = os.path.join(settings.STATUS_CHANGE_PATH, '%s-%s.txt' % (doc.name, doc.rev))
    not_uploaded_yet = doc.rev == "00" and not os.path.exists(path)

    if not_uploaded_yet:
        # this case is special - the status change text document doesn't actually exist yet
        next_rev = doc.rev
    else:
        next_rev = "%02d" % (int(doc.rev)+1) 

    if request.method == 'POST':
        if "submit_response" in request.POST:
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                doc.rev = next_rev

                events = []
                e = NewRevisionDocEvent(doc=doc, by=login, type="new_revision")
                e.desc = "New version available: <b>%s-%s.txt</b>" % (doc.name, doc.rev)
                e.rev = doc.rev
                e.save()
                events.append(e)
            
                # Save file on disk
                form.save(doc)

                doc.save_with_history(events)

                return redirect('ietf.doc.views_doc.document_main', name=doc.name)

        elif "reset_text" in request.POST:

            init = { "content": render_to_string("doc/status_change/initial_template.txt",dict())}
            form = UploadForm(initial=init)

        # Protect against handcrufted malicious posts
        else:
            form = None

    else:
        form = None

    if not form:
        init = { "content": ""}

        if not_uploaded_yet:
            init["content"] = render_to_string("doc/status_change/initial_template.txt",
                                                dict(),
                                              )
        else:
            filename = os.path.join(settings.STATUS_CHANGE_PATH, '%s-%s.txt' % (doc.name, doc.rev))
            try:
                with io.open(filename, 'r') as f:
                    init["content"] = f.read()
            except IOError:
                pass

        form = UploadForm(initial=init)

    return render(request, 'doc/status_change/submit.html',
                              {'form': form,
                               'next_rev': next_rev,
                               'doc' : doc,
                              })

class ChangeTitleForm(forms.Form):
    title = forms.CharField(max_length=255, label="Title", required=True)

@role_required("Area Director", "Secretariat")
def edit_title(request, name):
    """Change the title for this status_change document."""

    status_change = get_object_or_404(Document, type="statchg", name=name)

    if request.method == 'POST':
        form = ChangeTitleForm(request.POST)
        if form.is_valid():

            status_change.title = form.cleaned_data['title']

            c = DocEvent(type="added_comment", doc=status_change, rev=status_change.rev, by=request.user.person)
            c.desc = "Title changed to '%s'"%status_change.title
            c.save()

            status_change.save_with_history([c])

            return redirect("ietf.doc.views_doc.document_main", name=status_change.name)

    else:
        init = { "title" : status_change.title }
        form = ChangeTitleForm(initial=init)

    titletext = '%s-%s.txt' % (status_change.name,status_change.rev)
    return render(request, 'doc/change_title.html',
                              {'form': form,
                               'doc': status_change,
                               'titletext' : titletext,
                              },
                          )

@role_required("Area Director", "Secretariat")
def edit_ad(request, name):
    """Change the shepherding Area Director for this status_change."""

    status_change = get_object_or_404(Document, type="statchg", name=name)

    if request.method == 'POST':
        form = AdForm(request.POST)
        if form.is_valid():
            status_change.ad = form.cleaned_data['ad']

            c = DocEvent(type="added_comment", doc=status_change, rev=status_change.rev, by=request.user.person)
            c.desc = "Shepherding AD changed to "+status_change.ad.name
            c.save()

            status_change.save_with_history([c])
    
            return redirect("ietf.doc.views_doc.document_main", name=status_change.name)

    else:
        init = { "ad" : status_change.ad_id }
        form = AdForm(initial=init)

    titletext = '%s-%s.txt' % (status_change.name,status_change.rev)
    return render(request, 'doc/change_ad.html',
                              {'form': form,
                               'doc': status_change,
                               'titletext' : titletext,
                              },
                          )

def newstatus(relateddoc):

    level_map = { 
                  'tops'    : 'ps',
                  'tois'    : 'std',
                  'tohist'  : 'hist',
                  'toinf'   : 'inf',
                  'tobcp'   : 'bcp',
                  'toexp'   : 'exp',
                }

    return StdLevelName.objects.get(slug=level_map[relateddoc.relationship.slug])

def default_approval_text(status_change,relateddoc):

    current_text = status_change.text_or_error() # pyflakes:ignore

    if relateddoc.target.std_level_id in ('std','ps','ds','bcp',):
        action = "Protocol Action"
    else:
        action = "Document Action"


    addrs = gather_address_lists('ballot_approved_status_change',doc=status_change).as_strings(compact=False)
    text = render_to_string("doc/status_change/approval_text.txt",
                               dict(status_change=status_change,
                                    status_change_url = settings.IDTRACKER_BASE_URL+status_change.get_absolute_url(),
                                    relateddoc= relateddoc,
                                    relateddoc_url = settings.IDTRACKER_BASE_URL+relateddoc.target.get_absolute_url(),
                                    approved_text = current_text,
                                    action=action,
                                    newstatus=newstatus(relateddoc),
                                    to=addrs.to,
                                    cc=addrs.cc,
                                   )
                              )

    return text

from django.forms.formsets import formset_factory

class AnnouncementForm(forms.Form):
    announcement_text = forms.CharField(widget=forms.Textarea, label="Status Change Announcement", help_text="Edit the announcement message.", required=True, strip=False)
    label = None
      
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.label = self.initial.get('label')

@role_required("Secretariat")
def approve(request, name):
    """Approve this status change, setting the appropriate state and send the announcements to the right parties."""
    status_change = get_object_or_404(Document, type="statchg", name=name)

    if status_change.get_state('statchg').slug not in ('appr-pend'):
      raise Http404

    login = request.user.person

    AnnouncementFormSet = formset_factory(AnnouncementForm,extra=0)        

    if request.method == 'POST':

        formset = AnnouncementFormSet(request.POST)

        if formset.is_valid():

            prev_state = status_change.get_state()
            new_state = State.objects.get(type='statchg', slug='appr-sent')

            status_change.set_state(new_state)

            events = []
            events.append(add_state_change_event(status_change, login, prev_state, new_state))

            close_open_ballots(status_change, login)

            e = DocEvent(doc=status_change, rev=status_change.rev, by=login)
            e.type = "iesg_approved"
            e.desc = "IESG has approved the status change"
            e.save()
            events.append(e)

            status_change.save_with_history(events)


            for form in formset.forms:

                send_mail_preformatted(request, form.cleaned_data['announcement_text'], extra={})

                c = DocEvent(type="added_comment", doc=status_change, rev=status_change.rev, by=login)
                c.desc = "The following approval message was sent\n"+form.cleaned_data['announcement_text']
                c.save()

            for rel in status_change.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS):
                # Add a document event to each target
                c = DocEvent(type="added_comment", doc=rel.target, rev=rel.target.rev, by=login)
                c.desc = "New status of %s approved by the IESG\n%s%s" % (newstatus(rel), settings.IDTRACKER_BASE_URL,reverse('ietf.doc.views_doc.document_main', kwargs={'name': status_change.name}))
                c.save()

            return HttpResponseRedirect(status_change.get_absolute_url())

    else:

        init = []
        for rel in status_change.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS):
            init.append({"announcement_text" : escape(default_approval_text(status_change,rel)),
                         "label": "Announcement text for %s to %s"%(rel.target.name,newstatus(rel)),
                       })
        formset = AnnouncementFormSet(initial=init)
        for form in formset.forms:
           form.fields['announcement_text'].label=form.label
    
    return render(request, 'doc/status_change/approve.html',
                              dict(
                                   doc = status_change,
                                   formset = formset,
                                   ))

def clean_helper(form, formtype):
        cleaned_data = super(formtype, form).clean()

        new_relations = {}
        rfc_fields = {}
        status_fields={}
        for k in sorted(form.data.keys()):
            v = form.data[k].lower()
            if k.startswith('new_relation_row'):
                if re.match(r'\d{1,4}',v):
                    v = 'rfc'+v
                rfc_fields[k[17:]]=v
            elif k.startswith('statchg_relation_row'):
                status_fields[k[21:]]=v
        for key in rfc_fields:
            if rfc_fields[key]!="":
                if key in status_fields:
                    new_relations[rfc_fields[key]]=status_fields[key]
                else:
                    new_relations[rfc_fields[key]]=None
        
        form.relations = new_relations

        errors=[]
        for key in new_relations:

           if not re.match(r'(?i)rfc\d{1,4}',key):
              errors.append(key+" is not a valid RFC - please use the form RFCn\n")
           elif not Document.objects.filter(name=key):
              errors.append(key+" does not exist\n")

           if new_relations[key] not in STATUSCHANGE_RELATIONS:
              errors.append("Please choose a new status level for "+key+"\n")

        if errors:
           raise forms.ValidationError(errors) 

        cleaned_data['relations']=new_relations

        return cleaned_data

class EditStatusChangeForm(forms.Form):
    relations={}                        # type: Dict[str, str]

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.relations = self.initial.get('relations')

    def clean(self):
        return clean_helper(self,EditStatusChangeForm)

class StartStatusChangeForm(forms.Form):
    document_name = forms.CharField(max_length=255, label="Document name", help_text="A descriptive name such as status-change-md2-to-historic is better than status-change-rfc1319.", required=True)
    title = forms.CharField(max_length=255, label="Title", required=True)
    ad = forms.ModelChoiceField(Person.objects.filter(role__name="ad", role__group__state="active",role__group__type='area').order_by('name'), 
                                label="Shepherding AD", empty_label="(None)", required=False)
    create_in_state = forms.ModelChoiceField(State.objects.filter(type="statchg", slug__in=("needshep", "adrev")), empty_label=None, required=False)
    notify = forms.CharField(
        widget=forms.Textarea,
        max_length=1023,
        label="Notice emails",
        help_text="Separate email addresses with commas.",
        required=False,
    )
    telechat_date = forms.TypedChoiceField(coerce=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date(), empty_value=None, required=False, widget=forms.Select(attrs={'onchange':'make_bold()'}))
    relations={}                        # type: Dict[str, str]

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.relations = self.initial.get('relations')

        # telechat choices
        dates = [d.date for d in TelechatDate.objects.active().order_by('date')]
        self.fields['telechat_date'].choices = [("", "(not on agenda)")] + [(d, d.strftime("%Y-%m-%d")) for d in dates]

    def clean_document_name(self):
        name = self.cleaned_data['document_name']
        errors=[]
        if re.search("[^a-z0-9-]", name):
            errors.append("The name of the document may only contain digits, lowercase letters and dashes")
        if re.search("--", name):
            errors.append("Please do not put more than one hyphen between any two words in the name")
        if name.startswith('status-change'):
            errors.append("status-change- will be added automatically as a prefix")
        if name.startswith('-'):
            errors.append("status-change- will be added automatically as a prefix, starting with a - will result in status-change-%s"%name)
        if re.search("-[0-9]{2}$", name):
            errors.append("This name looks like ends in a version number. -00 will be added automatically. Please adjust the end of the name.")
        if Document.objects.filter(name='status-change-%s'%name):
            errors.append("status-change-%s already exists"%name)
        if name.endswith('CHANGETHIS'):
            errors.append("Please change CHANGETHIS to reflect the intent of this status change")
        if errors:
            raise forms.ValidationError(errors)
        return name

    def clean_title(self):
       title = self.cleaned_data['title']
       errors=[]
       if title.endswith('CHANGETHIS'):
            errors.append("Please change CHANGETHIS to reflect the intent of this status change")
       if errors:
            raise forms.ValidationError(errors)
       return title

    def clean(self):
        return clean_helper(self,StartStatusChangeForm)

def rfc_status_changes(request):
    """Show the rfc status changes that are under consideration, and those that are completed."""

    docs=Document.objects.filter(type__slug='statchg')
    doclist=[x for x in docs]
    doclist.sort(key=lambda obj: obj.get_state().order)
    return render(request, 'doc/status_change/status_changes.html',
                              {'docs' : doclist,
                              },
                          )

@role_required("Area Director","Secretariat")
def start_rfc_status_change(request, name=None):
    """Start the RFC status change review process, setting the initial shepherding AD, and possibly putting the review on a telechat."""

    if name:
       if not re.match("(?i)rfc[0-9]{1,4}",name):
           raise Http404
       seed_rfc = get_object_or_404(Document, type="rfc", name=name)

    login = request.user.person

    relation_slugs = DocRelationshipName.objects.filter(slug__in=STATUSCHANGE_RELATIONS)

    if request.method == 'POST':
        form = StartStatusChangeForm(request.POST)
        if form.is_valid():
            
            iesg_group = Group.objects.get(acronym='iesg')

            status_change = Document.objects.create(
                type_id="statchg",
                name='status-change-'+form.cleaned_data['document_name'],
                title=form.cleaned_data['title'],
                rev="00",
                ad=form.cleaned_data['ad'],
                notify=form.cleaned_data['notify'],
                stream_id='ietf',
                group=iesg_group,
            )
            status_change.set_state(form.cleaned_data['create_in_state'])
            
            for key in form.cleaned_data['relations']:
                status_change.relateddocument_set.create(target=Document.objects.get(name=key),
                                                         relationship_id=form.cleaned_data['relations'][key])

            tc_date = form.cleaned_data['telechat_date']
            if tc_date:
                update_telechat(request, status_change, login, tc_date)

            return HttpResponseRedirect(status_change.get_absolute_url())
    else: 
        init = {}
        if name:
           init['title'] = "%s to CHANGETHIS" % seed_rfc.title
           init['document_name'] = "%s-to-CHANGETHIS" % seed_rfc.name
           relations={}
           relations[seed_rfc.name]=None
           init['relations'] = relations
        form = StartStatusChangeForm(initial=init)

    return render(request, 'doc/status_change/start.html',
                              {'form':   form,
                               'relation_slugs': relation_slugs,
                              },
                          )

@role_required("Area Director", "Secretariat")
def edit_relations(request, name):
    """Change the affected set of RFCs"""

    status_change = get_object_or_404(Document, type="statchg", name=name)

    login = request.user.person

    relation_slugs = DocRelationshipName.objects.filter(slug__in=STATUSCHANGE_RELATIONS)

    if request.method == 'POST':
        form = EditStatusChangeForm(request.POST)
        if form.is_valid():
    
            old_relations={}
            for rel in status_change.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS):
                old_relations[rel.target.name]=rel.relationship.slug
            new_relations=form.cleaned_data['relations']
            status_change.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS).delete()
            for key in new_relations:
                status_change.relateddocument_set.create(target=Document.objects.get(name=key),
                                                         relationship_id=new_relations[key])
            c = DocEvent(type="added_comment", doc=status_change, rev=status_change.rev, by=login)
            c.desc = "Affected RFC list changed.\nOLD:"
            for relname,relslug in (set(old_relations.items())-set(new_relations.items())):
                c.desc += "\n  "+relname+": "+DocRelationshipName.objects.get(slug=relslug).name
            c.desc += "\nNEW:"
            for relname,relslug in (set(new_relations.items())-set(old_relations.items())):
                c.desc += "\n  "+relname+": "+DocRelationshipName.objects.get(slug=relslug).name
            c.desc += "\n"
            c.save()

            return HttpResponseRedirect(status_change.get_absolute_url())

    else: 
        relations={}
        for rel in status_change.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS):
            relations[rel.target.name]=rel.relationship.slug
        init = { "relations":relations, 
               }
        form = EditStatusChangeForm(initial=init)

    return render(request, 'doc/status_change/edit_relations.html',
                              {
                               'doc':            status_change, 
                               'form':           form,
                               'relation_slugs': relation_slugs,
                              },
                          )

def generate_last_call_text(request, doc):

    # requester should be set based on doc.group once the group for a status change can be set to something other than the IESG
    # and when groups are set, vary the expiration time accordingly

    requester = "an individual participant"
    expiration_date = date_today(DEADLINE_TZINFO) + datetime.timedelta(days=28)
    cc = []
    
    new_text = render_to_string("doc/status_change/last_call_announcement.txt",
                                dict(doc=doc,
                                     settings=settings,
                                     requester=requester,
                                     expiration_date=expiration_date.strftime("%Y-%m-%d"),
                                     changes=['%s from %s to %s\n    (%s)'%(rel.target.name.upper(),rel.target.std_level.name,newstatus(rel),rel.target.title) for rel in doc.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS)],
                                     urls=[rel.target.get_absolute_url() for rel in doc.relateddocument_set.filter(relationship__slug__in=STATUSCHANGE_RELATIONS)],
                                     cc=cc
                                    )
                               )

    e = WriteupDocEvent()
    e.type = 'changed_last_call_text'
    e.by = request.user.person
    e.doc = doc
    e.rev = doc.rev
    e.desc = 'Last call announcement was generated'
    e.text = force_str(new_text)
    e.save()

    return e 

@role_required("Area Director", "Secretariat")
def last_call(request, name):
    """Edit the Last Call Text for this status change and possibly request IETF LC"""

    status_change = get_object_or_404(Document, type="statchg", name=name)

    login = request.user.person

    last_call_event = status_change.latest_event(WriteupDocEvent, type="changed_last_call_text")
    if not last_call_event:
        last_call_event = generate_last_call_text(request, status_change)

    form = LastCallTextForm(initial=dict(last_call_text=escape(last_call_event.text)))

    if request.method == 'POST':
        if "save_last_call_text" in request.POST or ("send_last_call_request" in request.POST and status_change.ad is not None):
            form = LastCallTextForm(request.POST)
            if form.is_valid():
                events = []

                t = form.cleaned_data['last_call_text']
                if t != last_call_event.text:
                    e = WriteupDocEvent(doc=status_change, rev=status_change.rev, by=login)
                    e.by = login
                    e.type = "changed_last_call_text"
                    e.desc = "Last call announcement was changed"
                    e.text = t
                    e.save()

                    events.append(e)

                if "send_last_call_request" in request.POST:
                    prev_state = status_change.get_state()
                    new_state = State.objects.get(type='statchg', slug='lc-req')

                    status_change.set_state(new_state)
                    e = add_state_change_event(status_change, login, prev_state, new_state)
                    if e:
                        events.append(e)

                    if events:
                        status_change.save_with_history(events)

                    request_last_call(request, status_change)

                    return render(request, 'doc/draft/last_call_requested.html',
                                      dict(doc=status_change,
                                          url = status_change.get_absolute_url(),
                                      )
                                  )

        if "regenerate_last_call_text" in request.POST:
            e = generate_last_call_text(request,status_change)
            form = LastCallTextForm(initial=dict(last_call_text=escape(e.text)))
            
    return render(request, 'doc/status_change/last_call.html',
                               dict(doc=status_change,
                                    back_url = status_change.get_absolute_url(),
                                    last_call_event = last_call_event,
                                    last_call_form  = form,
                                   ),
                           )
               
