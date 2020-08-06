# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.exceptions import PermissionDenied
from django.utils.safestring import mark_safe

def permission_denied(request, msg):
    "A wrapper around the PermissionDenied exception"
    if not request.user.is_authenticated:
        msg += "  <br/>You may want to <a href='/accounts/login?next=%s'><u>Log in</u></a> if you have a datatracker role that lets you access this page." % request.path
    raise PermissionDenied(mark_safe(msg))
