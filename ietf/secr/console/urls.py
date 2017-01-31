from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.console.views.main', name='console'),
]
