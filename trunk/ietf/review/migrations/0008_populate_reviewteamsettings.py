# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward(apps, schema_editor):
    ReviewTeamSettings = apps.get_model('review','ReviewTeamSettings')
    ResultUsedInReviewTeam = apps.get_model('review','ResultUsedInReviewTeam')
    TypeUsedInReviewTeam = apps.get_model('review','TypeUsedInReviewTeam')

    for group_id in ResultUsedInReviewTeam.objects.values_list('team',flat=True).distinct():
        rts = ReviewTeamSettings.objects.create(group_id=group_id)
        rts.review_types = TypeUsedInReviewTeam.objects.filter(team_id=group_id).values_list('type',flat=True).distinct()
        rts.review_results = ResultUsedInReviewTeam.objects.filter(team_id=group_id).values_list('result',flat=True).distinct()


def reverse(apps, schema_editor):
    ReviewTeamSettings = apps.get_model('review','ReviewTeamSettings')
    ReviewTeamSettings.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('review', '0007_reviewteamsettings'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]
