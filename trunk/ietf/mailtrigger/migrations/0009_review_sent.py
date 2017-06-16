# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):

    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    Recipient=apps.get_model('mailtrigger','Recipient')

    Recipient.objects.create(
        slug='review_team_mail_list',
        desc="The review team's email list",
        template="{{review_req.team.list_email}}"
    )

    Recipient.objects.create(
        slug='review_doc_group_mail_list',
        desc="The working group list for the document being reviewed",
        template="{{review_req.doc.group.list_email}}"
    )

    Recipient.objects.create(
        slug='review_doc_all_parties',
        desc="The .all alias for the document being reviewed",
        template="{% if review_req.doc.type_id == 'draft' %}<{{review_req.doc.name}}.all@ietf.org>{% endif %}"
    )

    Recipient.objects.create(
        slug='ietf_general',
        desc="The IETF general discussion list",
        template="ietf@ietf.org"
    )
    annc = MailTrigger.objects.create(
        slug='review_completed',
        desc='Recipients when an review is completed',
    )
    annc.to = Recipient.objects.filter(slug__in=['review_team_mail_list',])
    annc.cc = Recipient.objects.filter(slug__in=['review_doc_all_parties','review_doc_group_mail_list','ietf_general'])

def reverse(apps, schema_editor):

    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    Recipient=apps.get_model('mailtrigger','Recipient')

    MailTrigger.objects.filter(slug='review_completed').delete()
    Recipient.objects.filter(slug__in=['review_team_mail_list','review_doc_group_mail_list','review_doc_all_parties','ietf_general']).delete()
    
class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0008_review_summary_triggers'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
