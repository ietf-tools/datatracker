from django.contrib import admin
from ietf.iesg.models import *

class TelechatAgendaItemAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatAgendaItem, TelechatAgendaItemAdmin)

class WGActionAdmin(admin.ModelAdmin):
    pass
admin.site.register(WGAction, WGActionAdmin)

admin.site.register(TelechatDate)

