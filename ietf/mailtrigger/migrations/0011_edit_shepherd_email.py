# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def make_mailtriggers(apps):

    Recipient = apps.get_model('mailtrigger', 'Recipient')
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')

    def mt_factory(slug, desc, to_slugs, cc_slugs=[]):
        # Try to protect ourselves from typos
        all_slugs = to_slugs[:]
        all_slugs.extend(cc_slugs)
        m = MailTrigger.objects.create(slug=slug, desc=desc)
        m.to = Recipient.objects.filter(slug__in=to_slugs)

    mt_factory(
        slug='email_edit_shepherd',
        desc="Recipients when a sheperd has changed",
        to_slugs=[
            'doc_group_chairs',
            'doc_notify',
            'doc_group_delegates',
            'doc_shepherd',
        ], )


def forward(apps, schema_editor):
    #    make_recipients(apps)
    make_mailtriggers(apps)


def reverse(apps, schema_editor):
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')

    MailTrigger.objects.filter(slug__in=['email_edit_shepherd']).delete()
    # recipients are not deleted because they are all created
    # from a previous migration


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0010_auto_20161207_1104'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
