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

import datetime

from django.db import models

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

    def __unicode__(self):
        type_name = self.TYPE_CHOICES_DICT.get(self.type, str(self.type))
        return u'%s: %s' % (type_name, self.title or "")

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
