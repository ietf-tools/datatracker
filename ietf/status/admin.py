from django.contrib import admin

from .models import Status


class StatusAdmin(admin.ModelAdmin):
    list_display = ['message', 'url', 'active']
    raw_id_fields = ['by']

    # def save_model(self, request, obj, form, change):
    #     e = DocEvent.objects.create(
    #             doc=obj,
    #             rev=obj.rev,
    #             by=request.user.person,
    #             type='changed_document',
    #             desc=form.cleaned_data.get('comment_about_changes'),
    #         )
    #     obj.save_with_history([e])

admin.site.register(Status, StatusAdmin)
