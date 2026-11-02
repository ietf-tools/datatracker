# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import functools
from urllib.parse import quote as urlquote

from django.urls import reverse
from django.http import HttpResponseRedirect


# Views that use nomcom_private_key_required, which private_key may return to
NOMCOM_PRIVATE_KEY_RETURN_VIEWS = frozenset(
    {
        "ietf.nomcom.views.view_feedback",
        "ietf.nomcom.views.view_feedback_pending",
        "ietf.nomcom.views.view_feedback_unrelated",
        "ietf.nomcom.views.view_feedback_topic",
        "ietf.nomcom.views.view_feedback_nominee",
    }
)


def nomcom_private_key_required(view_func):
    def inner(request, *args, **kwargs):
        year = kwargs.get('year', None)
        if not year:
            raise Exception('View decorated with nomcom_private_key_required must receive a year argument')
        if not 'NOMCOM_PRIVATE_KEY_%s' % year in request.session:
            return HttpResponseRedirect('%s?back_to=%s' % (reverse('ietf.nomcom.views.private_key', None, args=(year, )), urlquote(request.get_full_path())))
        else:
            return view_func(request, *args, **kwargs)
    return functools.update_wrapper(inner, view_func)
