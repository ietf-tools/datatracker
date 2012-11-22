from django.contrib import admin

from ietf.group.admin import GroupAdmin
from ietf.nomcom.models import NomComGroup


class NomComGroupAdmin(GroupAdmin):
    exclude = ('type',)


admin.site.register(NomComGroup, NomComGroupAdmin)
