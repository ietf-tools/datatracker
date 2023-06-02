# Copyright The IETF Trust 2023, All Rights Reserved
# -*- coding: utf-8 -*-

def is_ajax(request):
    """Checks whether a request was an AJAX call

    See https://docs.djangoproject.com/en/3.1/releases/3.1/#id2 - this implements the
    exact reproduction of the deprecated method suggested there.
    """
    return request.headers.get("x-requested-with") == "XMLHttpRequest"
