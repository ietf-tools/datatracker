# Copyright The IETF Trust 2015, All Rights Reserved

from django.db import models
from django.template import Template, Context

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
            rendering = Template(self.template).render(Context(kwargs))
            if rendering:
                retval.extend(rendering.split(','))

        return retval

    def gather_doc_group_chairs(self, **kwargs):
        addrs = []
        if 'doc' in kwargs:
            doc=kwargs['doc']
            if doc.group.type.slug in ['wg','rg']:
                addrs.append('%s-chairs@ietf.org'%doc.group.acronym)
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

