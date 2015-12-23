from django.contrib import admin

from ietf.nomcom.models import NomCom, Nomination, Nominee, NomineePosition, \
                               Position, Feedback


class NomComAdmin(admin.ModelAdmin):
    raw_id_fields = ('group', )


class NominationAdmin(admin.ModelAdmin):
    list_display = ('candidate_email', 'nominator_email', 'position')


class NomineeAdmin(admin.ModelAdmin):
    list_display = ('email',)


class NomineePositionAdmin(admin.ModelAdmin):
    pass
    list_display = ('nominee', 'position', 'state')
    list_filter = ('state', 'position')


class PositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'nomcom', 'is_open')
    list_filter = ('nomcom',)


class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('author', 'type')
    list_filter = ('type',)

admin.site.register(NomCom, NomComAdmin)
admin.site.register(Nomination, NominationAdmin)
admin.site.register(Nominee, NomineeAdmin)
admin.site.register(NomineePosition, NomineePositionAdmin)
admin.site.register(Position, PositionAdmin)
admin.site.register(Feedback, FeedbackAdmin)
