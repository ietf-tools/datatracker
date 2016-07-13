from django.conf.urls import patterns, url


urlpatterns = patterns('ietf.dbtemplate.views',
    url(r'^(?P<acronym>[-a-z0-9]+)/$', 'template_list', name='template_list'),
    url(r'^(?P<acronym>[-a-z0-9]+)/(?P<template_id>[\d]+)/$', 'template_edit', name='template_edit'),
)
