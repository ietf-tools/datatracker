import datetime
import json
from urlparse import urlsplit

from django.core.urlresolvers import reverse as urlreverse

from ietf.group.models import Group
from ietf.meeting.models import Schedule, TimeSlot, Session, SchedTimeSessAssignment, Meeting, Constraint
from ietf.meeting.test_data import make_meeting_test_data
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase
from ietf.utils.mail import outbox


class ApiTests(TestCase):
    def test_update_agenda(self):
        meeting = make_meeting_test_data()
        schedule = Schedule.objects.get(meeting__number=42,name="test-agenda")
        mars_session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        ames_session = Session.objects.filter(meeting=meeting, group__acronym="ames").first()
    
        mars_scheduled = SchedTimeSessAssignment.objects.get(session=mars_session,schedule__name='test-agenda')
        mars_slot = mars_scheduled.timeslot 

        ames_scheduled = SchedTimeSessAssignment.objects.get(session=ames_session,schedule__name='test-agenda')
        ames_slot = ames_scheduled.timeslot 

        def do_unschedule(assignment):
            url = urlreverse("ietf.meeting.ajax.assignment_json", 
                             kwargs=dict(num=assignment.session.meeting.number, 
                                         owner=assignment.schedule.owner_email(),
                                         name=assignment.schedule.name,
                                         assignment_id=assignment.pk,))
            return self.client.delete(url)

        def do_schedule(schedule,session,timeslot):
            url = urlreverse("ietf.meeting.ajax.assignments_json",
                              kwargs=dict(num=session.meeting.number,
                                          owner=schedule.owner_email(),
                                          name=schedule.name,))
            post_data = '{ "session_id": "%s", "timeslot_id": "%s" }'%(session.pk,timeslot.pk)
            return self.client.post(url,post_data,content_type='application/x-www-form-urlencoded')

        def do_extend(schedule, assignment):
            session = assignment.session
            url = urlreverse("ietf.meeting.ajax.assignments_json",
                              kwargs=dict(num=session.meeting.number,
                                          owner=schedule.owner_email(),
                                          name=schedule.name,))
            post_data = '{ "session_id": "%s", "timeslot_id": "%s", "extendedfrom_id": "%s" }'%(session.pk,assignment.timeslot.slot_to_the_right.pk,assignment.pk)


            return self.client.post(url,post_data,content_type='application/x-www-form-urlencoded')

        # not logged in
        # faulty delete 
        r = do_unschedule(mars_scheduled)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(SchedTimeSessAssignment.objects.get(pk=mars_scheduled.pk).session, mars_session)
        # faulty post
        r = do_schedule(schedule,ames_session,mars_slot)
        self.assertEqual(r.status_code, 403)

        # logged in as non-owner
        # faulty delete
        self.client.login(username="ad", password="ad+password")
        r = do_unschedule(mars_scheduled)
        self.assertEqual(r.status_code, 403)
        self.assertTrue("error" in json.loads(r.content))
        # faulty post
        r = do_schedule(schedule,ames_session,mars_slot)
        self.assertEqual(r.status_code, 403)

        # Put ames in the same timeslot as mars
        self.client.login(username="plain", password='plain+password')
        r = do_unschedule(ames_scheduled)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" not in json.loads(r.content))

        r = do_schedule(schedule,ames_session,mars_slot)
        self.assertEqual(r.status_code, 201)

        # Move the two timeslots close enough together for extension to work
        ames_slot_qs=TimeSlot.objects.filter(id=ames_slot.id)
        ames_slot_qs.update(time=mars_slot.time+mars_slot.duration+datetime.timedelta(minutes=10))
        
        # Extend the mars session
        r = do_extend(schedule,mars_scheduled)
        self.assertEqual(r.status_code, 201)
        self.assertTrue("error" not in json.loads(r.content))
        self.assertEqual(mars_session.timeslotassignments.filter(schedule__name='test-agenda').count(),2)

        # Unschedule mars 
        r = do_unschedule(mars_scheduled)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" not in json.loads(r.content))
        # Make sure it got both the original and extended session
        self.assertEqual(mars_session.timeslotassignments.filter(schedule__name='test-agenda').count(),0)

        self.assertEqual(SchedTimeSessAssignment.objects.get(session=ames_session,schedule__name='test-agenda').timeslot, mars_slot)


    def test_constraints_json(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").select_related("group").first()
        c_ames = Constraint.objects.create(meeting=meeting, source=session.group,
                                           target=Group.objects.get(acronym="ames"),
                                           name_id="conflict")

        c_person = Constraint.objects.create(meeting=meeting, source=session.group,
                                             person=Person.objects.get(user__username="ad"),
                                             name_id="bethere")

        r = self.client.get(urlreverse("ietf.meeting.ajax.session_constraints", kwargs=dict(num=meeting.number, sessionid=session.pk)))
        self.assertEqual(r.status_code, 200)
        constraints = json.loads(r.content)
        self.assertEqual(set([c_ames.pk, c_person.pk]), set(c["constraint_id"] for c in constraints))

    def test_meeting_json(self):
        meeting = make_meeting_test_data()

        r = self.client.get(urlreverse("ietf.meeting.ajax.meeting_json", kwargs=dict(num=meeting.number)))
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["name"], meeting.number)

    def test_get_room_json(self):
        meeting = make_meeting_test_data()
        room = meeting.room_set.first()

        r = self.client.get(urlreverse("ietf.meeting.ajax.timeslot_roomurl", kwargs=dict(num=meeting.number, roomid=room.pk)))
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["name"], room.name)

    def test_create_new_room(self):
        meeting = make_meeting_test_data()
        timeslots_before = meeting.timeslot_set.count()
        url = urlreverse("ietf.meeting.ajax.timeslot_roomsurl", kwargs=dict(num=meeting.number))

        post_data = { "name": "new room", "capacity": "50" , "resources": [], "session_types":["session"]}

        # unauthorized post
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(not meeting.room_set.filter(name="new room"))

        # create room
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.room_set.filter(name="new room"))

        timeslots_after = meeting.timeslot_set.count()
        # It's not clear that what that ajax function is doing is the right thing to do,
        # but it currently makes a new timeslot for any existing timeslot.
        # The condition tested below relies on the timeslots before this test all having different start and end times
        self.assertEqual( timeslots_after, 2 * timeslots_before)

    def test_delete_room(self):
        meeting = make_meeting_test_data()
        room = meeting.room_set.first()
        timeslots_before = list(room.timeslot_set.values_list("pk", flat=True))

        url = urlreverse("ietf.meeting.ajax.timeslot_roomurl", kwargs=dict(num=meeting.number, roomid=room.pk))

        # unauthorized delete
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.room_set.filter(pk=room.pk))

        # delete
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.delete(url)
        self.assertTrue(not meeting.room_set.filter(pk=room.pk))
        self.assertTrue(not TimeSlot.objects.filter(pk__in=timeslots_before))

    # This really belongs in group tests
    def test_group_json(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym="mars")

        url = urlreverse("ietf.group.views_ajax.group_json", kwargs=dict(acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["name"], group.name)

    # This really belongs in person tests
    def test_person_json(self):
        make_meeting_test_data()
        person = Person.objects.get(user__username="ad")

        url = urlreverse("ietf.person.ajax.person_json", kwargs=dict(personid=person.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["name"], person.name)

    def test_sessions_json(self):
        meeting = make_meeting_test_data()
 
        url = urlreverse("ietf.meeting.ajax.sessions_json",kwargs=dict(num=meeting.number))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(set([x['short_name'] for x in info]),set([s.session.short_name for s in meeting.agenda.assignments.filter(session__type_id='session')]))

        schedule = meeting.agenda
        url = urlreverse("ietf.meeting.ajax.assignments_json",
                         kwargs=dict(num=meeting.number,owner=schedule.owner_email(),name=schedule.name))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(len(info),schedule.assignments.count())


    def test_slot_json(self):
        meeting = make_meeting_test_data()
        slot = meeting.timeslot_set.all()[0]

        url = urlreverse("ietf.meeting.ajax.timeslot_sloturl",
                         kwargs=dict(num=meeting.number, slotid=slot.pk))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["timeslot_id"], slot.pk)

    def test_create_new_slot(self):
        meeting = make_meeting_test_data()

        slot_time = datetime.date.today()

        url = urlreverse("ietf.meeting.ajax.timeslot_slotsurl",
                         kwargs=dict(num=meeting.number))
        post_data = {
            'type' : 'plenary',
            'time' : slot_time.strftime("%Y-%m-%d"),
            'duration': '08:00:00',
        }

        # unauthorized post
        prior_slotcount = meeting.timeslot_set.count()
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(meeting.timeslot_set.count(),prior_slotcount)

        # create slot
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(meeting.timeslot_set.filter(time=slot_time))
        self.assertEqual(meeting.timeslot_set.count(),prior_slotcount+1)

    def test_delete_slot(self):
        meeting = make_meeting_test_data()
        slot = meeting.timeslot_set.all()[0]

        url = urlreverse("ietf.meeting.ajax.timeslot_sloturl",
                         kwargs=dict(num=meeting.number, slotid=slot.pk))

        # unauthorized delete
        self.client.login(username="ad", password="ad+password")
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 403)

        # delete
        self.client.login(username="secretary", password="secretary+password")
        self.client.delete(url)
        self.assertTrue(not meeting.timeslot_set.filter(pk=slot.pk))

    def test_schedule_json(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.ajax.agenda_infourl",
                         kwargs=dict(num=meeting.number,
                                     owner=meeting.agenda.owner_email(),
                                     name=meeting.agenda.name))

        r = self.client.get(url)
        info = json.loads(r.content)
        self.assertEqual(info["schedule_id"], meeting.agenda.pk)

    def test_create_new_schedule(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.ajax.agenda_infosurl",
                         kwargs=dict(num=meeting.number))
        post_data = {
            'name': 'new-agenda',
        }

        # unauthorized post
        self.client.login(username="plain", password="plain+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(not meeting.schedule_set.filter(name='new-agenda'))

        # create new agenda
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.schedule_set.filter(name='new-agenda'))

    def test_update_schedule(self):
        meeting = make_meeting_test_data()

        self.assertTrue(meeting.agenda.visible)

        url = urlreverse("ietf.meeting.ajax.agenda_infourl",
                         kwargs=dict(num=meeting.number,
                                     owner=meeting.agenda.owner_email(),
                                     name=meeting.agenda.name))

        post_data = {
            'visible': 'false',
            'name': 'new-test-name',
        }

        # unauthorized posts
        self.client.logout()
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)

        # change agenda
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        changed_schedule = Schedule.objects.get(pk=meeting.agenda.pk)
        self.assertTrue(not changed_schedule.visible)
        self.assertEqual(changed_schedule.name, "new-test-name")

    def test_delete_schedule(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.ajax.agenda_infourl",
                         kwargs=dict(num=meeting.number,
                                     owner=meeting.agenda.owner_email(),
                                     name=meeting.agenda.name))
        # unauthorized delete
        self.client.login(username="plain", password="plain+password")
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 403)

        # delete
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.delete(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(not Schedule.objects.filter(pk=meeting.agenda.pk))

    def test_set_meeting_agenda(self):
        meeting = make_meeting_test_data()
        schedule = meeting.agenda

        url = urlreverse("ietf.meeting.ajax.meeting_json",
                         kwargs=dict(num=meeting.number))
        post_data = {
            "agenda": "",
            }
        # unauthorized post
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)

        # clear
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(not Meeting.objects.get(pk=meeting.pk).agenda)

        # set agenda - first fail with non-public
        post_data = {
            "agenda": schedule.name,
            }
        schedule.public = False
        schedule.save()

        r = self.client.post(url, post_data)
        self.assertTrue(r.status_code != 200)
        self.assertTrue(not Meeting.objects.get(pk=meeting.pk).agenda)

        # then go through with public
        schedule.public = True
        schedule.save()

        # Setting a meeting as official no longer sends mail immediately
        prior_length= len(outbox)
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Meeting.objects.get(pk=meeting.pk).agenda, schedule)
        self.assertEqual(len(outbox),prior_length)

    def test_read_only(self):
        meeting = make_meeting_test_data()

        # Secretariat
        self.client.login(username="secretary", password="secretary+password")
        url = '/meeting/%s/agenda/%s/%s/permissions' % (meeting.number, meeting.agenda.owner.email_address(), meeting.agenda.name);
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        info = json.loads(r.content)
        self.assertEqual(info['secretariat'], True)
        self.assertEqual(urlsplit(info['owner_href'])[2], "/person/%s.json" % meeting.agenda.owner_id)
        self.assertEqual(info['read_only'], True)
        self.assertEqual(info['save_perm'], True)

        # owner
        self.client.login(username=meeting.agenda.owner.user.username,
                          password=meeting.agenda.owner.user.username+"+password")
        url = '/meeting/%s/agenda/%s/%s/permissions' % (meeting.number, meeting.agenda.owner.email_address(), meeting.agenda.name);
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

        info = json.loads(r.content)
        self.assertEqual(info['secretariat'], False)
        self.assertEqual(info['read_only'], False)
        self.assertEqual(info['save_perm'], False)

    def test_update_timeslot_pinned(self):
        meeting = make_meeting_test_data()
        scheduled = SchedTimeSessAssignment.objects.filter(
            session__meeting=meeting, session__group__acronym="mars").first()

        url = '/meeting/%s/agenda/%s/%s/session/%u.json' % (meeting.number, meeting.agenda.owner_email(), meeting.agenda.name, scheduled.pk)

        post_data = {
            "pinned": True
            }

        # unauthorized post gets failure (no redirect)
        r = self.client.put(url, post_data)
        self.assertEqual(r.status_code, 403,
                         "post to %s should have failed, no permission, got: %u/%s" %
                         (url, r.status_code, r.content))
        self.assertTrue(not SchedTimeSessAssignment.objects.get(pk=scheduled.pk).pinned)

        # set pinned
        meeting.agenda.owner = Person.objects.get(user__username="secretary")
        meeting.agenda.save()

        # need to rebuild URL, since the agenda owner has changed.
        url = '/meeting/%s/agenda/%s/%s/session/%u.json' % (meeting.number, meeting.agenda.owner_email(), meeting.agenda.name, scheduled.pk)

        self.client.login(username="secretary", password="secretary+password")
        r = self.client.put(url, post_data)
        self.assertEqual(r.status_code, 200,
                         "post to %s should have worked, but got: %u/%s" %
                         (url, r.status_code, r.content))
        self.assertTrue(SchedTimeSessAssignment.objects.get(pk=scheduled.pk).pinned)

class TimeSlotEditingApiTests(TestCase):

    def test_manipulate_timeslot(self):
        meeting = make_meeting_test_data()
        slot = meeting.timeslot_set.all()[0]
        self.assertEqual(TimeSlot.objects.get(pk=slot.pk).type.name,'Session')

        url = urlreverse("ietf.meeting.ajax.timeslot_sloturl",
                         kwargs=dict(num=meeting.number, slotid=slot.pk))

        modify_post_data = {
            "purpose"       : "plenary"
        }

        # Fail as non-secretariat
        self.client.login(username="plain", password="plain+password")
        r = self.client.post(url, modify_post_data)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(TimeSlot.objects.get(pk=slot.pk).type.name,'Session')

        # Successful change of purpose
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, modify_post_data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(TimeSlot.objects.get(pk=slot.pk).type.name,'Plenary')
