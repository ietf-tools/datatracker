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

def make_recipients():

    Recipient.objects.all().delete()
    Recipient.objects.create(slug='iesg',
                              desc='The IESG',
                              template='The IESG <iesg@ietf.org>')
    Recipient.objects.create(slug='ietf_announce',
                              desc='The IETF Announce list',
                              template='IETF-Announce <ietf-announce@ietf.org>')
    Recipient.objects.create(slug='rfc_editor',
                              desc='The RFC Editor',
                              template='<rfc-editor@rfc-editor.org>')
    Recipient.objects.create(slug='iesg_secretary',
                              desc='The Secretariat',
                              template='<iesg-secretary@ietf.org>')
    Recipient.objects.create(slug='doc_authors',
                              desc="The document's authors",
                              template='{{doc.name}}@ietf.org')
    Recipient.objects.create(slug='doc_notify',
                              desc="The addresses in the document's notify field",
                              template='{{doc.notify}}')
    Recipient.objects.create(slug='doc_group_chairs',
                              desc="The document's group chairs (if the document is assigned to a working or research group)",
                              template=None)
    Recipient.objects.create(slug='doc_affecteddoc_authors',
                              desc="The authors of the subject documents of a conflict-review or status-change",
                              template=None)
    Recipient.objects.create(slug='doc_affecteddoc_group_chairs',
                              desc="The chairs of groups of the subject documents of a conflict-review or status-change",
                              template=None)
    Recipient.objects.create(slug='doc_shepherd',
                              desc="The document's shepherd",
                              template='{% if doc.shepherd %}{{doc.shepherd.address}}{% endif %}' )
    Recipient.objects.create(slug='doc_ad',
                              desc="The document's responsible Area Director",
                              template='{% if doc.ad %}{{doc.ad.email_address}}{% endif %}' )
    Recipient.objects.create(slug='doc_group_mail_list',
                              desc="The list address of the document's group",
                              template=None )
    Recipient.objects.create(slug='conflict_review_stream_owner',
                              desc="The stream owner of a document being reviewed for IETF stream conflicts",
                              template='{% ifequal doc.type_id "conflrev" %}{% ifequal doc.stream_id "ise" %}<rfc-ise@rfc-editor.org>{% endifequal %}{% ifequal doc.stream_id "irtf" %}<irtf-chair@irtf.org>{% endifequal %}{% endifequal %}')
    Recipient.objects.create(slug='iana_approve',
                              desc="IANA's draft approval address",
                              template='IANA <drafts-approval@icann.org>')

def make_mailtokens():
    
    MailToken.objects.all().delete()

    m = MailToken.objects.create(slug='ballot_saved',
                                 desc='Recipients when a new ballot position (with discusses, other blocking positions, or comments) is saved')
    m.recipients = Recipient.objects.filter(slug__in=['iesg'])

    m = MailToken.objects.create(slug='ballot_saved_cc',
                                 desc='Copied when a new ballot position (with discusses, other blocking positions, or comments) is saved')
    m.recipients = Recipient.objects.filter(slug__in=['doc_authors',
                                                        'doc_group_chairs',
                                                        'doc_shepherd',
                                                        'doc_affecteddoc_authors',
                                                        'doc_affecteddoc_group_chairs',
                                                        'conflict_review_stream_owner',
                                                        ])

    m = MailToken.objects.create(slug='ballot_deferred',
                                 desc='Recipients when a ballot is deferred to or undeferred from a future telechat')
    m.recipients = Recipient.objects.filter(slug__in=['iesg',
                                                        'iesg_secretary',
                                                        'doc_group_chairs',
                                                        'doc_notify',
                                                        'doc_authors',
                                                        'doc_shepherd',
                                                        'doc_affecteddoc_authors',
                                                        'doc_affecteddoc_group_chairs',
                                                        'conflict_review_stream_owner',
                                                        ])

    m = MailToken.objects.create(slug='ballot_approved_ietf_stream',
                                 desc='Recipients when an IETF stream document ballot is approved')
    m.recipients = Recipient.objects.filter(slug__in=['ietf_announce'])

    m = MailToken.objects.create(slug='ballot_approved_ietf_stream_cc',
                                 desc='Copied when an IETF stream document ballot is approved')
    m.recipients = Recipient.objects.filter(slug__in=['iesg',
                                                        'doc_notify',
                                                        'doc_ad',
                                                        'doc_authors',
                                                        'doc_shepherd',
                                                        'doc_group_mail_list',
                                                        'doc_group_chairs',
                                                        'rfc_editor',
                                                        ])
 
    m = MailToken.objects.create(slug='ballot_approved_ietf_stream_iana',
                                 desc='Recipients for IANA message when an IETF stream document ballot is approved')
    m.recipients = Recipient.objects.filter(slug__in=['iana_approve'])


