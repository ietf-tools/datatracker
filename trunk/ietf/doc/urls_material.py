
from ietf.doc import views_material
from ietf.utils.urls import url

urlpatterns = [
    url(r'^(?P<action>state|title|abstract|revise)/$', views_material.edit_material),
]

