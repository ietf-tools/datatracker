# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def create_ad_roles(apps, schema_editor):
    RoleName = apps.get_model('name', 'RoleName')
    Group    = apps.get_model('group', 'Group')
    #
    rolename, __ = RoleName.objects.get_or_create(slug='ad')
    for group in Group.objects.exclude(ad=None):
        email = None
        if group.parent:
            ad_rolematch = group.parent.role_set.filter(person=group.ad,name=rolename).first()
            if ad_rolematch:
                email = ad_rolematch.email
        if not email:
            email = group.ad.email_set.order_by("-active","-time").first()
        try:
            group.role_set.get_or_create(name=rolename,person=group.ad,email=email)
        except Exception as e:
            import sys
            sys.stderr.write('Exeption: %s\n' % e)
            raise

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_ad_roles),
    ]
