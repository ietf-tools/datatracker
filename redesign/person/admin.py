from django.contrib import admin
from models import *

class EmailAdmin(admin.ModelAdmin):
    list_display = ["address", "person", "time", "active", ]
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

class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "short", "time", ]
    search_fields = ["name", "ascii"]
    inlines = [ EmailInline, AliasInline, ]
#    actions = None
admin.site.register(Person, PersonAdmin)

