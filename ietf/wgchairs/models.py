from django.db import models

from ietf.idtracker.models import IETFWG, PersonOrOrgInfo


class WGDelegate(models.Model):
    person = models.ForeignKey(
        PersonOrOrgInfo,
        )

    wg = models.ForeignKey(IETFWG)

    def __unicode__(self):
        return "%s" % self.person

    class Meta:
        verbose_name = "WG Delegate"
