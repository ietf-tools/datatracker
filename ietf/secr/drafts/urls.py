
from ietf.secr.drafts import views
from ietf.utils.urls import url

urlpatterns = [
    url(r'^$', views.search, name='drafts'),
    url(r'^add/$', views.add, name='drafts_add'),
    url(r'^approvals/$', views.approvals, name='drafts_approvals'),
    url(r'^dates/$', views.dates, name='drafts_dates'),
    url(r'^nudge-report/$', views.nudge_report, name='drafts_nudge_report'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/$', views.view, name='drafts_view'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/abstract/$', views.abstract, name='drafts_abstract'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/announce/$', views.announce, name='drafts_announce'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/authors/$', views.authors, name='drafts_authors'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/author_delete/(?P<oid>\d{1,6})$', views.author_delete, name='drafts_author_delete'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/confirm/$', views.confirm, name='drafts_confirm'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/edit/$', views.edit, name='drafts_edit'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/extend/$', views.extend, name='drafts_extend'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/email/$', views.email, name='drafts_email'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/makerfc/$', views.makerfc, name='drafts_makerfc'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/replace/$', views.replace, name='drafts_replace'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/resurrect/$', views.resurrect, name='drafts_resurrect'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/revision/$', views.revision, name='drafts_revision'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/update/$', views.update, name='drafts_update'),
    url(r'^(?P<id>[A-Za-z0-9._\-\+]+)/withdraw/$', views.withdraw, name='drafts_withdraw'),
]