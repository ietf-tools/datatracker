# Copyright The IETF Trust 2010-2020, All Rights Reserved
from django.contrib import admin

from ietf.name.models import (
    AgendaTypeName, BallotPositionName, ConstraintName, ContinentName, CountryName, DBTemplateTypeName,
    DocRelationshipName, DocReminderTypeName, DocTagName, DocTypeName, DraftSubmissionStateName,
    FeedbackTypeName, FormalLanguageName, GroupMilestoneStateName, GroupStateName, GroupTypeName,
    ImportantDateName, IntendedStdLevelName, IprDisclosureStateName, IprEventTypeName,
    IprLicenseTypeName, LiaisonStatementEventTypeName, LiaisonStatementPurposeName,
    LiaisonStatementState, LiaisonStatementTagName, MeetingTypeName, NomineePositionStateName,
    ReviewRequestStateName, ReviewResultName, ReviewTypeName, RoleName, RoomResourceName,
    SessionStatusName, StdLevelName, StreamName, TimeSlotTypeName, TopicAudienceName,
    DocUrlTagName, ReviewAssignmentStateName, ReviewerQueuePolicyName, TimerangeName,
    ExtResourceName, ExtResourceTypeName, SlideSubmissionStatusName)


from ietf.stats.models import CountryAlias

class NameAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "desc", "used"]
    search_fields = ["slug", "name"]
    prepopulate_from = { "slug": ("name",) }

class DocRelationshipNameAdmin(NameAdmin):
    list_display = ["slug", "name", "revname", "desc", "used"]
admin.site.register(DocRelationshipName, DocRelationshipNameAdmin)
    
class DocTypeNameAdmin(NameAdmin):
    list_display = ["slug", "name", "prefix", "desc", "used"]
admin.site.register(DocTypeName, DocTypeNameAdmin)

class GroupTypeNameAdmin(NameAdmin):
    list_display = ["slug", "name", "verbose_name", "desc", "used"]
admin.site.register(GroupTypeName, GroupTypeNameAdmin)

class CountryAliasInline(admin.TabularInline):
    model = CountryAlias
    extra = 1

class CountryNameAdmin(NameAdmin):
    list_display = ["slug", "name", "continent", "in_eu"]
    list_filter = ["continent", "in_eu"]
    inlines = [CountryAliasInline]
admin.site.register(CountryName, CountryNameAdmin)

class ImportantDateNameAdmin(NameAdmin):
    list_display = ["slug", "name", "desc", "used", "default_offset_days"]
    ordering = ('-used','default_offset_days',)
admin.site.register(ImportantDateName,ImportantDateNameAdmin)

class ExtResourceNameAdmin(NameAdmin):
    list_display = ["slug", "name", "type", "desc", "used",]
admin.site.register(ExtResourceName,ExtResourceNameAdmin)

admin.site.register(AgendaTypeName, NameAdmin)
admin.site.register(BallotPositionName, NameAdmin)
admin.site.register(ConstraintName, NameAdmin)
admin.site.register(ContinentName, NameAdmin)
admin.site.register(DBTemplateTypeName, NameAdmin)
admin.site.register(DocReminderTypeName, NameAdmin)
admin.site.register(DocTagName, NameAdmin)
admin.site.register(DraftSubmissionStateName, NameAdmin)
admin.site.register(FormalLanguageName, NameAdmin)
admin.site.register(FeedbackTypeName, NameAdmin)
admin.site.register(GroupMilestoneStateName, NameAdmin)
admin.site.register(GroupStateName, NameAdmin)
admin.site.register(IntendedStdLevelName, NameAdmin)
admin.site.register(IprDisclosureStateName, NameAdmin)
admin.site.register(IprEventTypeName, NameAdmin)
admin.site.register(IprLicenseTypeName, NameAdmin)
admin.site.register(LiaisonStatementEventTypeName, NameAdmin)
admin.site.register(LiaisonStatementPurposeName, NameAdmin)
admin.site.register(LiaisonStatementState, NameAdmin)
admin.site.register(LiaisonStatementTagName, NameAdmin)
admin.site.register(MeetingTypeName, NameAdmin)
admin.site.register(NomineePositionStateName, NameAdmin)
admin.site.register(ReviewRequestStateName, NameAdmin)
admin.site.register(ReviewAssignmentStateName, NameAdmin)
admin.site.register(ReviewResultName, NameAdmin)
admin.site.register(ReviewerQueuePolicyName, NameAdmin)
admin.site.register(ReviewTypeName, NameAdmin)
admin.site.register(RoleName, NameAdmin)
admin.site.register(RoomResourceName, NameAdmin)
admin.site.register(SessionStatusName, NameAdmin)
admin.site.register(StdLevelName, NameAdmin)
admin.site.register(StreamName, NameAdmin)
admin.site.register(TimeSlotTypeName, NameAdmin)
admin.site.register(TimerangeName, NameAdmin)
admin.site.register(TopicAudienceName, NameAdmin)
admin.site.register(DocUrlTagName, NameAdmin)
admin.site.register(ExtResourceTypeName, NameAdmin)
admin.site.register(SlideSubmissionStatusName, NameAdmin)
