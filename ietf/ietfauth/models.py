# Portions Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from django.contrib.auth.models import User
from ietf.idtracker.models import PersonOrOrgInfo, IESGLogin
from ietf.utils.admin import admin_link

def find_person(username):
    try: 
        person = IESGLogin.objects.get(login_name=username).person
        return person
    except IESGLogin.DoesNotExist, PersonOrOrgInfo.DoesNotExist:
        pass
    # try LegacyWgPassword next
    try:
        return LegacyWgPassword.objects.get(login_name=username).person
    except LegacyWgPassword.DoesNotExist, PersonOrOrgInfo.DoesNotExist:
        pass
    # try LegacyLiaisonUser next
    try:
        return LegacyLiaisonUser.objects.get(login_name=username).person
    except LegacyLiaisonUser.DoesNotExist, PersonOrOrgInfo.DoesNotExist:
        pass
    return None

class IetfUserProfile(models.Model):
    user = models.ForeignKey(User,unique=True)

    def person(self):
        return find_person(self.user.username)

    def iesg_login_id(self):
        person = self.person()
        if not person:
            return None
        try:
            return person.iesglogin_set.all()[0].id
        except:
            return None

    def email(self):
        # quick hack to bind new and old schema together for the time being
        try:
            l = IESGLogin.objects.get(login_name=self.user.username)
            if l.person:
                person = l.person
            else:
                person = PersonOrOrgInfo.objects.get(first_name=l.first_name,
                                                     last_name=l.last_name)
        except IESGLogin.DoesNotExist, PersonOrOrgInfo.DoesNotExist:
            person = None
        from person.models import Email
        return Email.objects.get(address=person.email()[1])

    def __str__(self):
	return "IetfUserProfile(%s)" % (self.user,)


######################################################
# legacy per-tool access tables.
# ietf.idtracker.models.IESGLogin is in the same vein.

class LegacyLiaisonUser(models.Model):
    USER_LEVEL_CHOICES = (
	(0, 'Secretariat'),
	(1, 'IESG'),
	(2, 'ex-IESG'),
	(3, 'Level 3'),
	(4, 'Comment Only(?)'),
    )
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True)
    login_name = models.CharField(max_length=255)
    password = models.CharField(max_length=25, blank=True, editable=False)
    user_level = models.IntegerField(null=True, blank=True, choices=USER_LEVEL_CHOICES)
    comment = models.TextField(blank=True,null=True)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'users'
	ordering = ['login_name']
    person_link = admin_link('person')

class LegacyWgPassword(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True)
    password = models.CharField(blank=True, null=True,max_length=255)
    secrete_question_id = models.IntegerField(null=True, blank=True)
    secrete_answer = models.CharField(blank=True, null=True, max_length=255)
    is_tut_resp = models.IntegerField(null=True, blank=True)
    irtf_id = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True,null=True)
    login_name = models.CharField(blank=True, max_length=100)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'wg_password'
	ordering = ['login_name']
    person_link = admin_link('person')

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed max_num_in_admin
# removed num_in_admin
# removed raw_id_admin
