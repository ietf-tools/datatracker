from django.contrib import admin
from ietf.iesg.models import *

class TelechatAgendaItemAdmin(admin.ModelAdmin):
    pass
admin.site.register(TelechatAgendaItem, TelechatAgendaItemAdmin)

admin.site.register(TelechatDate)

