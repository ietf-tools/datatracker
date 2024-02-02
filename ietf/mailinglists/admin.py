# Copyright The IETF Trust 2016, All Rights Reserved

from django.contrib import admin

from ietf.mailinglists.models import List, NonWgMailingList, Subscribed, Allowlisted


class ListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'advertised')
    search_fields = ('name',)
admin.site.register(List, ListAdmin)

class NonWgMailingListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)
admin.site.register(NonWgMailingList, NonWgMailingListAdmin)

class SubscribedAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'email')
    raw_id_fields = ('lists',)
    search_fields = ('email',)
admin.site.register(Subscribed, SubscribedAdmin)


class AllowlistedAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'email', 'by')
admin.site.register(Allowlisted, AllowlistedAdmin)
