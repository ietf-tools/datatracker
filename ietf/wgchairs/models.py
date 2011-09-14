import datetime

from django.db import models
from django.conf import settings

from ietf.idtracker.models import (IETFWG, PersonOrOrgInfo,
                                   InternetDraft)


class WGDelegate(models.Model):
    person = models.ForeignKey(
        PersonOrOrgInfo,
        )

    wg = models.ForeignKey(IETFWG, related_name="old_wgdelegate_set" if settings.USE_DB_REDESIGN_PROXY_CLASSES else None)

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

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    from redesign.group.models import Role
    class WGDelegateProxy(Role):
        #person = models.ForeignKey(PersonOrOrgInfo) # same name
        #wg = models.ForeignKey(IETFWG)
        @property
        def wg(self):
            return self.group

        def __unicode__(self):
            return u"%s" % self.person

        class Meta:
            proxy = True

    from redesign.doc.models import DocEvent
    class ProtoWriteUpProxy(DocEvent):
        #person = models.ForeignKey(PersonOrOrgInfo, blank=False, null=False)
        #draft = models.ForeignKey(InternetDraft, blank=False, null=False)
        #date = models.DateTimeField(default=datetime.datetime.now(), blank=False, null=False)
        #writeup = models.TextField(blank=False, null=False)
        class Meta:
            proxy = True

    #WGDelegateOld = WGDelegate
    WGDelegate = WGDelegateProxy
    ProtoWriteUpOld = ProtoWriteUp
    ProtoWriteUp = ProtoWriteUpProxy
