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

import sys
import socket
from django.conf import settings
import django

mail_outbox = []
test_database_name = None
old_destroy = None
old_create = None

def safe_create_0(verbosity, *args, **kwargs):
    global test_database_name, old_create
    print "Creating test database..."
    x = old_create(0, *args, **kwargs)
    print "Saving test database name "+settings.DATABASE_NAME+"..."
    test_database_name = settings.DATABASE_NAME
    return x

def safe_create_1(self, verbosity, *args, **kwargs):
    global test_database_name, old_create
    print "Creating test database..."
    x = old_create(self, 0, *args, **kwargs)
    print "Saving test database name "+settings.DATABASE_NAME+"..."
    test_database_name = settings.DATABASE_NAME
    return x

def safe_destroy_0_1(*args, **kwargs):
    global test_database_name, old_destroy
    print "Checking that it's safe to destroy test database..."
    if settings.DATABASE_NAME != test_database_name:
        print "NOT SAFE; Changing settings.DATABASE_NAME from "+settings.DATABASE_NAME+" to "+test_database_name
        settings.DATABASE_NAME = test_database_name
    return old_destroy(*args, **kwargs)

# Test that test/r5106.patch has been applied. This is not written
# as normal test case, because it needs to be run before Django's
# test framework takes over. This test applies only to Django 0.96,
# and can be removed once we transition to 1.x.
def test_django_foreignkey_patch():
    print "Testing Django 0.96 ForeignKey patch..."
    try:
        import ietf
        t = django.core.management._get_sql_model_create(ietf.idtracker.models.GoalMilestone)
    except KeyError, f:
        if str(f.args) == "('ForeignKey',)":
            raise Exception("Django 0.96 patch in test/r5106.patch not installed?")
        else:
            raise

def test_send_smtp(msg, bcc=None):
    global mail_outbox
    mail_outbox.append(msg)

def run_tests_0(*args, **kwargs):
    global old_destroy, old_create, test_database_name
    import django.test.utils
    m = sys.modules['django.test.utils']
    old_create = m.create_test_db
    m.create_test_db = safe_create_0
    old_destroy = m.destroy_test_db
    m.destroy_test_db = safe_destroy_0_1
    from django.test.simple import run_tests
    run_tests(*args, **kwargs)

def run_tests_1(test_labels, *args, **kwargs):
    global old_destroy, old_create, test_database_name
    from django.db import connection
    old_create = connection.creation.__class__.create_test_db
    connection.creation.__class__.create_test_db = safe_create_1
    old_destroy = connection.creation.__class__.destroy_test_db
    connection.creation.__class__.destroy_test_db = safe_destroy_0_1
    from django.test.simple import run_tests
    if not test_labels:
        test_labels = [x.split(".")[-1] for x in settings.INSTALLED_APPS if x.startswith("ietf")]
    run_tests(test_labels, *args, **kwargs)

def run_tests(*args, **kwargs):
    # Tests that involve switching back and forth between the real
    # database and the test database are way too dangerous to run
    # against the production database
    if socket.gethostname().startswith("core3"):
        raise EnvironmentError("Refusing to run tests on core3")
    import ietf.utils.mail
    ietf.utils.mail.send_smtp = test_send_smtp
    if django.VERSION[0] == 0:
        test_django_foreignkey_patch()
        run_tests_0(*args, **kwargs)
    else:
        run_tests_1(*args, **kwargs)
    
