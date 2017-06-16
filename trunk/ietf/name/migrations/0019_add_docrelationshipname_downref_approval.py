# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.db import migrations

def addDocRelationshipName(apps,schema_editor):
    DocRelationshipName = apps.get_model('name','DocRelationshipName')
    DocRelationshipName.objects.create(
        slug = 'downref-approval',
        name = 'approves downref to',
        revname = 'was approved for downref by',
        desc = 'Approval for downref')

def removeDocRelationshipName(apps,schema_editor):
    DocRelationshipName = apps.get_model('name','DocRelationshipName')
    DocRelationshipName.objects.filter(slug='downref-approval').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0018_iab_programs'),
    ]

    operations = [
        migrations.RunPython(addDocRelationshipName,removeDocRelationshipName)
    ]
