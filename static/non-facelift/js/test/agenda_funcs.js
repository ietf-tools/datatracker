// globals needed for tests cases.
var agenda_globals;
var scheduledsession_post_href = "/test/agenda_ui.html";
var read_only = false;
var days = [];

function reset_globals() {
    // hack to reach in and manipulate global specifically.
    window.agenda_globals = new AgendaGlobals();
}

function three_by_eight_grid() {
    var rooms = ["apple", "orange", "grape", "pineapple",
                 "tomato","squash", "raisin","cucumber" ];
    var times = [
        {"time":"0900", "date":"2013-12-02"},
        {"time":"1300", "date":"2013-12-02"},
        {"time":"0900", "date":"2013-12-03"}
    ];
    var slots = [{}];
    var slotid= 1;

    days.push("2013-12-02");
    days.push("2013-12-03");

    for(var roomkey in rooms) {
        var room = rooms[roomkey];
        for(var timekey in times) {
            var time = times[timekey];
            //console.log("data", room, time.date, time.time);
            slot = make_timeslot({"timeslot_id": slotid,
                                  "room" : room,
                                  "roomtype" : "session",
                                  "date" : time.date,
                                  "time" : time.time,
                                  "domid": "room" + roomkey + "_" + time.date + "_" + time.time
                                 });
            slots[slotid] = slot;
            slotid += 1;
        }
    }
    return slots;
}

function make_6_sessions() {
    monarchs = ["henry", "george", "richard", "victoria", "william", "elizabeth"];
    $.each(monarchs, function(index) {
        monarch = monarchs[index];
        console.log("monarch", monarch);
        var group = create_group_by_href("http://localhost:8000/group/"+monarch+".json");
        group.acronym = monarch;
        group.name    = "Royalty fun" + monarch;
        group.type  = "wg";
        group.group_id = 1
    });

    var sessions = {};
    var sessionid = 1;
    monarch = "henry";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "description": "Henry Beauclerc",
                     "session_id": sessionid,
                     "attendees":  50,
                     "short_name": monarch,
                     "comments":   "Long Live the King!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Pope Francis",
                     "requested_duration": "1.0",
                     "area" :      "TSV",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    monarch = "george";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "description": "Georg Ludwig",
                     "session_id": sessionid,
                     "attendees":  60,
                     "short_name": monarch,
                     "comments":   "Long Live the King!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Pope Bacon",
                     "requested_duration": "1.5",
                     "area" :      "SEC",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    monarch = "richard";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "description": "Richard the Lionheart",
                     "session_id": sessionid,
                     "attendees":  70,
                     "short_name": monarch,
                     "comments":   "Lion Hart!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Robin Hood",
                     "requested_duration": "2.0",
                     "area" :      "RTG",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    monarch = "victoria";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "description": "the grandmother of Europe",
                     "session_id": sessionid,
                     "attendees":  80,
                     "short_name": monarch,
                     "comments":   "Long Live the Queen!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Docter Who",
                     "requested_duration": "1.0",
                     "area" :      "INT",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    monarch = "william";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "description": "William the Conqueror",
                     "session_id": sessionid,
                     "attendees":  90,
                     "short_name": monarch,
                     "comments":   "Just Married!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Pope Francis",
                     "requested_duration": "2.5",
                     "area" :      "RAI",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    monarch = "elizabeth";
    sessions[monarch] =
        session_obj({"title":      monarch,
                     "session_id": sessionid,
                     "description": "Head of the Commonwealth",
                     "attendees":  100,
                     "short_name": monarch,
                     "comments":   "Long Live the Queen!",
                     "special_request": "",
                     "requested_time": "2013-11-27",
                     "requested_by":   "Margaret Thatcher",
                     "requested_duration": "1.0",
                     "area" :      "GEN",
                     "group_href": "http://localhost:8000/group/"+monarch+".json"
                    });
    sessionid += 1;

    return sessions;
}

function place_6_sessions(slots, sessions) {
    var ss_id = 1;
    make_ss({"scheduledsession_id": ss_id,
             "timeslot_id":         slots[3].timeslot_id,
             "session_id":          sessions["henry"].session_id});
    ss_id += 1;
    make_ss({"scheduledsession_id": ss_id,
             "timeslot_id":         slots[20].timeslot_id,
             "session_id":          sessions["george"].session_id});
    ss_id += 1;
    make_ss({"scheduledsession_id": ss_id,
             "timeslot_id":         slots[5].timeslot_id,
             "session_id":          sessions["richard"].session_id});
    ss_id += 1;
    make_ss({"scheduledsession_id": ss_id,
             "timeslot_id":         slots[9].timeslot_id,
             "session_id":          sessions["victoria"].session_id});
    ss_id += 1;
    make_ss({"scheduledsession_id": ss_id,
             "timeslot_id":         slots[13].timeslot_id,
             "session_id":          sessions["william"].session_id});
    // last session is unscheduled.
}

function conflict_4_sessions(sessions) {
    // fill in session constraints

    $.each(sessions, function(index) {
        var session = sessions[index];

        var deferred = $.Deferred();
        session.constraints_promise = deferred;

        // $.ajax has a success option.
        deferred.success = function(func) {
            deferred.done(function(obj) {
                func(obj, "success", {});
            });
        };

        deferred.resolve({});

        session.fill_in_constraints([]);
        find_and_populate_conflicts(session);
    });

    sessions["henry"].fill_in_constraints([
        {    "constraint_id": 21046,
             "href": "http://localhost:8000/meeting/83/constraint/21046.json",
             "meeting_href": "http://localhost:8000/meeting/83.json",
             "name": "conflict",
             "source_href": "http://localhost:8000/group/henry.json",
             "target_href": "http://localhost:8000/group/george.json"
        },
        {    "constraint_id": 21047,
             "href": "http://localhost:8000/meeting/83/constraint/21047.json",
             "meeting_href": "http://localhost:8000/meeting/83.json",
             "name": "conflic2",
             "source_href": "http://localhost:8000/group/henry.json",
             "target_href": "http://localhost:8000/group/richard.json"
        }]);
    find_and_populate_conflicts(sessions["henry"]);
}


function full_83_setup() {
    reset_globals();
    scheduledsession_post_href = "/meeting/83/schedule/mtg_83/sessions.json";
    var ts_promise      = load_timeslots("/meeting/83/timeslots.json");
    var session_promise = load_sessions("/meeting/83/sessions.json");
    var ss_promise      = load_scheduledsessions(ts_promise, session_promise,
                                                 scheduledsession_post_href)
    return ss_promise;
}

function henry_setup(sessions) {
    reset_globals();

    /* define a slot for unscheduled items */
    var unassigned = new ScheduledSlot();
    unassigned.make_unassigned();

    t_slots = three_by_eight_grid();
    t_sessions = make_6_sessions();
    place_6_sessions(t_slots, t_sessions);
    conflict_4_sessions(t_sessions);

    load_events();

    var henry0 = agenda_globals.sessions_objs["henry"];
    var henry = henry0[0];

    return henry;
}

var ss_id_next = 999;
function mock_scheduledslot_id(json) {
    if(json.scheduledsession_id == undefined) {
        console.log("adding scheduledsession_id to answer", ss_id_next);
        ss_id_next += 1;
        json.scheduledsession_id = ss_id_next;
    }
};

ScheduledSlot.prototype.initialize = function(json) {
    mock_scheduledslot_id(json);
    this.real_initialize(json);
}

function mock_ui_draggable() {
    // mock up the ui object.
    var ui = new Object();
    ui.draggable = new Object();
    ui.draggable.remove = function() { return true; };

    return ui;
}

function mock_dom_obj(domid) {
    // mock up the dom object
    var dom_obj = "#" + domid;

    // in the unit tests, the object won't exist, so make it.
    // when testing this test code, it might already be there
    if($(dom_obj).length == 0) {
        var div = document.createElement("div");
        div.innerHTML = "welcome";
        div.id = dom_obj;
    }
    return dom_obj;
}

function richard_move() {
    var richard0 = agenda_globals.sessions_objs["richard"];
    var richard = richard0[0];

    var ui = mock_ui_draggable();
    var dom_obj = mock_dom_obj(t_slots[4].domid);

    /* current situation was tested in above test, so go ahead */
    /* and move "richard" to another slot  */
    move_slot({"session": richard,
               "to_slot_id":  t_slots[4].domid,
               "to_slot":     t_slots[4],
               "from_slot_id":t_slots[5].domid,
               "from_slot":   [t_slots[5]],
               "bucket_list": false,
               "ui":          ui,
               "dom_obj":     dom_obj,
               "force":       true});

    return richard;
}
