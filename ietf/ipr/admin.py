#coding: utf-8
from django import forms
from django.contrib import admin
from ietf.name.models import DocRelationshipName
from ietf.ipr.models import (IprNotification, IprDisclosureBase, IprDocRel, IprEvent,
    RelatedIpr, HolderIprDisclosure, ThirdPartyIprDisclosure, GenericIprDisclosure, 
    NonDocSpecificIprDisclosure)

# ------------------------------------------------------
# ModelAdmins
# ------------------------------------------------------
class IprDocRelAdminForm(forms.ModelForm):
    class Meta:
        model = IprDocRel
        widgets = {
          'sections':forms.TextInput,
        }

class IprDocRelInline(admin.TabularInline):
    model = IprDocRel
    form = IprDocRelAdminForm
    raw_id_fields = ['document']
    extra = 1

class RelatedIprInline(admin.TabularInline):
    model = RelatedIpr
    raw_id_fields = ['target']
    fk_name = 'source'
    extra = 1
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "relationship":
            kwargs["queryset"] = DocRelationshipName.objects.filter(slug='updates')
        return super(RelatedIprInline, self).formfield_for_foreignkey(db_field, request, **kwargs)
        
class IprDisclosureBaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'time', 'related_docs', 'state']
    search_fields = ['title', 'legal_name']
    raw_id_fields = ['by']
    inlines = [IprDocRelInline,RelatedIprInline]
    
    def related_docs(self, obj):
        return u", ".join(a.formatted_name() for a in IprDocRel.objects.filter(disclosure=obj).order_by("id").select_related("document"))

admin.site.register(IprDisclosureBase, IprDisclosureBaseAdmin)

class HolderIprDisclosureAdmin(admin.ModelAdmin):
    list_display = ['title', 'time', 'related_docs', 'state']
    raw_id_fields = ["by"]
    inlines = [IprDocRelInline,RelatedIprInline]
    
    def related_docs(self, obj):
        return u", ".join(a.formatted_name() for a in IprDocRel.objects.filter(disclosure=obj).order_by("id").select_related("document"))

admin.site.register(HolderIprDisclosure, HolderIprDisclosureAdmin)

class ThirdPartyIprDisclosureAdmin(admin.ModelAdmin):
    list_display = ['title', 'time', 'related_docs', 'state']
    raw_id_fields = ["by"]
    inlines = [IprDocRelInline,RelatedIprInline]
    
    def related_docs(self, obj):
        return u", ".join(a.formatted_name() for a in IprDocRel.objects.filter(disclosure=obj).order_by("id").select_related("document"))

admin.site.register(ThirdPartyIprDisclosure, ThirdPartyIprDisclosureAdmin)

class GenericIprDisclosureAdmin(admin.ModelAdmin):
    list_display = ['title', 'time', 'related_docs', 'state']
    raw_id_fields = ["by"]
    inlines = [RelatedIprInline]
    
    def related_docs(self, obj):
        return u", ".join(a.formatted_name() for a in IprDocRel.objects.filter(disclosure=obj).order_by("id").select_related("document"))

admin.site.register(GenericIprDisclosure, GenericIprDisclosureAdmin)

class NonDocSpecificIprDisclosureAdmin(admin.ModelAdmin):
    list_display = ['title', 'time', 'related_docs', 'state']
    raw_id_fields = ["by"]
    inlines = [RelatedIprInline]
    
    def related_docs(self, obj):
        return u", ".join(a.formatted_name() for a in IprDocRel.objects.filter(disclosure=obj).order_by("id").select_related("document"))

admin.site.register(NonDocSpecificIprDisclosure, NonDocSpecificIprDisclosureAdmin)

class IprNotificationAdmin(admin.ModelAdmin):
    pass
admin.site.register(IprNotification, IprNotificationAdmin)

class IprDocRelAdmin(admin.ModelAdmin):
    raw_id_fields = ["disclosure", "document"]
admin.site.register(IprDocRel, IprDocRelAdmin)

class RelatedIprAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'relationship', ]
    search_fields = ['source__name', 'target__name', 'target__document__name', ]
    raw_id_fields = ['source', 'target', ]
admin.site.register(RelatedIpr, RelatedIprAdmin)

class IprEventAdmin(admin.ModelAdmin):
    list_display = ["disclosure", "type", "by", "time"]
    list_filter = ["time", "type"]
    search_fields = ["disclosure__title", "by__name"]
    raw_id_fields = ["disclosure", "by", "message", "in_reply_to"]
admin.site.register(IprEvent, IprEventAdmin)
