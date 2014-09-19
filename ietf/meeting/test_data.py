import datetime

from ietf.doc.models import Document, State
from ietf.group.models import Group
from ietf.meeting.models import Meeting, Room, TimeSlot, Session, Schedule, ScheduledSession, ResourceAssociation, SessionPresentation
from ietf.name.models import RoomResourceName
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data


def make_meeting_test_data():
    if not Group.objects.filter(acronym='mars'):
        make_test_data()
    system_person = Person.objects.get(name="(System)")
    plainman = Person.objects.get(user__username="plain")
    #secretary = Person.objects.get(user__username="secretary") ## not used

    meeting = Meeting.objects.get(number="42", type="ietf")
    schedule = Schedule.objects.create(meeting=meeting, owner=plainman, name="test-agenda", visible=True, public=True)
    pname = RoomResourceName.objects.create(name='projector',slug='proj')
    projector = ResourceAssociation.objects.create(name=pname,icon="notfound.png",desc="Basic projector")
    room = Room.objects.create(meeting=meeting, name="Test Room", capacity=123)
    room.resources = [projector]

    # mars WG
    slot = TimeSlot.objects.create(meeting=meeting, type_id="session", duration=30 * 60, location=room,
                                   time=datetime.datetime.combine(datetime.date.today(), datetime.time(9, 30)))
    mars_session = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym="mars"),
                                          attendees=10, requested_by=system_person,
                                          requested_duration=20, status_id="schedw",
                                          scheduled=datetime.datetime.now())
    mars_session.resources = [projector]
    ScheduledSession.objects.create(timeslot=slot, session=mars_session, schedule=schedule)

    # ames WG
    slot = TimeSlot.objects.create(meeting=meeting, type_id="session", duration=30 * 60, location=room,
                                   time=datetime.datetime.combine(datetime.date.today(), datetime.time(10, 30)))
    ames_session = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym="ames"),
                                          attendees=10, requested_by=system_person,
                                          requested_duration=20, status_id="schedw",
                                          scheduled=datetime.datetime.now())
    ScheduledSession.objects.create(timeslot=slot, session=ames_session, schedule=schedule)

    meeting.agenda = schedule
    meeting.save()

    doc = Document.objects.create(name='agenda-mars-ietf-42', type_id='agenda', title="Agenda", external_url="agenda-mars")
    doc.set_state(State.objects.get(type=doc.type_id, slug="active"))
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))

    doc = Document.objects.create(name='minutes-mars-ietf-42', type_id='minutes', title="Minutes", external_url="minutes-mars")
    doc.set_state(State.objects.get(type=doc.type_id, slug="active"))
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))

    doc = Document.objects.create(name='slides-mars-ietf-42', type_id='slides', title="Slideshow", external_url="slides-mars")
    doc.set_state(State.objects.get(type=doc.type_id, slug="active"))
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))
    
    return meeting



