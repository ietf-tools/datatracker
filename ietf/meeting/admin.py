# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin

from ietf.meeting.models import (Attended, Meeting, Room, Session, TimeSlot, Constraint, Schedule,
    SchedTimeSessAssignment, ResourceAssociation, FloorPlan, UrlResource,
    SessionPresentation, ImportantDate, SlideSubmission, SchedulingEvent, BusinessConstraint,
    ProceedingsMaterial, MeetingHost)


class UrlResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'room', 'url', ]
    list_filter = ['name', 'room__meeting', ]
    raw_id_fields = ['room', ]
admin.site.register(UrlResource, UrlResourceAdmin)

class UrlResourceInline(admin.TabularInline):
    model = UrlResource

class RoomAdmin(admin.ModelAdmin):
    list_display = ["id", "meeting", "name", "capacity", "functional_name", "x1", "y1", "x2", "y2", ]
    list_filter = ["meeting"]
    inlines = [UrlResourceInline, ]

admin.site.register(Room, RoomAdmin)

class RoomInline(admin.TabularInline):
    model = Room

class MeetingAdmin(admin.ModelAdmin):
    list_display = ["number", "type", "date", "location", "time_zone"]
    list_filter = ["type"]
    search_fields = ["number"]
    inlines = [RoomInline]

    def location(self, instance):
        loc = []
        if instance.city:
            loc.append(instance.city)
        if instance.country:
            loc.append(instance.get_country_display())

        return ", ".join(loc)

admin.site.register(Meeting, MeetingAdmin)


class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["meeting", "type", "name", "time", "duration", "location", "session_desc"]
    list_filter = ["meeting", ]
    raw_id_fields = ["location"]
    ordering = ["-time"]

    def session_desc(self, instance):
        if instance.session:
            if instance.session.name:
                return instance.session.name
            elif instance.session.group:
                return "%s (%s)" % (instance.session.group.name, instance.session.group.acronym)

        return ""
    session_desc.short_description = "session" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(TimeSlot, TimeSlotAdmin)


class BusinessConstraintAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "penalty"]
    search_fields = ["slug", "name"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "businessconstraint" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(BusinessConstraint, BusinessConstraintAdmin)


class ConstraintAdmin(admin.ModelAdmin):
    list_display = ["meeting", "source", "name_lower", "target"]
    raw_id_fields = ["meeting", "source", "target"]
    search_fields = ["source__name", "source__acronym", "target__name", "target__acronym"]
    ordering = ["-meeting__date"]

    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(Constraint, ConstraintAdmin)

class SchedulingEventInline(admin.TabularInline):
    model = SchedulingEvent
    raw_id_fields = ["by"]

class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "meeting", "name", "group_acronym", "purpose", "attendees", "has_onsite_tool", "chat_room", "requested", "current_status"
    ]
    list_filter = ["purpose", "meeting", ]
    raw_id_fields = ["meeting", "group", "materials", "joint_with_groups", "tombstone_for"]
    search_fields = ["meeting__number", "name", "group__name", "group__acronym", "purpose__name"]
    ordering = ["-id"]
    inlines = [SchedulingEventInline]


    def get_queryset(self, request):
        qs = super(SessionAdmin, self).get_queryset(request)
        return qs.prefetch_related('schedulingevent_set')

    def group_acronym(self, instance):
        return instance.group and instance.group.acronym

    def current_status(self, instance):
        events = sorted(instance.schedulingevent_set.all(), key=lambda e: (e.time, e.id))
        if events:
            return f'{events[-1].status} ({events[-1].time:%Y-%m-%d %H:%M})'
        else:
            return None

    def requested(self, instance):
        events = sorted(instance.schedulingevent_set.all(), key=lambda e: (e.time, e.id))
        if events:
            return events[0].time
        else:
            return None
        
    def name_lower(self, instance):
        return instance.name.name.lower()

    name_lower.short_description = "constraint name" # type: ignore # https://github.com/python/mypy/issues/2087

admin.site.register(Session, SessionAdmin)

class SchedulingEventAdmin(admin.ModelAdmin):
    list_display = ["session", "status", "time", "by"]
    raw_id_fields = ["session", "by"]
    search_fields = ['session__name', 'session__meeting__number', 'session__group__acronym']
    ordering = ["-id"]

admin.site.register(SchedulingEvent, SchedulingEventAdmin)

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ["name", "meeting", "owner", "visible", "public", "badness"]
    list_filter = ["meeting"]
    raw_id_fields = ["meeting", "owner", "origin", "base"]
    search_fields = ["meeting__number", "name", "owner__name"]
    ordering = ["-meeting", "name"]

admin.site.register(Schedule, ScheduleAdmin)


class SchedTimeSessAssignmentAdmin(admin.ModelAdmin):
    list_display = ["id", "schedule", "timeslot", "session", "modified"]
    list_filter = ["timeslot__meeting", "session__group__acronym"]
    raw_id_fields = ["timeslot", "session", "schedule", "extendedfrom", ]
    search_fields = ["session__group__acronym", "schedule__name", ]

admin.site.register(SchedTimeSessAssignment, SchedTimeSessAssignmentAdmin)


class ResourceAssociationAdmin(admin.ModelAdmin):
    def used(self, instance):
        return instance.name.used
    used.boolean = True                 # type: ignore # https://github.com/python/mypy/issues/2087

    list_display = ["name", "icon", "used", "desc"]
admin.site.register(ResourceAssociation, ResourceAssociationAdmin)

class FloorPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'meeting', 'name', 'short', 'order', 'image', ]
    raw_id_fields = ['meeting', ]
admin.site.register(FloorPlan, FloorPlanAdmin)

class SessionPresentationAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'document', 'rev', 'order', ]
    list_filter = ['session__meeting', 'document__group__acronym', ]
    raw_id_fields = ['document', 'session', ]
admin.site.register(SessionPresentation, SessionPresentationAdmin)

class ImportantDateAdmin(admin.ModelAdmin):
    model = ImportantDate
    list_filter = ['meeting', ]
    list_display = ['meeting', 'name', 'date']
admin.site.register(ImportantDate,ImportantDateAdmin)

class SlideSubmissionAdmin(admin.ModelAdmin):
    model = SlideSubmission
    list_display = ['session', 'submitter', 'title']
    raw_id_fields = ['submitter', 'session', 'doc']

admin.site.register(SlideSubmission, SlideSubmissionAdmin)


class ProceedingsMaterialAdmin(admin.ModelAdmin):
    model = ProceedingsMaterial
    list_display = ['meeting', 'type', 'document']
    raw_id_fields = ['meeting', 'document']
admin.site.register(ProceedingsMaterial, ProceedingsMaterialAdmin)


class MeetingHostAdmin(admin.ModelAdmin):
    model = MeetingHost
    list_display = ['name', 'meeting']
    raw_id_fields = ['meeting']
admin.site.register(MeetingHost, MeetingHostAdmin)

class AttendedAdmin(admin.ModelAdmin):
    model = Attended
    list_display= ["id", "person", "session"]
    search_fields = ["person__name", "session__group__acronym", "session__meeting__number", "session__name", "session__purpose__name"]
    raw_id_fields= ["person", "session"]
admin.site.register(Attended, AttendedAdmin)
