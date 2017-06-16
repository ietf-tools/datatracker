# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def set_state(doc, state):
    already_set = doc.states.filter(type=state.type)
    others = [s for s in already_set if s != state]
    if others:
        doc.states.remove(*others)
    if state not in already_set:
        doc.states.add(state)
    doc.state_cache = None 

def forward_archive_slides(apps,schema_editor):
    Document = apps.get_model('doc', 'Document')
    State = apps.get_model('doc','State')
    archived = State.objects.get(type__slug='slides',slug='archived')
    for doc in Document.objects.filter(name__startswith='slides-92-',states__type__slug='slides',states__slug='active'): 
        set_state(doc,archived)

def reverse_archive_slides(apps,schema_editor):
    Document = apps.get_model('doc', 'Document')
    State = apps.get_model('doc','State')
    active = State.objects.get(type__slug='slides',slug='active')
    for doc in Document.objects.filter(name__startswith='slides-92-',states__type__slug='slides',states__slug='archived'): 
        set_state(doc,active)

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0003_auto_20150326_0728'),
    ]

    operations = [
        migrations.RunPython(forward_archive_slides,reverse_archive_slides),
    ]
