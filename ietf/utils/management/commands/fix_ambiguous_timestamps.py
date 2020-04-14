# Copyright The IETF Trust 2019-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import pytz
import sys

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models

import debug                            # pyflakes:ignore

from ietf.person.models import Person
from ietf.doc.models import DocEvent

# ----------------------------------------------------------------------

by = Person.objects.get(name='(System)')
tz = pytz.timezone(settings.TIME_ZONE)

class Command(BaseCommand):

    def note(self, msg):
        if not self.quiet:
            sys.stderr.write('%s\n' % msg)

    def fixup(self, model, field, start, stop):
        lookup = {
            '%s__gt'%field: start,
            '%s__lt'%field: stop,
            }
        app_label = model._meta.app_label
        self.note("%s.%s.%s:" % (app_label, model.__name__, field))
        for d in model.objects.filter(**lookup).order_by('-%s'%field):
            orig = getattr(d, field)
            try:
                tz.localize(orig, is_dst=None)
            except pytz.AmbiguousTimeError as e:
                new = orig-datetime.timedelta(minutes=60)
                setattr(d, field, new)
                desc = "  %s: changed ambiguous time:  %s --> %s" % (d.pk, orig, new)
                self.note(desc)
                if app_label == 'doc' and model.__name__ == 'Document':
                    e = DocEvent(type='added_comment', doc=d, rev=d.rev, by=by, desc=desc)
                    e.save()
                    d.save_with_history([e])
                else:
                    d.save()

    def handle(self, *app_labels, **options):
        self.verbosity = options['verbosity']
        self.quiet = self.verbosity < 1
        stop = datetime.datetime.now()
        start = stop - datetime.timedelta(days=14)

        for name, appconf in apps.app_configs.items():
            for model in appconf.get_models():
                for field in model._meta.fields:
                    if isinstance(field, models.DateTimeField):
                        self.fixup(model, field.name, start, stop)
                        
