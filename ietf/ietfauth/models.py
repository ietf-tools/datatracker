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


def find_person(username):
    try: 
        person = IESGLogin.objects.get(login_name=username).person
        return person
    except IESGLogin.DoesNotExist, PersonOrOrgInfo.DoesNotExist:
        pass
    # TODO: try LegacyWgPassword next
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

    def __str__(self):
	return "IetfUserProfile(%s)" % (self.user,)


######################################################
# legacy per-tool access tables.
# ietf.idtracker.models.IESGLogin is in the same vein.

class LegacyLiaisonUser(models.Model):
    person = models.ForeignKey(PersonOrOrgInfo, db_column='person_or_org_tag', primary_key=True)
    login_name = models.CharField(max_length=255)
    password = models.CharField(max_length=25)
    user_level = models.IntegerField(null=True, blank=True)
    comment = models.TextField(blank=True,null=True)
    def __str__(self):
	return self.login_name
    class Meta:
        db_table = 'users'
	ordering = ['login_name']

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

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
# removed max_num_in_admin
# removed num_in_admin
# removed raw_id_admin
