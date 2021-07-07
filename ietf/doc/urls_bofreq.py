
from ietf.doc import views_bofreq, views_doc
from ietf.utils.urls import url

urlpatterns = [
    url(r'^notices/$',               views_doc.edit_notify,              name='ietf.doc.views_doc.edit_notify;bofreq'),
    url(r'^relations/$',             views_bofreq.edit_relations),
    url(r'^state/$',                 views_bofreq.change_state),
    url(r'^submit/$',                views_bofreq.submit),
    url(r'^title/$',                 views_bofreq.edit_title),
    url(r'^editors/$',               views_bofreq.change_editors),
    url(r'^responsible/$',           views_bofreq.change_responsible),
]