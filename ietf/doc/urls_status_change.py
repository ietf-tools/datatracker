from django.conf.urls import url

urlpatterns = [
    url(r'^state/$',                 "ietf.doc.views_status_change.change_state",   name='status_change_change_state'),
    url(r'^submit/$',                "ietf.doc.views_status_change.submit",         name='status_change_submit'),
    url(r'^ad/$',                    "ietf.doc.views_status_change.edit_ad",        name='status_change_ad'),
    url(r'^title/$',                 "ietf.doc.views_status_change.edit_title",     name='status_change_title'),
    url(r'^approve/$',               "ietf.doc.views_status_change.approve",        name='status_change_approve'),
    url(r'^relations/$',             "ietf.doc.views_status_change.edit_relations", name='status_change_relations'),
    url(r'^last-call/$',             "ietf.doc.views_status_change.last_call",      name='status_change_last_call'),
    url(r'^telechat/$',              "ietf.doc.views_doc.telechat_date",  name='status_change_telechat_date'),
    url(r'^notices/$',               "ietf.doc.views_doc.edit_notify",   name='status_change_notices'),
]


