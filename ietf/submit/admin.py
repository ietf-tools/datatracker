from django.core.urlresolvers import reverse as urlreverse
from django.contrib import admin


from ietf.submit.models import Preapproval, Submission, SubmissionCheck

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['id', 'draft_link', 'status_link', 'submission_date',]
    ordering = [ '-id' ]
    search_fields = ['name', ]
    raw_id_fields = ['group']

    def status_link(self, instance):
        url = urlreverse('submit_submission_status_by_hash',
                         kwargs=dict(submission_id=instance.pk,
                                     access_token=instance.access_token()))
        return '<a href="%s">%s</a>' % (url, instance.state)
    status_link.allow_tags = True

    def draft_link(self, instance):
        if instance.state_id == "posted":
            return '<a href="https://www.ietf.org/id/%s-%s.txt">%s</a>' % (instance.name, instance.rev, instance.name)
        else:
            return instance.name
    draft_link.allow_tags = True
admin.site.register(Submission, SubmissionAdmin)

class SubmissionCheckAdmin(admin.ModelAdmin):
    list_display = ['submission', 'time', 'checker', 'passed', 'errors', 'warnings', 'items']
    raw_id_fields = ['submission']
admin.site.register(SubmissionCheck, SubmissionCheckAdmin)

class PreapprovalAdmin(admin.ModelAdmin):
    pass
admin.site.register(Preapproval, PreapprovalAdmin)

