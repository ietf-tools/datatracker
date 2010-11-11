# Copyright The IETF Trust 2010, All Rights Reserved

from django.conf.urls.defaults import patterns
from ietf.cookies import views

urlpatterns = patterns('',
     (r'^$', views.settings),
     (r'^new_enough/(?P<days>.*)$', views.new_enough),
     (r'^new_enough/', views.new_enough),
     (r'^expires_soon/(?P<days>.*)$', views.expires_soon),
     (r'^expires_soon/', views.expires_soon),
     (r'^full_draft/(?P<enabled>.*)$', views.full_draft),
     (r'^full_draft/', views.full_draft),
)
