from django.conf.urls import patterns, url

urlpatterns = patterns('ietf.doc.views_material',
    url(r'^(?P<action>state|title|abstract|revise)/$', "edit_material", name="material_edit"),
    url(r'^sessions/$', "material_presentations", name="material_presentations"),
)

