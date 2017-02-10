from django.conf.urls import url
from ietf.person import views, ajax

urlpatterns = [
    url(r'^search/(?P<model_name>(person|email))/$', views.ajax_select2_search, None, 'ajax_select2_search_person_email'),
    url(r'^(?P<personid>[a-z0-9]+).json$', ajax.person_json),
    url(ur'^(?P<email_or_name>[-\w\s\']+)', views.profile),
]
