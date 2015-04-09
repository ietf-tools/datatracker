# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def forward_materials_state(apps, schema_editor):
    StateType = apps.get_model('doc', 'StateType')
    State     = apps.get_model('doc', 'State')

    StateType.objects.create(slug='reuse_policy',label='Policy')

    single = State.objects.create(type_id='reuse_policy',slug='single',name='Single Meeting')
    multiple = State.objects.create(type_id='reuse_policy',slug='multiple',name='Multiple Meetings')

    Document = apps.get_model('doc', 'Document')
    for doc in Document.objects.filter(type='slides'):
        if doc.group.type.slug=='team':
            doc.states.add(multiple)
        else:
            doc.states.add(single) 

    # Expected to be a no-op on current database, but just for completeness
    for doc in Document.objects.filter(type='slides'):
        doc.states.filter(type='slides',slug='sessonly').update(slug='active')

    State.objects.filter(type_id='slides',slug='sessonly').delete()
    

def reverse_materials_state(apps, schema_editor):
    Document = apps.get_model('doc', 'Document')
    for doc in Document.objects.filter(type='slides'):
        doc.states.filter(type='update_policy').delete()

    StateType = apps.get_model('doc', 'StateType')
    StateType.objects.filter(slug='update_policy').delete()

    State     = apps.get_model('doc', 'State')
    State.objects.create(type='slides',slug='sessonly',name='Session Only')


class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0002_auto_20141222_1749'),
        ('group', '0003_auto_20150304_0743'),
    ]

    operations = [
        migrations.RunPython(forward_materials_state,reverse_materials_state),
    ]
