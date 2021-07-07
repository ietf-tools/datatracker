
from ietf.doc import views_bofreq
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/$',                 views_bofreq.change_state),
    url(r'^submit/$',                views_bofreq.submit),
    url(r'^title/$',                 views_bofreq.edit_title),
    url(r'^editors/$',               views_bofreq.change_editors),
    url(r'^responsible/$',           views_bofreq.change_responsible),
]