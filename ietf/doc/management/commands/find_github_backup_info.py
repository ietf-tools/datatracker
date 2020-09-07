# Copyright The IETF Trust 2020, All Rights Reserved


import github3

from collections import Counter
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ietf.doc.models import DocExtResource
from ietf.group.models import GroupExtResource
from ietf.person.models import PersonExtResource

# TODO: Think more about submodules. This currently will only take top level repos, with the assumption that the clone will include arguments to grab all the submodules. 
# As a consequence, we might end up pulling more than we need (or that the org or user expected)
# Make sure this is what we want.

class Command(BaseCommand):
    help = ('Locate information about github repositories to backup')

    def add_arguments(self, parser):
        parser.add_argument('--verbose', dest='verbose', action='store_true', help='Show counts of types of repositories')

    def handle(self, *args, **options):

        if not (hasattr(settings,'GITHUB_BACKUP_API_KEY') and settings.GITHUB_BACKUP_API_KEY):
            raise CommandError("ERROR: can't find GITHUB_BACKUP_API_KEY") # TODO: at >= py3.1, use returncode

        github = github3.login(token = settings.GITHUB_BACKUP_API_KEY)
        owners = dict()
        repos = set()

        for cls in (DocExtResource, GroupExtResource, PersonExtResource):
            for res in cls.objects.filter(name_id__in=('github_repo','github_org')):
                path_parts = urlparse(res.value).path.strip('/').split('/')
                if not path_parts or not path_parts[0]:
                    continue

                owner = path_parts[0]

                if owner not in owners:
                    try:
                        gh_owner = github.user(username=owner)
                        owners[owner] = gh_owner
                    except github3.exceptions.NotFoundError:
                        continue 

                if gh_owner.type in ('User', 'Organization'):
                    if len(path_parts) > 1:
                        repo = path_parts[1]
                        if (owner, repo) not in repos:
                            try:
                                github.repository(owner,repo)
                                repos.add( (owner, repo) )
                            except github3.exceptions.NotFoundError:
                                continue
                    else:
                        for repo in github.repositories_by(owner):
                            repos.add( (owner, repo.name) )

        owner_types = Counter([owners[owner].type for owner in owners])
        if options['verbose']:
            self.stdout.write("Owners:")
            for key in owner_types:
                self.stdout.write("    %s: %s"%(key,owner_types[key]))
            self.stdout.write("Repositories: %d" % len(repos))
            for repo in sorted(repos):
                self.stdout.write("    https://github.com/%s/%s" % repo )
        else:
            for repo in sorted(repos):
                self.stdout.write("%s/%s" % repo )

