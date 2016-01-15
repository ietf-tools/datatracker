# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def remove_extension(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    for template in DBTemplate.objects.filter(path__endswith="requirements.txt"):
        template.path = template.path[:-4]
        template.save()

def restore_extension(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    for template in DBTemplate.objects.filter(path__endswith="requirements"):
        template.path = template.path+".txt"
        template.save()

def default_rst(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    default_req = DBTemplate.objects.get(path__startswith='/nomcom/defaults/position/requirements')
    default_req.type_id = 'rst'
    default_req.save()

def default_plain(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    default_req = DBTemplate.objects.get(path__startswith='/nomcom/defaults/position/requirements')
    default_req.type_id = 'plain'
    default_req.save()

def rst_2015(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    DBTemplate.objects.filter(path__startswith='/nomcom/nomcom2015/').filter(path__contains='position/requirements').exclude(path__contains='/27/').update(type_id='rst')

def plain_2015(apps, schema_editor):
    DBTemplate = apps.get_model('dbtemplate','DBTemplate')
    DBTemplate.objects.filter(path__startswith='/nomcom/nomcom2015/').filter(path__contains='position/requirements').update(type_id='plain')

class Migration(migrations.Migration):

    dependencies = [
        ('nomcom', '0008_auto_20151209_1423'),
        ('dbtemplate', '0002_auto_20141222_1749'),
    ]

    operations = [
        migrations.RunPython(remove_extension,restore_extension),
        migrations.RunPython(default_rst,default_plain),
        migrations.RunPython(rst_2015,plain_2015),
    ]
