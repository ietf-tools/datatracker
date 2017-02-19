

from ietf.dbtemplate import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^(?P<acronym>[-a-z0-9]+)/$', views.template_list, name='template_list'),
    url(r'^(?P<acronym>[-a-z0-9]+)/(?P<template_id>[\d]+)/$', views.template_edit, name='template_edit'),
]
