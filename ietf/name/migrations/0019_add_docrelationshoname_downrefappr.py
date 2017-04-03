# -*- coding: utf-8 -*-
from django.db import models, migrations

def addDocRelationshipName(apps,schema_editor):
    DocRelationshipName = apps.get_model('name','DocRelationshipName')
    DocRelationshipName.objects.create(
        slug = 'downrefappr',
        name = 'approves downref to',
        revname = 'was approved for downref by',
        desc = 'Approval for downref')

def removeDocRelationshipName(apps,schema_editor):
    DocRelationshipName = apps.get_model('name','DocRelationshipName')
    DocRelationshipName.objects.filter(slug='downrefappr').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('name', '0018_iab_programs'),
    ]

    operations = [
        migrations.RunPython(addDocRelationshipName,removeDocRelationshipName)
    ]
