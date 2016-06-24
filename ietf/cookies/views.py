# Copyright The IETF Trust 2010, All Rights Reserved

from django.shortcuts import render_to_response as render
from django.template import RequestContext
from django.conf import settings

import debug                            # pyflakes:ignore

def preferences(request, **kwargs):
    preferences = request.COOKIES.copy()
    new_cookies = {}
    del_cookies = []
    for key in settings.USER_PREFERENCE_DEFAULTS.keys():
        if key in kwargs:
            if kwargs[key] == None:
                del_cookies += [key]
            else:
                # ignore bad kwargs
                if key in ['new_enough', 'expires_soon'] and not kwargs[key].isdigit():
                    pass
                elif key in ['full_draft', 'left_menu'] and not kwargs[key] in ['on', 'off']:
                    pass
                else:
                    preferences[key] = new_cookies[key] = kwargs[key]
        if not key in preferences or preferences[key] in [None, 'None', ''] or key in del_cookies:
            preferences[key] = settings.USER_PREFERENCE_DEFAULTS[key]
        # reset bad cookie values
        if key in ['new_enough', 'expires_soon'] and not preferences[key].isdigit():
            preferences[key] = settings.USER_PREFERENCE_DEFAULTS[key]
            del_cookies += [key]
        elif key in ['full_draft', 'left_menu'] and not preferences[key] in ['on', 'off']:
            preferences[key] = settings.USER_PREFERENCE_DEFAULTS[key]
            del_cookies += [key]
    request.COOKIES.update(preferences)
    response = render("cookies/settings.html", preferences, context_instance=RequestContext(request))
    for key in new_cookies:
        response.set_cookie(key, new_cookies[key], settings.PREFERENCES_COOKIE_AGE)
    for key in del_cookies:
        response.delete_cookie(key)
    return response

def new_enough(request, days=None):
    return preferences(request, new_enough=days)

def expires_soon(request, days=None):
    return preferences(request, expires_soon=days)


def full_draft(request, enabled=None):
    return preferences(request, full_draft=enabled)

def left_menu(request, enabled=None):
    return preferences(request, left_menu=enabled)

