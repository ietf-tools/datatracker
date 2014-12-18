from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.doc.views_material',
    url(r'^(?P<action>state|title|abstract|revise)/$', "edit_material", name="material_edit"),
    url(r'^sessions/$', "material_presentations", name="material_presentations"),
    (r'^sessions/(?P<seq>\d+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<seq>\d+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<week_day>[a-zA-Z]+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<week_day>[a-zA-Z]+)/(?P<seq>\d+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/(?P<seq>\d+)/edit/$',  "edit_material_presentations"),
    (r'^sessions/(?P<seq>\d+)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<seq>\d+)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<week_day>[a-zA-Z]+)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<week_day>[a-zA-Z]+)/(?P<seq>\d+)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/$',  "material_presentations"),
    (r'^sessions/(?P<acronym>[A-Za-z0-9_\-\+]+)/(?P<date>\d{4}-\d{2}-\d{2}(-\d{4})?)/(?P<seq>\d+)/$',  "material_presentations"),
)

