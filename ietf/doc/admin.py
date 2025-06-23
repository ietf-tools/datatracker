# Copyright The IETF Trust 2010-2025, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin
from django.db import models
from django import forms
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import (StateType, State, RelatedDocument, DocumentAuthor, Document, RelatedDocHistory,
    DocHistoryAuthor, DocHistory, DocReminder, DocEvent, NewRevisionDocEvent,
    StateDocEvent, ConsensusDocEvent, BallotType, BallotDocEvent, WriteupDocEvent, LastCallDocEvent,
    TelechatDocEvent, BallotPositionDocEvent, ReviewRequestDocEvent, InitialReviewDocEvent,
    AddedMessageEvent, SubmissionDocEvent, DeletedEvent, EditedAuthorsDocEvent, DocumentURL,
    ReviewAssignmentDocEvent, IanaExpertDocEvent, IRSGBallotDocEvent, DocExtResource, DocumentActionHolder,
    BofreqEditorDocEvent, BofreqResponsibleDocEvent, StoredObject )

from ietf.utils.validators import validate_external_resource_value

class StateTypeAdmin(admin.ModelAdmin):
    list_display = ["slug", "label"]
admin.site.register(StateType, StateTypeAdmin)

class StateAdmin(admin.ModelAdmin):
    list_display = ["slug", "type", 'name', 'order', 'desc']
    list_filter = ["type", ]
    search_fields = ["slug", "type__label", "type__slug", "name", "desc"]
    filter_horizontal = ["next_states"]
admin.site.register(State, StateAdmin)

class DocAuthorInline(admin.TabularInline):
    model = DocumentAuthor
    raw_id_fields = ['person', 'email']
    extra = 1

class DocActionHolderInline(admin.TabularInline):
    model = DocumentActionHolder
    raw_id_fields = ['person']
    extra = 1

class RelatedDocumentInline(admin.TabularInline):
    model = RelatedDocument
    fk_name= 'source'
    def this(self, instance):
        return instance.source.name
    readonly_fields = ['this', ]
    fields = ['this', 'relationship', 'target', ]
    raw_id_fields = ['target']
    extra = 1

class AdditionalUrlInLine(admin.TabularInline):
    model = DocumentURL
    fields = ['tag','desc','url',]
    extra = 1
    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size':'50'})},
    }

class DocumentForm(forms.ModelForm):
    comment_about_changes = forms.CharField(
        widget=forms.Textarea(attrs={'rows':10,'cols':40,'class':'vLargeTextField'}), strip=False,
        help_text="This comment about the changes made will be saved in the document history.")
    
    class Meta:
        fields = '__all__'
        exclude = ('states',)
        model = Document

class DocumentAuthorAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'person', 'email', 'affiliation', 'country', 'order']
    search_fields = ['document__name', 'person__name', 'email__address', 'affiliation', 'country']
    raw_id_fields = ["document", "person", "email"]
admin.site.register(DocumentAuthor, DocumentAuthorAdmin)
    
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'rev', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['name']
    list_filter = ['type']
    raw_id_fields = ['group', 'shepherd', 'ad']
    inlines = [DocAuthorInline, DocActionHolderInline, RelatedDocumentInline, AdditionalUrlInLine]
    form = DocumentForm

    def save_model(self, request, obj, form, change):
        e = DocEvent.objects.create(
                doc=obj,
                rev=obj.rev,
                by=request.user.person,
                type='changed_document',
                desc=form.cleaned_data.get('comment_about_changes'),
            )
        obj.save_with_history([e])

    def state(self, instance):
        return self.get_state()

admin.site.register(Document, DocumentAdmin)

class DocHistoryAdmin(admin.ModelAdmin):
    list_display = ['doc', 'rev', 'state', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['doc__name']
    ordering = ['time', 'doc', 'rev']
    raw_id_fields = ['doc', 'group', 'shepherd', 'ad']

    def state(self, instance):
        return instance.get_state()

admin.site.register(DocHistory, DocHistoryAdmin)

class DocReminderAdmin(admin.ModelAdmin):
    list_display = ['id', 'event', 'type', 'due', 'active']
    list_filter = ['type', 'due', 'active']
    raw_id_fields = ['event']
admin.site.register(DocReminder, DocReminderAdmin)

class RelatedDocumentAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'relationship', ]
    list_filter = ['relationship', ]
    search_fields = ['source__name', 'target__name', ]
    raw_id_fields = ['source', 'target', ]
admin.site.register(RelatedDocument, RelatedDocumentAdmin)

class RelatedDocHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'target', 'relationship']
    list_filter = ['relationship']
    raw_id_fields = ['source', 'target']
admin.site.register(RelatedDocHistory, RelatedDocHistoryAdmin)

class DocHistoryAuthorAdmin(admin.ModelAdmin):
    list_display = ['id', 'person', 'email', 'affiliation', 'country', 'order', 'document']
    raw_id_fields = ['person', 'email', 'document']
admin.site.register(DocHistoryAuthor, DocHistoryAuthorAdmin)

class BallotTypeAdmin(admin.ModelAdmin):
    list_display = ["slug", "doc_type", "name", "question"]
admin.site.register(BallotType, BallotTypeAdmin)


class DocumentActionHolderAdmin(admin.ModelAdmin):
    list_display = ['id', 'document', 'person', 'time_added']
    raw_id_fields = ['document', 'person']
admin.site.register(DocumentActionHolder, DocumentActionHolderAdmin)


# events

class DeletedEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_type', 'json', 'by', 'time']
    list_filter = ['time']
    raw_id_fields = ['content_type', 'by']
admin.site.register(DeletedEvent, DeletedEventAdmin)


class DocEventAdmin(admin.ModelAdmin):
    def event_type(self, obj):
        return str(obj.type)
    def doc_time(self, obj):
        h = obj.get_dochistory()
        return h.time if h else ""
    def short_desc(self, obj):
        return obj.desc[:32]
    list_display = ["id", "doc", "event_type", "rev", "by", "time", "doc_time", "short_desc" ]
    search_fields = ["doc__name", "by__name"]
    raw_id_fields = ["doc", "by"]
admin.site.register(DocEvent, DocEventAdmin)

admin.site.register(NewRevisionDocEvent, DocEventAdmin)
admin.site.register(StateDocEvent, DocEventAdmin)
admin.site.register(ConsensusDocEvent, DocEventAdmin)
admin.site.register(BallotDocEvent, DocEventAdmin)
admin.site.register(IRSGBallotDocEvent, DocEventAdmin)
admin.site.register(WriteupDocEvent, DocEventAdmin)
admin.site.register(LastCallDocEvent, DocEventAdmin)
admin.site.register(TelechatDocEvent, DocEventAdmin)
admin.site.register(InitialReviewDocEvent, DocEventAdmin)
admin.site.register(EditedAuthorsDocEvent, DocEventAdmin)
admin.site.register(IanaExpertDocEvent, DocEventAdmin)

class BallotPositionDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["balloter", "ballot"]
admin.site.register(BallotPositionDocEvent, BallotPositionDocEventAdmin)

class BofreqEditorDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["editors"]
admin.site.register(BofreqEditorDocEvent, BofreqEditorDocEventAdmin)
    
class BofreqResponsibleDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["responsible"]
admin.site.register(BofreqResponsibleDocEvent, BofreqResponsibleDocEventAdmin)
    
class ReviewRequestDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["review_request"]
admin.site.register(ReviewRequestDocEvent, ReviewRequestDocEventAdmin)

class ReviewAssignmentDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["review_assignment"]
admin.site.register(ReviewAssignmentDocEvent, ReviewAssignmentDocEventAdmin)

class AddedMessageEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["message"]
admin.site.register(AddedMessageEvent, AddedMessageEventAdmin)

class SubmissionDocEventAdmin(DocEventAdmin):
    raw_id_fields = DocEventAdmin.raw_id_fields + ["submission"]
admin.site.register(SubmissionDocEvent, SubmissionDocEventAdmin)

class DocumentUrlAdmin(admin.ModelAdmin):
    list_display = ['id', 'doc', 'tag', 'url', 'desc', ]
    search_fields = ['doc__name', 'url', ]
    raw_id_fields = ['doc', ]
admin.site.register(DocumentURL, DocumentUrlAdmin)

class DocExtResourceAdminForm(forms.ModelForm):
    def clean(self):
        validate_external_resource_value(self.cleaned_data['name'],self.cleaned_data['value'])

class DocExtResourceAdmin(admin.ModelAdmin):
    form = DocExtResourceAdminForm
    list_display = ['id', 'doc', 'name', 'display_name', 'value',]
    search_fields = ['doc__name', 'value', 'display_name', 'name__slug',]
    raw_id_fields = ['doc', ]
admin.site.register(DocExtResource, DocExtResourceAdmin)

class StoredObjectAdmin(admin.ModelAdmin):
    list_display = ['store', 'name', 'doc_name', 'modified', 'is_deleted']
    list_filter = [
        'store',
        ('modified', DateRangeQuickSelectListFilterBuilder()),
        ('deleted', DateRangeQuickSelectListFilterBuilder()),
    ]
    search_fields = ['name', 'doc_name', 'doc_rev']
    list_display_links = ['name']

    @admin.display(boolean=True, description="Deleted?", ordering="deleted")
    def is_deleted(self, instance):
        return instance.deleted is not None
    

admin.site.register(StoredObject, StoredObjectAdmin)
