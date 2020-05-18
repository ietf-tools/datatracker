# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from tqdm import tqdm

import django
django.setup()

from django.apps import apps
from django.core.management.base import BaseCommand #, CommandError
from django.db import IntegrityError
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField


import debug                            # pyflakes:ignore

class Command(BaseCommand):
    help = "Check all models for referential integrity."

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete', action='store_true', default=False,
            help="Delete dangling references",
        )


    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        verbose = verbosity > 1
        if verbosity > 1:
            self.stdout.ending = None
            self.stderr.ending = None

        def check_field(field, through_table=False):
            try:
                foreign_model = field.related_model
            except Exception:
                debug.pprint('dir(field)')
                raise
            if verbosity > 1:
                self.stdout.write("  [....]  %s -> %s.%s" % (
                    field.name, foreign_model.__module__, foreign_model.__name__))
                self.stdout.flush()
            used = set(field.model.objects.values_list(field.name, flat=True))
            used.discard(None)
            exists = set(foreign_model.objects.values_list('pk', flat=True))
            if through_table:
                used = set( int(i) if isinstance(i, str) and i.isdigit() else i for i in used )
                exists = set( int(i) if isinstance(i, str) and i.isdigit() else i for i in exists )
            dangling = used - exists
            if dangling:
                debug.say('')
                debug.show('len(used)')
                debug.show('len(exists)')
                used_list = list(used)
                used_list.sort()
                debug.show('used_list[:20]')
                exists_list = list(exists)
                exists_list.sort()
                debug.show('exists_list[:20]')
                for d in dangling:
                    if d in exists:
                        debug.say("%s exists, it isn't dangling!" % d)
                        exit()
                exit()
            if verbosity > 1:
                if dangling:
                    self.stdout.write("\r  ["+self.style.ERROR("fail")+"]\n  ** Bad key values: %s\n" % sorted(list(dangling)))
                else:
                    self.stdout.write("\r  [ "+self.style.SUCCESS('ok')+" ]\n")
            else:
                if dangling:
                    self.stdout.write("\n%s.%s.%s -> %s.%s  ** Bad key values:\n   %s\n" % (model.__module__, model.__name__, field.name, foreign_model.__module__, foreign_model.__name__, sorted(list(dangling))))

            if dangling and options.get('delete'):
                if verbosity > 1:
                    self.stdout.write("Removing dangling values: %s.%s.%s\n" % (model.__module__, model.__name__, field.name, ))
                for value in tqdm(dangling):
                    kwargs = { field.name: value }
                    for obj in field.model.objects.filter(**kwargs):
                        try:
                            if through_table:
                                obj.delete()
                            else:
                                if   isinstance(field, (ForeignKey, OneToOneField)):
                                    setattr(obj, field.name, None)
                                    obj.save()
                                elif isinstance(field, (ManyToManyField, )):
                                    manager = getattr(obj, field.name)
                                    manager.remove(value)
                                else:
                                    self.stderr.write("\nUnexpected field type: %s\n" % type(field))
                        except IntegrityError as e:
                            self.stderr.write('\n')
                            self.stderr.write("Tried setting %s[%s].%s to %s, but got:\n" % (model.__name__, obj.pk, field.name, None))
                            self.stderr.write("Exception: %s\n" % e)
                if verbosity > 1:
                    self.stdout.write('\n')

        def check_many_to_many_field(field):
            model = field.remote_field.through
            self.stdout.write("        %s.%s (through table)\n" % (model.__module__,model.__name__))

            for ff in [f for f in model._meta.fields if isinstance(f, (ForeignKey, OneToOneField)) ]: 
                check_field(ff, through_table=True)

        for conf in tqdm([ c for c in apps.get_app_configs() if c.name.startswith('ietf')], desc='apps  ', disable=verbose):
            if verbosity > 1:
                self.stdout.write("\nChecking %s\n" % conf.name)
            for model in tqdm(list(conf.get_models()), desc='models', disable=verbose):
                if model._meta.proxy:
                    continue
                if verbosity > 1:
                    self.stdout.write("        %s.%s\n" % (model.__module__,model.__name__))
                for field in [f for f in model._meta.fields if isinstance(f, (ForeignKey, OneToOneField)) ]: 
                    check_field(field)
                for field in [f for f in model._meta.many_to_many ]: 
                    check_many_to_many_field(field)
