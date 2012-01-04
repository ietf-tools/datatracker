# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2008 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
# 
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
# 
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from django.db import models
from django.conf import settings
from ietf.idtracker.models import Acronym
import datetime

# This table is not used by any code right now, and according to Glen,
# probably not currently (Aug 2009) maintained by the secretariat.
#class TelechatMinutes(models.Model):
#    telechat_date = models.DateField(null=True, blank=True)
#    telechat_minute = models.TextField(blank=True)
#    exported = models.IntegerField(null=True, blank=True)
#    def get_absolute_url(self):
#	return "/iesg/telechat/%d/" % self.id
#    def __str__(self):
#	return "IESG Telechat Minutes for %s" % self.telechat_date
#    class Meta:
#        db_table = 'telechat_minutes'
#        verbose_name = "Telechat Minute Text"
#        verbose_name_plural = "Telechat Minutes"

# this model is deprecated
class TelechatDates(models.Model):
    date1 = models.DateField(primary_key=True, null=True, blank=True)
    date2 = models.DateField(null=True, blank=True)
    date3 = models.DateField(null=True, blank=True)
    date4 = models.DateField(null=True, blank=True)
    def dates(self):
        l = []
        if self.date1:
            l.append(self.date1)
        if self.date2:
            l.append(self.date2)
        if self.date3:
            l.append(self.date3)
        if self.date4:
            l.append(self.date4)
        return l

    def save(self):
        # date1 isn't really a primary id, so save() doesn't work
        raise NotImplemented
    
    def __str__(self):
        return " / ".join([str(d) for d in [self.date1,self.date2,self.date3,self.date4]])
    class Meta:
        db_table = "telechat_dates"
        verbose_name = "Next Telechat Date"

class TelechatAgendaItem(models.Model):
    TYPE_CHOICES = (
        (1, "Working Group News"),
        (2, "IAB News"),
        (3, "Management Item")
        )
    TYPE_CHOICES_DICT = dict(TYPE_CHOICES)
    id = models.AutoField(primary_key=True, db_column='template_id')
    text = models.TextField(blank=True, db_column='template_text')
    type = models.IntegerField(db_column='template_type', choices=TYPE_CHOICES, default=3)
    title = models.CharField(max_length=255, db_column='template_title')
    #The following fields are apparently not used
    #note = models.TextField(null=True,blank=True)
    #discussed_status_id = models.IntegerField(null=True, blank=True)
    #decision = models.TextField(null=True,blank=True)
    def __unicode__(self):
        type_name = self.TYPE_CHOICES_DICT.get(self.type, str(self.type))
        return u'%s: %s' % (type_name, self.title or "")
    class Meta:
        if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
            db_table = 'templates'

class WGAction(models.Model):
    CATEGORY_CHOICES = (
        (11, "WG Creation::In Internal Review"),
        (12, "WG Creation::Proposed for IETF Review"),
        (13, "WG Creation::Proposed for Approval"),
        (21, "WG Rechartering::In Internal Review"),
        (22, "WG Rechartering::Under evaluation for IETF Review"),
        (23, "WG Rechartering::Proposed for Approval")
    )
    # note that with the new schema, Acronym is monkey-patched and is really Group
    group_acronym = models.ForeignKey(Acronym, db_column='group_acronym_id', primary_key=True, unique=True)
    note = models.TextField(blank=True,null=True)
    status_date = models.DateField()
    agenda = models.BooleanField("On Agenda")
    token_name = models.CharField(max_length=25)
    category = models.IntegerField(db_column='pwg_cat_id', choices=CATEGORY_CHOICES, default=11)
    telechat_date = models.DateField() #choices = [(x.telechat_date,x.telechat_date) for x in Telechat.objects.all().order_by('-telechat_date')])
    def __str__(self):
        return str(self.telechat_date)+": "+str(self.group_acronym)
    class Meta:
        if not settings.USE_DB_REDESIGN_PROXY_CLASSES:
            db_table = 'group_internal'
        ordering = ['-telechat_date']
        verbose_name = "WG Action"

class Telechat(models.Model):
    telechat_id = models.IntegerField(primary_key=True)
    telechat_date = models.DateField(null=True, blank=True)
    minute_approved = models.IntegerField(null=True, blank=True)
    wg_news_txt = models.TextField(blank=True)
    iab_news_txt = models.TextField(blank=True)
    management_issue = models.TextField(blank=True)
    frozen = models.IntegerField(null=True, blank=True)
    mi_frozen = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'telechat'


def next_telechat_date():
    dates = TelechatDate.objects.order_by("-date")
    if dates:
        return dates[0].date + datetime.timedelta(days=14)
    return datetime.date.today()

class TelechatDateManager(models.Manager):
    def active(self):
        return self.get_query_set().filter(date__gte=datetime.date.today())

class TelechatDate(models.Model):
    objects = TelechatDateManager()

    date = models.DateField(default=next_telechat_date)

    def __unicode__(self):
        return self.date.isoformat()

    class Meta:
        ordering = ['-date']

class TelechatDatesProxyDummy(object):
    def all(self):
        class Dummy(object):
            def __getitem__(self, i):
                return self

            def get_date(self, index):
                if not hasattr(self, "date_cache"):
                    self.date_cache = TelechatDate.objects.active().order_by("date")

                if index < len(self.date_cache):
                    return self.date_cache[index].date
                return None

            #date1 = models.DateField(primary_key=True, null=True, blank= True)
            @property
            def date1(self):
                return self.get_date(0)
            #date2 = models.DateField(null=True, blank=True)
            @property
            def date2(self):
                return self.get_date(1)
            #date3 = models.DateField(null=True, blank=True)
            @property
            def date3(self):
                return self.get_date(2)
            #date4 = models.DateField(null=True, blank=True)
            @property
            def date4(self):
                return self.get_date(3)

            def dates(self):
                l = []
                if self.date1:
                    l.append(self.date1)
                if self.date2:
                    l.append(self.date2)
                if self.date3:
                    l.append(self.date3)
                if self.date4:
                    l.append(self.date4)
                return l

        return Dummy()

class TelechatDatesProxy(object):
    objects = TelechatDatesProxyDummy()

if settings.USE_DB_REDESIGN_PROXY_CLASSES:
    TelechatDatesOld = TelechatDates
    TelechatDates = TelechatDatesProxy
