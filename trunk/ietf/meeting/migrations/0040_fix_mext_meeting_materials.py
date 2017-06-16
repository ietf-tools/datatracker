# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.utils import IntegrityError

def forward(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    Document = apps.get_model('doc', 'Document')
    SessionPresentation = apps.get_model('meeting', 'SessionPresentation')
    #
    mext = Group.objects.get(acronym='mext')
    plist = SessionPresentation.objects.filter(session__group=mext)
    for p in plist:
        print(p.document_id)
        name = p.document_id.replace('-dmm', '-mext')
        try:
            doc = p.document
            Document.objects.create(
                time=doc.time,
                type=doc.type,
                title=doc.title.replace('DMM', 'MEXT'),
                group=mext,
                rev=doc.rev,
                order=doc.order,
                external_url=doc.external_url.replace('dmm', 'mext'),
                name=name,
            )
            doc.delete()
        except Document.DoesNotExist as e:
            print("%s: %s" % (p.document_id, e))
        except IntegrityError as e:
            print("%s: %s" % (p.document_id, e))
        if not SessionPresentation.objects.filter(document_id=name).exists():
            p.document_id = name
            p.save()

def backward(apps, schema_editor):
    Group = apps.get_model('group', 'Group')
    Document = apps.get_model('doc', 'Document')
    SessionPresentation = apps.get_model('meeting', 'SessionPresentation')
    mext = Group.objects.get(acronym='mext')
    dmm  = Group.objects.get(acronym='dmm')
    plist = SessionPresentation.objects.filter(session__group=mext)
    for p in plist:
        print(p.document_id)
        name = p.document_id.replace('-mext', '-dmm')
        try:
            doc = p.document
            Document.objects.create(
                time=doc.time,
                type=doc.type,
                title=doc.title.replace('MEXT', 'DMM'),
                group=dmm,
                rev=doc.rev,
                order=doc.order,
                external_url=doc.external_url.replace('mext', 'dmm'),
                name=name,
            )
            doc.delete()
        except Document.DoesNotExist as e:
            print("%s: %s" % (p.document_id, e))
        except IntegrityError as e:
            print("%s: %s" % (p.document_id, e))
        if not SessionPresentation.objects.filter(document_id=name).exists():
            p.document_id = name
            p.save()

class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0039_auto_20161017_1053'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]
