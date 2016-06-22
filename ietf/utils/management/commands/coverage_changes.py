# Copyright The IETF Trust 2016, All Rights Reserved

import os
import json
import codecs
import gzip
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.six import string_types

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    name, _ = os.path.splitext(os.path.basename(__file__))
    help = ("Show coverage info for the latest test run.  By default, the difference in \n"
            "coverage compared with the latest available release data is shown.\n"
            "\n"
            "Examples:\n"
            "\n"
            "    Show the coverage difference from the previous release:\n"
            "        $ manage.py {name}\n"
            "\n"
            "    Show the coverage difference with another release:\n"
            "        $ manage.py {name} --release=6.0.0\n"
            "\n"
            "    Show the coverage difference for a provided data-file:\n"
            "        $ manage.py {name} release-coverage.json.gz beeblebrox.json\n"
            "\n"
            "    List URLs which are not covered:\n"
            "        $ manage.py {name} --absolute --sections=url | grep False\n"
            "\n"
        ).format(**locals())
    args = "[[master_json] latest_json]"
    option_list = BaseCommand.option_list + (
        make_option('--sections', default='template,url,code', dest='sections',
            help='Specify which kinds of coverage changes to show. Default: %default'),
        make_option('--release', dest='release',
            help='Which release to use as baseline.  Default is the latest release in '
                 'the release coverage file.'),
        make_option('--absolute', dest='absolute', action='store_true', default=False,
            help='Show absolute figures instead of changes from last release.'),
    )    

    diff_line_format = "%-58s  %8s  %8s\n"
    list_line_format = "%-68s  %8s\n"
    valid_sections = ['template', 'url', 'code']

    def read_coverage(self, filename, version=None):
        if isinstance(filename, string_types):
            try:
                if filename.endswith(".gz"):
                    file = gzip.open(filename, "rb")
                else:
                    file = codecs.open(filename, "r", encoding="utf-8")
            except IOError as e:
                self.stderr.write(u"%s" % e)
                exit(1)
        else:
            file = filename
        try:
            data = json.load(file)
        except ValueError as e:
            raise CommandError("Failure to read json data from %s: %s" % (filename, e))
        version = version or data["version"]
        if not version in data:
            raise CommandError("There is no data for version %s available in %s" % (version, filename))
        return data[version], version

    def coverage_diff(self, master, latest, sections, release=None, **options):
        master_coverage, mversion = self.read_coverage(master, release)
        latest_coverage, lversion = self.read_coverage(latest)
        self.stdout.write("\nShowing coverage differeces between %s and %s:\n" % (mversion, lversion))
        for section in sections:
            mcoverage = master_coverage[section]["covered"]
            mformat   = master_coverage[section].get("format", 1)
            lcoverage = latest_coverage[section]["covered"]
            lformat   = latest_coverage[section].get("format", 1)
            #
            mkeys = mcoverage.keys()
            lkeys = lcoverage.keys()
            #
            keys = list(lkeys)
            keys.sort()
            header_written = False

            for key in keys:
                mkey = key
                if not mkey in mcoverage:
                    if mkey.endswith(".py"):
                        mkey = mkey[:-3]
                    else:
                        mkey = mkey + ".py"
                if not mkey in mcoverage:
                    mlines, mcov = None, None
                else:
                    if   mformat == 1:
                        mlines, mcov = None, mcoverage[mkey]
                    elif mformat == 2:
                        mlines, mcov = mcoverage[mkey]
                    else:
                        raise CommandError("The release coverage data has an unknown format ('%s'), quitting." % mformat)
                if   lformat == 1:
                    llines, lcov = None, lcoverage[key]
                elif lformat == 2:
                    llines, lcov = lcoverage[key]
                else:
                    raise CommandError("The latest coverage data has an unknown format ('%s'), quitting." % lformat)
                    
                if type(mcov) is float or type(lcov) is float:
                    mval = ("%5.1f" % (100*mcov)) if mcov else "-"
                    lval = ("%5.1f  %%" % (100*lcov)) if lcov else "-   "
                else:
                    mval = mcov
                    lval = lcov
                if mcov != lcov:
                    if not header_written:
                        self.stdout.write(self.diff_line_format %
                            ("\n%s"%section.capitalize(), mversion[:7], lversion[:7]))
                        self.stdout.write(self.diff_line_format % ("-"*58, "-"*8, "-"*8))
                        header_written = True
                    self.stdout.write(self.diff_line_format % (key, mval, lval))
            lkey_set = set(lkeys)
            rkey_set = set(mkeys)
            missing_key_set = rkey_set - lkey_set
            missing_key_count = len(missing_key_set)
            if missing_key_count > 0:
                self.stdout.write("\nThere were %s items in the %s %s coverage data which\n"
                    "were absent from the %s %s coverage data.\n" % (missing_key_count, mversion, section, lversion, section))
                if missing_key_count <= 10:
                    self.stdout.write("\nMissing items:\n")
                    for key in missing_key_set:
                        self.stdout.write("  %s\n" % key)


    def coverage_list(self, latest, sections, **options):
        latest_coverage, lversion = self.read_coverage(latest)
        self.stdout.write("\nShowing coverage for %s:\n" % (lversion, ))
        for section in sections:
            lcoverage = latest_coverage[section]["covered"]
            lformat   = latest_coverage[section].get("format", 1)
            #
            lkeys = lcoverage.keys()
            #
            keys = list(lkeys)
            keys.sort()
            header_written = False

            for key in keys:
                if   lformat == 1:
                    llines, lcov = None, lcoverage[key]
                elif lformat == 2:
                    llines, lcov = lcoverage[key]
                else:
                    raise CommandError("The latest coverage data has an unknown format ('%s'), quitting." % lformat)
                    
                if type(lcov) is float:
                    lval = ("%5.1f  %%" % (100*lcov)) if lcov else "-   "
                else:
                    lval = lcov
                if not header_written:
                    self.stdout.write(self.list_line_format %
                        ("\n%s"%section.capitalize(), lversion[:7]))
                    self.stdout.write(self.list_line_format % ("-"*58, "-"*8, ))
                    header_written = True
                self.stdout.write(self.list_line_format % (key, lval))

    def handle(self, *filenames, **options):
        sections = options.get('sections', ','.join(self.valid_sections))
        options.pop('sections')
        sections = sections.split(',')
        for section in sections:
            if not section in self.valid_sections:
                raise CommandError("Found an unexpected section name, '%s' in the section list. "
                    "Valid names are %s or any combination of them."%(section, ','.join(self.valid_sections)))

        absolute = options.get('absolute', False)

        if absolute:
            if not filenames:
                filenames = [
                    getattr(settings, 'TEST_COVERAGE_LATEST_FILE'),
                ]
            if len(filenames) != 1:
                raise CommandError(
                    "Coverage can be listed only for one json coverage-data file, "
                    "got: %s" % " ".join(filenames))
            self.coverage_list(filenames[0], sections=sections, **options)
        else:
            # verbosity = int(options.get('verbosity'))
            if not filenames:
                filenames = [
                    getattr(settings, 'TEST_COVERAGE_MASTER_FILE'),
                    getattr(settings, 'TEST_COVERAGE_LATEST_FILE'),
                ]
            if len(filenames) != 2:
                raise CommandError(
                    "Need two and only two files in order to show coverage difference, "
                    "got: %s" % " ".join(filenames))
            self.coverage_diff(*filenames, sections=sections, **options)
