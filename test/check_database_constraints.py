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

from django.db.models.fields.related import ForeignKey
from django import db
from django.db import models

cursor = db.connection.cursor()

def check_foreign_key(model, field):
    print "Checking foreign key", model._meta.db_table+"."+field.column
    print "    points to:", field.rel.to._meta.db_table+"."+field.rel.field_name
    sql = "SELECT src.%s,src.%s FROM %s AS src LEFT OUTER JOIN %s as dst on src.%s=dst.%s WHERE src.%s IS NOT NULL AND dst.%s IS NULL;" % (model._meta.pk.column, field.column, model._meta.db_table, field.rel.to._meta.db_table, field.column, field.rel.get_related_field().column, field.column, field.rel.get_related_field().column)
    #print sql
    cursor.execute(sql)
    rows = cursor.fetchall()
    if len(rows) == 0:
        print "    OK, no hanging rows found"
    else:
        print "    ERROR, found", len(rows), "hanging rows"
        for row in rows[0:20]:
            print "   ", row
        print "    Use the following SQL to debug:"
        print sql

def check_not_null(model, field):
    print "Checking NULL values", model._meta.db_table+"."+field.column
    sql = "SELECT x.%s,x.%s FROM %s as x WHERE x.%s IS NULL" % (model._meta.pk.column, field.column, model._meta.db_table, field.column)
    cursor.execute(sql)
    rows = cursor.fetchall()
    if len(rows) == 0:
        print "    OK"
    else:
        print "    ERROR, found", len(rows), "NULL rows"
        for row in rows[0:20]:
            print "   ", row
        print "    Use the following SQL to debug:"
        print sql

def check_unique(model,field):
    print "Checking unique values", model._meta.db_table+"."+field.column
    sql = "SELECT %s FROM %s GROUP BY %s HAVING COUNT(*)>1" % (field.column, model._meta.db_table, field.column)
    cursor.execute(sql)
    rows = cursor.fetchall()
    if len(rows) == 0:
        print "    OK"
    else:
        print "    ERROR, found non-unique rows"
        for row in rows[0:20]:
            print "   ", row
        print "    Use the following SQL to debug:"
        print sql

APPS = ['announcements','idrfc','idtracker','iesg','ietfauth','ipr','liaisons','proceedings','redirects']
all_models = []
for app_label in APPS:
    all_models.extend(models.get_models(models.get_app(app_label)))

for model in all_models:
    print "\n\nChecking %s (table %s)" % (model._meta.object_name, model._meta.db_table)
    for f in model._meta.fields:
        if isinstance(f, ForeignKey):
            check_foreign_key(model,f)
        if not f.null:
            check_not_null(model, f)
        if f.unique:
            check_unique(model, f)
    
