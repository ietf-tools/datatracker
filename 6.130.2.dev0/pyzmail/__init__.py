#
# pyzmail/__init__.py
# (c) Alain Spineux <alain.spineux@gmail.com>
# http://www.magiksys.net/pyzmail
# Released under LGPL

from . import utils
from .generate import compose_mail, send_mail, send_mail2
from .parse import email_address_re, PyzMessage, PzMessage, decode_text
from .parse import message_from_string, message_from_file
from .parse import message_from_bytes, message_from_binary_file # python >= 3.2
from .version import __version__

# to help epydoc to display functions available from top of the package
__all__= [ 'compose_mail', 'send_mail', 'send_mail2', 'email_address_re', \
           'PyzMessage', 'PzMessage', 'decode_text', '__version__', 
           'utils', 'generate', 'parse', 'version',
           'message_from_string','message_from_file',
           'message_from_binary_file', 'message_from_bytes', # python >= 3.2
           ]

