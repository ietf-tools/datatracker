from django.contrib import admin
from ietf.name.models import (
    BallotPositionName, ConstraintName, DBTemplateTypeName,
    DocRelationshipName, DocReminderTypeName, DocTagName, DocTypeName,
    DraftSubmissionStateName, FeedbackTypeName, GroupMilestoneStateName,
    GroupStateName, GroupTypeName, IntendedStdLevelName,
    IprDisclosureStateName, IprEventTypeName, IprLicenseTypeName,
    LiaisonStatementEventTypeName, LiaisonStatementPurposeName,
    LiaisonStatementState, LiaisonStatementTagName, MeetingTypeName,
    NomineePositionStateName, RoleName, RoomResourceName, SessionStatusName,
    StdLevelName, StreamName, TimeSlotTypeName, )

class NameAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "desc", "used"]
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

admin.site.register(BallotPositionName, NameAdmin)
admin.site.register(ConstraintName, NameAdmin)
admin.site.register(DBTemplateTypeName, NameAdmin)
admin.site.register(DocReminderTypeName, NameAdmin)
admin.site.register(DocTagName, NameAdmin)
admin.site.register(DraftSubmissionStateName, NameAdmin)
admin.site.register(FeedbackTypeName, NameAdmin)
admin.site.register(GroupMilestoneStateName, NameAdmin)
admin.site.register(GroupStateName, NameAdmin)
admin.site.register(IntendedStdLevelName, NameAdmin)
admin.site.register(IprDisclosureStateName, NameAdmin)
admin.site.register(IprLicenseTypeName, NameAdmin)
admin.site.register(IprEventTypeName, NameAdmin)
admin.site.register(LiaisonStatementState, NameAdmin)
admin.site.register(LiaisonStatementEventTypeName, NameAdmin)
admin.site.register(LiaisonStatementPurposeName, NameAdmin)
admin.site.register(LiaisonStatementTagName, NameAdmin)
admin.site.register(MeetingTypeName, NameAdmin)
admin.site.register(NomineePositionStateName, NameAdmin)
admin.site.register(RoleName, NameAdmin)
admin.site.register(RoomResourceName, NameAdmin)
admin.site.register(SessionStatusName, NameAdmin)
admin.site.register(StdLevelName, NameAdmin)
admin.site.register(StreamName, NameAdmin)
admin.site.register(TimeSlotTypeName, NameAdmin)
