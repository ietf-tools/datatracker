import json

from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.http import QueryDict
from django.http import Http404
from django.views.decorators.http import require_POST

from ietf.ietfauth.utils import role_required, has_role
from ietf.meeting.helpers import get_meeting, get_schedule, agenda_permissions, get_person_by_email, get_schedule_by_name
from ietf.meeting.models import TimeSlot, Session, Schedule, Room, Constraint, SchedTimeSessAssignment, ResourceAssociation
from ietf.meeting.views   import edit_timeslots, edit_agenda

import debug                            # pyflakes:ignore

def is_truthy_enough(value):
    return not (value == "0" or value == 0 or value=="false")

# look up a schedule by number, owner and schedule name, returning an API error if it can not be found
def get_meeting_schedule(num, owner, name):
    meeting = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)

    if schedule is None or person is None or meeting is None:
        meeting_pk = 0
        person_pk  = 0
        schedule_pk =0
        # to make diagnostics more meaningful, log what we found
        if meeting:
            meeting_pk = meeting.pk
        if person:
            person_pk = person.pk
        if schedule:
            schedule_pk=schedule.pk
        return HttpResponse(json.dumps({'error' : 'invalid meeting=%s/person=%s/schedule=%s' % (num,owner,name),
                                        'meeting': meeting_pk,
                                        'person':  person_pk,
                                        'schedule': schedule_pk}),
                            content_type="application/json",
                            status=404);
    return meeting, person, schedule



# should asking if an agenda is read-only require any kind of permission?
def agenda_permission_api(request, num, owner, name):
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)

    save_perm   = False
    secretariat = False
    cansee      = False
    canedit     = False
    owner_href  = ""

    if schedule is not None:
        cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)
        owner_href = request.build_absolute_uri(schedule.owner.json_url())

    if has_role(request.user, "Area Director") or secretariat:
        save_perm  = True

    return HttpResponse(json.dumps({'secretariat': secretariat,
                                    'save_perm':   save_perm,
                                    'read_only':   canedit==False,
                                    'owner_href':  owner_href}),
                        content_type="application/json")

#############################################################################
## ROOM API
#############################################################################
from django.forms.models import modelform_factory
AddRoomForm = modelform_factory(Room, exclude=('meeting',))

# no authorization required
def timeslot_roomlist(request, mtg):
    rooms = mtg.room_set.all()
    json_array=[]
    for room in rooms:
        json_array.append(room.json_dict(request.build_absolute_uri('/')))
    return HttpResponse(json.dumps(json_array),
                        content_type="application/json")

@role_required('Secretariat')
def timeslot_addroom(request, meeting):
    newroomform = AddRoomForm(request.POST)
    if not newroomform.is_valid():
        return HttpResponse(status=404)

    newroom = newroomform.save(commit=False)
    newroom.meeting = meeting
    newroom.save()
    newroom.create_timeslots()

    if "HTTP_ACCEPT" in request.META and "application/json" in request.META['HTTP_ACCEPT']:
        return redirect(timeslot_roomurl, meeting.number, newroom.pk)
    else:
        return redirect(edit_timeslots, meeting.number)

@role_required('Secretariat')
def timeslot_delroom(request, meeting, roomid):
    room = get_object_or_404(meeting.room_set, pk=roomid)

    room.delete_timeslots()
    room.delete()
    return HttpResponse('{"error":"none"}', status = 200)

@role_required('Secretariat')
def timeslot_updroom(request, meeting, roomid):
    room = get_object_or_404(meeting.room_set, pk=roomid)

    if "name" in request.POST:
        room.name = request.POST["name"]

    if "capacity" in request.POST:
        room.capacity = request.POST["capacity"]

    if "resources" in request.POST:
        new_resource_ids = request.POST["resources"]
        new_resources = [ ResourceAssociation.objects.get(pk=a)
                          for a in new_resource_ids]
        room.resources = new_resources

    room.save()
    return HttpResponse('{"error":"none"}', status = 200)

def timeslot_roomsurl(request, num=None):
    meeting = get_meeting(num)

    if request.method == 'GET':
        return timeslot_roomlist(request, meeting)
    elif request.method == 'POST':
        return timeslot_addroom(request, meeting)

    # unacceptable reply
    return HttpResponse(status=406)

def timeslot_roomurl(request, num=None, roomid=None):
    meeting = get_meeting(num)

    if request.method == 'GET':
        room = get_object_or_404(meeting.room_set, pk=roomid)
        return HttpResponse(json.dumps(room.json_dict(request.build_absolute_uri('/'))),
                            content_type="application/json")
    elif request.method == 'PUT':
        return timeslot_updroom(request, meeting, roomid)
    elif request.method == 'DELETE':
        return timeslot_delroom(request, meeting, roomid)

#############################################################################
## DAY/SLOT API
##  -- this creates groups of timeslots, and associated schedtimesessassignments.
#############################################################################
AddSlotForm = modelform_factory(TimeSlot, exclude=('meeting','name','location','sessions', 'modified'))

# no authorization required to list.
def timeslot_slotlist(request, mtg):
    slots = mtg.timeslot_set.all()
    # Restrict graphical editing to slots of type 'session' for now
    slots = slots.filter(type__slug='session')
    json_array=[]
    for slot in slots:
        json_array.append(slot.json_dict(request.build_absolute_uri('/')))
    return HttpResponse(json.dumps(json_array, sort_keys=True, indent=2),
                        content_type="application/json")

@role_required('Secretariat')
def timeslot_addslot(request, meeting):
    addslotform = AddSlotForm(request.POST)
    #debug.log("newslot: %u" % ( addslotform.is_valid() ))
    if not addslotform.is_valid():
        return HttpResponse(status=404)

    newslot = addslotform.save(commit=False)
    newslot.meeting = meeting
    newslot.save()

    # no longer create concurrent timeslots, because they will default, when there is
    # no timeslots, to unavailable, which can be created later on.
    # newslot.create_concurrent_timeslots()

    # XXX FIXME: timeslot_dayurl is undefined.  Placeholder:
    # timeslot_dayurl = None
    # XXX FIXME: newroom is undefined.  Placeholder:
    # newroom = None
    values   = newslot.json_dict(request.build_absolute_uri('/'))
    response = HttpResponse(json.dumps(values),
                            content_type="application/json",
                            status=201)
    response['Location'] = values['href']
    return response

@role_required('Secretariat')
def timeslot_updslot(request, meeting, slotid):
    slot = get_object_or_404(meeting.timeslot_set, pk=slotid)

    # at present, updates to the purpose only is supported.
    # updates to time or duration would need likely need to be
    # propogated to the entire vertical part of the grid, and nothing
    # needs to do that yet.
    if request.method == 'POST':
        put_vars = request.POST
        slot.type_id = put_vars["purpose"]
    else:
        put_vars = QueryDict(request.body)
        slot.type_id = put_vars.get("purpose")

    slot.save()

    # need to return the new object.
    dict1 = slot.json_dict(request.build_absolute_uri('/'))
    dict1['message'] = 'valid'
    return HttpResponse(json.dumps(dict1),
                        content_type="application/json")

@role_required('Secretariat')
def timeslot_delslot(request, meeting, slotid):
    slot = get_object_or_404(meeting.timeslot_set, pk=slotid)

    # this will delete self as well.
    slot.delete_concurrent_timeslots()
    return HttpResponse('{"error":"none"}', status = 200)

def timeslot_slotsurl(request, num=None):
    meeting = get_meeting(num)

    if request.method == 'GET':
        return timeslot_slotlist(request, meeting)
    elif request.method == 'POST':
        return timeslot_addslot(request, meeting)

    # unacceptable reply
    return HttpResponse(status=406)

def timeslot_sloturl(request, num=None, slotid=None):
    meeting = get_meeting(num)

    if request.method == 'GET':
        slot = get_object_or_404(meeting.timeslot_set, pk=slotid)
        return HttpResponse(json.dumps(slot.json_dict(request.build_absolute_uri('/'))),
                            content_type="application/json")
    elif request.method == 'POST' or request.method == 'PUT':
        return timeslot_updslot(request, meeting, slotid)
    elif request.method == 'DELETE':
        return timeslot_delslot(request, meeting, slotid)

#############################################################################
## Agenda List API
#############################################################################
AgendaEntryForm = modelform_factory(Schedule, exclude=('meeting','owner'))
EditAgendaEntryForm = modelform_factory(Schedule, exclude=('meeting','owner', 'name'))

@role_required('Area Director','Secretariat')
def agenda_list(request, mtg):
    agendas = mtg.schedule_set.all()
    json_array=[]
    for agenda in agendas:
        json_array.append(agenda.json_dict(request.build_absolute_uri('/')))
    return HttpResponse(json.dumps(json_array),
                        content_type="application/json")

# duplicates save-as functionality below.
@role_required('Area Director','Secretariat')
def agenda_add(request, meeting):
    newagendaform = AgendaEntryForm(request.POST)
    if not newagendaform.is_valid():
        return HttpResponse(status=404)

    newagenda = newagendaform.save(commit=False)
    newagenda.meeting = meeting
    newagenda.owner   = request.user.person
    newagenda.save()

    if "HTTP_ACCEPT" in request.META and "application/json" in request.META['HTTP_ACCEPT']:
        return redirect(agenda_infourl, meeting.number, newagenda.owner_email(), newagenda.name)
    else:
        return redirect(edit_agenda, meeting.number, newagenda.owner_email(), newagenda.name)

@require_POST
def agenda_update(request, meeting, schedule):
    # forms are completely useless for update actions that want to
    # accept a subset of values. (huh? we could use required=False)

    user = request.user

    if not user.is_authenticated():
        return HttpResponse({'error':'no permission'}, status=403)

    cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)
    #read_only = not canedit ## not used

    # TODO: Secretariat should always get canedit
    if not (canedit or secretariat):
        return HttpResponse({'error':'no permission'}, status=403)

    if "public" in request.POST:
        schedule.public = is_truthy_enough(request.POST["public"])

    if "visible" in request.POST:
        schedule.visible = is_truthy_enough(request.POST["visible"])

    if "name" in request.POST:
        schedule.name = request.POST["name"]

    schedule.save()

    # enforce that a non-public schedule can not be the public one.
    if meeting.agenda == schedule and not schedule.public:
        meeting.agenda = None
        meeting.save()

    if "HTTP_ACCEPT" in request.META and "application/json" in request.META['HTTP_ACCEPT']:
        return HttpResponse(json.dumps(schedule.json_dict(request.build_absolute_uri('/'))),
                            content_type="application/json")
    else:
        return redirect(edit_agenda, meeting.number, schedule.owner_email(), schedule.name)

@role_required('Secretariat')
def agenda_del(request, meeting, schedule):
    schedule.delete_assignments()
    #debug.log("deleting meeting: %s agenda: %s" % (meeting, meeting.agenda))
    if meeting.agenda == schedule:
        meeting.agenda = None
        meeting.save()
    schedule.delete()
    return HttpResponse('{"error":"none"}', status = 200)

def agenda_infosurl(request, num=None):
    meeting = get_meeting(num)

    if request.method == 'GET':
        return agenda_list(request, meeting)
    elif request.method == 'POST':
        return agenda_add(request, meeting)

    # unacceptable action
    return HttpResponse(status=406)

def agenda_infourl(request, num=None, owner=None, name=None):
    meeting  = get_meeting(num)
    person   = get_person_by_email(owner)
    schedule = get_schedule_by_name(meeting, person, name)
    if schedule is None:
        raise Http404("No meeting information for meeting %s schedule %s available" % (num,name))

    #debug.log("results in agenda: %u / %s" % (schedule.id, request.method))

    if request.method == 'GET':
        return HttpResponse(json.dumps(schedule.json_dict(request.build_absolute_uri('/'))),
                            content_type="application/json")
    elif request.method == 'POST':
        return agenda_update(request, meeting, schedule)
    elif request.method == 'DELETE':
        return agenda_del(request, meeting, schedule)
    else:
        return HttpResponse(status=406)

#############################################################################
## Meeting API  (very limited)
#############################################################################

def meeting_get(request, meeting):
    return HttpResponse(json.dumps(meeting.json_dict(request.build_absolute_uri('/')),
                                sort_keys=True, indent=2),
                        content_type="application/json")

@role_required('Secretariat')
def meeting_update(request, meeting):
    # at present, only the official agenda can be updated from this interface.

    #debug.log("1 meeting.agenda: %s / %s / %s" % (meeting.agenda, update_dict, request.body))
    if "agenda" in request.POST:
        value = request.POST["agenda"]
        #debug.log("4 meeting.agenda: %s" % (value))
        if not value or value == "None": # value == "None" is just weird, better with empty string
            meeting.set_official_agenda(None)
        else:
            schedule = get_schedule(meeting, value)
            if not schedule.public:
                return HttpResponse(status = 406)
            #debug.log("3 meeting.agenda: %s" % (schedule))
            meeting.set_official_agenda(schedule)

    #debug.log("2 meeting.agenda: %s" % (meeting.agenda))
    meeting.save()
    return meeting_get(request, meeting)

def meeting_json(request, num):
    meeting = get_meeting(num)

    if request.method == 'GET':
        return meeting_get(request, meeting)
    elif request.method == 'POST':
        return meeting_update(request, meeting)
    else:
        return HttpResponse(status=406)


#############################################################################
## Session details API functions
#############################################################################

def session_json(request, num, sessionid):
    meeting = get_meeting(num)

    try:
        session = meeting.session_set.get(pk=int(sessionid))
    except Session.DoesNotExist:
#        return json.dumps({'error':"no such session %s" % sessionid})
        return HttpResponse(json.dumps({'error':"no such session %s" % sessionid}),
                            status = 404,
                            content_type="application/json")

    sess1 = session.json_dict(request.build_absolute_uri('/'))
    return HttpResponse(json.dumps(sess1, sort_keys=True, indent=2),
                        content_type="application/json")

# get group of all sessions.
def sessions_json(request, num):
    meeting = get_meeting(num)

    sessions = meeting.sessions_that_can_meet.all()

    sess1_dict = [ x.json_dict(request.build_absolute_uri('/')) for x in sessions ]
    return HttpResponse(json.dumps(sess1_dict, sort_keys=True, indent=2),
                        content_type="application/json")

#############################################################################
## Scheduledsesion
#############################################################################

# this creates an entirely *NEW* schedtimesessassignment
def assignments_post(request, meeting, schedule):
    cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)
    if not canedit:
        return HttpResponse(json.dumps({'error':'no permission to modify this agenda'}),
                            status = 403,
                            content_type="application/json")

    # get JSON out of raw body. XXX should check Content-Type!
    newvalues = json.loads(request.body)
    if not ("session_id" in newvalues) or not ("timeslot_id" in newvalues):
        return HttpResponse(json.dumps({'error':'missing values, timeslot_id and session_id required'}),
                            status = 406,
                            content_type="application/json")

    ss1 = SchedTimeSessAssignment(schedule = schedule,
                           session_id  = newvalues["session_id"],
                           timeslot_id = newvalues["timeslot_id"])
    if("extendedfrom_id" in newvalues):
        val = int(newvalues["extendedfrom_id"])
        try:
            ss2 = schedule.assignments.get(pk = val)
            ss1.extendedfrom = ss2
        except SchedTimeSessAssignment.DoesNotExist:
            return HttpResponse(json.dumps({'error':'invalid extendedfrom value: %u' % val}),
                                status = 406,
                                content_type="application/json")
    ss1.save()
    ss1_dict = ss1.json_dict(request.build_absolute_uri('/'))
    response = HttpResponse(json.dumps(ss1_dict),
                        status = 201,
                        content_type="application/json")
    # 201 code needs a Location: header.
    response['Location'] = ss1_dict["href"],
    return response

def assignments_get(request, num, schedule):
    assignments = schedule.assignments.all()

    sess1_dict = [ x.json_dict(request.build_absolute_uri('/')) for x in assignments ]
    return HttpResponse(json.dumps(sess1_dict, sort_keys=True, indent=2),
                        content_type="application/json")

# this returns the list of scheduled sessions for the given named agenda
def assignments_json(request, num, owner, name):
    meeting, person, schedule = get_meeting_schedule(num, owner, name)

    if request.method == 'GET':
        return assignments_get(request, meeting, schedule)
    elif request.method == 'POST':
        return assignments_post(request, meeting, schedule)
    else:
        return HttpResponse(json.dumps({'error':'inappropriate action: %s' % (request.method)}),
                            status = 406,
                            content_type="application/json")

# accepts both POST and PUT in order to implement Postel Doctrine.
def assignment_update(request, meeting, schedule, ss):
    cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)
    if not canedit:
        return HttpResponse(json.dumps({'error':'no permission to update this agenda'}),
                            status = 403,
                            content_type="application/json")

    if request.method == 'POST':
        put_vars = request.POST
        ss.pinned = is_truthy_enough(put_vars["pinned"])
    else:
        put_vars = QueryDict(request.body)
        ss.pinned = is_truthy_enough(put_vars.get("pinned"))

    ss.save()
    return HttpResponse(json.dumps({'message':'valid'}),
                        content_type="application/json")

def assignment_delete(request, meeting, schedule, ss):
    cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)
    if not canedit:
        return HttpResponse(json.dumps({'error':'no permission to update this agenda'}),
                            status = 403,
                            content_type="application/json")

    # in case there is, somehow, more than one item with the same pk.. XXX
    assignments = schedule.assignments.filter(pk = ss.pk)
    if len(assignments) == 0:
        return HttpResponse(json.dumps({'error':'no such object'}),
                            status = 404,
                            content_type="application/json")
    count=0
    for ss in assignments:
        ss.delete()
        count += 1

    return HttpResponse(json.dumps({'result':"%u objects deleted"%(count)}),
                        status = 200,
                        content_type="application/json")

def assignment_get(request, meeting, schedule, ss):
    cansee,canedit,secretariat = agenda_permissions(meeting, schedule, request.user)

    if not cansee:
        return HttpResponse(json.dumps({'error':'no permission to see this agenda'}),
                            status = 403,
                            content_type="application/json")

    sess1_dict = ss.json_dict(request.build_absolute_uri('/'))
    return HttpResponse(json.dumps(sess1_dict, sort_keys=True, indent=2),
                        content_type="application/json")

# this return a specific session, updates a session or deletes a SPECIFIC scheduled session
def assignment_json(request, num, owner, name, assignment_id):
    meeting, person, schedule = get_meeting_schedule(num, owner, name)

    assignments = schedule.assignments.filter(pk = assignment_id)
    if len(assignments) == 0:
        return HttpResponse(json.dumps({'error' : 'invalid assignment'}),
                            content_type="application/json",
                            status=404);
    ss = assignments[0]

    if request.method == 'GET':
        return assignment_get(request, meeting, schedule, ss)
    elif request.method == 'PUT' or request.method=='POST':
        return assignment_update(request, meeting, schedule, ss)
    elif request.method == 'DELETE':
        return assignment_delete(request, meeting, schedule, ss)

#############################################################################
## Constraints API
#############################################################################


# Would like to cache for 1 day, but there are invalidation issues.
#@cache_page(86400)
def constraint_json(request, num, constraintid):
    meeting = get_meeting(num)

    try:
        constraint = meeting.constraint_set.get(pk=int(constraintid))
    except Constraint.DoesNotExist:
        return HttpResponse(json.dumps({'error':"no such constraint %s" % constraintid}),
                            status = 404,
                            content_type="application/json")

    json1 = constraint.json_dict(request.build_absolute_uri('/'))
    return HttpResponse(json.dumps(json1, sort_keys=True, indent=2),
                        content_type="application/json")


# Cache for 2 hour2
#@cache_page(7200)
# caching is a problem if there Host: header changes.
#
def session_constraints(request, num, sessionid):
    meeting = get_meeting(num)

    #print "Getting meeting=%s session contraints for %s" % (num, sessionid)
    try:
        session = meeting.session_set.get(pk=int(sessionid))
    except Session.DoesNotExist:
        return json.dumps({"error":"no such session"})

    constraint_list = session.constraints_dict(request.build_absolute_uri('/'))

    json_str = json.dumps(constraint_list,
                          sort_keys=True, indent=2),
    #print "  gives: %s" % (json_str)

    return HttpResponse(json_str, content_type="application/json")



