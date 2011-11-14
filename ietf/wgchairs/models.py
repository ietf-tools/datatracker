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

    if settings.USE_DB_REDESIGN_PROXY_CLASSES:
        from ietf.idtracker.models import InternetDraftOld as InternetDraft

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

    from redesign.doc.models import WriteupDocEvent
    class ProtoWriteUpProxy(WriteupDocEvent):
        #person = models.ForeignKey(PersonOrOrgInfo, blank=False, null=False)
        @property
        def person(self):
            return self.by
        #draft = models.ForeignKey(InternetDraft, blank=False, null=False)
        @property
        def draft(self):
            return self.doc
        #date = models.DateTimeField(default=datetime.datetime.now(), blank=False, null=False)
        @property
        def date(self):
            return self.time
        #writeup = models.TextField(blank=False, null=False)
        @property
        def writeup(self):
            return self.text
        class Meta:
            proxy = True

    #WGDelegateOld = WGDelegate
    WGDelegate = WGDelegateProxy
