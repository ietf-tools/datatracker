# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django.contrib import admin
from django.db import models
from django import forms

from .models import (StateType, State, RelatedDocument, DocumentAuthor, Document, RelatedDocHistory,
    DocHistoryAuthor, DocHistory, DocAlias, DocReminder, DocEvent, NewRevisionDocEvent,
    StateDocEvent, ConsensusDocEvent, BallotType, BallotDocEvent, WriteupDocEvent, LastCallDocEvent,
    TelechatDocEvent, BallotPositionDocEvent, ReviewRequestDocEvent, InitialReviewDocEvent,
    AddedMessageEvent, SubmissionDocEvent, DeletedEvent, EditedAuthorsDocEvent, DocumentURL,
    ReviewAssignmentDocEvent, IanaExpertDocEvent, IRSGBallotDocEvent )


class StateTypeAdmin(admin.ModelAdmin):
    list_display = ["slug", "label"]
admin.site.register(StateType, StateTypeAdmin)

class StateAdmin(admin.ModelAdmin):
    list_display = ["slug", "type", 'name', 'order', 'desc']
    list_filter = ["type", ]
    filter_horizontal = ["next_states"]
admin.site.register(State, StateAdmin)

# class DocAliasInline(admin.TabularInline):
#     model = DocAlias
#     extra = 1

class DocAuthorInline(admin.TabularInline):
    model = DocumentAuthor
    raw_id_fields = ['person', 'email']
    extra = 1

class RelatedDocumentInline(admin.TabularInline):
    model = RelatedDocument
    def this(self, instance):
        return instance.source.canonical_name()
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
    search_fields = ['document__docalias__name', 'person__name', 'email__address', 'affiliation', 'country']
    raw_id_fields = ["document", "person", "email"]
admin.site.register(DocumentAuthor, DocumentAuthorAdmin)
    
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'rev', 'group', 'pages', 'intended_std_level', 'author_list', 'time']
    search_fields = ['name']
    list_filter = ['type']
    raw_id_fields = ['group', 'shepherd', 'ad']
    inlines = [DocAuthorInline, RelatedDocumentInline, AdditionalUrlInLine]
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

class DocAliasAdmin(admin.ModelAdmin):
#     list_display = ['name', 'document_link']
#     search_fields = ['name', 'document__name']
    raw_id_fields = ['docs']
admin.site.register(DocAlias, DocAliasAdmin)

class DocReminderAdmin(admin.ModelAdmin):
    list_display = ['id', 'event', 'type', 'due', 'active']
    list_filter = ['type', 'due', 'active']
    raw_id_fields = ['event']
admin.site.register(DocReminder, DocReminderAdmin)

class RelatedDocumentAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'relationship', ]
    list_filter = ['relationship', ]
    search_fields = ['source__name', 'target__name', 'target__docs__name', ]
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

# events

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
admin.site.register(WriteupDocEvent, DocEventAdmin)
admin.site.register(LastCallDocEvent, DocEventAdmin)
admin.site.register(TelechatDocEvent, DocEventAdmin)
admin.site.register(ReviewRequestDocEvent, DocEventAdmin)
admin.site.register(ReviewAssignmentDocEvent, DocEventAdmin)
admin.site.register(InitialReviewDocEvent, DocEventAdmin)
admin.site.register(AddedMessageEvent, DocEventAdmin)
admin.site.register(SubmissionDocEvent, DocEventAdmin)
admin.site.register(EditedAuthorsDocEvent, DocEventAdmin)
admin.site.register(IanaExpertDocEvent, DocEventAdmin)

class DeletedEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_type', 'json', 'by', 'time']
    list_filter = ['time']
    raw_id_fields = ['content_type', 'by']
admin.site.register(DeletedEvent, DeletedEventAdmin)

class BallotPositionDocEventAdmin(DocEventAdmin):
    raw_id_fields = ["doc", "by", "balloter", "ballot"]
admin.site.register(BallotPositionDocEvent, BallotPositionDocEventAdmin)
 
class IRSGBallotDocEventAdmin(DocEventAdmin):
    raw_id_fields = ["doc", "by"]
admin.site.register(IRSGBallotDocEvent, IRSGBallotDocEventAdmin)
    
class DocumentUrlAdmin(admin.ModelAdmin):
    list_display = ['id', 'doc', 'tag', 'url', 'desc', ]
    search_fields = ['doc__name', 'url', ]
    raw_id_fields = ['doc', ]
admin.site.register(DocumentURL, DocumentUrlAdmin)
