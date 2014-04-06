import datetime
import json
from urlparse import urlsplit

from django.core.urlresolvers import reverse as urlreverse

from ietf.group.models import Group
from ietf.meeting.models import Schedule, TimeSlot, Session, ScheduledSession, Meeting, Constraint
from ietf.meeting.test_data import make_meeting_test_data
from ietf.person.models import Person
from ietf.utils.test_utils import TestCase


class ApiTests(TestCase):
    def test_dajaxice_core_js(self):
        # this is vital for Dajaxice to work and we have hacked it
        # slightly to avoid copying static files around, so make sure
        # we can fetch it
        r = self.client.get("/dajaxice/dajaxice.core.js")
        self.assertEqual(r.status_code, 200)

    def test_update_agenda_item(self):
        meeting = make_meeting_test_data()
        session = Session.objects.filter(meeting=meeting, group__acronym="mars").first()
        mars_scheduled = ScheduledSession.objects.get(session=session)
        #mars_slot = mars_scheduled.timeslot ## never used

        ames_scheduled = ScheduledSession.objects.get(session__meeting=meeting, session__group__acronym="ames")
        #ames_slot = ames_scheduled.timeslot ## never used

        def do_post(to):
            # move this session from one timeslot to another
            return self.client.post('/dajaxice/ietf.meeting.update_timeslot/', {
                'argv': json.dumps({
                    "schedule_id": mars_scheduled.schedule.pk,
                    "session_id": session.pk,
                    "scheduledsession_id": to.pk if to else None,
                })})

        # faulty post - not logged in
        r = do_post(to=ames_scheduled)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" in json.loads(r.content))
        self.assertEqual(ScheduledSession.objects.get(pk=mars_scheduled.pk).session, session)

        # faulty post - logged in as non-owner
        self.client.login(username="ad", password="ad+password")
        r = do_post(to=ames_scheduled)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" in json.loads(r.content))

        # Until the next agenda merge, the access permissions on the function under
        # test only allow the secretariat to make changes.
        # Tweaking the test data here instead of in make_meeting_test_data to simplify
        # returning to the intended test scenario after that merge
        test_schedule = mars_scheduled.schedule
        test_schedule.owner=Person.objects.get(user__username='secretary')
        test_schedule.save()

        # move to ames
        self.client.login(username="secretary", password="secretary+password")
        r = do_post(to=ames_scheduled)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" not in json.loads(r.content))

        self.assertEqual(ScheduledSession.objects.get(pk=mars_scheduled.pk).session, None)
        self.assertEqual(ScheduledSession.objects.get(pk=ames_scheduled.pk).session, session)

        # unschedule
        self.client.login(username="secretary", password="secretary+password")
        r = do_post(to=None)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" not in json.loads(r.content))

        self.assertEqual(ScheduledSession.objects.get(pk=ames_scheduled.pk).session, None)


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

        post_data = { "name": "new room", "capacity": "50" }

        # unauthorized post
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(not meeting.room_set.filter(name="new room"))

        # create room
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertTrue(meeting.room_set.filter(name="new room"))

        timeslots_after = meeting.timeslot_set.count()
        self.assertEqual((timeslots_after - timeslots_before), (meeting.room_set.count() - 1) * timeslots_before)

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

    def test_group_json(self):
        make_meeting_test_data()
        group = Group.objects.get(acronym="mars")

        url = urlreverse("ietf.group.ajax.group_json", kwargs=dict(acronym=group.acronym))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        info = json.loads(r.content)
        self.assertEqual(info["name"], group.name)

    def test_person_json(self):
        make_meeting_test_data()
        person = Person.objects.get(user__username="ad")

        url = urlreverse("ietf.person.ajax.person_json", kwargs=dict(personid=person.pk))
        r = self.client.get(url)
        info = json.loads(r.content)
        self.assertEqual(info["name"], person.name)

    def test_slot_json(self):
        meeting = make_meeting_test_data()
        slot = meeting.timeslot_set.all()[0]

        url = urlreverse("ietf.meeting.ajax.timeslot_sloturl",
                         kwargs=dict(num=meeting.number, slotid=slot.pk))
        r = self.client.get(url)
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
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)

        # create room
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(meeting.timeslot_set.filter(time=slot_time))

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
                         kwargs=dict(num=meeting.number, schedule_name=meeting.agenda.name))

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
                                     schedule_name=meeting.agenda.name))

        post_data = {
            'visible': 'false',
            'name': 'new-test-name',
        }

        # unauthorized post
        self.client.login(username="plain", password="plain+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 403)

        # change agenda
        self.client.login(username="ad", password="ad+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 302)
        changed_schedule = Schedule.objects.get(pk=meeting.agenda.pk)
        self.assertTrue(not changed_schedule.visible)
        self.assertEqual(changed_schedule.name, "new-test-name")

    def test_delete_schedule(self):
        meeting = make_meeting_test_data()

        url = urlreverse("ietf.meeting.ajax.agenda_infourl",
                         kwargs=dict(num=meeting.number,
                                     schedule_name=meeting.agenda.name))
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

        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Meeting.objects.get(pk=meeting.pk).agenda, schedule)

    def test_read_only(self):
        meeting = make_meeting_test_data()

        data = {
            'argv': json.dumps({
                "meeting_num": meeting.number,
                "schedule_id": meeting.agenda.pk,
            })}

        # Secretariat
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post('/dajaxice/ietf.meeting.readonly/', data)
        self.assertEqual(r.status_code, 200)

        info = json.loads(r.content)
        self.assertEqual(info['secretariat'], True)
        self.assertEqual(urlsplit(info['owner_href'])[2], "/person/%s.json" % meeting.agenda.owner_id)
        self.assertEqual(info['read_only'], True)
        self.assertEqual(info['write_perm'], True)

        # owner
        self.client.login(username=meeting.agenda.owner.user.username,
                          password=meeting.agenda.owner.user.username+"+password")
        r = self.client.post('/dajaxice/ietf.meeting.readonly/', data)
        self.assertEqual(r.status_code, 200)

        info = json.loads(r.content)
        self.assertEqual(info['secretariat'], False)
        self.assertEqual(info['read_only'], False)
        self.assertEqual(info['write_perm'], False)

    def test_update_timeslot_pinned(self):
        meeting = make_meeting_test_data()
        scheduled = ScheduledSession.objects.filter(
            session__meeting=meeting, session__group__acronym="mars").first()

        url = '/dajaxice/ietf.meeting.update_timeslot_pinned/'

        post_data = {
            'argv': json.dumps({
                "schedule_id": meeting.agenda.pk,
                "scheduledsession_id": scheduled.pk,
                "pinned": True,
            })}

        # unauthorized post
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertTrue("error" in json.loads(r.content))
        self.assertTrue(not ScheduledSession.objects.get(pk=scheduled.pk).pinned)

        # set pinned
        meeting.agenda.owner = Person.objects.get(user__username="secretary")
        meeting.agenda.save()
        self.client.login(username="secretary", password="secretary+password")
        r = self.client.post(url, post_data)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ScheduledSession.objects.get(pk=scheduled.pk).pinned)
