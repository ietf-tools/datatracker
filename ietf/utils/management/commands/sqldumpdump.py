# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import collections
import gzip
import io
import re
import sys


from django.apps import apps
from django.core import serializers
from django.core.management.base import CommandError
from django.core.management.commands.dumpdata import Command as DumpdataCommand
from django.core.management.utils import parse_apps_and_model_labels
from django.db import router

import debug                            # pyflakes:ignore

# ------------------------------------------------------------------------------

class Command(DumpdataCommand):
    """
    Read 'INSERT INTO' lines from a (probably partial) SQL dump file, and
    extract table names and primary keys; then use these to do a data dump of
    the indicated records.

    Only simpler variations on the full sql INSERT command are recognized.

    The expected way to derive the input file is to do a diff between two sql
    dump files, and remove any diff line prefixes ('<' or '>' or '+' or -)
    from the diff, leaving only SQL "INSERT INTO" statements.
    """
    help = __doc__

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        # remove the usual positional args
        for i, a in enumerate(parser._actions):
            if a.dest == 'args':
                break
        del parser._actions[i]
        parser.add_argument('filenames', nargs='*',
            help="One or more files to process")
        parser.add_argument('--pk-name', default='id', type=str,
            help="Use the specified name as the primary key filed name (default: '%(default)s')" )
        parser.add_argument('--list-tables', action='store_true', default=False,
            help="Just list the tables found in the input files, with record counts")

    def note(self, msg):
        if self.verbosity > 1:
            self.stderr.write('%s\n' % msg)

    def warn(self, msg):
        self.stderr.write('Warning: %s\n' % msg)

    def err(self, msg):
        self.stderr.write('Error: %s\n' % msg)
        sys.exit(1)

    def get_tables(self):
        seen = set([])
        tables = {}
        for name, appconf in apps.app_configs.items():
            for model in appconf.get_models():
                if not model in seen:
                    seen.add(model)
                    app_label = model._meta.app_label
                    tables[model._meta.db_table] = {
                            'app_config': apps.get_app_config(app_label),
                            'app_label': app_label,
                            'model': model,
                            'model_label': model.__name__,
                            'pk': model._meta.pk.name,
                        }
        return tables

    def get_pks(self, filenames, tables):
        count = 0
        pks = {}
        for fn in filenames:
            prev = ''
            lc = 0
            with gzip.open(fn, 'rt') if fn.endswith('.gz') else io.open(fn) as f:
                for line in f:
                    lc += 1
                    line = line.strip()
                    if line and line[0] in ['<', '>']:
                        self.err("Input file '%s' looks like a diff file.  Please provide just the SQL 'INSERT' statements for the records to be dumped." % (fn, ))
                    if prev:
                        line = prev + line
                    prev = None
                    if not line.endswith(';'):
                        prev = line
                        continue
                    sql = line
                    if not sql.upper().startswith('INSERT '):
                        if self.verbosity > 2:
                            self.warn("Skipping sql '%s...'" % sql[:64])
                    else:
                        sql = sql.replace("\\'", "\\x27")
                        match = re.match(r"INSERT( +(LOW_PRIORITY|DELAYED|HIGH_PRIORITY))*( +IGNORE)?( +INTO)?"
                                         r" +(?P<table>\S+)"
                                         r" +\((?P<fields>([^ ,]+)(, [^ ,]+)*)\)"
                                         r" +(VALUES|VALUE)"
                                         r" +\((?P<values>(\d+|'[^']*'|-1|NULL)(,(\d+|'[^']*'|-1|NULL))*)\)"
                                         r" *;"
                                         , sql)
                        if not match:
                            self.warn("Unrecognized sql command: '%s'" % sql)
                        else:
                            table = match.group('table').strip('`')
                            if not table in pks:
                                pks[table] = []
                            fields = match.group('fields')
                            fields = [ f.strip("`") for f in re.split(r"(`[^`]+`)", fields) if f and not re.match(r'\s*,\s*', f)] # pyflakes:ignore
                            values = match.group('values')
                            values = [ v.strip("'") for v in re.split(r"(\d+|'[^']*'|NULL)", values) if v and not re.match(r'\s*,\s*', v) ]
                            try:
                                pk_name = tables[table]['pk']
                                ididx = fields.index(pk_name)
                                pk = values[ididx]
                                pks[table].append(pk)
                                count += 1
                            except (KeyError, ValueError):
                                pass
        return pks, count
        
    def get_objects(self, app_list, pks, count_only=False):
        """
        Collate the objects to be serialized. If count_only is True, just
        count the number of objects to be serialized.
        """
        models = serializers.sort_dependencies(app_list.items())
        excluded_models, __ = parse_apps_and_model_labels(self.excludes)
        for model in models:
            if model in excluded_models:
                continue
            if not model._meta.proxy and router.allow_migrate_model(self.using, model):
                if self.use_base_manager:
                    objects = model._base_manager
                else:
                    objects = model._default_manager

                queryset = objects.using(self.using).order_by(model._meta.pk.name)
                primary_keys = pks[model._meta.db_table] if model._meta.db_table in pks else []
                if primary_keys:
                    queryset = queryset.filter(pk__in=primary_keys)
                    #self.stderr.write('+ %s: %s\n' % (model._meta.db_table, queryset.count() ))
                else:
                    continue
                if count_only:
                    yield queryset.order_by().count()
                else:
                    for obj in queryset.iterator():
                        yield obj


    def handle(self, filenames=[], **options):
        self.verbosity = int(options.get('verbosity'))
        format = options['format']
        indent = options['indent']
        self.using = options['database']
        self.excludes = options['exclude']
        output = options['output']
        show_traceback = options['traceback']
        use_natural_foreign_keys = options['use_natural_foreign_keys']
        use_natural_primary_keys = options['use_natural_primary_keys']
        self.use_base_manager = options['use_base_manager']
        pks = options['primary_keys']

        # Check that the serialization format exists; this is a shortcut to
        # avoid collating all the objects and _then_ failing.
        if format not in serializers.get_public_serializer_formats():
            try:
                serializers.get_serializer(format)
            except serializers.SerializerDoesNotExist:
                pass

            raise CommandError("Unknown serialization format: %s" % format)

        tables = self.get_tables()
        pks, count = self.get_pks(filenames, tables)
        if options.get('list_tables', False):
            for key in pks:
                self.stdout.write("%-32s  %6d\n" % (key, len(pks[key])))
        else:
            self.stdout.write("Found %s SQL records.\n" % count)

            app_list = collections.OrderedDict()

            for t in tables:
                #print("%32s\t%s" % (t, ','.join(pks[t])))
                app_config = tables[t]['app_config']
                app_list.setdefault(app_config, [])
                app_list[app_config].append(tables[t]['model'])

            #debug.pprint('app_list')

            try:
                self.stdout.ending = None
                progress_output = None
                object_count = 0
                # If dumpdata is outputting to stdout, there is no way to display progress
                if (output and self.stdout.isatty() and options['verbosity'] > 0):
                    progress_output = self.stdout
                    object_count = sum(self.get_objects(app_list, pks, count_only=True))
                stream = open(output, 'w') if output else None
                try:
                    serializers.serialize(
                        format, self.get_objects(app_list, pks), indent=indent,
                        use_natural_foreign_keys=use_natural_foreign_keys,
                        use_natural_primary_keys=use_natural_primary_keys,
                        stream=stream or self.stdout, progress_output=progress_output,
                        object_count=object_count,
                    )
                    self.stdout.write("Dumped %s objects.\n" % object_count)
                finally:
                    if stream:
                        stream.close()
            except Exception as e:
                if show_traceback:
                    raise
                raise CommandError("Unable to serialize database: %s" % e)
        