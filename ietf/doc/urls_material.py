from django.conf.urls import patterns, url
from django.conf import settings

urlpatterns = patterns('ietf.doc.views_material',
    url(r'^(?P<action>state|title|abstract|revise)/$', "edit_material", name="material_edit"),
    url(r'^sessions/$', "material_presentations", name="material_presentations"),
    (r'^sessions/(?P<seq>\d+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/(?P<seq>\d+)/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/(?P<week_day>[a-zA-Z]+)/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/(?P<week_day>[a-zA-Z]+)/(?P<seq>\d+)/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/%(acronym)s/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/(?P<seq>\d+)/edit/$' % settings.URL_REGEXPS,  "edit_material_presentations"),
    (r'^sessions/(?P<seq>\d+)/$',  "material_presentations"),
    (r'^sessions/%(acronym)s/$' % settings.URL_REGEXPS,  "material_presentations"),
    (r'^sessions/%(acronym)s/(?P<seq>\d+)/$' % settings.URL_REGEXPS,  "material_presentations"),
    (r'^sessions/%(acronym)s/(?P<week_day>[a-zA-Z]+)/$' % settings.URL_REGEXPS,  "material_presentations"),
    (r'^sessions/%(acronym)s/(?P<week_day>[a-zA-Z]+)/(?P<seq>\d+)/$' % settings.URL_REGEXPS,  "material_presentations"),
    (r'^sessions/%(acronym)s/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/$' % settings.URL_REGEXPS,  "material_presentations"),
    (r'^sessions/%(acronym)s/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/(?P<seq>\d+)/$' % settings.URL_REGEXPS,  "material_presentations"),
)

