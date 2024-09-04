from ietf.person import views, ajax
from ietf.utils.urls import url

urlpatterns = [
    url(r'^merge/?$', views.merge),
    url(r'^search/(?P<model_name>(person|email))/$', views.ajax_select2_search),
    url(r'^(?P<personid>[0-9]+)/email.json$', ajax.person_email_json),
    url(r'^(?P<email_or_name>[^/]+)$', views.profile),
    url(r'^(?P<email_or_name>[^/]+)/photo/?$', views.photo),
]
