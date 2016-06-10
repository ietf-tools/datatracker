from django.conf.urls import patterns
from ietf.person import views, ajax

urlpatterns = patterns('',
        (r'^search/(?P<model_name>(person|email))/$', "ietf.person.views.ajax_select2_search", None, 'ajax_select2_search_person_email'),
        (r'^(?P<personid>[a-z0-9]+).json$', ajax.person_json),
        (ur'^(?P<email_or_name>[\w\s]+)', views.profile),
)
