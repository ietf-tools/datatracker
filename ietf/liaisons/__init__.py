# Copyright The IETF Trust 2007, All Rights Reserved
# coding: latin-1

from types import ModuleType
import urls, models, views, forms, accounts, admin, utils, widgets, decorators, sitemaps, feeds

# These people will be sent a stack trace if there's an uncaught exception in
# code any of the modules imported above:
DEBUG_EMAILS = [
    ('Emilio A. Sánchez', 'esanchez@yaco.es'),
]

for k in locals().keys():
    m = locals()[k]
    if isinstance(m, ModuleType):
        if hasattr(m, "DEBUG_EMAILS"):
            DEBUG_EMAILS += list(getattr(m, "DEBUG_EMAILS"))
        setattr(m, "DEBUG_EMAILS", DEBUG_EMAILS)

