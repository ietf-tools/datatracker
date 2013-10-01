from django.test import TestCase
from django.core.management import call_command
from django.db import transaction, connections, DEFAULT_DB_ALIAS
from django.test.testcases import connections_support_transactions, disable_transaction_methods

class AgendaTransactionalTestCase(TestCase):
    """
    Does basically the same as TransactionTestCase, but surrounds every test
    with a transaction, which is started after the fixtures are loaded.
    """

    def _fixture_setup(self):
        if not connections_support_transactions():
            return super(TestCase, self)._fixture_setup()

        # If the test case has a multi_db=True flag, setup all databases.
        # Otherwise, just use default.
        if getattr(self, 'multi_db', False):
            databases = connections
        else:
            databases = [DEFAULT_DB_ALIAS]

        if not TestCase.fixtures_loaded:

            print "Loading agenda fixtures for the first time"
            from django.contrib.sites.models import Site
            Site.objects.clear_cache()
            for db in databases:
                # should be a no-op, but another test case method might have left junk.
                call_command('flush', verbosity=0, interactive=False, database=db)

                # BUG, if the set of fixtures changes between test cases,
                # then it might not get reloaded properly.
                if hasattr(self, 'fixtures'):
                    print "  fixtures: %s" % (self.fixtures)
                    call_command('loaddata', *self.fixtures, **{
                                                             'verbosity': 0,
                                                             'commit': False,
                                                             'database': db
                                                             })
            TestCase.fixtures_loaded = True

        # now start a transaction.
        for db in databases:
            transaction.enter_transaction_management(using=db)
            transaction.managed(True, using=db)
        disable_transaction_methods()

