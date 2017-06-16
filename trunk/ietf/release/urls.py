# Copyright The IETF Trust 2016, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from django.views.generic import TemplateView

from ietf.release import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$',  views.release),
    url(r'^(?P<version>[0-9.]+.*)/$',  views.release),
    url(r'^about/?$',  TemplateView.as_view(template_name='release/about.html')),
    url(r'^stats/?$',  views.stats),
    url(r'^todo/?$',  TemplateView.as_view(template_name='release/todo.html')),
]

