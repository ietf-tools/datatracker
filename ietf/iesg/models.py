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
from ietf.idtracker.models import Acronym

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
#    class Admin:
#	pass

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
    
    def __str__(self):
        return " / ".join([str(d) for d in [self.date1,self.date2,self.date3,self.date4]])
    class Meta:
        db_table = "telechat_dates"
        verbose_name = "Next Telechat Date"
    class Admin:
        pass

class TelechatAgendaItem(models.Model):
    TYPE_CHOICES = (
        (1, "Working Group News"),
        (2, "IAB News"),
        (3, "Management Items")
        )
    id = models.AutoField(primary_key=True, db_column='template_id')
    text = models.TextField(blank=True, db_column='template_text')
    type = models.IntegerField(db_column='template_type', choices=TYPE_CHOICES)
    title = models.CharField(max_length=255, db_column='template_title')
    #The following fields are apparently not used
    #note = models.TextField(null=True,blank=True)
    #discussed_status_id = models.IntegerField(null=True, blank=True)
    #decision = models.TextField(null=True,blank=True)
    class Meta:
        db_table = 'templates'
    class Admin:
        pass

class WGAction(models.Model):
    CATEGORY_CHOICES = (
        (11, "WG Creation::In Internal Review"),
        (12, "WG Creation::Proposed for IETF Review"),
        (13, "WG Creation::Proposed for Approval"),
        (21, "WG Rechartering::In Internal Review"),
        (22, "WG Rechartering::Under evaluation for IETF Review"),
        (23, "WG Rechartering::Proposed for Approval")
    )
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
        db_table = 'group_internal'
        ordering = ['-telechat_date']
        verbose_name = "WG Action"
    class Admin:
        pass


# changes done by convert-096.py:changed maxlength to max_length
