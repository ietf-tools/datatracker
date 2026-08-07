# Copyright The IETF Trust 2022, All Rights Reserved
from django.contrib import admin
import simple_history

from django import forms
from django.contrib import messages
from django.db import transaction

from ietf.person.models import Email, Alias, Person, PersonalApiKey, PersonEvent, \
    PersonApiKeyEvent, PersonExtResource, PersonUUID
from ietf.person.name import name_parts
from ietf.person.utils import queue_person_uuid_push

from ietf.utils.admin import SaferStackedInline, SaferTabularInline
from ietf.utils.validators import validate_external_resource_value


class EmailAdmin(simple_history.admin.SimpleHistoryAdmin):
    list_display = ["address", "person", "time", "active", "origin"]
    raw_id_fields = ["person", ]
    search_fields = ["address", "person__name", ]
admin.site.register(Email, EmailAdmin)
    
class EmailInline(SaferTabularInline):
    model = Email

class AliasAdmin(admin.ModelAdmin):
    list_display = ["name", "person", ]
    search_fields = ["name",]
    raw_id_fields = ["person"]
admin.site.register(Alias, AliasAdmin)

class AliasInline(SaferStackedInline):
    model = Alias


@admin.action(description="Make this the person's primary UUID")
def set_primary(modeladmin, request, queryset):
    """Re-designate a Person's primary UUID

    Acts on exactly one UUID at a time: promoting two at once would either violate the
    one-primary-per-person constraint or silently ignore one of them.
    """
    if queryset.count() != 1:
        modeladmin.message_user(
            request, "Select exactly one UUID.", level=messages.ERROR
        )
        return
    new_primary = queryset.first()
    if new_primary.primary:
        modeladmin.message_user(request, "That UUID is already primary.")
        return
    person = new_primary.person
    with transaction.atomic():
        person.uuids.filter(primary=True).update(primary=False)
        new_primary.primary = True
        new_primary.save(update_fields=["primary"])
    queue_person_uuid_push(person)
    modeladmin.message_user(
        request, f"{new_primary.uuid} is now the primary UUID for {person}."
    )


class PersonUUIDAdmin(admin.ModelAdmin):
    list_display = ["uuid", "person", "primary", "time"]
    list_filter = ["primary"]
    search_fields = ["uuid", "person__name"]
    raw_id_fields = ["person"]
    readonly_fields = ["uuid", "primary", "time"]
    actions = [set_primary]
admin.site.register(PersonUUID, PersonUUIDAdmin)


class PersonUUIDInline(SaferStackedInline):
    model = PersonUUID
    extra = 0
    # primary is changed through the PersonUUID admin's set_primary action, which demotes
    # the old primary first. Editing it here would trip the uniqueness constraint.
    readonly_fields = ["uuid", "primary", "time"]
    can_delete = False


class PersonAdmin(simple_history.admin.SimpleHistoryAdmin):
    def plain_name(self, obj):
        if obj.plain:
            return obj.plain
        else:
            prefix, first, middle, last, suffix = name_parts(obj.name)
            return "%s %s" % (first, last)
    list_display = ["name", "short", "plain_name", "time", "user", ]
    fields = ("user", "time", "name", "plain", "name_from_draft", "ascii", "ascii_short", "pronouns_selectable", "pronouns_freetext", "biography", "photo", "photo_thumb",)
    readonly_fields = ("name_from_draft", )
    search_fields = ["name", "ascii"]
    raw_id_fields = ["user"]
    inlines = [ EmailInline, AliasInline, PersonUUIDInline]
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
