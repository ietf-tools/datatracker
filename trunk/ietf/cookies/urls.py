# Copyright The IETF Trust 2010, All Rights Reserved

from ietf.cookies import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.preferences),
    url(r'^new_enough/(?P<days>.+)$', views.new_enough),
    url(r'^new_enough/', views.new_enough),
    url(r'^expires_soon/(?P<days>.+)$', views.expires_soon),
    url(r'^expires_soon/', views.expires_soon),
    url(r'^full_draft/(?P<enabled>.+)$', views.full_draft),
    url(r'^full_draft/', views.full_draft),
    url(r'^left_menu/(?P<enabled>.+)$', views.left_menu),
    url(r'^left_menu/', views.left_menu),
]
