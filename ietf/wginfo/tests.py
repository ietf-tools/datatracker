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

import os, unittest, shutil

import django.test
from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from ietf.utils.mail import outbox
from ietf.utils.test_data import make_test_data
from ietf.utils.test_utils import login_testing_unauthorized

from pyquery import PyQuery

from ietf.utils.test_utils import SimpleUrlTestCase
from ietf.doc.models import *
from ietf.group.models import *
from ietf.group.utils import *
from ietf.name.models import *
from ietf.person.models import *


class WgInfoUrlTestCase(SimpleUrlTestCase):
    def testUrls(self):
        self.doTestUrls(__file__)

class WgFileTestCase(unittest.TestCase):
    def testFileExistence(self):
        fpath = os.path.join(settings.IETFWG_DESCRIPTIONS_PATH, "tls.desc.txt")
        if not os.path.exists(fpath):
            print "\nERROR: charter files not found in "+settings.IETFWG_DESCRIPTIONS_PATH
            print "They are needed for testing WG charter pages."
            print "Download them to a local directory with:"
            print "wget -nd -nc -np -r http://www.ietf.org/wg-descriptions/"
            print "And set IETFWG_DESCRIPTIONS_PATH in settings_local.py\n"

class WgOverviewTestCase(django.test.TestCase):
    fixtures = ["names"]

    def test_overview(self):
        make_test_data()

        wg = Group.objects.get(acronym="mars")
        wg.charter.set_state(State.objects.get(type="charter", slug="intrev"))

        url = urlreverse('ietf.wginfo.views.chartering_wgs')
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('table.ietf-doctable td.acronym a:contains("mars")')), 1)


class WgEditTestCase(django.test.TestCase):
    fixtures = ["names"]

    def setUp(self):
        self.charter_dir = os.path.abspath("tmp-charter-dir")
        os.mkdir(self.charter_dir)
        settings.CHARTER_PATH = self.charter_dir

    def tearDown(self):
        shutil.rmtree(self.charter_dir)

    def test_create(self):
        make_test_data()

        url = urlreverse('wg_create')
        login_testing_unauthorized(self, "secretary", url)

        num_wgs = len(Group.objects.filter(type="wg"))

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form input[name=acronym]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(acronym="foobarbaz")) # No name
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(len(Group.objects.filter(type="wg")), num_wgs)

        # creation
        r = self.client.post(url, dict(acronym="testwg", name="Testing WG"))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(len(Group.objects.filter(type="wg")), num_wgs + 1)
        group = Group.objects.get(acronym="testwg")
        self.assertEquals(group.name, "Testing WG")
        self.assertEquals(group.charter.name, "charter-ietf-testwg")
        self.assertEquals(group.charter.rev, "00-00")

    def test_create_based_on_existing(self):
        make_test_data()

        url = urlreverse('wg_create')
        login_testing_unauthorized(self, "secretary", url)

        group = Group.objects.get(acronym="mars")

        # try hijacking area - faulty
        r = self.client.post(url, dict(name="Test", acronym=group.parent.acronym))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(len(q('form input[name="confirmed"]')), 0) # can't confirm us out of this

        # try elevating BoF to WG
        group.state_id = "bof"
        group.save()

        r = self.client.post(url, dict(name="Test", acronym=group.acronym))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        self.assertEquals(len(q('form input[name="confirmed"]')), 1)

        self.assertEquals(Group.objects.get(acronym=group.acronym).state_id, "bof")

        # confirm elevation
        r = self.client.post(url, dict(name="Test", acronym=group.acronym, confirmed="1"))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(Group.objects.get(acronym=group.acronym).state_id, "proposed")
        self.assertEquals(Group.objects.get(acronym=group.acronym).name, "Test")

    def test_edit_info(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")

        url = urlreverse('wg_edit', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form select[name=parent]')), 1)
        self.assertEquals(len(q('form input[name=acronym]')), 1)

        # faulty post
        Group.objects.create(name="Collision Test Group", acronym="collide")
        r = self.client.post(url, dict(acronym="collide"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

        # create old acronym
        group.acronym = "oldmars"
        group.save()
        save_group_in_history(group)
        group.acronym = "mars"
        group.save()

        # post with warning
        r = self.client.post(url, dict(acronym="oldmars"))
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)
        
        # edit info
        with open(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev)), "w") as f:
            f.write("This is a charter.")
        area = group.parent
        ad = Person.objects.get(name="Aread Irector")
        r = self.client.post(url,
                             dict(name="Mars Not Special Interest Group",
                                  acronym="mnsig",
                                  parent=area.pk,
                                  ad=ad.pk,
                                  chairs="aread@ietf.org, ad1@ietf.org",
                                  secretaries="aread@ietf.org, ad1@ietf.org, ad2@ietf.org",
                                  techadv="aread@ietf.org",
                                  list_email="mars@mail",
                                  list_subscribe="subscribe.mars",
                                  list_archive="archive.mars",
                                  urls="http://mars.mars (MARS site)"
                                  ))
        self.assertEquals(r.status_code, 302)

        group = Group.objects.get(acronym="mnsig")
        self.assertEquals(group.name, "Mars Not Special Interest Group")
        self.assertEquals(group.parent, area)
        self.assertEquals(group.ad, ad)
        for k in ("chair", "secr", "techadv"):
            self.assertTrue(group.role_set.filter(name=k, email__address="aread@ietf.org"))
        self.assertEquals(group.list_email, "mars@mail")
        self.assertEquals(group.list_subscribe, "subscribe.mars")
        self.assertEquals(group.list_archive, "archive.mars")
        self.assertEquals(group.groupurl_set.all()[0].url, "http://mars.mars")
        self.assertEquals(group.groupurl_set.all()[0].name, "MARS site")
        self.assertTrue(os.path.exists(os.path.join(self.charter_dir, "%s-%s.txt" % (group.charter.canonical_name(), group.charter.rev))))

    def test_conclude(self):
        make_test_data()

        group = Group.objects.get(acronym="mars")

        url = urlreverse('wg_conclude', kwargs=dict(acronym=group.acronym))
        login_testing_unauthorized(self, "secretary", url)

        # normal get
        r = self.client.get(url)
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertEquals(len(q('form textarea[name=instructions]')), 1)
        
        # faulty post
        r = self.client.post(url, dict(instructions="")) # No instructions
        self.assertEquals(r.status_code, 200)
        q = PyQuery(r.content)
        self.assertTrue(len(q('form ul.errorlist')) > 0)

        # request conclusion
        mailbox_before = len(outbox)
        r = self.client.post(url, dict(instructions="Test instructions"))
        self.assertEquals(r.status_code, 302)
        self.assertEquals(len(outbox), mailbox_before + 1)
        # the WG remains active until the Secretariat takes action
        group = Group.objects.get(acronym=group.acronym)
        self.assertEquals(group.state_id, "active")
