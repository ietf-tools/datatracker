# Copyright The IETF Trust 2016, All Rights Reserved

from django.contrib import admin

from ietf.mailinglists.models import NonWgMailingList, Allowlisted




class NonWgMailingListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)
admin.site.register(NonWgMailingList, NonWgMailingListAdmin)


class AllowlistedAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'email', 'by')
admin.site.register(Allowlisted, AllowlistedAdmin)
