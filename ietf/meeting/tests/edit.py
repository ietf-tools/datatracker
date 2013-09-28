import re
import sys
from settings import BASE_DIR
from django.test              import Client
from django.test import TestCase
#from ietf.person.models import Person
from django.contrib.auth.models import User
from django.test.client import Client
from ietf.meeting.models  import TimeSlot, Session, ScheduledSession
from auths import auth_joeblow, auth_wlo, auth_ietfchair, auth_ferrel

capture_output = False

class EditTestCase(TestCase):
    fixtures = [ 'names.xml',  # ietf/names/fixtures/names.xml for MeetingTypeName, and TimeSlotTypeName
                 'meeting83.json',
                 'constraint83.json',
                 'workinggroups.json',
                 'groupgroup.json',
                 'person.json', 'users.json' ]

    def test_getEditData(self):
        # confirm that we can get edit data from the edit interface
        resp = self.client.get('/meeting/83/schedule/edit',{},
                               **auth_wlo)
        m = re.search(".*session_obj.*", resp.content)
        # to capture new output (and check it for correctness)
        if capture_output:
            out = open("%s/meeting/tests/edit_out.html" % BASE_DIR, "w")
            out.write(resp.content)
            out.close()
        self.assertIsNotNone(m)

    def test_schedule_lookup(self):
        from ietf.meeting.views import get_meeting

        # determine that there isn't a schedule called "fred"
        mtg = get_meeting(83)
        sched83 = mtg.get_schedule_by_name("mtg:83")
        self.assertIsNotNone(sched83, "sched83 not found")

