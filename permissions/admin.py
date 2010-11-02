from django.contrib import admin

from permissions.models import ObjectPermission
admin.site.register(ObjectPermission)

from permissions.models import Permission
admin.site.register(Permission)

from permissions.models import Role
admin.site.register(Role)

from permissions.models import PrincipalRoleRelation
admin.site.register(PrincipalRoleRelation)
