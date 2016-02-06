# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url, include
from django.views.generic import RedirectView

from ietf.meeting import views
from ietf.meeting import ajax

safe_for_all_meeting_types = [
    url(r'^session/(?P<acronym>[A-Za-z0-9_\-\+]+)/$',  views.session_details),
]

type_ietf_only_patterns = [
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+)/edit$', views.edit_agenda),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+)/details$', views.edit_agenda_properties),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+).(?P<ext>.html)?/?$', views.agenda),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+)/permissions$', ajax.agenda_permission_api),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+)/session/(?P<assignment_id>\d+).json$', ajax.assignment_json),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+)/sessions.json$',      ajax.assignments_json),
    url(r'^agenda/(?P<owner>[A-Za-z0-9-.+_]+@[A-Za-z0-9._]+)/(?P<name>[A-Za-z0-9-:_]+).json$', ajax.agenda_infourl),
    url(r'^agenda/by-room$', views.agenda_by_room),
    url(r'^agenda/by-type$', views.agenda_by_type),
    url(r'^agenda/by-type/(?P<type>[a-z]+)$', views.agenda_by_type),
    url(r'^agenda/by-type/(?P<type>[a-z]+)/ics$', views.agenda_by_type_ics),
    url(r'^agendas/edit$',                       views.edit_agendas),
    url(r'^timeslots/edit$',                     views.edit_timeslots),
    url(r'^rooms$',                              ajax.timeslot_roomsurl),
    url(r'^room/(?P<roomid>\d+).json$',          ajax.timeslot_roomurl),
    url(r'^room/(?P<roomid>\d+)(?:.html)?/?$',          views.edit_roomurl),
    url(r'^timeslots$',                          ajax.timeslot_slotsurl),
    url(r'^timeslots.json$',                     ajax.timeslot_slotsurl),
    url(r'^timeslot/(?P<slotid>\d+).json$',      ajax.timeslot_sloturl),
    url(r'^agendas$',                            ajax.agenda_infosurl),
    url(r'^agendas.json$',                       ajax.agenda_infosurl),
    url(r'^agenda/(?P<session>[A-Za-z0-9-]+)-drafts.pdf$', views.session_draft_pdf),
    url(r'^agenda/(?P<session>[A-Za-z0-9-]+)-drafts.tgz$', views.session_draft_tarfile),
    url(r'^agenda/(?P<session>[A-Za-z0-9-]+)/?$', views.session_agenda),
    url(r'^sessions.json',                               ajax.sessions_json),
    url(r'^session/(?P<sessionid>\d+).json',             ajax.session_json),
    url(r'^session/(?P<sessionid>\d+)/constraints.json', ajax.session_constraints),
    url(r'^constraint/(?P<constraintid>\d+).json',       ajax.constraint_json),
    url(r'^json$',                               ajax.meeting_json),
]

type_ietf_only_patterns_id_optional = [
    url(r'^agenda(-utc)?(?P<ext>.html)?/?$',     views.agenda),
    url(r'^agenda(?P<ext>.txt)$', views.agenda),
    url(r'^agenda(?P<ext>.csv)$', views.agenda),
    url(r'^agenda/edit$', views.edit_agenda),
    url(r'^requests$', views.meeting_requests),
    url(r'^agenda/agenda.ics$', views.ical_agenda),
    url(r'^agenda.ics$', views.ical_agenda),
    url(r'^agenda/week-view(?:.html)?/?$', views.week_view),
    url(r'^agenda/room-view(?:.html)?/?$', views.room_view),
    url(r'^week-view(?:.html)?/?$', views.week_view),
    url(r'^room-view(?:.html)?/$', views.room_view),
]

urlpatterns = [
    # TODO - views.material should take num instead of meeting_num so it can move into one of the above lists
    url(r'^(?P<meeting_num>\d+)/materials(?:.html)?/?$', views.materials),
    url(r'^requests.html$', RedirectView.as_view(url='/meeting/requests', permanent=True)),
    url(r'^(?P<num>\d+)/requests.html$', RedirectView.as_view(url='/meeting/%(num)s/requests', permanent=True)),
    url(r'^(?P<num>[A-Za-z0-9._+-]+)/', include(safe_for_all_meeting_types)),
    # The optionals have to go first, otherwise the agenda/(owner)/(name)/ patterns match things they shouldn't
    url(r'^(?:(?P<num>\d+)/)?', include(type_ietf_only_patterns_id_optional)),
    url(r'^(?P<num>\d+)/', include(type_ietf_only_patterns)),
    url(r'^$', views.current_materials),
]


