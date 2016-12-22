from django.conf.urls import url

urlpatterns = [
    url(r'^(?P<action>state|title|abstract|revise)/$', "ietf.doc.views_material.edit_material", name="material_edit"),
]

