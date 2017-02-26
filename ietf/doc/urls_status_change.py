
from ietf.doc import views_status_change, views_doc
from ietf.utils.urls import url

urlpatterns = [
    url(r'^state/$',                 views_status_change.change_state),
    url(r'^submit/$',                views_status_change.submit),
    url(r'^ad/$',                    views_status_change.edit_ad),
    url(r'^title/$',                 views_status_change.edit_title),
    url(r'^approve/$',               views_status_change.approve),
    url(r'^relations/$',             views_status_change.edit_relations),
    url(r'^last-call/$',             views_status_change.last_call),
    url(r'^telechat/$',              views_doc.telechat_date,            name='ietf.doc.views_doc.telechat_date;status-change'),
    url(r'^notices/$',               views_doc.edit_notify,              name='ietf.doc.views_doc.edit_notify;status-change'),
]


