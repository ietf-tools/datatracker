from django.contrib import admin
from models import *

class NameAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "desc", "used"]
    prepopulate_from = { "slug": ("name",) }
    
admin.site.register(GroupTypeName, NameAdmin)
admin.site.register(GroupStateName, NameAdmin)
admin.site.register(RoleName, NameAdmin)
admin.site.register(StreamName, NameAdmin)
admin.site.register(DocRelationshipName, NameAdmin)
admin.site.register(DocTypeName, NameAdmin)
admin.site.register(DocTagName, NameAdmin)
admin.site.register(StdLevelName, NameAdmin)
admin.site.register(IntendedStdLevelName, NameAdmin)
admin.site.register(DocReminderTypeName, NameAdmin)
admin.site.register(BallotPositionName, NameAdmin)
admin.site.register(SessionStatusName, NameAdmin)
admin.site.register(TimeSlotTypeName, NameAdmin)
admin.site.register(ConstraintName, NameAdmin)
