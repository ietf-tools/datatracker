from django.conf.urls import url

urlpatterns = [
    url(r'^$', 'ietf.secr.announcement.views.main', name='announcement'),
    url(r'^confirm/$', 'ietf.secr.announcement.views.confirm', name='announcement_confirm'),
]
