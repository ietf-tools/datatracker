from django.core import management
from django.core.management.commands import testserver
from django.core.management.commands import syncdb
from django.conf import settings

from syncdb import Command as SyncDbCommand


class MigrateAndSyncCommand(SyncDbCommand):
    option_list = SyncDbCommand.option_list
    for opt in option_list:
        if "--migrate" == opt.get_opt_string():
            opt.default = True
            break


class Command(testserver.Command):
    
    def handle(self, *args, **kwargs):
        management.get_commands()
        if not hasattr(settings, "SOUTH_TESTS_MIGRATE") or not settings.SOUTH_TESTS_MIGRATE:
            # point at the core syncdb command when creating tests
            # tests should always be up to date with the most recent model structure
            management._commands['syncdb'] = 'django.core'
        else:
            management._commands['syncdb'] = MigrateAndSyncCommand()
        super(Command, self).handle(*args, **kwargs)