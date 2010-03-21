# Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).
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

from ietf import settings
from django.core import management
management.setup_environ(settings)

from django.db.models.fields import CharField, TextField
from django import db
from django.db import models

cursor = db.connection.cursor()

def check_non_ascii(model, field):
    #print "    Checking", field.column
    sql = "SELECT src.%s,src.%s FROM %s AS src WHERE src.%s RLIKE '[^\\t-~]+'" % (model._meta.pk.column, field.column, model._meta.db_table, field.column)
    #print sql
    cursor.execute(sql)
    rows = cursor.fetchall()
    if len(rows) > 0:
        print "    NON-ASCII: %s.%s (%d rows)" % (model._meta.db_table,field.column, len(rows))
        #for row in rows[0:20]:
        #    print "   ", row
        #print "    Use the following SQL to debug:"
        #print sql

APPS = ['announcements', 'idrfc','idtracker','iesg','ietfauth','ipr','liaisons','proceedings','redirects']
all_models = []
for app_label in APPS:
    all_models.extend(models.get_models(models.get_app(app_label)))

for model in all_models:
    print "\nChecking %s (table %s)" % (model._meta.object_name, model._meta.db_table)
    for f in model._meta.fields:
        if isinstance(f, CharField) or isinstance(f, TextField):
            check_non_ascii(model,f)
