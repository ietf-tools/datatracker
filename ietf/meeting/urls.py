# Copyright The IETF Trust 2007-2024, All Rights Reserved

from django.conf import settings
from django.urls import include
from django.views.generic import RedirectView

from ietf.meeting import views, views_proceedings
from ietf.utils.urls import url

class AgendaRedirectView(RedirectView):
    ignore_kwargs = ('owner', 'name')
    def get_redirect_url(self, *args, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v is not None and k not in self.ignore_kwargs}
        return super().get_redirect_url(*args, **kwargs)

safe_for_all_meeting_types = [
    url(r'^session/(?P<acronym>[-a-z0-9]+)/?$',  views.session_details),
    url(r'^session/(?P<session_id>\d+)/drafts$',  views.add_session_drafts),
    url(r'^session/(?P<session_id>\d+)/attendance$', views.session_attendance),
    url(r'^session/(?P<session_id>\d+)/bluesheets$', views.upload_session_bluesheets),
    url(r'^session/(?P<session_id>\d+)/minutes$', views.upload_session_minutes),
    url(r'^session/(?P<session_id>\d+)/narrativeminutes$', views.upload_session_narrativeminutes),
    url(r'^session/(?P<session_id>\d+)/agenda$', views.upload_session_agenda),
    url(r'^session/(?P<session_id>\d+)/import/minutes$', views.import_session_minutes),
    url(r'^session/(?P<session_id>\d+)/slides(?:/%(name)s)?$' % settings.URL_REGEXPS, views.upload_session_slides),
    url(r'^session/(?P<session_id>\d+)/add_to_session$', views.ajax_add_slides_to_session),
    url(r'^session/(?P<session_id>\d+)/remove_from_session$', views.ajax_remove_slides_from_session),
    url(r'^session/(?P<session_id>\d+)/reorder_in_session$', views.ajax_reorder_slides_in_session),
    url(r'^session/(?P<session_id>\d+)/doc/%(name)s/remove$' % settings.URL_REGEXPS, views.remove_sessionpresentation),
    url(r'^session/(?P<session_id>\d+)\.ics$',    views.agenda_ical),
    url(r'^sessions/(?P<acronym>[-a-z0-9]+)\.ics$', views.agenda_ical),
    url(r'^slidesubmission/(?P<slidesubmission_id>\d+)$', views.approve_proposed_slides)
]


type_ietf_only_patterns = [
    url(r'^agenda/%(owner)s/%(schedule_name)s/edit/?$' % settings.URL_REGEXPS, views.edit_meeting_schedule),
    url(r'^agenda/%(owner)s/%(schedule_name)s/timeslots/$' % settings.URL_REGEXPS, views.edit_meeting_timeslots_and_misc_sessions),
    url(r'^agenda/%(owner)s/%(schedule_name)s/details$' % settings.URL_REGEXPS, views.edit_schedule_properties),
    url(r'^agenda/%(owner)s/%(schedule_name)s/delete$' % settings.URL_REGEXPS, views.delete_schedule),
    url(r'^agenda/%(owner)s/%(schedule_name)s/make_official$' % settings.URL_REGEXPS, views.make_schedule_official),
    url(r'^agenda/%(owner)s/%(schedule_name)s(\.(?P<ext>.html))?/?$' % settings.URL_REGEXPS, views.agenda),
    url(r'^agenda/%(owner)s/%(schedule_name)s/week-view(?:.html)?/?$' % settings.URL_REGEXPS, AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^agenda/%(owner)s/%(schedule_name)s/by-room/?$' % settings.URL_REGEXPS, AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^agenda/%(owner)s/%(schedule_name)s/by-type/?$' % settings.URL_REGEXPS, AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^agenda/%(owner)s/%(schedule_name)s/by-type/(?P<type>[a-z]+)$' % settings.URL_REGEXPS, AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^agenda/%(owner)s/%(schedule_name)s/new/$' % settings.URL_REGEXPS, views.new_meeting_schedule),
    url(r'^agenda/by-type/(?P<type>[a-z]+)/ics$', views.agenda_by_type_ics),
    url(r'^agenda/personalize', views.agenda, name='agenda-personalize'),
    url(r'^agendas/list$', views.list_schedules),
    url(r'^agendas/edit$', RedirectView.as_view(pattern_name='ietf.meeting.views.list_schedules', permanent=True)),
    url(r'^agendas/diff/$', views.diff_schedules),
    url(r'^agenda/new/$', views.new_meeting_schedule),
    url(r'^timeslots/edit/?$',                     views.edit_timeslots),
    url(r'^timeslot/new$',                       views.create_timeslot),
    url(r'^timeslot/(?P<slot_id>\d+)/edit$',     views.edit_timeslot),
    url(r'^timeslot/(?P<slot_id>\d+)/edittype$', views.edit_timeslot_type),
    url(r'^agenda/(?P<acronym>[-a-z0-9]+)-drafts.pdf$', views.session_draft_pdf),
    url(r'^agenda/(?P<acronym>[-a-z0-9]+)-drafts.tgz$', views.session_draft_tarfile),
]

# This is a limited subset of the list above -- many of the views above won't work for interim meetings
type_interim_patterns = [
    url(r'^agenda/(?P<acronym>[A-Za-z0-9-]+)-drafts.pdf$', views.session_draft_pdf),
    url(r'^agenda/(?P<acronym>[A-Za-z0-9-]+)-drafts.tgz$', views.session_draft_tarfile),
    url(r'^materials/%(document)s((?P<ext>\.[a-z0-9]+)|/)?$' % settings.URL_REGEXPS, views.materials_document),
    url(r'^agenda.json$', views.agenda_json)
]

type_ietf_only_patterns_id_optional = [
    url(r'^agenda(?P<utc>-utc)?(?P<ext>\.html)?/?$', views.agenda, name='agenda'),
    url(r'^agenda(?P<utc>-utc)?(?P<ext>\.txt|\.csv)$', views.agenda_plain),
    url(r'^agenda/edit$',
        RedirectView.as_view(pattern_name='ietf.meeting.views.edit_meeting_schedule', permanent=True),
        name='ietf.meeting.views.edit_meeting_schedule'),
    url(r'^agenda/edit/$', views.edit_meeting_schedule),
    url(r'^requests$', views.meeting_requests),
    url(r'^agenda/agenda\.ics$', views.agenda_ical),
    url(r'^agenda\.ics$', views.agenda_ical),
    url(r'^agenda.json$', views.agenda_json),
    url(r'^agenda/week-view(?:.html)?/?$', AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^floor-plan/?$', views.agenda, name='floor-plan'),
    url(r'^week-view(?:.html)?/?$', AgendaRedirectView.as_view(pattern_name='agenda', permanent=True)),
    url(r'^materials(?:.html)?/?$', views.materials),
    url(r'^request_minutes/?$', views.request_minutes),
    url(r'^materials/%(document)s(?P<ext>\.[a-z0-9]+)?/?$' % settings.URL_REGEXPS, views.materials_document),
    url(r'^session/?$', views.materials_editable_groups),
    url(r'^proceedings(?:.html)?/?$', views.proceedings),
    url(r'^proceedings(?:.html)?/finalize/?$', views.finalize_proceedings),
    url(r'^proceedings/acknowledgements/$', views.proceedings_acknowledgements),
    url(r'^proceedings/attendees/$', views.proceedings_attendees),
    url(r'^proceedings/overview/$', views.proceedings_overview),
    url(r'^proceedings/activity-report/$', views.proceedings_activity_report),
    url(r'^proceedings/materials/$', views_proceedings.material_details),
    url(r'^proceedings/materials/(?P<material_type>[a-z_]+)/$', views_proceedings.edit_material),
    url(r'^proceedings/materials/(?P<material_type>[a-z_]+)/new/$', views_proceedings.upload_material),
    url(r'^proceedings/materials/(?P<material_type>[a-z_]+)/remove/$',
        views_proceedings.remove_restore_material,
        {'action': 'remove'},
        'ietf.meeting.views_proceedings.remove_material'),
    url(r'^proceedings/materials/(?P<material_type>[a-z_]+)/restore/$',
        views_proceedings.remove_restore_material,
        {'action': 'restore'},
        'ietf.meeting.views_proceedings.restore_material'),
    url(r'^important-dates/$', views.important_dates),
    url(r'^important-dates.(?P<output_format>ics)$', views.important_dates),
    url(r'^proceedings/meetinghosts/edit/', views_proceedings.edit_meetinghosts),
    url(r'^proceedings/meetinghosts/(?P<host_id>\d+)/logo/$', views_proceedings.meetinghost_logo),
]

urlpatterns = [
    # First patterns which start with unique strings
    url(r'^$', views.current_materials),
    url(r'^interim/announce/?$', views.interim_announce),
    url(r'^interim/announce/(?P<number>[A-Za-z0-9._+-]+)/?$', views.interim_send_announcement),
    url(r'^interim/skip_announce/(?P<number>[A-Za-z0-9._+-]+)/?$', views.interim_skip_announcement),
    url(r'^interim/request/?$', views.interim_request),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/?$', views.interim_request_details),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/edit/?$', views.interim_request_edit),
    url(r'^interim/request/(?P<number>[A-Za-z0-9._+-]+)/cancel/?$', views.interim_request_cancel),
    url(r'^interim/session/(?P<sessionid>[A-Za-z0-9._+-]+)/cancel/?$', views.interim_request_session_cancel),
    url(r'^interim/pending/?$', views.interim_pending),
    url(r'^requests.html$', RedirectView.as_view(url='/meeting/requests', permanent=True)),
    url(r'^past/?$', views.past),
    url(r'^upcoming/?$', views.upcoming),
    url(r'^upcoming\.ics/?$', views.upcoming_ical),
    url(r'^upcoming\.json/?$', views.upcoming_json),
    url(r'^session/(?P<session_id>\d+)/agenda_materials$', views.session_materials),
    url(r'^session/(?P<session_id>\d+)/cancel/?', views.cancel_session),
    url(r'^session/(?P<session_id>\d+)/edit/?', views.edit_session),
    # Then patterns from more specific to less
    url(r'^(?P<num>interim-[a-z0-9-]+)/', include(type_interim_patterns)),
    url(r'^(?P<num>\d+)/requests.html$', RedirectView.as_view(url='/meeting/%(num)s/requests', permanent=True)),
    # The optionals have to go first of these two, otherwise the agenda/(owner)/(name)/ patterns match things they shouldn't
    url(r'^(?:(?P<num>\d+)/)?', include(type_ietf_only_patterns_id_optional)),
    url(r'^(?P<num>\d+)/', include(type_ietf_only_patterns)),
    #
    url(r'^(?P<num>\d+)/', include(safe_for_all_meeting_types)),
    url(r'^(?P<num>interim-[a-z0-9-]+)/', include(safe_for_all_meeting_types)),
]

