import datetime

from ietf.doc.factories import DocumentFactory
from ietf.group.models import Group
from ietf.meeting.models import (Meeting, Room, TimeSlot, Session, Schedule, SchedTimeSessAssignment,
    ResourceAssociation, SessionPresentation, UrlResource)
from ietf.meeting.helpers import create_interim_meeting
from ietf.name.models import RoomResourceName
from ietf.person.models import Person
from ietf.utils.test_data import make_test_data

def make_interim_meeting(group,date,status='sched'):
    system_person = Person.objects.get(name="(System)")
    time = datetime.datetime.combine(date, datetime.time(9))
    meeting = create_interim_meeting(group=group,date=date)
    session = Session.objects.create(meeting=meeting, group=group,
        attendees=10, requested_by=system_person,
        requested_duration=20, status_id=status,
        remote_instructions='http://webex.com',
        scheduled=datetime.datetime.now(),type_id="session")
    slot = TimeSlot.objects.create(
        meeting=meeting,
        type_id="session",
        duration=session.requested_duration,
        time=time)
    SchedTimeSessAssignment.objects.create(
        timeslot=slot,
        session=session,
        schedule=session.meeting.agenda)
    return meeting

def make_meeting_test_data(meeting=None):
    if not Group.objects.filter(acronym='mars'):
        make_test_data()
    system_person = Person.objects.get(name="(System)")
    plainman = Person.objects.get(user__username="plain")
    #secretary = Person.objects.get(user__username="secretary") ## not used

    if not meeting:
        meeting = Meeting.objects.get(number="42", type="ietf")
    schedule = Schedule.objects.create(meeting=meeting, owner=plainman, name="test-agenda", visible=True, public=True)
    unofficial_schedule = Schedule.objects.create(meeting=meeting, owner=plainman, name="test-unofficial-agenda", visible=True, public=True)

    # test room
    pname = RoomResourceName.objects.create(name='projector',slug='proj')
    projector = ResourceAssociation.objects.create(name=pname,icon="notfound.png",desc="Basic projector")
    room = Room.objects.create(meeting=meeting, name="Test Room", capacity=123, functional_name="Testing Ground")
    room.session_types.add("session")
    room.resources.add(projector)
    asname = RoomResourceName.objects.get(slug='audiostream')
    UrlResource.objects.create(name=asname, room=room, url='http://ietf{number}streaming.dnsalias.net/ietf/ietf{number}1.m3u'.format(number=meeting.number))

    # another room
    breakfast_room = Room.objects.create(meeting=meeting, name="Breakfast Room", capacity=40)
    breakfast_room.session_types.add("lead")

    # slots
    session_date = meeting.date + datetime.timedelta(days=1)
    slot1 = TimeSlot.objects.create(meeting=meeting, type_id="session", duration=30 * 60, location=room,
                                    time=datetime.datetime.combine(session_date, datetime.time(9, 30)))
    slot2 = TimeSlot.objects.create(meeting=meeting, type_id="session", duration=30 * 60, location=room,
                                    time=datetime.datetime.combine(session_date, datetime.time(10, 30)))
    breakfast_slot = TimeSlot.objects.create(meeting=meeting, type_id="lead", duration=90 * 60,
                                   location=breakfast_room, 
                                   time=datetime.datetime.combine(session_date, datetime.time(7,0)))
    # mars WG
    mars = Group.objects.get(acronym='mars')
    mars_session = Session.objects.create(meeting=meeting, group=mars,
                                          attendees=10, requested_by=system_person,
                                          requested_duration=20, status_id="schedw",
                                          scheduled=datetime.datetime.now(),type_id="session")
    SchedTimeSessAssignment.objects.create(timeslot=slot1, session=mars_session, schedule=schedule)
    SchedTimeSessAssignment.objects.create(timeslot=slot2, session=mars_session, schedule=unofficial_schedule)

    # ames WG
    ames_session = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym="ames"),
                                          attendees=10, requested_by=system_person,
                                          requested_duration=20, status_id="schedw",
                                          scheduled=datetime.datetime.now(),type_id="session")
    SchedTimeSessAssignment.objects.create(timeslot=slot2, session=ames_session, schedule=schedule)
    SchedTimeSessAssignment.objects.create(timeslot=slot1, session=ames_session, schedule=unofficial_schedule)

    # IESG breakfast
    iesg_session = Session.objects.create(meeting=meeting, group=Group.objects.get(acronym="iesg"),
                                          name="IESG Breakfast",
                                          attendees=25, requested_by=system_person,
                                          requested_duration=20, status_id="schedw",
                                          scheduled=datetime.datetime.now(),type_id="lead")
    SchedTimeSessAssignment.objects.create(timeslot=breakfast_slot, session=iesg_session, schedule=schedule)
    # No breakfast on unofficial schedule

    meeting.agenda = schedule
    meeting.save()

    # Convenience for the tests
    meeting.unofficial_schedule = unofficial_schedule
    

    doc = DocumentFactory.create(name='agenda-42-mars', type_id='agenda', title="Agenda",
        external_url="agenda-42-mars.txt", group=mars, rev='00', states=[('draft','active')])
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev)) # 

    doc = DocumentFactory.create(name='minutes-42-mars', type_id='minutes', title="Minutes",
        external_url="minutes-42-mars.txt", group=mars, rev='00', states=[('minutes','active')])
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))

    doc = DocumentFactory.create(name='slides-42-mars-1-active', type_id='slides', title="Slideshow",
        external_url="slides-42-mars.txt", group=mars, rev='00',
        states=[('slides','active'), ('reuse_policy', 'single')])
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))

    doc = DocumentFactory.create(name='slides-42-mars-2-deleted', type_id='slides',
        title="Bad Slideshow", external_url="slides-42-mars-2-deleted.txt", group=mars, rev='00',
        states=[('slides','deleted'), ('reuse_policy', 'single')])
    mars_session.sessionpresentation_set.add(SessionPresentation(session=mars_session,document=doc,rev=doc.rev))
    
    # Future Interim Meetings
    date = datetime.date.today() + datetime.timedelta(days=365)
    date2 = datetime.date.today() + datetime.timedelta(days=1000)
    ames = Group.objects.get(acronym="ames")

    make_interim_meeting(group=mars,date=date,status='sched')
    make_interim_meeting(group=mars,date=date2,status='apprw')
    make_interim_meeting(group=ames,date=date,status='canceled')
    make_interim_meeting(group=ames,date=date2,status='apprw')

    return meeting



