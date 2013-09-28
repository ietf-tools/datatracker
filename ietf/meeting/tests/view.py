import re
import sys
from django.test.client       import Client
from django.test import TestCase
#from ietf.person.models import Person
from django.contrib.auth.models import User
from settings import BASE_DIR
from ietf.meeting.models  import TimeSlot, Session, ScheduledSession
from auths import auth_joeblow, auth_wlo, auth_ietfchair, auth_ferrel
from ietf.meeting.helpers import get_meeting
from django.core.urlresolvers import reverse
from ietf.meeting.views import edit_agenda

capture_output = True

class ViewTestCase(TestCase):
    fixtures = [ 'names.xml',  # ietf/names/fixtures/names.xml for MeetingTypeName, and TimeSlotTypeName
                 'meeting83.json',
                 'constraint83.json',
                 'workinggroups.json',
                 'groupgroup.json',
                 'person.json', 'users.json' ]

    def test_agenda83txt(self):
        # verify that the generated text has not changed.
        import io
        agenda83txtio = open("%s/meeting/tests/agenda-83-txt-output.txt" % BASE_DIR, "r")
        agenda83txt = agenda83txtio.read();  # read entire file
        resp = self.client.get('/meeting/83/agenda.txt')
        # to capture new output (and check it for correctness)
        if capture_output:
            out = open("%s/meeting/tests/agenda-83-txt-output-out.txt" % BASE_DIR, "w")
            out.write(resp.content)
            out.close()
        self.assertEqual(resp.content, agenda83txt, "agenda83 txt changed")

    def test_agenda83utc(self):
        # verify that the generated html has not changed.
        import io
        agenda83utcio = open("%s/meeting/tests/agenda-83-utc-output.html" % BASE_DIR, "r")
        agenda83utc = agenda83utcio.read();  # read entire file
        resp = self.client.get('/meeting/83/agenda-utc.html')
        # to capture new output (and check it for correctness set capture_output above)
        if capture_output:
            out = open("%s/meeting/tests/agenda-83-utc-output-out.html" % BASE_DIR, "w")
            out.write(resp.content)
            out.close()
        self.assertEqual(resp.content, agenda83utc, "agenda83 utc changed")

    def test_nameOfClueWg(self):
        clue_session = Session.objects.get(pk=2194)
        self.assertEqual(clue_session.short_name, "clue")

    def test_nameOfIEPG(self):
        iepg_session = Session.objects.get(pk=2288)
        self.assertEqual(iepg_session.short_name, "IEPG Meeting")

    def test_nameOfEdu1(self):
        edu1_session = Session.objects.get(pk=2274)
        self.assertEqual(edu1_session.short_name, "Tools for Creating Internet-Drafts Tutorial")

    def test_js_identifier_clue(self):
        iepg_ss = ScheduledSession.objects.get(pk=2413)
        slot = iepg_ss.timeslot
        self.assertEqual(slot.js_identifier, "252b_2012-03-27_0900")

    def test_agenda_save(self):
        #
        # determine that there isn't a schedule called "fred"
        mtg = get_meeting(83)
        fred = mtg.get_schedule_by_name("fred")
        self.assertIsNone(fred)
        #
        # move this session from one timeslot to another.
        self.client.post('/meeting/83/schedule/edit', {
            'savename': "fred",
            'saveas': "saveas",
            }, **auth_wlo)
        #
        # confirm that a new schedule has been created
        fred = mtg.get_schedule_by_name("fred")
        self.assertNotEqual(fred, None, "fred not found")

    def test_agenda_edit_url(self):
        url = reverse(edit_agenda,
                      args=['83', 'fred'])
        self.assertEqual(url, "/meeting/83/schedule/fred/edit")

    def test_agenda_edit_visible_farrel(self):
        # farrel is an AD
        url = reverse(edit_agenda,
                      args=['83', 'russ_83_visible'])
        resp = self.client.get(url, **auth_ferrel)
        # a visible agenda can be seen by any logged in AD/Secretariat
        self.assertEqual(resp.status_code, 200)

    def test_agenda_edit_visible_joeblow(self):
        url = reverse(edit_agenda,
                      args=['83', 'russ_83_visible'])
        resp = self.client.get(url, **auth_joeblow)
        # a visible agenda can not be seen unless logged in
        self.assertEqual(resp.status_code, 403)

    def test_agenda_edit_visible_authwlo(self):
        url = reverse(edit_agenda,
                      args=['83', 'russ_83_visible'])
        resp = self.client.get(url, **auth_wlo)
        # secretariat can always see things
        self.assertEqual(resp.status_code, 200)

    def test_agenda_edit_public_farrel(self):
        # farrel is an AD
        url = reverse(edit_agenda,
                      args=['83', 'mtg:83'])
        resp = self.client.get(url, **auth_ferrel)
        self.assertEqual(resp.status_code, 200) # a public agenda can be seen by any logged in AD/Secretariat

    def test_agenda_edit_public_joeblow(self):
        url = reverse(edit_agenda,
                      args=['83', 'mtg:83'])
        resp = self.client.get(url, **auth_joeblow)
        self.assertEqual(resp.status_code, 200) # a public agenda can be seen by unlogged in people (read-only) XXX
        #self.assertEqual(resp.status_code, 403) # a public agenda can not be seen by unlogged in people

    def test_agenda_edit_public_authwlo(self):
        url = reverse(edit_agenda,
                      args=['83', 'mtg:83'])
        resp = self.client.get(url, **auth_wlo)
        self.assertEqual(resp.status_code, 200) # a public agenda can be seen by the secretariat

    def test_agenda_edit_private_russ(self):
        # farrel is an AD
        url = reverse(edit_agenda,
                      args=['83', 'russ_83_inv'])
        resp = self.client.get(url, **auth_ferrel)
        # a private agenda can only be seen its owner
        self.assertEqual(resp.status_code, 403)  # even a logged in AD can not see another

    def test_agenda_edit_private_farrel(self):
        url = reverse(edit_agenda,
                      args=['83', 'sf_83_invisible'])
        resp = self.client.get(url, **auth_ferrel)
        self.assertEqual(resp.status_code, 200)  # a private agenda can only be seen its owner XXX

    def test_agenda_edit_private_joeblow(self):
        url = reverse(edit_agenda,
                      args=['83', 'sf_83_invisible'])
        resp = self.client.get(url, **auth_joeblow)
        self.assertEqual(resp.status_code, 403)  # a private agenda can not be seen by the public

    def test_agenda_edit_private_authwlo(self):
        url = reverse(edit_agenda,
                      args=['83', 'sf_83_invisible'])
        self.assertEqual(url, "/meeting/83/schedule/sf_83_invisible/edit")
        resp = self.client.get(url, **auth_wlo)
        self.assertEqual(resp.status_code, 200) # secretariat can see any agenda, even a private one.








