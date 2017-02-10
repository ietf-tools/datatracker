from django.conf.urls import url

from ietf.doc import views_material

urlpatterns = [
    url(r'^(?P<action>state|title|abstract|revise)/$', views_material.edit_material, name="material_edit"),
]

