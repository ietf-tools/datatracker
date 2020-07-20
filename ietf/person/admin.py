from django.contrib import admin
import simple_history

from django import forms

from ietf.person.models import Email, Alias, Person, PersonalApiKey, PersonEvent, PersonApiKeyEvent, PersonExtResource
from ietf.person.name import name_parts

from ietf.utils.validators import validate_external_resource_value


class EmailAdmin(simple_history.admin.SimpleHistoryAdmin):
    list_display = ["address", "person", "time", "active", "origin"]
    raw_id_fields = ["person", ]
    search_fields = ["address", "person__name", ]
admin.site.register(Email, EmailAdmin)
    
class EmailInline(admin.TabularInline):
    model = Email

class AliasAdmin(admin.ModelAdmin):
    list_display = ["name", "person", ]
    search_fields = ["name",]
    raw_id_fields = ["person"]
admin.site.register(Alias, AliasAdmin)

class AliasInline(admin.StackedInline):
    model = Alias

class PersonAdmin(simple_history.admin.SimpleHistoryAdmin):
    def plain_name(self, obj):
        if obj.plain:
            return obj.plain
        else:
            prefix, first, middle, last, suffix = name_parts(obj.name)
            return "%s %s" % (first, last)
    list_display = ["name", "short", "plain_name", "time", "user", ]
    fields = ("user", "time", "name", "plain", "name_from_draft", "ascii", "ascii_short", "biography", "photo", "photo_thumb", "consent",)
    readonly_fields = ("name_from_draft", )
    search_fields = ["name", "ascii"]
    raw_id_fields = ["user"]
    inlines = [ EmailInline, AliasInline, ]
#    actions = None
admin.site.register(Person, PersonAdmin)

class PersonalApiKeyAdmin(admin.ModelAdmin):
    list_display = ['id', 'person', 'created', 'endpoint', 'valid', 'count', 'latest', ]
    list_filter = ['endpoint', 'created', ]
    raw_id_fields = ['person', ]
    search_fields = ['person__name', ]
admin.site.register(PersonalApiKey, PersonalApiKeyAdmin)

class PersonEventAdmin(admin.ModelAdmin):
    list_display = ["id", "person", "time", "type", ]
    search_fields = ["person__name", ]
    raw_id_fields = ['person', ]
admin.site.register(PersonEvent, PersonEventAdmin)

class PersonApiKeyEventAdmin(admin.ModelAdmin):
    list_display = ["id", "person", "time", "type", "key"]
    search_fields = ["person__name", ]
    raw_id_fields = ['person', ]
admin.site.register(PersonApiKeyEvent, PersonApiKeyEventAdmin)



class PersonExtResourceAdminForm(forms.ModelForm):
    def clean(self):
        validate_external_resource_value(self.cleaned_data['name'],self.cleaned_data['value'])

class PersonExtResourceAdmin(admin.ModelAdmin):
    form = PersonExtResourceAdminForm
    list_display = ['id', 'person', 'name', 'display_name', 'value',]
    search_fields = ['person__name', 'value', 'display_name', 'name__slug',]
    raw_id_fields = ['person', ]
admin.site.register(PersonExtResource, PersonExtResourceAdmin) 
