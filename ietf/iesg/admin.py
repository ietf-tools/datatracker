#coding: utf-8
from django.contrib import admin
from ietf.iesg.models import *
                
class TelechatAgendaItemAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatAgendaItem, TelechatAgendaItemAdmin)

class TelechatDatesAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatDates, TelechatDatesAdmin)

class WGActionAdmin(admin.ModelAdmin):
    pass
admin.site.register(WGAction, WGActionAdmin)

