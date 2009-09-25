# Copyright The IETF Trust 2007, All Rights Reserved

# Portion Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
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

import django
from django.db import connection
import ietf

class RealDatabaseTest:
    def setUpRealDatabase(self):
        self._original_testdb = self._getDatabaseName()
        newdb = ietf.settings.DATABASE_NAME
        print "Switching database from "+self._original_testdb+" to "+newdb
        self._setDatabaseName(newdb)

    def tearDownRealDatabase(self):
        curdb = self._getDatabaseName()
        print "Switching database from "+curdb+" to "+self._original_testdb
        self._setDatabaseName(self._original_testdb)

    def _getDatabaseName(self):
        if django.VERSION[0] == 0:
            return django.conf.settings.DATABASE_NAME 
        else:
            return connection.settings_dict['DATABASE_NAME'] 

    def _setDatabaseName(self, name):        
        connection.close()
        if django.VERSION[0] == 0:
            django.conf.settings.DATABASE_NAME = name
        else:
            connection.settings_dict['DATABASE_NAME'] = name
        connection.cursor()
