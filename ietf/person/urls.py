from ietf.person import views, ajax
from ietf.utils.urls import url

urlpatterns = [
    url(r'^merge/?$', views.merge),
    url(r'^search/(?P<model_name>(person|email))/$', views.ajax_select2_search),
    url(r'^(?P<personid>[0-9]+)/email.json$', ajax.person_email_json),
    url(r'^(?P<email_or_name>[^/]+)$', views.profile),
    url(r'^(?P<email_or_name>[^/]+)/photo/?$', views.photo),
    url(r'^sleepy/write/$', views.sleepy_write),
    url(r'^sleepy/pgwrite/$', views.pg_sleep_write),
    url(r'^sleepy/pgwrite2/$', views.pg_sleep_write2),
    url(r'^(?P<frag>[a-z]+)/sleepy/$', views.very_sleepy_view),
    url(r'^(?P<frag>[a-z]+)/pgsleep/$', views.pg_sleep_view),
]
