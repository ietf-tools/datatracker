from django.contrib import admin
from models import *

class NameAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "desc", "used"]
    prepopulate_from = { "slug": ("name",) }
    
admin.site.register(GroupTypeName, NameAdmin)
admin.site.register(GroupStateName, NameAdmin)
admin.site.register(RoleName, NameAdmin)
admin.site.register(DocStreamName, NameAdmin)
admin.site.register(DocStateName, NameAdmin)
admin.site.register(DocRelationshipName, NameAdmin)
admin.site.register(WgDocStateName, NameAdmin)
admin.site.register(IesgDocStateName, NameAdmin)
admin.site.register(IanaDocStateName, NameAdmin)
admin.site.register(RfcDocStateName, NameAdmin)
admin.site.register(DocTypeName, NameAdmin)
admin.site.register(DocInfoTagName, NameAdmin)
admin.site.register(StdLevelName, NameAdmin)
admin.site.register(IntendedStdLevelName, NameAdmin)
admin.site.register(BallotPositionName, NameAdmin)
