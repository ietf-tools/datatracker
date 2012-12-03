from django.contrib import admin

from ietf.nomcom.models import NomCom, Nomination, Nominee, NomineePosition, \
                               Position, Feedback


class NomComAdmin(admin.ModelAdmin):
    pass


class NominationAdmin(admin.ModelAdmin):
    pass


class NomineeAdmin(admin.ModelAdmin):
    pass


class NomineePositionAdmin(admin.ModelAdmin):
    pass


class PositionAdmin(admin.ModelAdmin):
    pass


class FeedbackAdmin(admin.ModelAdmin):
    pass

admin.site.register(NomCom, NomComAdmin)
admin.site.register(Nomination, NominationAdmin)
admin.site.register(Nominee, NomineeAdmin)
admin.site.register(NomineePosition, NomineePositionAdmin)
admin.site.register(Position, PositionAdmin)
admin.site.register(Feedback, FeedbackAdmin)
