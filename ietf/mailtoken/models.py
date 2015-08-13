# Copyright The IETF Trust 2015, All Rights Reserved

from django.db import models
from django.template import Template, Context

from ietf.group.models import Role

class MailToken(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    desc = models.TextField(blank=True)
    recipients = models.ManyToManyField('Recipient', null=True, blank=True)

    class Meta:
        ordering = ["slug"]

    def __unicode__(self):
        return self.slug

class Recipient(models.Model):
    slug = models.CharField(max_length=32, primary_key=True)
    desc = models.TextField(blank=True)
    template = models.CharField(max_length=512, null=True, blank=True)

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

        retval = list(set(retval))
        return retval

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
                addrs.extend(Role.objects.filter(group=doc.group,name='delegate').values_list('email__address',flat=True))
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
                if reldoc.document.stream_id=='irsg':
                    addrs.append('"Internet Research Steering Group" <irsg@ietf.org>')
        return addrs

    def gather_group_steering_group(self,**kwargs):
        addrs = []
        sg_map = dict( wg='"The IESG" <iesg@ietf.org>', rg='"Internet Research Steering Group" <irsg@ietf.org>' )
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

    def gather_group_responsible_directors(self, **kwargs):
        addrs = []
        if 'group' in kwargs:
            group = kwargs['group']
            addrs.extend(Role.objects.filter(group=group,name='ad').values_list('email__address',flat=True))
            if group.type_id=='rg':
                addrs.extend(Recipient.objects.get(slug='stream_managers').gather(**{'streams':['irtf']}))
        return addrs
