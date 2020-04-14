#coding: utf-8
from django.contrib import admin
from ietf.redirects.models import Command, Redirect, Suffix
                
class CommandAdmin(admin.ModelAdmin):
    pass
admin.site.register(Command, CommandAdmin)

class RedirectAdmin(admin.ModelAdmin):
    pass
admin.site.register(Redirect, RedirectAdmin)

class SuffixAdmin(admin.ModelAdmin):
    pass
admin.site.register(Suffix, SuffixAdmin)

