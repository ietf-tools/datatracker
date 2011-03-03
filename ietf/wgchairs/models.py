import datetime

from django.db import models

from ietf.idtracker.models import (IETFWG, PersonOrOrgInfo,
                                   InternetDraft)


class WGDelegate(models.Model):
    person = models.ForeignKey(
        PersonOrOrgInfo,
        )

    wg = models.ForeignKey(IETFWG)

    def __unicode__(self):
        return "%s" % self.person

    class Meta:
        verbose_name = "WG Delegate"


class ProtoWriteUp(models.Model):
    person = models.ForeignKey(
        PersonOrOrgInfo,
        blank=False,
        null=False,
        )

    draft = models.ForeignKey(
        InternetDraft,
        blank=False,
        null=False,
        )

    date = models.DateTimeField(
        default=datetime.datetime.now(),
        blank=False,
        null=False,
        )

    writeup = models.TextField(
        blank=False,
        null=False,
        )
