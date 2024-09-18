# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import models
from django.template import Template, Context

from email.utils import parseaddr

from ietf.doc.utils_bofreq import bofreq_editors, bofreq_responsible
from ietf.utils.mail import formataddr, get_email_addresses_from_text
from ietf.group.models import Group, Role
from ietf.person.models import Email, Alias
from ietf.review.models import ReviewTeamSettings

import debug                            # pyflakes:ignore

def clean_duplicates(addrlist):
    address_info = {}
    for a in addrlist:
        (name,addr) = parseaddr(a)
        # This collapses duplicate addresses to one, using (arbitrarily) the
        # name from the last one:
        address_info[addr] = (name, a)
    addresses = []
    for addr, info in address_info.items():
        name, a = info
        if (name,addr)==('',''):
            addresses.append(a)
        elif name:
            addresses.append(formataddr((name,addr)))
        else:
            addresses.append(addr)
    return addresses

class MailTrigger(models.Model):
    slug = models.CharField(max_length=64, primary_key=True)
    desc = models.TextField(blank=True)
    to   = models.ManyToManyField('mailtrigger.Recipient', blank=True, related_name='used_in_to')
    cc   = models.ManyToManyField('mailtrigger.Recipient', blank=True, related_name='used_in_cc')

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.slug

class Recipient(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    desc = models.TextField(blank=True)
    template = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.slug

    def gather(self, **kwargs):
        retval = []
        if hasattr(self,'gather_%s'%self.slug):
            retval.extend(eval('self.gather_%s(**kwargs)'%self.slug))
        if self.template:
            rendering = Template('{%% autoescape off %%}%s{%% endautoescape %%}'%self.template).render(Context(kwargs))
            if rendering:
                retval.extend( get_email_addresses_from_text(rendering) )

        return clean_duplicates(retval)

    def gather_doc_group_chairs(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.features.acts_like_wg:
                addrs.append('%s-chairs@ietf.org'%doc.group.acronym)
        return addrs

    def gather_doc_group_delegates(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.features.acts_like_wg:
                addrs.extend(doc.group.role_set.filter(name='delegate').values_list('email__address',flat=True))
        return addrs

    def gather_doc_group_mail_list(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.features.acts_like_wg:
                if doc.group.list_email:
                    addrs.append(doc.group.list_email)
        return addrs

    def gather_doc_affecteddoc_authors(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(('conflrev','tohist','tois','tops')):
                addrs.extend(Recipient.objects.get(slug='doc_authors').gather(**{'doc':reldoc}))
        return addrs

    def gather_doc_affecteddoc_group_chairs(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(('conflrev','tohist','tois','tops')):
                addrs.extend(Recipient.objects.get(slug='doc_group_chairs').gather(**{'doc':reldoc}))
        return addrs

    def gather_doc_affecteddoc_notify(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(('conflrev','tohist','tois','tops')):
                addrs.extend(Recipient.objects.get(slug='doc_notify').gather(**{'doc':reldoc}))
        return addrs

    def gather_conflict_review_stream_manager(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(('conflrev',)):
                addrs.extend(Recipient.objects.get(slug='doc_stream_manager').gather(**{'doc':reldoc}))
        return addrs

    def gather_conflict_review_steering_group(self,**kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(('conflrev',)):
                if reldoc.stream_id=='irtf':
                    addrs.append('"Internet Research Steering Group" <irsg@irtf.org>')
        return addrs

    def gather_group_steering_group(self,**kwargs):
        addrs = []
        sg_map = dict( wg='"The IESG" <iesg@ietf.org>', rg='"Internet Research Steering Group" <irsg@irtf.org>' )
        if 'group' in kwargs and kwargs['group'].type_id in sg_map:
            addrs.append(sg_map[kwargs['group'].type_id])
        return addrs 

    def gather_stream_managers(self, **kwargs):
        addrs = []
        manager_map = dict(
            ise  = ['<rfc-ise@rfc-editor.org>'],
            irtf = ['<irtf-chair@irtf.org>'],
            ietf = ['<iesg@ietf.org>'],
            iab  = ['<iab-chair@iab.org>'],
            editorial = Role.objects.filter(group__acronym="rsab",name_id="chair").values_list("email__address", flat=True),
        )
        if 'streams' in kwargs:
            for stream in kwargs['streams']:
                if stream in manager_map:
                    addrs.extend(manager_map[stream])
        return addrs

    def gather_doc_stream_manager(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':[kwargs['doc'].stream_id]}))
        return addrs

    def gather_doc_non_ietf_stream_manager(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc = kwargs['doc']
            if doc.stream_id and doc.stream_id != 'ietf':
                addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':[doc.stream_id,]}))
        return addrs

    def gather_group_responsible_directors(self, **kwargs):
        addrs = []
        if 'group' in kwargs:
            group = kwargs['group']
            if not group.acronym=='none':
                addrs.extend(group.role_set.filter(name='ad').values_list('email__address',flat=True))
            if group.type_id=='rg':
                addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':['irtf']}))
            elif group.type_id=='program':
                addrs.extend(Recipient.objects.get(slug='iab').gather(**{}))
        return addrs

    def gather_group_secretaries(self, **kwargs):
        addrs = []
        if 'group' in kwargs:
            group = kwargs['group']
            if not group.acronym=='none':
                rts = ReviewTeamSettings.objects.filter(group=group).first()
                if rts and rts.secr_mail_alias and len(rts.secr_mail_alias) > 1:
                    addrs = get_email_addresses_from_text(rts.secr_mail_alias)
                else:
                    for role in group.role_set.filter(name='secr'):
                        addrs.append(role.email.address)
        return addrs
    
    def gather_review_req_reviewers(self, **kwargs):
        addrs = []
        if 'review_request' in kwargs:
            review_request = kwargs['review_request']
            for assignment in review_request.reviewassignment_set.all():
                addrs.append(assignment.reviewer.formatted_email())
        return addrs
    
    def gather_review_secretaries(self, **kwargs):
        if not kwargs.get('skip_secretary'):
            return self.gather_group_secretaries(**kwargs)
        return []
        
    def gather_doc_group_responsible_directors(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            group = kwargs['doc'].group
            if group and not group.acronym=='none':
                addrs.extend(Recipient.objects.get(slug='group_responsible_directors').gather(**{'group':group}))
        return addrs

    def gather_submission_authors(self, **kwargs):
        """
        Returns a list of name and email, e.g.: [ 'Ano Nymous <ano@nymous.org>' ]
        Is intended for display use, not in email context.
        """
        addrs = []
        if 'submission' in kwargs:
            submission = kwargs['submission']
            addrs.extend(["%s <%s>" % (author["name"], author["email"]) for author in submission.authors if author.get("email")])
        return addrs

    def gather_submission_submitter(self, **kwargs):
        """
        Returns a list of name and email, e.g.: [ 'Ano Nymous <ano@nymous.org>' ]
        """
        addrs = []
        if 'submission' in kwargs:
            submission = kwargs['submission']
            if '@' in submission.submitter:
                addrs.extend( get_email_addresses_from_text(submission.submitter) )
            else:
                try:
                    submitter = Alias.objects.get(name=submission.submitter).person
                    if submitter and submitter.email():
                        addrs.append(f"{submitter.name} <{submitter.email().address}>")
                except (Alias.DoesNotExist, Alias.MultipleObjectsReturned):
                    pass
        return addrs

    def gather_submission_group_chairs(self, **kwargs):
        addrs = []
        if 'submission' in kwargs: 
            submission = kwargs['submission']
            if submission.group: 
                addrs.extend(Recipient.objects.get(slug='group_chairs').gather(**{'group':submission.group}))
        return addrs

    def gather_sub_group_parent_directors(self, **kwargs):
        addrs = []
        if 'submission' in kwargs:
            submission = kwargs['submission']
            if submission.group and submission.group.parent:
                addrs.extend(
                    Recipient.objects.get(
                        slug='group_responsible_directors').gather(group=submission.group.parent)
                )
        return addrs

    def gather_doc_group_parent_directors(self, **kwargs):
        addrs = []
        doc = kwargs.get('doc')
        if doc and doc.group and doc.group.parent:
            addrs.extend(
                Recipient.objects.get(
                    slug='group_responsible_directors').gather(group=doc.group.parent)
            )
        return addrs

    def gather_submission_confirmers(self, **kwargs):
        """If a submitted document is revising an existing document, the confirmers 
           are the authors of that existing document, and the chairs if the document is
           a working group document and the author list has changed. Otherwise, the confirmers
           are the authors and submitter of the submitted document."""

        addrs=[]
        if 'submission' in kwargs:
            submission = kwargs['submission']
            doc=submission.existing_document()
            if doc:
                old_authors = [ author for author in doc.documentauthor_set.all() if author.email ]

                addrs.extend([ author.formatted_email() for author in old_authors])

                old_author_email_set = set(author.email.address for author in old_authors)
                new_author_email_set = set(author["email"] for author in submission.authors if author.get("email"))

                if doc.group and old_author_email_set != new_author_email_set:
                    if doc.group.features.acts_like_wg:
                        addrs.extend(Recipient.objects.get(slug='group_chairs').gather(**{'group':doc.group}))
                    elif doc.group.type_id in ['area']:
                        addrs.extend(Recipient.objects.get(slug='group_responsible_directors').gather(**{'group':doc.group}))
                    else:
                        pass
                    if doc.stream_id and doc.stream_id not in ['ietf']:
                        addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':[doc.stream_id]}))
            else:
                # This is a bit roundabout, but we do it to get consistent and unicode-compliant
                # email names for known persons, without relying on the name parsed from the
                # draft (which might be ascii, also for persons with non-ascii names)
                emails = [ Email.objects.filter(address=author['email']).first() or author for author in submission.authors if author.get('email') ]
                addrs.extend([ e.formatted_email() if isinstance(e, Email) else formataddr((e["name"], e["email"])) for e in emails ] )
                submitter_email = submission.submitter_parsed()["email"]
                if submitter_email and not submitter_email in [ parseaddr(a)[1] for a in addrs ]:
                    addrs.append(submission.submitter)
        return addrs

    def gather_submission_group_mail_list(self, **kwargs):
        addrs=[]
        if 'submission' in kwargs:
            submission = kwargs['submission']
            if submission.group:  
                addrs.extend(Recipient.objects.get(slug='group_mail_list').gather(**{'group':submission.group}))
        return addrs

    def gather_rfc_editor_if_doc_in_queue(self, **kwargs):
        addrs=[]
        if 'doc' in kwargs:
            doc = kwargs['doc']
            if doc.get_state_slug("draft-rfceditor") is not None:
                addrs.extend(Recipient.objects.get(slug='rfc_editor').gather(**{}))
        return addrs

    def gather_doc_discussing_ads(self, **kwargs):
        addrs=[]
        if 'doc' in kwargs:
            doc = kwargs['doc']
            active_ballot = doc.active_ballot()
            if active_ballot:
                for balloter, pos in active_ballot.active_balloter_positions().items():
                    if pos and pos.pos_id == "discuss":
                        addrs.append(balloter.role_email("ad").address)
        return addrs

    def gather_ipr_updatedipr_contacts(self, **kwargs):
        addrs=[]
        if 'ipr' in kwargs:
            ipr = kwargs['ipr']
            for rel in ipr.updates:
                if rel.target.submitter_email:
                    addrs.append(rel.target.submitter_email)
                elif hasattr(rel.target,'ietfer_email') and rel.target.ietfer_email:
                    addrs.append(rel.target.ietfer_email)
        return addrs
                
    def gather_ipr_updatedipr_holders(self, **kwargs):
        addrs=[]
        if 'ipr' in kwargs:
            ipr = kwargs['ipr']
            for disc in ipr.recursively_updates():
                if hasattr(ipr,'holder_contact_email') and ipr.holder_contact_email:
                    addrs.append(ipr.holder_contact_email)
        return addrs

    def gather_doc_ipr_group_or_ad(self, **kwargs):
        """A document's group email list if the document is a group document, 
           otherwise, the document's AD if the document is active, otherwise 
           nobody (in the past, the default was the IETF chair)"""
        addrs=[]
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.acronym == 'none':
                if doc.ad and doc.get_state_slug('draft')=='active':
                    addrs.extend(Recipient.objects.get(slug='doc_ad').gather(**kwargs))
                else:
                    pass
            else:
                addrs.extend(Recipient.objects.get(slug='doc_group_mail_list').gather(**kwargs)) 
        return addrs

    def gather_liaison_manager(self, **kwargs):
        addrs=[]
        if 'group' in kwargs:
            group=kwargs['group']
            addrs.extend(group.role_set.filter(name='liaiman').values_list('email__address',flat=True))
        return addrs

    def gather_session_requester(self, **kwargs):
        addrs=[]
        if 'session' in kwargs:
            session = kwargs['session']
            from ietf.meeting.models import SchedulingEvent
            first_event = SchedulingEvent.objects.filter(session=session).select_related('by').order_by('time', 'id').first()
            if first_event and first_event.status_id in ['appw', 'schedw']:
                addrs.append(first_event.by.role_email('chair').address)
        return addrs

    def gather_review_team_ads(self, **kwargs):
        addrs=[]
        if 'review_req' in kwargs:
            review_req = kwargs['review_req']
            if review_req.team.parent:
                for role in review_req.team.parent.role_set.filter(name='ad'):
                    addrs.append(role.email.address)
        return addrs

    def gather_yang_doctors_secretaries(self, **kwargs):
        return self.gather_group_secretaries(group=Group.objects.get(acronym='yangdoctors'))

    def gather_bofreq_editors(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            bofreq = kwargs['doc']
            editors = bofreq_editors(bofreq)
            addrs.extend([editor.email_address() for editor in editors])
        return addrs

    def gather_bofreq_responsible(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc = kwargs['doc']
            if doc.type_id=='bofreq':
                responsible = bofreq_responsible(doc)
                if responsible:
                    addrs.extend([leader.email_address() for leader in responsible])
                else:
                    addrs.extend(Recipient.objects.get(slug='iab').gather(**{}))
                    addrs.extend(Recipient.objects.get(slug='iesg').gather(**{}))
        return addrs

    def gather_bofreq_previous_responsible(self, **kwargs):
        addrs = []
        previous_responsible = None
        if previous_responsible in kwargs:
            previous_responsible = kwargs['previous_responsible']
        if previous_responsible:
            addrs = [p.email_address() for p in previous_responsible]
        else:
            addrs.extend(Recipient.objects.get(slug='iab').gather(**{}))
            addrs.extend(Recipient.objects.get(slug='iesg').gather(**{}))
        return addrs

