# Copyright 2016 IETF Trust

import os
import copy
import syslog
import pkg_resources
from optparse import make_option
#from optparse import make_option

from trac.core import TracError
from trac.env import Environment
from trac.perm import PermissionSystem
from trac.ticket.model import Component, Milestone, Severity
from trac.util.text import unicode_unquote
from trac.wiki.model import WikiPage

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

import debug                            # pyflakes:ignore

from ietf.group.models import Group, GroupURL
from ietf.utils.pipe import pipe

logtag = __name__.split('.')[-1]
logname = "user.log"
syslog.openlog(logtag, syslog.LOG_PID, syslog.LOG_USER)

class Command(BaseCommand):
    help = "Create group wikis for WGs, RGs and Areas which don't have one."

    option_list = BaseCommand.option_list + (
        make_option('--wiki-dir-pattern', dest='wiki_dir_pattern',
            default=settings.TRAC_WIKI_DIR_PATTERN,
            help='A pattern with %s placeholder for group wiki path'),
        make_option('--svn-dir-pattern', dest='svn_dir_pattern',
            default=settings.TRAC_SVN_DIR_PATTERN,
            help='A pattern with %s placeholder for group svn path'),
        make_option('--group-list', '-g', dest='group_list', help='Limit processing to groups with the given acronyms (a comma-separated list)'),
        make_option('--dummy-run', '-n', default=False, action='store_true', dest='dummy_run', help='Make no changes, just show what would be done'),
    )
    
    def note(self, msg):
        if self.verbosity > 1:
            self.stdout.write(msg)

    def log(self, msg):
        syslog.syslog(msg)
        self.stdout.write(msg)
        self.stderr.write(msg)

    # --- svn ---

    def do_cmd(self, cmd, *args):
        quoted_args = [ '"%s"'%a if ' ' in a else a for a in args ]
        if self.dummy_run:
            self.note("Would run %s %s ..." % (os.path.basename(cmd), " ".join(quoted_args)))
        else:
            self.note("Running %s %s ..." % (os.path.basename(cmd), " ".join(quoted_args)))
            command = [ cmd, ] + list(args)
            code, out, err = pipe(command)
            msg = None
            if code != 0:
                msg = "Error %s: %s when executing '%s'" % (code, err, " ".join(command))
                self.log(msg)
            return msg, out

    def svn_admin_cmd(self, *args):
        return self.do_cmd(settings.SVN_ADMIN_COMMAND, *args)

    def create_svn(self, svn):
        self.note("  Creating svn repository: %s" % svn)
        if not os.path.exists(os.path.dirname(svn)):
            msg = "Intended to create '%s', but parent directory is missing" % svn
            self.log(msg)
            return msg
        err, out= self.svn_admin_cmd("create", svn )
        if err:
            msg = "Error %s creating svn repository %s:\n   %s" % (err, svn, out)
            self.log(msg)
            return msg
        return None

    # --- trac ---

    def remove_demo_components(self, group, env):
        for component in Component.select(env):
            if component.name.startswith('component'):
                component.delete()

    def remove_demo_milestones(self, group, env):
        for milestone in Milestone.select(env):
            if milestone.name.startswith('milestone'):
                milestone.delete()

    def symlink_to_master_assets(self, group, env):
        master_dir = settings.TRAC_MASTER_DIR
        master_htdocs = os.path.join(master_dir, "htdocs")
        group_htdocs = os.path.join(group.trac_dir, "htdocs")
        self.note("  Symlinking %s to %s" % (master_htdocs, group_htdocs))
        os.removedirs(group_htdocs)
        os.symlink(master_htdocs, group_htdocs)

    def add_wg_draft_states(self, group, env):
        for state in settings.TRAC_ISSUE_SEVERITY_ADD:
            self.note("  Adding severity %s" % state)
            severity = Severity(env)
            severity.name = state
            severity.insert()

    def add_wiki_page(self, env, name, text):
        page = WikiPage(env, name)
        if page.time:
            self.note("  ** Page %s already exists, not adding it." % name)
            return
        page.text = text
        page.save(author="(System)", comment="Initial page import")

    def add_default_wiki_pages(self, group, env):
        dir = pkg_resources.resource_filename('trac.wiki', 'default-pages')
        #WikiAdmin(env).load_pages(dir)
        with env.db_transaction:
            for name in os.listdir(dir):
                filename = os.path.join(dir, name)
                name = unicode_unquote(name.encode('utf-8'))
                if os.path.isfile(filename):
                    self.note("  Adding page %s" % name)
                    with open(filename) as file:
                        text = file.read().decode('utf-8')
                    self.add_wiki_page(env, name, text)

    def add_custom_wiki_pages(self, group, env):
        for templ in settings.TRAC_WIKI_PAGES_TEMPLATES:
            _, name = os.path.split(templ)
            text = render_to_string(templ, {"group": group})
            self.note("  Adding page %s" % name)
            self.add_wiki_page(env, name, text)

    def sync_default_repository(self, group, env):
        repository = env.get_repository('')
        if repository:
            self.note("  Indexing default repository")
            repository.sync()
        else:
            self.log("Trac environment '%s' does not have any repository" % env)

    def create_trac(self, group):
        if not os.path.exists(os.path.dirname(group.trac_dir)):
            msg = "Intended to create '%s', but parent directory is missing" % group.trac_dir
            self.log(msg)
            return None, msg
        options = copy.deepcopy(settings.TRAC_ENV_OPTIONS)
        # Interpolate group field names to values in the option settings:
        for i in range(len(options)):
            sect, key, val = options[i]
            val = val.format(**group.__dict__)
            options[i] = sect, key, val
        # Try to creat ethe environment, remove unwanted defaults, and add
        # custom pages and settings.
        if self.dummy_run:
            self.note("Would create Trac for group '%s' at %s" % (group.acronym, group.trac_dir))
            return None, None
        else:
            try:
                self.note("Creating Trac for group '%s' at %s" % (group.acronym, group.trac_dir))
                env = Environment(group.trac_dir, create=True, options=options)
                self.remove_demo_components(group, env)
                self.remove_demo_milestones(group, env)
                self.maybe_add_group_url(group, 'Wiki', settings.TRAC_WIKI_URL_PATTERN % group.acronym)
                self.maybe_add_group_url(group, 'Issue tracker', settings.TRAC_ISSUE_URL_PATTERN % group.acronym)
                # Use custom assets (if any) from the master setup
                self.symlink_to_master_assets(group, env)
                if group.type_id == 'wg':
                    self.add_wg_draft_states(group, env)
                self.add_custom_wiki_pages(group, env)
                self.add_default_wiki_pages(group, env)
                self.sync_default_repository(group, env)
                # Components (i.e., drafts) will be handled during components
                # update later
                # Permissions will be handled during permission update later.
                return env, None
            except TracError as e:
                msg = "While creating Trac instance for %s: %s" % (group, e)
                self.log(msg)
                return None, msg

    def update_trac_permissions(self, group, env):
        if self.dummy_run:
            self.note("Would update Trac permissions for group '%s'" % group.acronym)
        else:
            self.note("Updating Trac permissions for group '%s'" % group.acronym)
            mgr = PermissionSystem(env)
            permission_list = mgr.get_all_permissions()
            permission_list = [ (u,a) for (u,a) in permission_list if not u in ['anonymous', 'authenticated']]
            permissions = {}
            for user, action in permission_list:
                if not user in permissions:
                    permissions[user] = []
                permissions[user].append(action)
            roles = group.role_set.filter(name_id__in=['chair', 'secr', 'ad'])
            users = []
            for role in roles:
                user = role.email.address.lower()
                users.append(user)
                if not user in permissions:
                    try:
                        mgr.grant_permission(user, 'TRAC_ADMIN')
                        self.note("  Granting admin permission for %s" % user)
                    except TracError as e:
                        self.log("While adding admin permission for %s: %s" (user, e))
            for user in permissions:
                if not user in users:
                    if 'TRAC_ADMIN' in permissions[user]:
                        try:
                            self.note("  Revoking admin permission for %s" % user)
                            mgr.revoke_permission(user, 'TRAC_ADMIN')
                        except TracError as e:
                            self.log("While revoking admin permission for %s: %s" (user, e))

    def update_trac_components(self, group, env):
        if self.dummy_run:
            self.note("Would update Trac components for group '%s'" % group.acronym)
        else:
            self.note("Updating Trac componets for group '%s'" % group.acronym)
            components = Component.select(env)
            comp_names = [ c.name for c in components ]
            group_docs = group.document_set.filter(states__slug='active', type_id='draft').distinct()
            group_comp = []
            for doc in group_docs:
                if not doc.name.startswith('draft-'):
                    self.log("While adding components: unexpectd %s group doc name: %s" % (group.acronym, doc.name))
                    continue
                name = doc.name[len('draft-'):]
                if   name.startswith('ietf-'):
                    name = name[len('ietf-'):]
                elif name.startswith('irtf-'):
                    name = name[len('ietf-'):]
                if name.startswith(group.acronym+'-'):
                    name = name[len(group.acronym+'-'):]
                group_comp.append(name)
                if not name in comp_names and not doc.name in comp_names:
                    self.note("  Group draft: %s" % doc.name)
                    self.note("  Adding component %s" % name)
                    comp = Component(env)
                    comp.name = name
                    comp.owner = "%s@ietf.org" % doc.name
                    comp.insert()

    def maybe_add_group_url(self, group, name, url):
        urls = [ u for u in group.groupurl_set.all() if name.lower() in u.name.lower() ]
        if not urls:
            self.note("  adding %s %s URL ..." % (group.acronym, name.lower()))
            group.groupurl_set.add(GroupURL(group=group, name=name, url=url))

    def add_custom_pages(self, group, env):
        for template_name in settings.TRAC_WIKI_PAGES_TEMPLATES:
            pass

    def add_custom_group_states(self, group, env):
        for state_name in settings.TRAC_ISSUE_SEVERITY_ADD:
            pass

    # --------------------------------------------------------------------

    def handle(self, *filenames, **options):
        self.verbosity = options['verbosity']
        self.errors = []
        self.wiki_dir_pattern = options.get('wiki_dir_pattern', settings.TRAC_WIKI_DIR_PATTERN)
        self.svn_dir_pattern = options.get('svn_dir_pattern', settings.TRAC_SVN_DIR_PATTERN)
        self.group_list = options.get('group_list', None)
        self.dummy_run = options.get('dummy_run', False)

        if not self.group_list is None:
            self.group_list = self.group_list.split('.')

        if isinstance(self.verbosity, (type(""), type(u""))) and self.verbosity.isdigit():
            self.verbosity = int(self.verbosity)

        if self.dummy_run and self.verbosity < 2:
            self.verbosity = 2

        if not os.path.exists(os.path.dirname(self.wiki_dir_pattern)):
            raise CommandError('The Wiki base direcory specified for the wiki directories (%s) does not exist.' % os.path.dirname(self.wiki_dir_pattern))

        if not os.path.exists(os.path.dirname(self.svn_dir_pattern)):
            raise CommandError('The SVN base direcory specified for the SVN directories (%s) does not exist.' % os.path.dirname(self.svn_dir_pattern))

        groups = Group.objects.filter(
                        type__slug__in=['wg','rg','area'],
                        state__slug='active',
                    ).order_by('acronym')
        if self.group_list:
            groups = groups.filter(acronym__in=self.group_list)

        for group in groups:
            try:
                self.note("Processing group '%s'" % group.acronym)
                group.trac_dir = self.wiki_dir_pattern % group.acronym
                group.svn_dir = self.svn_dir_pattern % group.acronym

                if not os.path.exists(group.svn_dir):
                    err = self.create_svn(group.svn_dir)
                    if err:
                        self.errors.append(err)

                if not os.path.exists(group.trac_dir):
                    trac_env, msg = self.create_trac(group)
                    if not trac_env: 
                        self.errors.append(msg)
                else:
                    if not self.dummy_run:
                        trac_env = Environment(group.trac_dir)

                if not trac_env and not self.dummy_run:
                    continue

                self.update_trac_permissions(group, trac_env)
                self.update_trac_components(group, trac_env)

            except Exception as e:
                self.errors.append(e)
                self.log("While processing %s: %s" % (group.acronym, e))
                raise

        if self.errors:
            raise CommandError("There were %s failures in WG Trac creation:\n   %s" % (len(self.errors), "\n   ".join(self.errors)))
