# Copyright The IETF Trust 2016, All Rights Reserved

from django.contrib import admin

from ietf.mailinglists.models import List, Subscribed, Whitelisted


class ListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'advertised')
    search_fields = ('name',)
admin.site.register(List, ListAdmin)


class SubscribedAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'address')
    raw_id_fields = ('lists',)
    search_fields = ('address',)
admin.site.register(Subscribed, SubscribedAdmin)


class WhitelistedAdmin(admin.ModelAdmin):
    list_display = ('id', 'time', 'address', 'by')
admin.site.register(Whitelisted, WhitelistedAdmin)
