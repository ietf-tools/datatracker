# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import warnings

from itertools import chain

import debug                            # pyflakes:ignore

from django.conf import settings
from django.core import serializers
from django.core.management.base import CommandError
from django.core.management.commands.loaddata import Command as LoadCommand, humanize
from django.db import DatabaseError, IntegrityError, router, transaction
from django.db.models import ManyToManyField
from django.utils.encoding import force_text

from ietf.utils.models import ForeignKey


def flatten(l):
    if isinstance(l, list):
        for el in l:
            if isinstance(el, list):
                for sub in flatten(el):
                    yield sub
            else:
                yield el
    else:
        yield l



class Command(LoadCommand):
    help = 'Merges the named fixture(s) into the database.'

    def add_arguments(self, parser):
#         parser.add_argument(
#             '-e', '--exclude', dest='exclude', action='append', default=[],
#             help='An app_label or app_label.ModelName to exclude. Can be used multiple times.',
#         )
        super(Command, self).add_arguments(parser)

    def load_label(self, fixture_label):
        """
        Loads fixtures files for a given label.
        """
#         def update_objects(objects, model, old_pk, new_pk):
#             debug.show('old_pk, new_pk')
#             for o in objects:
#                 for f in o._meta.fields:
#                     if   type(f) == ForeignKey:
#                         if f.pk in [old_pk, new_pk]:
#                             #debug.show('f')
#                             #debug.show('f.pk')
#                     elif type(f) == ManyToManyKey:
#                         pass

        def obj_to_dict(obj):
            opts = obj._meta
            data = {}
            for f in chain(opts.concrete_fields, opts.private_fields):
                data[f.name] = f.value_from_object(obj)
            return data

        def get_unique_field(obj):
            unique = {}
            for f in obj._meta.get_fields():
                if hasattr(f, 'primary_key') and f.primary_key:
                    continue
                if hasattr(f, 'unique') and f.unique:
                    unique[f.name] = f.value_from_object(obj)
            return unique

        show_progress = self.verbosity >= 3
        if hasattr(settings, 'SERVER_MODE'):
            # Try to avoid sending mail during repair
            settings.SERVER_MODE = 'repair'
        for fixture_file, fixture_dir, fixture_name in self.find_fixtures(fixture_label):
            _, ser_fmt, cmp_fmt = self.parse_name(os.path.basename(fixture_file))
            open_method, mode = self.compression_formats[cmp_fmt]
            fixture = open_method(fixture_file, mode)
            try:
                self.fixture_count += 1
                objects_in_fixture = 0
                loaded_objects_in_fixture = 0
                if self.verbosity >= 2:
                    self.stdout.write(
                        "Installing %s fixture '%s' from %s."
                        % (ser_fmt, fixture_name, humanize(fixture_dir))
                    )

                objects = list(serializers.deserialize(
                    ser_fmt, fixture, using=self.using, ignorenonexistent=self.ignore,
                ))

                # Prime fkrefs and m2mrefs with our deserialized objects
                fkrefs = {}
                m2mrefs = {}
                for obj in objects:
                    o = obj.object
                    oname = o._meta.app_label + '.' + o.__class__.__name__
                    fkrefs[(oname, o.pk)] = []
                    m2mrefs[(oname, o.pk)] = []

                # Tabulate all FKs and M2M fields
                for obj in objects:
                    o = obj.object
                    for f in o._meta.get_fields():
                        if   type(f) == ForeignKey:
                            fobj = getattr(o, f.name)
                            if fobj:
                                fmod = f.related_model
                                fname = fmod._meta.app_label + '.' + fmod.__name__
                                key = (fname, fobj.pk)
                                if key in fkrefs:
                                    fkrefs[key].append((o, f.name))
                        elif type(f) == ManyToManyField:
                            fobjs = getattr(o, f.name).all()
                            if fobjs:
                                fmod = f.related_model
                                fname = fmod._meta.app_label + '.' + fmod.__name__
                                for fobj in fobjs:
                                    key = (fname, fobj.pk)
                                    if key in m2mrefs:
                                        m2mrefs[key].append((o, f.name))                                
                        else:
                            pass
                            #debug.type('f')

                for obj in objects:
                    objects_in_fixture += 1
                    if (obj.object._meta.app_config in self.excluded_apps or
                            type(obj.object) in self.excluded_models):
                        continue
                    if router.allow_migrate_model(self.using, obj.object.__class__):
                        loaded_objects_in_fixture += 1
                        self.models.add(obj.object.__class__)
                        try:
                            model = obj.object.__class__
                            mname = model._meta.app_label + '.' + model.__name__
                            old_pk = obj.object.pk
                            unique = get_unique_field(obj.object)
                            if unique:
                                match = model.objects.filter(**unique)
                                if not match.exists():
                                    obj.object.pk = None
                                try:
                                    with transaction.atomic(using=self.using):
                                        obj.save(using=self.using)
                                        setattr(obj.object, '_saved', True)
                                except IntegrityError as e:
                                    this_pk = match.first().pk if match else None
                                    new_dict = obj_to_dict(obj.object)
                                    self.stderr.write("\nSaving an updated object failed, possibly due to manually inserted conflicting data.\n"
                                        "  Found PK: %s: %s\n"
                                        "  Unique key: %s\n"
                                        "  New record: %s\n"
                                        "  Exception: %s" % (mname, this_pk, unique, new_dict, e))
                            else:
                                match = model.objects.filter(pk=obj.object.pk)
                                if match.exists():
                                    #debug.say('PK exists: %s' % obj.object.pk)
                                    prev = match.first()
                                    prev_dict = obj_to_dict(prev)
                                    obj_dict = obj_to_dict(obj.object)
                                    if prev_dict == obj_dict:
                                        pass # nothing to do, the object is already there
                                    else:
                                        del obj_dict[obj.object._meta.pk.name]
                                        match = model.objects.filter(**obj_dict)
                                        if not match:
                                            try:
                                                obj.object.pk = None
                                                with transaction.atomic(using=self.using):
                                                    obj.save(using=self.using)
                                                setattr(obj.object, '_saved', True)
                                            except IntegrityError as e:
                                                new_dict = obj_to_dict(obj.object)
                                                self.stderr.write("\nSaving an object failed, possibly due to manually inserted conflicting data.\n"
                                                    "  Object type: %s\n"
                                                    "  New record: %s\n"
                                                    "  Exception: %s" % (mname, new_dict, e))
                                        else:
                                            obj.object.pk = match.first().pk
                                            #debug.say("Found matching object with new pk: %s" % (obj.object.pk, ))
                            new_pk = obj.object.pk
                            if new_pk != old_pk:
                                # Update other objects refering to this
                                # object to use the new pk
                                #debug.show('old_pk, new_pk')
                                mname = model._meta.app_label + '.' + model.__name__
                                key = (mname, old_pk)
                                if fkrefs[key] or m2mrefs[key]:
                                    #debug.pprint('fkrefs[key]')
                                    for o, f in fkrefs[key]:
                                            setattr(o, f+'_id', new_pk)
                                            if getattr(o, '_saved', False) == True:
                                                try:
                                                    with transaction.atomic(using=self.using):
                                                        o.save()
                                                except IntegrityError as e:
                                                    self.stderr.write("\nSaving an object failed, possibly due to manually inserted conflicting data.\n"
                                                        "  Object type: %s\n"
                                                        "  New record: %s\n"
                                                        "  Exception: %s" % (mname, obj_to_dict(o), e))
                                            
                                    #debug.pprint('m2mrefs[key]')
                                    for o, f in m2mrefs[key]:
                                        m2mfield = getattr(o, f)
                                        if m2mfield.through:
                                            through = m2mfield.instance
                                            for ff in through._meta.fields:
                                                if type(ff) == ForeignKey:
                                                    old_value = getattr(through, ff.name+'_id')
                                                    if ff.related_model == model and old_value == old_pk:
                                                        setattr(through, ff.name+'_id', new_pk)
                                                        through.save()
                                        else:
                                            m2mfield.remove(old_pk)
                                            m2mfield.add(new_pk)


                            if show_progress:
                                self.stdout.write(
                                    '\rProcessed %i object(s).' % loaded_objects_in_fixture,
                                    ending=''
                                )
                        except (DatabaseError, IntegrityError) as e:
                            e.args = ("Could not load %(app_label)s.%(object_name)s(pk=%(pk)s): %(error_msg)s\n  %(data)s\n" % {
                                'app_label': obj.object._meta.app_label,
                                'object_name': obj.object._meta.object_name,
                                'pk': obj.object.pk,
                                'data': obj_to_dict(obj.object),
                                'error_msg': force_text(e)
                            },)
                            raise
                if objects and show_progress:
                    self.stdout.write('')  # add a newline after progress indicator
                self.loaded_object_count += loaded_objects_in_fixture
                self.fixture_object_count += objects_in_fixture
            except Exception as e:
                if not isinstance(e, CommandError):
                    e.args = ("Problem installing fixture '%s': %s" % (fixture_file, e),)
                raise
            finally:
                fixture.close()

            # Warn if the fixture we loaded contains 0 objects.
            if objects_in_fixture == 0:
                warnings.warn(
                    "No fixture data found for '%s'. (File format may be "
                    "invalid.)" % fixture_name,
                    RuntimeWarning
                )

    def find_fixtures(self, fixture_label):
        fixture_files = []
        if os.path.exists(fixture_label):
            fixture_files = [ (fixture_label, os.path.dirname(fixture_label) or os.getcwd(), os.path.basename(fixture_label)) ]
        else:
            fixture_files = super(Command, self).find_fixtures(fixture_label)
        return fixture_files