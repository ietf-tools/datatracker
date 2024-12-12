# Copyright The IETF Trust 2018-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import gzip
import os
#import sys
import tqdm
import zipfile

try:
    import bz2
    has_bz2 = True
except ImportError:
    has_bz2 = False

from django.core.exceptions import ObjectDoesNotExist
from django.core import serializers
from django.db import DEFAULT_DB_ALIAS, DatabaseError, IntegrityError, connections
from django.db.models.signals import post_save
from django.utils.encoding import force_str
import django.core.management.commands.loaddata as loaddata

import debug                            # pyflakes:ignore

from ietf.community.signals import notify_of_events_receiver

class Command(loaddata.Command):
    help = ("""

        Load a fixture of related objects to the database.  The fixture is expected
        to contain a set of related objects, created with the 'dumprelated' management
        command.  It differs from the 'loaddata' command in that it silently ignores
        attempts to load duplicate entries, and continues loading subsequent entries.

        """)

    def add_arguments(self, parser):
        parser.add_argument('args', metavar='fixture', nargs='+', help='Fixture files.')
        parser.add_argument(
            '--database', action='store', dest='database', default=DEFAULT_DB_ALIAS,
            help='Nominates a specific database to load fixtures into. Defaults to the "default" database.',
        )
        parser.add_argument(
            '--ignorenonexistent', '-i', action='store_true', dest='ignore', default=False,
            help='Ignores entries in the serialized data for fields that do not '
                 'currently exist on the model.',
        )

    def handle(self, *args, **options):
        self.ignore = options['ignore']
        self.using = options['database']
        self.verbosity = options['verbosity']
        #
        self.compression_formats = {
            None: (open, 'rb'),
            'gz': (gzip.GzipFile, 'rb'),
            'zip': (SingleZipReader, 'r'),
        }
        if has_bz2:
            self.compression_formats['bz2'] = (bz2.BZ2File, 'r')
        #
        self.serialization_formats = serializers.get_public_serializer_formats()
        #
        post_save.disconnect(notify_of_events_receiver())
        #
        connection = connections[self.using]
        self.fixture_count = 0
        self.loaded_object_count = 0
        self.fixture_object_count = 0
        #
        for arg in args:
            fixture_file = arg
            self.stdout.write("Loading objects from %s" % fixture_file)
            _, ser_fmt, cmp_fmt = self.parse_name(os.path.basename(fixture_file))
            open_method, mode = self.compression_formats[cmp_fmt]
            fixture = open_method(fixture_file, mode)
            objects_in_fixture = 0
            self.stdout.write("Getting object count...\b\b\b", ending='')
            self.stdout.flush()
            for o in serializers.deserialize(ser_fmt, fixture, using=self.using, ignorenonexistent=self.ignore,):
                objects_in_fixture += 1
            self.stdout.write(" %d" % objects_in_fixture)
            #
            fixture = open_method(fixture_file, mode)
            self.fixture_count += 1
            objects = serializers.deserialize(ser_fmt, fixture, using=self.using, ignorenonexistent=self.ignore,)
            with connection.constraint_checks_disabled():
                for obj in tqdm.tqdm(objects, total=objects_in_fixture):
                    try:
                        obj.save(using=self.using)
                        self.loaded_object_count += 1
                    except (DatabaseError, IntegrityError, ObjectDoesNotExist, AttributeError) as e:
                        error_msg = force_str(e)
                        if "Duplicate entry" in error_msg:
                            pass
                        else:
                            self.stderr.write("Could not load %(app_label)s.%(object_name)s(pk=%(pk)s): %(error_msg)s" % {
                                'app_label': obj.object._meta.app_label,
                                'object_name': obj.object._meta.object_name,
                                'pk': obj.object.pk,
                                'error_msg': error_msg,
                            }, )
            self.fixture_object_count += objects_in_fixture

        if self.verbosity >= 1:
            if self.fixture_object_count == self.loaded_object_count:
                self.stdout.write(
                    "Installed %d object(s) from %d fixture(s)"
                    % (self.loaded_object_count, self.fixture_count)
                )
            else:
                self.stdout.write(
                    "Installed %d object(s) (of %d) from %d fixture(s)"
                    % (self.loaded_object_count, self.fixture_object_count, self.fixture_count)
                )

        
class SingleZipReader(zipfile.ZipFile):

    def __init__(self, *args, **kwargs):
        zipfile.ZipFile.__init__(self, *args, **kwargs)
        if len(self.namelist()) != 1:
            raise ValueError("Zip-compressed fixtures must contain one file.")

    def read(self):
        return zipfile.ZipFile.read(self, self.namelist()[0])


