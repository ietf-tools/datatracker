#coding: utf-8
from django.contrib import admin
from ietf.idtracker.models import *
                
class AcronymAdmin(admin.ModelAdmin):
    list_display=('acronym', 'name')
admin.site.register(Acronym, AcronymAdmin)

class AreaAdmin(admin.ModelAdmin):
    list_display=('area_acronym', 'status')
admin.site.register(Area, AreaAdmin)

class AreaDirectorAdmin(admin.ModelAdmin):
    raw_id_fields=['person']
admin.site.register(AreaDirector, AreaDirectorAdmin)

class AreaStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(AreaStatus, AreaStatusAdmin)

class AreaWGURLAdmin(admin.ModelAdmin):
    pass
admin.site.register(AreaWGURL, AreaWGURLAdmin)

class BallotInfoAdmin(admin.ModelAdmin):
    pass
admin.site.register(BallotInfo, BallotInfoAdmin)

class ChairsHistoryAdmin(admin.ModelAdmin):
    list_display=('person', 'chair_type', 'start_year', 'end_year')
admin.site.register(ChairsHistory, ChairsHistoryAdmin)

class DocumentCommentAdmin(admin.ModelAdmin):
    ordering=['-date']
    list_display=('pk', 'doc_id', 'date', 'time', 'comment_text')
admin.site.register(DocumentComment, DocumentCommentAdmin)

class EmailAddressAdmin(admin.ModelAdmin):
    list_display=('id', 'person_link', 'address', 'type', 'priority_link')
    search_fields=['address']
    raw_id_fields=['person_or_org', ]
admin.site.register(EmailAddress, EmailAddressAdmin)

class GoalMilestoneAdmin(admin.ModelAdmin):
    list_display=('group_acronym', 'description', 'expected_due_date', 'done')
    date_hierarchy='expected_due_date'
    list_filter=['done']
admin.site.register(GoalMilestone, GoalMilestoneAdmin)

class IDIntendedStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(IDIntendedStatus, IDIntendedStatusAdmin)

class IDInternalAdmin(admin.ModelAdmin):
    ordering=['draft']
    list_display=['draft', 'token_email', 'note']
    search_fields=['draft__filename']
    raw_id_fields=['draft','ballot']
admin.site.register(IDInternal, IDInternalAdmin)

class IDNextStateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IDNextState, IDNextStateAdmin)

class IDStateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IDState, IDStateAdmin)

class IDStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(IDStatus, IDStatusAdmin)

class IDSubStateAdmin(admin.ModelAdmin):
    pass
admin.site.register(IDSubState, IDSubStateAdmin)

class IESGCommentAdmin(admin.ModelAdmin):
    raw_id_fields = ['ballot','ad']
admin.site.register(IESGComment, IESGCommentAdmin)

class IESGDiscussAdmin(admin.ModelAdmin):
    raw_id_fields = ['ballot','ad']
admin.site.register(IESGDiscuss, IESGDiscussAdmin)

class IESGLoginAdmin(admin.ModelAdmin):
    ordering=['user_level', 'last_name']
    list_display=('login_name', 'first_name', 'last_name', 'user_level')
    raw_id_fields=['person']
admin.site.register(IESGLogin, IESGLoginAdmin)

class IETFWGAdmin(admin.ModelAdmin):
    list_display=('group_acronym', 'group_type', 'status', 'area_acronym', 'start_date', 'concluded_date', 'chairs_link')
    search_fields=['group_acronym__acronym', 'group_acronym__name']
    list_filter=['status', 'group_type']
admin.site.register(IETFWG, IETFWGAdmin)

class WGChairAdmin(admin.ModelAdmin):
    list_display = ('person_link', 'group_link')
admin.site.register(WGChair, WGChairAdmin)

class IRTFAdmin(admin.ModelAdmin):
    pass
admin.site.register(IRTF, IRTFAdmin)

class InternetDraftAdmin(admin.ModelAdmin):
    list_display=('filename', 'revision', 'title', 'status')
    search_fields=['filename', 'title']
    list_filter=['status']
    raw_id_fields=['replaced_by']
admin.site.register(InternetDraft, InternetDraftAdmin)

class PersonOrOrgInfoAdmin(admin.ModelAdmin):
    list_display = ['person_or_org_tag', 'last_name', 'first_name', ]
    fieldsets=((None, {'fields': (('first_name', 'middle_initial', 'last_name'), ('name_suffix', 'modified_by'))}), ('Obsolete Info', {'fields': ('record_type', 'created_by', 'address_type'), 'classes': 'collapse'}))
    search_fields=['first_name', 'last_name']
admin.site.register(PersonOrOrgInfo, PersonOrOrgInfoAdmin)

class PositionAdmin(admin.ModelAdmin):
    raw_id_fields=['ballot','ad']
admin.site.register(Position, PositionAdmin)

class RfcAdmin(admin.ModelAdmin):
    fieldsets=((None, {'fields': ('rfc_number', 'title', 'group_acronym', 'area_acronym', 'status', 'comments', 'last_modified_date')}), ('Metadata', {'fields': (('online_version', 'txt_page_count'), ('fyi_number', 'std_number')), 'classes': 'collapse'}), ('Standards Track Dates', {'fields': ('rfc_published_date', ('proposed_date', 'draft_date'), ('standard_date', 'historic_date')), 'classes': 'collapse'}), ('Last Call / Ballot Info', {'fields': ('intended_status', ('lc_sent_date', 'lc_expiration_date'), ('b_sent_date', 'b_approve_date')), 'classes': 'collapse'}))
    list_display=['rfc_number', 'title']
    search_fields=['title']
admin.site.register(Rfc, RfcAdmin)

class RfcIntendedStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(RfcIntendedStatus, RfcIntendedStatusAdmin)

class RfcObsoleteAdmin(admin.ModelAdmin):
    raw_id_fields=['rfc','rfc_acted_on']
admin.site.register(RfcObsolete, RfcObsoleteAdmin)

class RfcStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(RfcStatus, RfcStatusAdmin)

class RoleAdmin(admin.ModelAdmin):
    pass
admin.site.register(Role, RoleAdmin)

class WGStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(WGStatus, WGStatusAdmin)

class WGTypeAdmin(admin.ModelAdmin):
    pass
admin.site.register(WGType, WGTypeAdmin)

