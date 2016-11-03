# Copyright The IETF Trust 2015, All Rights Reserved

from django.db import models
from django.template import Template, Context

from email.utils import parseaddr

from ietf.group.models import Role

def clean_duplicates(addrlist):
    retval = set()
    for a in addrlist:
        (name,addr) = parseaddr(a)
        if (name,addr)==('',''):
            retval.add(a)
        elif name:
            retval.add('"%s" <%s>'%(name,addr))
        else:
            retval.add(addr)
    return list(retval) 

class MailTrigger(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    desc = models.TextField(blank=True)
    to   = models.ManyToManyField('Recipient', null=True, blank=True, related_name='used_in_to')
    cc   = models.ManyToManyField('Recipient', null=True, blank=True, related_name='used_in_cc')

    class Meta:
        ordering = ["slug"]

    def __unicode__(self):
        return self.slug

class Recipient(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    desc = models.TextField(blank=True)
    template = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["slug"]

    def __unicode__(self):
        return self.slug

    def gather(self, **kwargs):
        retval = []
        if hasattr(self,'gather_%s'%self.slug):
            retval.extend(eval('self.gather_%s(**kwargs)'%self.slug))
        if self.template:
            rendering = Template('{%% autoescape off %%}%s{%% endautoescape %%}'%self.template).render(Context(kwargs))
            if rendering:
                retval.extend([x.strip() for x in rendering.split(',')])

        return clean_duplicates(retval)

    def gather_doc_group_chairs(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.type.slug in ['wg','rg']:
                addrs.append('%s-chairs@ietf.org'%doc.group.acronym)
        return addrs

    def gather_doc_group_delegates(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.type.slug in ['wg','rg']:
                addrs.extend(doc.group.role_set.filter(name='delegate').values_list('email__address',flat=True))
        return addrs

    def gather_doc_group_mail_list(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group.type.slug in ['wg','rg']:
                if doc.group.list_email:
                    addrs.append(doc.group.list_email)
        return addrs

    def gather_doc_affecteddoc_authors(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(['conflrev','tohist','tois','tops']):
                addrs.extend(Recipient.objects.get(slug='doc_authors').gather(**{'doc':reldoc.document}))
        return addrs

    def gather_doc_affecteddoc_group_chairs(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(['conflrev','tohist','tois','tops']):
                addrs.extend(Recipient.objects.get(slug='doc_group_chairs').gather(**{'doc':reldoc.document}))
        return addrs

    def gather_doc_affecteddoc_notify(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(['conflrev','tohist','tois','tops']):
                addrs.extend(Recipient.objects.get(slug='doc_notify').gather(**{'doc':reldoc.document}))
        return addrs

    def gather_conflict_review_stream_manager(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(['conflrev']):
                addrs.extend(Recipient.objects.get(slug='doc_stream_manager').gather(**{'doc':reldoc.document}))
        return addrs

    def gather_conflict_review_steering_group(self,**kwargs):
        addrs = []
        if 'doc' in kwargs:
            for reldoc in kwargs['doc'].related_that_doc(['conflrev']):
                if reldoc.document.stream_id=='irtf':
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
        manager_map = dict(ise  = '<rfc-ise@rfc-editor.org>',
                           irtf = '<irtf-chair@irtf.org>',
                           ietf = '<iesg@ietf.org>',
                           iab  = '<iab-chair@iab.org>')
        if 'streams' in kwargs:
            for stream in kwargs['streams']:
                if stream in manager_map:
                    addrs.append(manager_map[stream])
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
        return addrs

    def gather_group_secretaries(self, **kwargs):
        addrs = []
        if 'group' in kwargs:
            group = kwargs['group']
            if not group.acronym=='none':
                addrs.extend(group.role_set.filter(name='secr').values_list('email__address',flat=True))
        return addrs

    def gather_doc_group_responsible_directors(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            group = kwargs['doc'].group
            if group and not group.acronym=='none':
                addrs.extend(Recipient.objects.get(slug='group_responsible_directors').gather(**{'group':group}))
        return addrs

    def gather_submission_authors(self, **kwargs):
        addrs = []
        if 'submission' in kwargs:
            submission = kwargs['submission']
            addrs.extend(["%s <%s>" % (author["name"], author["email"]) for author in submission.authors_parsed() if author["email"]]) 
        return addrs

    def gather_submission_group_chairs(self, **kwargs):
        addrs = []
        if 'submission' in kwargs: 
            submission = kwargs['submission']
            if submission.group: 
                addrs.extend(Recipient.objects.get(slug='group_chairs').gather(**{'group':submission.group}))
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
                old_authors = [i.author.formatted_email() for i in doc.documentauthor_set.all() if not i.author.invalid_address()]
                new_authors = [u'"%s" <%s>' % (author["name"], author["email"]) for author in submission.authors_parsed() if author["email"]]
                addrs.extend(old_authors)
                if doc.group and set(old_authors)!=set(new_authors):
                    if doc.group.type_id in ['wg','rg','ag']:
                        addrs.extend(Recipient.objects.get(slug='group_chairs').gather(**{'group':doc.group}))
                    elif doc.group.type_id in ['area']:
                        addrs.extend(Recipient.objects.get(slug='group_responsible_directors').gather(**{'group':doc.group}))
                    else:
                        pass
                    if doc.stream_id and doc.stream_id not in ['ietf']:
                        addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':[doc.stream_id]}))
            else:
                addrs.extend([u"%s <%s>" % (author["name"], author["email"]) for author in submission.authors_parsed() if author["email"]])
                if submission.submitter_parsed()["email"]: 
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
                for ad, pos in active_ballot.active_ad_positions().iteritems():
                    if pos and pos.pos_id == "discuss":
                        addrs.append(ad.role_email("ad").address)
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
           the IETF chair"""
        addrs=[]
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group and doc.group.acronym == 'none':
                if doc.ad and doc.get_state_slug('draft')=='active':
                    addrs.extend(Recipient.objects.get(slug='doc_ad').gather(**kwargs))
                else:
                    addrs.extend(Role.objects.filter(group__acronym='gen',name='ad').values_list('email__address',flat=True))
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
            addrs.append(session.requested_by.role_email('chair').address)
        return addrs
