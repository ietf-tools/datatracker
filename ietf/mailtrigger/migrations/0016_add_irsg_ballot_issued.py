# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations


def replace_mailtrigger(MailTrigger, old_slug, new_slug):
    """Replace a MailTrigger with an equivalent using a different slug"""
    # Per 0013_add_irsg_ballot_saved.py, can't just modify the existing because that
    # will lose the many-to-many relations.
    orig_mailtrigger = MailTrigger.objects.get(slug=old_slug)
    new_mailtrigger = MailTrigger.objects.create(slug=new_slug)
    new_mailtrigger.to.set(orig_mailtrigger.to.all())
    new_mailtrigger.cc.set(orig_mailtrigger.cc.all())
    new_mailtrigger.desc = orig_mailtrigger.desc
    new_mailtrigger.save()
    orig_mailtrigger.delete()  # get rid of the obsolete MailTrigger


def forward(apps, schema_editor):
    """Forward migration: create irsg_ballot_issued and rename ballot_issued to iesg_ballot_issued"""
    # Load historical models
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    Recipient = apps.get_model('mailtrigger', 'Recipient')

    # Create the new MailTrigger
    irsg_ballot_issued = MailTrigger.objects.create(
        slug='irsg_ballot_issued',
        desc='Recipients when a new IRSG ballot is issued',
    )
    irsg_ballot_issued.to.set(Recipient.objects.filter(slug='irsg'))
    irsg_ballot_issued.cc.set(Recipient.objects.filter(slug__in=[
        'doc_stream_manager', 'doc_affecteddoc_authors', 'doc_affecteddoc_group_chairs',
        'doc_affecteddoc_notify', 'doc_authors', 'doc_group_chairs', 'doc_group_mail_list',
        'doc_notify', 'doc_shepherd'
    ]))

    # Replace existing 'ballot_issued' object with an 'iesg_ballot_issued'
    replace_mailtrigger(MailTrigger, 'ballot_issued', 'iesg_ballot_issued')


def reverse(apps, shema_editor):
    """Reverse migration: rename iesg_ballot_issued to ballot_issued and remove irsg_ballot_issued"""
    MailTrigger = apps.get_model('mailtrigger', 'MailTrigger')
    MailTrigger.objects.filter(slug='irsg_ballot_issued').delete()
    replace_mailtrigger(MailTrigger, 'iesg_ballot_issued', 'ballot_issued')


class Migration(migrations.Migration):
    dependencies = [
        ('mailtrigger', '0015_add_ad_approved_status_change'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
