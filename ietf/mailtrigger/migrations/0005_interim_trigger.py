# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


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

        m, _ = MailTrigger.objects.get_or_create(slug=slug, desc=desc)
        m.to = Recipient.objects.filter(slug__in=to_slugs)
        m.cc = Recipient.objects.filter(slug__in=cc_slugs)

    mt_factory(slug='interim_approved',
               desc="Recipients when an interim meeting is approved "
                    "and an announcement needs to be sent",
               to_slugs=['iesg_secretary'],
               cc_slugs=[]
              )

def forward(apps, schema_editor):
    make_mailtriggers(apps)

def reverse(apps, schema_editor):
    MailTrigger=apps.get_model('mailtrigger','MailTrigger')
    MailTrigger.objects.filter(slug='interim_approved').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('mailtrigger', '0004_auto_20160516_1659'),
    ]

    operations = [migrations.RunPython(forward, reverse)]
