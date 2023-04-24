# Copyright The IETF Trust 2021 All Rights Reserved

from django.db import migrations

def forward(apps, schema_editor):
    GroupTypeName = apps.get_model('name','GroupTypeName')
    Group = apps.get_model('group', 'Group')
    GroupHistory = apps.get_model('group', 'GroupHistory')
    GroupFeatures = apps.get_model('group', 'GroupFeatures')

    a = GroupTypeName.objects.get(pk='admin')
    a.pk='adm'
    a.order=1
    a.save()
    f = GroupFeatures.objects.get(pk='admin')
    f.pk='adm'
    f.save()

    Group.objects.filter(type_id='admin').update(type_id='adm')
    GroupHistory.objects.filter(type_id='admin').update(type_id='adm')

    GroupFeatures.objects.filter(pk='admin').delete()
    GroupTypeName.objects.filter(pk='admin').delete()

def reverse(apps, schema_editor):
    GroupTypeName = apps.get_model('name','GroupTypeName')
    Group = apps.get_model('group', 'Group')
    GroupHistory = apps.get_model('group','GroupHistory')
    GroupFeatures = apps.get_model('group', 'GroupFeatures')

    a = GroupTypeName.objects.get(pk='adm')
    a.pk='admin'
    a.order=0
    a.save()
    f = GroupFeatures.objects.get(pk='adm')
    f.pk='admin'
    f.save()

    Group.objects.filter(type_id='adm').update(type_id='admin')
    GroupHistory.objects.filter(type_id='adm').update(type_id='admin')

    GroupFeatures.objects.filter(type_id='adm').delete()
    GroupTypeName.objects.filter(pk='adm').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0045_iabasg'),
        ('name', '0028_iabasg'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
