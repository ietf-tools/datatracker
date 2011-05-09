from django.contrib import admin
from ietf.submit.models import *

class IdSubmissionStatusAdmin(admin.ModelAdmin):
    pass
admin.site.register(IdSubmissionStatus, IdSubmissionStatusAdmin)    

class IdSubmissionDetailAdmin(admin.ModelAdmin):
    list_display = ['submission_id', 'filename', 'status_link', 'submission_date', 'last_updated_date',]
    ordering = [ '-submission_date' ]
    search_fields = ['filename', ]
admin.site.register(IdSubmissionDetail, IdSubmissionDetailAdmin)    

class IdApprovedDetailAdmin(admin.ModelAdmin):
    pass
admin.site.register(IdApprovedDetail, IdApprovedDetailAdmin)    

class TempIdAuthorsAdmin(admin.ModelAdmin):
    ordering = ["-id"]
    pass
admin.site.register(TempIdAuthors, TempIdAuthorsAdmin)    
