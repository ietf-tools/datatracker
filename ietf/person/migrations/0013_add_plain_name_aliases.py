# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from ietf.person.name import name_parts

def plain_name(self):
    if '<>' in self.name:
        return None
    prefix, first, middle, last, suffix = name_parts(self.name)
    if not first and last:
        return None
    if first.isupper():
        first = first.capitalize()
    if last.isupper():
        last = last.capitalize()
    return u" ".join([first, last])

def add_plain_name_aliases(apps, schema_editor):
    Person = apps.get_model('person','Person')
    Alias  = apps.get_model('person','Alias')
    for person in Person.objects.all():
        name = plain_name(person)
        if name and not Alias.objects.filter(name=name):
            print("Created alias %-24s for %s" % (name, person.name))
            alias = Alias(name=name, person=person)
            alias.save()

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0012_auto_20160606_0823'),
    ]

    operations = [
        migrations.RunPython(add_plain_name_aliases),
    ]
