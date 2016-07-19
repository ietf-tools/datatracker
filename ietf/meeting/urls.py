# Copyright The IETF Trust 2007, All Rights Reserved

from django.conf.urls import url, include
from django.views.generic import RedirectView

from ietf.meeting import views
from ietf.meeting import ajax

safe_for_all_meeting_types = [
    url(r'^session/(?P<acronym>[-a-z0-9]+)/?$',  views.session_details),
    url(r'^session/(?P<session_id>\d+)/drafts$',  views.add_session_drafts),
]

type_ietf_only_patterns = [
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/edit$', views.edit_agenda),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/details$', views.edit_agenda_properties),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/delete$', views.delete_schedule),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/make_official$', views.make_schedule_official),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)(\.(?P<ext>.html))?/?$', views.agenda),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/week-view(?:.html)?/?$', views.week_view),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/room-view(?:.html)?/?$', views.room_view),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/by-room/?$', views.agenda_by_room),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/by-type/?$', views.agenda_by_type),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/by-type/(?P<type>[a-z]+)$', views.agenda_by_type),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/permissions$', ajax.agenda_permission_api),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/session/(?P<assignment_id>\d+).json$', ajax.assignment_json),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+)/sessions.json$',      ajax.assignments_json),
    url(r'^agenda/(?P<owner>[-A-Za-z0-9\'+._]+@[A-Za-z0-9-._]+)/(?P<name>[A-Za-z0-9-:_]+).json$', ajax.agenda_infourl),
    url(r'^agenda/by-room$', views.agenda_by_room),
    url(r'^agenda/by-type$', views.agenda_by_type),
    url(r'^agenda/by-type/(?P<type>[a-z]+)$', views.agenda_by_type),
    url(r'^agenda/by-type/(?P<type>[a-z]+)/ics$', views.agenda_by_type_ics),
    url(r'^agendas/list$', views.list_agendas, name='meeting_list_agendas'),
    url(r'^agendas/edit$', RedirectView.as_view(pattern_name='meeting_list_agendas', permanent=True)),
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
    url(r'^agenda(?P<utc>-utc)?(?P<ext>.html)?/?$',     views.agenda),
    url(r'^agenda(?P<ext>.txt)$', views.agenda),
    url(r'^agenda(?P<ext>.csv)$', views.agenda),
    url(r'^agenda/edit$', views.edit_agenda),
    url(r'^requests$', views.meeting_requests),
    url(r'^agenda/agenda.ics$', views.ical_agenda),
    url(r'^agenda.ics$', views.ical_agenda),
    url(r'^agenda/week-view(?:.html)?/?$', views.week_view),
    url(r'^agenda/room-view(?:.html)?/?$', views.room_view),
    url(r'^floor-plan/?$', views.floor_plan),
    url(r'^floor-plan/(?P<floor>[-a-z0-9_]+)/?$', views.floor_plan),
    url(r'^week-view(?:.html)?/?$', views.week_view),
    url(r'^room-view(?:.html)?/?$', views.room_view),
    url(r'^materials(?:.html)?/?$', views.materials),
    url(r'^proceedings(?:.html)?/?$', views.proceedings),
]

urlpatterns = [
    # First patterns which start with unique strings
    url(r'^$', views.current_materials),
    url(r'^ajax/get-utc/?$', views.ajax_get_utc),
    url(r'^interim/announce/?$', views.interim_announce),
    url(r'^interim/announce/(?P<number>[A-Za-z0-9._+-]+)/?$', views.interim_send_announcement),
    url(r'^interim/request/?$', views.interim_request),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/?$', views.interim_request_details),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/edit/?$', views.interim_request_edit),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/cancel/?$', views.interim_request_cancel),
    url(r'^interim/pending/?$', views.interim_pending),
    url(r'^requests.html$', RedirectView.as_view(url='/meeting/requests', permanent=True)),
    url(r'^upcoming/?$', views.upcoming),
    url(r'^upcoming.ics/?$', views.upcoming_ical),
    # Then patterns from more specific to less
    url(r'^(?P<num>interim-[a-z0-9-]+)/', include(type_ietf_only_patterns)),
    url(r'^(?P<num>\d+)/requests.html$', RedirectView.as_view(url='/meeting/%(num)s/requests', permanent=True)),
    # The optionals have to go first of these two, otherwise the agenda/(owner)/(name)/ patterns match things they shouldn't
    url(r'^(?:(?P<num>\d+)/)?', include(type_ietf_only_patterns_id_optional)),
    url(r'^(?P<num>\d+)/', include(type_ietf_only_patterns)),
    #
    url(r'^(?P<num>\d+)/', include(safe_for_all_meeting_types)),
    url(r'^(?P<num>interim-[a-z0-9-]+)/', include(safe_for_all_meeting_types)),
]

