# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import collections

from django.core.management.base import BaseCommand
from django.db.models.fields import BooleanField

import debug                            # pyflakes:ignore

from ietf.group.models import GroupFeatures

class Command(BaseCommand):
    help = "Show group features"

    def handle(self, *filenames, **options):
        self.verbosity = options['verbosity']
        hasfeature = {}
        hasrole = {}
        # By property:
        for field in GroupFeatures.objects.first()._meta.fields:
            if isinstance(field, BooleanField):
                hasfeature[field.name] = []
            else:
                hasrole[field.name] = collections.defaultdict(list)
        for f in GroupFeatures.objects.all():
            for field in f._meta.fields:
                value = getattr(f, field.name)
                if value == True:
                    hasfeature[field.name].append(str(f.type.slug))
                elif isinstance(value, list):
                    for role in value:
                        hasrole[field.name][role].append(str(f.type.slug))
        for k,v in sorted(hasfeature.items()):
            print("%-24s: %s" % (k, sorted(v)))
        print("")
        for k,roles in sorted(hasrole.items()):
            if roles and 'roles' in k:
                print("%s:" % k)
                for r, v in sorted(roles.items()):
                    print("%16s%-8s: %s" % ('', r, sorted(v)))

