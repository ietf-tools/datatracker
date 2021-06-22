import os
import sys
import json
import tempfile
import shutil
import hashlib
import glob
import textwrap
from subprocess import call, check_output, CalledProcessError
from optparse import make_option

import debug                            # pyflakes:ignore

from django.core.management.base import BaseCommand
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.contrib.staticfiles.finders import BaseStorageFinder, AppDirectoriesFinder

class BaseDirectoryFinder(BaseStorageFinder):
    storage = FileSystemStorage(location=settings.BASE_DIR)

class Command(BaseCommand):
    """

    This command goes through any static/ directories of installed apps,
    and the directories listed in settings.STATICFILES_DIRS. If package
    description files for bower, npm, or grunt are found in any of these
    locations, it will use the appropriate package manager to install the
    listed packages in a temporary folder, using these commands:

        - package.json: npm install
        - Gruntfile.js: grunt default
        - bower.json: bower install

    It will then extract the distribution files to the location indicated in
    settings.COMPONENT_ROOT.
    """
    help = textwrap.dedent(__doc__).lstrip()
    component_root = getattr(settings, 'COMPONENT_ROOT', os.path.join(settings.STATIC_ROOT, "components"))

    def add_arguments(self, parser):
        parser.add_argument('--with-version', dest='with_version', default=False, action='store_true',
            help='Create component directories with version numbers')
        parser.add_argument('--keep-packages', dest='keep_packages', default=False, action='store_true',
            help='Keep the downloaded bower packages, instead of removing them after moving '
                'distribution files to settings.COMPONENT_ROOT')

    bower_info = {}
    overrides = {}

    def npm_install(self, pkg_json_path):
        os.chdir(os.path.dirname(pkg_json_path))
        call(['npm', 'install'])

    def grunt_default(self, grunt_js_path):
        os.chdir(os.path.dirname(grunt_js_path))
        call(['grunt'])

    def bower_install(self, bower_json_path, dest_dir):
        """Runs bower commnand for the passed bower.json path.

        :param bower_json_path: bower.json file to install
        :param dest_dir: where the compiled result will arrive
        """

        # Verify that we are able to run bower, in order to give a good error message in the
        # case that it's not installed.  Do this separately from the 'bower install' call, in
        # order not to warn about a missing bower in the case of installation-related errors.
        try:
            bower_version = check_output(['bower', '--version']).strip()
        except OSError as e:
            print("Trying to run bower failed -- is it installed?  The error was: %s" % e)
            exit(1)
        except CalledProcessError as e:
            print("Checking the bower version failed: %s" % e)
            exit(2)

        print("\nBower %s" % bower_version)
        print("Installing from %s\n" % bower_json_path)

        # bower args
        args = ['bower', 'install', bower_json_path, '--allow-root',
                '--verbose', '--config.cwd={}'.format(dest_dir), '-p']

        # run bower command
        call(args)

    def get_bower_info(self, bower_json_path):
        if not bower_json_path in self.bower_info:
            self.bower_info[bower_json_path] = json.load(open(bower_json_path))

    def get_bower_main_list(self, bower_json_path, override):
        """
        Returns the bower.json main list or empty list.
        Applies overrides from the site-wide bower.json.
        """
        self.get_bower_info(bower_json_path)

        main_list = self.bower_info[bower_json_path].get('main')
        component = self.bower_info[bower_json_path].get('name')

        if (override in self.bower_info
            and "overrides" in self.bower_info[override] 
            and component in self.bower_info[override].get("overrides")
            and "main" in self.bower_info[override].get("overrides").get(component)):
                main_list = self.bower_info[override].get("overrides").get(component).get("main")

        if isinstance(main_list, list):
            return main_list

        if main_list:
            return [main_list]

        return []

    def get_bower_version(self, bower_json_path):
        """Returns the bower.json main list or empty list.
        """
        self.get_bower_info(bower_json_path)

        return self.bower_info[bower_json_path].get("version")

    def clean_components_to_static_dir(self, bower_dir, override):
        print("\nMoving component files to %s\n" % (self.component_root,))

        for directory in os.listdir(bower_dir):
            print("Component: %s" % (directory, ))

            src_root = os.path.join(bower_dir, directory)

            for bower_json in ['bower.json', '.bower.json']:
                bower_json_path = os.path.join(src_root, bower_json)
                if os.path.exists(bower_json_path):
                    main_list = self.get_bower_main_list(bower_json_path, override) + ['bower.json']
                    version   = self.get_bower_version(bower_json_path)

                    dst_root = os.path.join(self.component_root, directory)
                    if self.with_version:
                        assert not dst_root.endswith(os.sep)
                        dst_root += "-"+version

                    for pattern in filter(None, main_list):
                        src_pattern = os.path.join(src_root, pattern)
                        # main_list elements can be fileglob patterns
                        for src_path in glob.glob(src_pattern):
                            if not os.path.exists(src_path):
                                print("Could not find source path: %s" % (src_path, ))

                            # Build the destination path
                            src_part = src_path[len(src_root+'/'):]
                            if src_part.startswith('dist/'):
                                src_part = src_part[len('dist/'):]
                            dst_path = os.path.join(dst_root, src_part)

                            # Normalize the paths, for good looks
                            src_path = os.path.abspath(src_path)
                            dst_path = os.path.abspath(dst_path)

                            # Check if we need to copy the file at all.
                            if os.path.exists(dst_path):
                                with open(src_path, 'br') as src:
                                    src_hash = hashlib.sha1(src.read()).hexdigest()
                                with open(dst_path, 'br') as dst:
                                    dst_hash = hashlib.sha1(dst.read()).hexdigest()
                                if src_hash == dst_hash:
                                    #print('{0} = {1}'.format(src_path, dst_path))
                                    continue

                            # Make sure dest dir exists.
                            dst_dir = os.path.dirname(dst_path)
                            if not os.path.exists(dst_dir):
                                os.makedirs(dst_dir)

                            print('  {0} > {1}'.format(src_path, dst_path))
                            shutil.copy(src_path, dst_path)
                    break

    def handle(self, *args, **options):

        self.with_version = options.get("with_version")
        self.keep_packages = options.get("keep_packages")

        temp_dir = getattr(settings, 'BWR_APP_TMP_FOLDER', 'tmp')
        temp_dir = os.path.abspath(temp_dir)

        # finders
        basefinder = BaseDirectoryFinder()
        appfinder = AppDirectoriesFinder()
        # Assume bower.json files are to be found in each app directory,
        # rather than in the app's static/ subdirectory:
        appfinder.source_dir = '.'

        finders = (basefinder, appfinder, )

        if os.path.exists(temp_dir):
            if not self.keep_packages:
                sys.stderr.write(
                    "\nWARNING:\n\n"
                    "  The temporary package installation directory exists, but the --keep-packages\n"
                    "  option has not been given.  In order to not delete anything which should be\n"
                    "  kept, %s will not be removed.\n\n"
                    "  Please remove it manually, or use the --keep-packages option to avoid this\n"
                    "  message.\n\n" % (temp_dir,))
                self.keep_packages = True
        else:
            os.makedirs(temp_dir)

        for finder in finders:
            for path in finder.find('package.json', all=True):
                self.npm_install(path)

        for finder in finders:
            for path in finder.find('Gruntfile.json', all=True):
                self.grunt_default(path)

        for finder in finders:
            for path in finder.find('bower.json', all=True):
                self.get_bower_info(path)
                self.bower_install(path, temp_dir)

        bower_dir = os.path.join(temp_dir, 'bower_components')

        # nothing to clean
        if not os.path.exists(bower_dir):
            print('No components seems to have been found by bower, exiting.')
            sys.exit(0)

        self.clean_components_to_static_dir(bower_dir, path)

        if not self.keep_packages:
            shutil.rmtree(temp_dir)

