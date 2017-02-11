from ietf.person import views, ajax
from ietf.utils.urls import url

urlpatterns = [
    url(r'^search/(?P<model_name>(person|email))/$', views.ajax_select2_search),
    url(r'^(?P<personid>[a-z0-9]+).json$', ajax.person_json),
    url(ur'^(?P<email_or_name>[-\w\s\']+)', views.profile),
]
