# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.db import migrations

def forward(apps, schema_editor):
    ReviewTeamSettings = apps.get_model('review', 'ReviewTeamSettings')
    MailTrigger = apps.get_model('mailtrigger', 'Mailtrigger')
    Group = apps.get_model('group', 'Group')
    GroupFeatures = apps.get_model('group', 'GroupFeatures')

    template = MailTrigger.objects.get(slug='review_completed')
    template.desc = 'Default template for recipients when an review is completed - ' \
                    'customised mail triggers are used/created per team and review type.'
    template.save()
    
    for group in Group.objects.all().only('pk', 'type', 'acronym'):
        if not GroupFeatures.objects.get(type=group.type).has_reviews:
            continue
        try:
            review_team = ReviewTeamSettings.objects.get(group=group.pk)
        except ReviewTeamSettings.DoesNotExist:
            continue
        team_acronym = group.acronym.lower()
        for review_type in review_team.review_types.all():
            slug = 'review_completed_{}_{}'.format(team_acronym, review_type.slug)
            desc = 'Recipients when a {} {} review is completed'.format(team_acronym, review_type)
            if MailTrigger.objects.filter(slug=slug):
                # Never overwrite existing triggers
                continue
            mailtrigger = MailTrigger.objects.create(slug=slug, desc=desc)
            mailtrigger.to.set(template.to.all())
            mailtrigger.cc.set(template.cc.all())
    

def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mailtrigger', '0008_lengthen_mailtrigger_slug'),
        ('review', '0014_document_primary_key_cleanup'),
        ('group', '0019_rename_field_document2'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
