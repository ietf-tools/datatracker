from django.contrib import admin
from models import *

class GroupAdmin(admin.ModelAdmin):
    list_display = ["acronym", "name", "type"]
    search_fields = ["name"]
    ordering = ["name"]
    raw_id_fields = ["charter"]

admin.site.register(Group, GroupAdmin)
admin.site.register(GroupHistory)

admin.site.register(Role)
