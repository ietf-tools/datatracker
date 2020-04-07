# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from tqdm import tqdm

import django
django.setup()

from django.apps import apps
from django.core.management.base import BaseCommand #, CommandError
from django.core.exceptions import FieldError
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

        def check_field(field):
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
            dangling = used - exists
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
            try:
                foreign_model = field.related_model
            except Exception:
                debug.pprint('dir(field)')
                raise
            if foreign_model == field.model:
                return
            foreign_field_name  = field.remote_field.name
            foreign_accessor_name = field.remote_field.get_accessor_name()
            if verbosity > 1:
                self.stdout.write("  [....]  %s <- %s ( -> %s.%s)" %
                    (field.model.__name__, field.remote_field.through._meta.db_table,
                        foreign_model.__module__, foreign_model.__name__))
                self.stdout.flush()

            try:
                used = set(foreign_model.objects.values_list(foreign_field_name, flat=True))
                accessor_name = foreign_field_name
            except FieldError:
                try:
                    used = set(foreign_model.objects.values_list(foreign_accessor_name, flat=True))
                    accessor_name = foreign_accessor_name
                except FieldError:
                    self.stdout.write("\n    ** Warning: could not find foreign field name for %s.%s -> %s.%s\n" %
                        (field.model.__module__, field.model.__name__,
                            foreign_model.__name__, foreign_field_name))
            used.discard(None)
            exists = set(field.model.objects.values_list('pk',flat=True))
            dangling = used - exists
            if verbosity > 1:
                if dangling:
                    self.stdout.write("\r  ["+self.style.ERROR("fail")+"]\n  ** Bad key values:\n    %s\n" % sorted(list(dangling)))
                else:
                    self.stdout.write("\r  [ "+self.style.SUCCESS("ok")+" ]\n")
            else:
                if dangling:
                    self.stdout.write("\n%s.%s <- %s (-> %s.%s) ** Bad target key values:\n    %s\n" %
                        (field.model.__module__, field.model.__name__,
                            field.remote_field.through._meta.db_table,
                            foreign_model.__module__, foreign_model.__name__,
                            sorted(list(dangling))))

            if dangling and options.get('delete'):
                through = field.remote_field.through                
                if verbosity > 1:
                    self.stdout.write("Removing dangling entries from %s.%s\n" % (through._meta.app_label, through.__name__))

                kwargs = { accessor_name+'_id__in': dangling }
                to_delete = field.remote_field.through.objects.filter(**kwargs)
                count = to_delete.count()
                to_delete.delete()
                if verbosity > 1:
                    self.stdout.write("Removed %s entries from through table %s.%s\n" % (count, through._meta.app_label, through.__name__))


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
                    check_field(field)
                    check_many_to_many_field(field)
