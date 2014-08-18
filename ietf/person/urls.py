from django.conf.urls import patterns
from ietf.person import ajax

urlpatterns = patterns('',
        (r'^search/(?P<model_name>(person|email))/$', "ietf.person.views.ajax_tokeninput_search", None, 'ajax_tokeninput_search'),
        (r'^(?P<personid>[a-z0-9]+).json$', ajax.person_json),
)
