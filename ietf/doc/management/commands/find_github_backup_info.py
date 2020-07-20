# Copyright The IETF Trust 2020, All Rights Reserved

from django.core.management.base import BaseCommand
from django.db.models import F

from ietf.doc.models import DocExtResource
from ietf.group.models import GroupExtResource
from ietf.person.models import PersonExtResource

class Command(BaseCommand):
    help = ('Locate information about gihub repositories to backup')

    def handle(self, *args, **options):

        info_dict = {}


        for repo in DocExtResource.objects.filter(name__slug='github_repo'):
            if not repo.value.endswith('/'):
                repo.value += '/'
            if repo not in info_dict:
                info_dict[repo.value] = []
            for username in DocExtResource.objects.filter(name__slug='github_username', doc=F('doc')):
                info_dict[repo.value].push(username.value)

        for repo in GroupExtResource.objects.filter(name__slug='github_repo'):
            if not repo.value.endswith('/'):
                repo.value += '/'
            if repo not in info_dict:
                info_dict[repo.value] = []
            for username in GroupExtResource.objects.filter(name__slug='github_username', group=F('group')):
                info_dict[repo.value].push(username.value)

        for repo in PersonExtResource.objects.filter(name__slug='github_repo'):
            if not repo.value.endswith('/'):
                repo.value += '/'
            if repo not in info_dict:
                info_dict[repo.value] = []
            for username in PersonExtResource.objects.filter(name__slug='github_username', person=F('person')):
                info_dict[repo.value].push(username.value)

        #print (json.dumps(info_dict))
        # For now, all we need are the repo names
        for name in info_dict.keys():
            print(name)
