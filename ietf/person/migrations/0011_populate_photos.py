# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from hashids import Hashids

from django.db import migrations
from django.conf import settings
from django.utils.text import slugify

from ietf.person.name import name_parts

def photo_name(person,thumb=False):
    hasher = Hashids(salt='Person photo name salt',min_length=5)
    _, first, _, last, _ = name_parts(person.ascii)
    return '%s-%s%s' % ( slugify("%s %s" % (first, last)), hasher.encode(person.id), '-th' if thumb else '' )

def forward(apps,schema_editor):
    Person = apps.get_model('person','Person')
    images_dir = settings.PHOTOS_DIR
    image_filenames = []
    for (dirpath, dirnames, filenames) in os.walk(images_dir):
        image_filenames.extend(filenames)
        break # Only interested in the files in the top directory
    image_basenames = [os.path.splitext(name)[0] for name in image_filenames]
    for person in Person.objects.all():
        if not person.name.strip():
            continue
        dirty = False
        if photo_name(person,thumb=False) in image_basenames:
            person.photo = os.path.join(settings.PHOTOS_DIRNAME, image_filenames[image_basenames.index(photo_name(person,thumb=False))])
            dirty = True
        if photo_name(person,thumb=True) in image_basenames:
            person.photo_thumb = os.path.join(settings.PHOTOS_DIRNAME, image_filenames[image_basenames.index(photo_name(person,thumb=True))])
            dirty = True
        if dirty:
            person.save()

def reverse(apps, schema_editor):
    Person = apps.get_model('person','Person')
    for person in Person.objects.filter(photo__gt=''):
        person.photo = None
        person.save()
    for person in Person.objects.filter(photo_thumb__gt=''):
        person.photo_thumb = None
        person.save()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0010_add_photo_fields'),
    ]

    operations = [
        migrations.RunPython(forward,reverse)
    ]
