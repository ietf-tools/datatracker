
import django
django.setup()

from django.core.management.base import BaseCommand #, CommandError
from django.core.exceptions import FieldError
from django.db import models
from django.db.models.fields.related import ForeignKey, OneToOneField

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    help = "Check all models for referential integrity."

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", "1")
        verbosity = int(verbosity) if verbosity.isdigit() else 1

        def check_field(field):
            foreign_model = field.related.parent_model
            if verbosity > 1:
                print "    %s -> %s.%s" % (field.name,foreign_model.__module__,foreign_model.__name__),
            used = set(field.model.objects.values_list(field.name,flat=True))
            used.discard(None)
            exists = set(foreign_model.objects.values_list('pk',flat=True))
            if verbosity > 1:
                if used - exists:
                    print "  ** Bad key values:",list(used - exists)
                else:
                    print "  ok"
            else:
                if used - exists:
                    print "%s.%s.%s -> %s.%s Bad key values:" % (model.__module__,model.__name__,field.name,foreign_model.__module__,foreign_model.__name__),list(used - exists)

        def check_reverse_field(field):
            foreign_model = field.related.parent_model
            if foreign_model == field.model:
                return
            foreign_field_name  = field.related.var_name
            foreign_accessor_name = field.related.get_accessor_name()
            if verbosity > 1:
                print "    %s <- %s -> %s.%s" % (field.model.__name__, field.rel.through._meta.db_table, foreign_model.__module__, foreign_model.__name__),
            try:
                used = set(foreign_model.objects.values_list(foreign_field_name, flat=True))
            except FieldError:
                try:
                    used = set(foreign_model.objects.values_list(foreign_accessor_name, flat=True))
                except FieldError:
                    print "    ** Warning: could not find reverse name for %s.%s -> %s.%s" % (field.model.__module__, field.model.__name__, foreign_model.__name__, foreign_field_name),
            used.discard(None)
            exists = set(field.model.objects.values_list('pk',flat=True))
            if verbosity > 1:
                if used - exists:
                    print "  ** Bad key values:\n    ",list(used - exists)
                else:
                    print "  ok"
            else:
                if used - exists:
                    print "%s.%s <- %s -> %s.%s  ** Bad key values:\n    " % (field.model.__module__, field.model.__name__, field.rel.through._meta.db_table, foreign_model.__module__, foreign_model.__name__), list(used - exists)

        for app in [a for a in models.get_apps() if a.__name__.startswith('ietf.')]:
            if verbosity > 1:
                print "Checking",app.__name__
            for model in models.get_models(app):
                if model._meta.proxy:
                    continue
                if verbosity > 1:
                    print "  %s.%s" % (model.__module__,model.__name__)
                for field in [f for f in model._meta.fields if isinstance(f, (ForeignKey, OneToOneField)) ]: 
                    check_field(field)
                for field in [f for f in model._meta.many_to_many ]: 
                    check_field(field)
                    check_reverse_field(field)
