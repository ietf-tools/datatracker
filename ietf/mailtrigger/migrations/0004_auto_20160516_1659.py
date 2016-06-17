# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def make_recipients(apps):
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    rc = Recipient.objects.create

    rc(slug='group_secretaries',
       desc="The group's secretaries",
       template=None)


def make_mailtriggers(apps):
    Recipient = apps.get_model('mailtrigger','Recipient')
    MailTrigger = apps.get_model('mailtrigger','MailTrigger')

    def mt_factory(slug,desc,to_slugs,cc_slugs=[]):

        # Try to protect ourselves from typos
        all_slugs = to_slugs[:]
        all_slugs.extend(cc_slugs)
        for recipient_slug in all_slugs:
            try:
                Recipient.objects.get(slug=recipient_slug)
            except Recipient.DoesNotExist:
                print "****Some rule tried to use",recipient_slug
                raise

        m = MailTrigger.objects.create(slug=slug, desc=desc)
        m.to = Recipient.objects.filter(slug__in=to_slugs)
        m.cc = Recipient.objects.filter(slug__in=cc_slugs)

    mt_factory(slug='session_minutes_reminder',
               desc="Recipients when a group is sent a reminder "
                    "to submit minutes for a session",
               to_slugs=['group_chairs','group_secretaries'],
               cc_slugs=['group_responsible_directors']
              )

def forward(apps, schema_editor):
    make_recipients(apps)
    make_mailtriggers(apps)


class Migration(migrations.Migration):
    dependencies = [
        ('mailtrigger', '0003_merge_request_trigger'),
    ]

    operations = [migrations.RunPython(forward)]
