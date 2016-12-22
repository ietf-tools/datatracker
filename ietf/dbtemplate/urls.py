from django.conf.urls import url


urlpatterns = [
    url(r'^(?P<acronym>[-a-z0-9]+)/$', 'ietf.dbtemplate.views.template_list', name='template_list'),
    url(r'^(?P<acronym>[-a-z0-9]+)/(?P<template_id>[\d]+)/$', 'ietf.dbtemplate.views.template_edit', name='template_edit'),
]
