# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.exceptions import PermissionDenied
from django.utils.safestring import mark_safe

def permission_denied(request, msg):
    "A wrapper around the PermissionDenied exception"
    msg += "  <br/>You can <a href='/accounts/login?next=%s'><u>Log in</u></a> if you have that role but aren't logged in." % request.path
    raise PermissionDenied(mark_safe(msg))
