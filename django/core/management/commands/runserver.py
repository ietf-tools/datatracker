from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
import os
import socket
import sys
import re

naiveip_re = r'^(?:(?P<addr>\d{1,3}(?:\.\d{1,3}){3}|\[[a-fA-F0-9:]+\]):)?(?P<port>\d+)$'
DEFAULT_PORT = "8000"

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--ipv6', '-6', action='store_true', dest='enable_ipv6', default=False,
            help='Force the use of IPv6 address.'),
        make_option('--noreload', action='store_false', dest='use_reloader', default=True,
            help='Tells Django to NOT use the auto-reloader.'),
        make_option('--adminmedia', dest='admin_media_path', default='',
            help='Specifies the directory from which to serve admin media.'),
    )
    help = "Starts a lightweight Web server for development."
    args = '[optional port number, or ipaddr:port]'

    # Validation is called explicitly each time the server is reloaded.
    requires_model_validation = False

    def handle(self, addrport='', *args, **options):
        import django
        from django.core.servers.basehttp import run, AdminMediaHandler, WSGIServerException
        from django.core.handlers.wsgi import WSGIHandler
        enable_ipv6 = options.get('enable_ipv6')
        if enable_ipv6 and not hasattr(socket, 'AF_INET6'):
            raise CommandError("Your Python does not support IPv6.")

        if args:
            raise CommandError('Usage is runserver %s' % self.args)
        if not addrport:
            addr = ''
            port = DEFAULT_PORT
        else:
            m = re.match(naiveip_re, addrport)
            if m is None:
                raise CommandError("%r is not a valid port number or address:port pair." % addrport)
            addr, port = m.groups()
            
        if not port.isdigit():
            raise CommandError("%r is not a valid port number." % port)
        if addr:
            if addr[0] == '[' and addr[-1] == ']':
                enable_ipv6 = True
                addr = addr[1:-1]
            elif enable_ipv6:
                 raise CommandError("IPv6 addresses must be surrounded with brackets")
        if not addr:
            addr = '127.0.0.1'
            addr = (enable_ipv6 and '::1') or '127.0.0.1'

        use_reloader = options.get('use_reloader', True)
        admin_media_path = options.get('admin_media_path', '')
        shutdown_message = options.get('shutdown_message', '')
        quit_command = (sys.platform == 'win32') and 'CTRL-BREAK' or 'CONTROL-C'

        def inner_run():
            from django.conf import settings
            from django.utils import translation
            print "Validating models..."
            self.validate(display_num_errors=True)
            print "\nDjango version %s, using settings %r" % (django.get_version(), settings.SETTINGS_MODULE)
            fmt_addr = (enable_ipv6 and '[%s]' % addr) or addr
            print "Development server is running at http://%s:%s/" % (fmt_addr, port)
            print "Quit the server with %s." % quit_command

            # django.core.management.base forces the locale to en-us. We should
            # set it up correctly for the first request (particularly important
            # in the "--noreload" case).
            translation.activate(settings.LANGUAGE_CODE)

            try:
                handler = AdminMediaHandler(WSGIHandler(), admin_media_path)
                run(addr, int(port), handler, enable_ipv6=enable_ipv6)
            except WSGIServerException, e:
                # Use helpful error messages instead of ugly tracebacks.
                ERRORS = {
                    13: "You don't have permission to access that port.",
                    98: "That port is already in use.",
                    99: "That IP address can't be assigned-to.",
                }
                try:
                    error_text = ERRORS[e.args[0].args[0]]
                except (AttributeError, KeyError):
                    error_text = str(e)
                sys.stderr.write(self.style.ERROR("Error: %s" % error_text) + '\n')
                # Need to use an OS exit because sys.exit doesn't work in a thread
                os._exit(1)
            except KeyboardInterrupt:
                if shutdown_message:
                    print shutdown_message
                sys.exit(0)

        if use_reloader:
            from django.utils import autoreload
            autoreload.main(inner_run)
        else:
            inner_run()
