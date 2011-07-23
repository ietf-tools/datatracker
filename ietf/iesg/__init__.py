# Copyright The IETF Trust 2007, All Rights Reserved
# coding: latin-1

from types import ModuleType
import urls, models, views, feeds, admin

# These people will be sent a stack trace if there's an uncaught exception in
# code any of the modules imported above:
DEBUG_EMAILS = [
    ('Ole Laursen', 'olau@iola.dk'),
]

for k in locals().keys():
    m = locals()[k]
    if isinstance(m, ModuleType):
        if hasattr(m, "DEBUG_EMAILS"):
            DEBUG_EMAILS += list(getattr(m, "DEBUG_EMAILS"))
        setattr(m, "DEBUG_EMAILS", DEBUG_EMAILS)


