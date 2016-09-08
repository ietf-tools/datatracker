import sys

from optparse import make_option
from textwrap import dedent

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

def import_htpasswd_file(filename, verbosity=1, overwrite=False):
    with open(filename) as file:
        for line in file:
            if not ':' in line:
                raise ValueError('Found a line without colon separator in the htpassword file %s:'+
                    '   "%s"' % (file.name, line)) # pylint: disable=too-many-format-args
            username, password = line.strip().split(':', 1)
            try:
                user = User.objects.get(username=username)
                if overwrite == True or not user.password:
                    if   password.startswith('{SHA}'):
                        user.password = "sha1$$%s" % password[len('{SHA}'):]
                    elif password.startswith('$apr1$'):
                        user.password = "md5$%s" % password[len('$apr1$'):]
                    else:       # Assume crypt
                        user.password = "crypt$$%s" % password
                    user.save()
                    if verbosity > 0:
                        sys.stderr.write('.')
                    if verbosity > 1:
                        sys.stderr.write(' %s\n' % username)
            except User.DoesNotExist:
                if verbosity > 1:
                    sys.stderr.write('\nNo such user: %s\n' % username)

class Command(BaseCommand):
    """
    Import passwords from one or more htpasswd files to Django's auth_user table.

    This command only imports passwords; it does not import usernames, as that
    would leave usernames without associated Person records in the database,
    something which is undesirable.

    By default the command won't overwrite existing password entries, but
    given the --force switch, it will overwrite existing entries too.  Without
    the --force switch, the command is safe to run repeatedly.
    """

    help = dedent(__doc__).strip()
            
    option_list = BaseCommand.option_list + (
        make_option('--force',
            action='store_true', dest='overwrite', default=False,
            help='Overwrite existing passwords in the auth_user table.'),
        )

    args = '[path [path [...]]]'

    def handle(self, *filenames, **options):
        overwrite = options.get('overwrite', False)
        verbosity = int(options.get('verbosity'))
        for fn in filenames:
            import_htpasswd_file(fn, verbosity=verbosity, overwrite=overwrite)
                    
