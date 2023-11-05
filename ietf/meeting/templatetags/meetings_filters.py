# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

from django import template
from ietf.meeting.helpers import can_request_interim_meeting

import debug                            # pyflakes:ignore

register = template.Library()

@register.filter
def can_request_interim(user):
    """Determine whether the user can request an interim meeting

    Usage: can_request_interim
        Returns Boolean. True means user can request an interim meeting.
    """

    if not user:
        return False
    return can_request_interim_meeting(user)
