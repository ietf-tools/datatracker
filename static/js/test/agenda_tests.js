test( "hello test", function() {
  ok( 1 == "1", "Passed!" );
});

test( "TimeSlot Create test", function() {
    reset_globals();
    var nts = make_timeslot({"timeslot_id":"123",
                             "room"       :"Regency A",
                             "time"       :"0900",
                             "date"       :"2013-11-04",
                             "domid"      :"regencya_2013-11-04_0900"});
    equal(nts.slot_title(), "id#123 dom:regencya_2013-11-04_0900", "slot_title correct");
});

asyncTest("Load Timeslots", function() {
    reset_globals();
    expect( 1 );     // expect one assertion.

    var ts_promise = load_timeslots("/meeting/83/timeslots.json");
    ts_promise.done(function() {
        equal(Object.keys(agenda_globals.timeslot_byid).length, 179, "179 timeslots loaded");
        start();
    });
});

asyncTest("Load Sessions", function() {
    reset_globals();
    expect( 1 );     // expect one assertion.

    var session_promise = load_sessions("/meeting/83/sessions.json");
    session_promise.done(function() {
        equal(Object.keys(agenda_globals.meeting_objs).length, 145, "145 sessions loaded");
        start();
    });
});

asyncTest("Load ScheduledSlot (ticket 1210)", function() {
    expect( 1 );     // expect one assertion.

    var ss_promise = full_83_setup();
    ss_promise.done(function() {
        equal(Object.keys(agenda_globals.slot_objs).length, 148, "148 scheduled sessions loaded");
        start();
    });
});

asyncTest( "move a session using the API (ticket 1211)", function() {
    expect(4);

    var ss_promise = full_83_setup();
    ss_promise.done(function() {
        equal(Object.keys(agenda_globals.slot_objs).length, 148, "148 scheduled sessions loaded");

        // now move a session.. like selenium test, move forced from Monday to Friday:
        // monday_room_253  = is #room208_2012-03-26_1510
        // friday_room_252A = is #room209_2012-03-30_1230

        var forces_list  = agenda_globals.sessions_objs["forces"];
        var forces       = forces_list[0];
        var from_slot_id = "room208_2012-03-26_1510";
        var from_slot    = agenda_globals.timeslot_bydomid[from_slot_id];
        var to_slot_id   = "room209_2012-03-30_1230";
        var to_slot      = agenda_globals.timeslot_bydomid[to_slot_id];
        var ui           = mock_ui_draggable();
        var dom_obj      = "#" + to_slot_id;

        /* current situation was tested in above test, so go ahead */
        /* and move "richard" to another slot  */

        var move_promise = move_slot({"session": forces,
                                      "to_slot_id":  to_slot_id,
                                      "to_slot":     to_slot,
                                      "from_slot_id":from_slot_id,
                                      "from_slot":   [from_slot],
                                      "bucket_list": false,
                                      "ui":          ui,
                                      "dom_obj":     dom_obj,
                                      "force":       true});
        notEqual(move_promise, undefined);

        if(move_promise != undefined) {
            // now we need to check that it is all been done.
            move_promise.done(function() {
                // see that the placed is right.
                equal(forces.slot.domid, to_slot_id);

                // now move the item back again.

                var return_promise = move_slot({"session": forces,
                                                "to_slot_id":  from_slot_id,
                                                "to_slot":     from_slot,
                                                "from_slot_id":to_slot_id,
                                                "from_slot":   [to_slot],
                                                "bucket_list": false,
                                                "ui":          ui,
                                                "dom_obj":     dom_obj,
                                                "force":       true});

                return_promise.done(function() {
                    // see that the placed is right.
                    equal(forces.slot.domid, from_slot_id);
                    start();
                });
            });
        } else {
            // it is not legitimate to wind up here, but it does
            // keep the test cases from hanging.
            start();
        }
    });
});

test( "3x8 grid create (ticket 1212 - part 1)", function() {
    expect(0);        // just make sure things run without error
    reset_globals();

    t_slots = three_by_eight_grid();
    t_sessions = make_6_sessions();
    place_6_sessions(t_slots, t_sessions);
});

test( "calculate conflict columns for henry (ticket 1212 - part 2)", function() {
    expect(10);

    scheduledsession_post_href = "/test/agenda_ui.html";

    var henry = henry_setup();
    equal(henry.session_id, 1);

    equal(henry.column_class_list.length, 1);
    equal(henry.column_class_list[0].room, "apple");
    equal(henry.column_class_list[0].time, "0900");
    equal(henry.column_class_list[0].date, "2013-12-03");

    equal(henry.conflicts.length, 2);

    var conflict0 = henry.conflicts[0];
    equal(conflict0.conflict_groupP(), true);

    var classes = conflict0.column_class_list();
    var cc00 = classes[0];
    equal(cc00.th_tag, ".day_2013-12-02-1300");

    var conflict1 = henry.conflicts[1];
    equal(conflict1.conflict_groupP(), true);

    var classes = conflict1.column_class_list();
    var cc10 = classes[0];
    equal(cc10.th_tag, ".day_2013-12-02-1300");
});

test( "re-calculate conflict columns for henry (ticket 1213)", function() {
    expect(5);
    reset_globals();

    scheduledsession_post_href = "/test/agenda_ui.html";
    agenda_globals.__debug_session_move = true;

    var henry = henry_setup();
    equal(henry.session_id, 1);

    var richard = richard_move();
    var conflict0 = henry.conflicts[0];
    equal(conflict0.conflict_groupP(), true);

    var classes = conflict0.column_class_list();
    var cc00 = classes[0];
    equal(cc00.th_tag, ".day_2013-12-02-1300");

    var conflict1 = henry.conflicts[1];
    equal(conflict1.conflict_groupP(), true);

    var classes = conflict1.column_class_list();
    var cc10 = classes[0];
    equal(cc10.th_tag, ".day_2013-12-02-0900");
});

test( "build WG template for regular group (ticket #1135)", function() {
    reset_globals();
    var nts = make_timeslot({"timeslot_id":"123",
                             "room"       :"Regency A",
                             "time"       :"0900",
                             "date"       :"2013-11-04",
                             "domid"      :"regencya_2013-11-04_0900"});

    // this is from http://localhost:8000/meeting/83/session/2157.json
    var group1 = session_obj(
        {
            "agenda_note": "",
            "area": "SEC",
            "attendees": "45",
            "bof": "False",
            "comments": "please, no evening sessions.",
            "description": "Public-Key Infrastructure (X.509)",
            "group": {
                "acronym": "pkix",
                "ad_href": "http://localhost:8000/person/19483.json",
                "comments": "1st met, 34th IETF Dallas, TX (December 4-8, 1995)",
                "href": "http://localhost:8000/group/pkix.json",
                "list_archive": "http://www.ietf.org/mail-archive/web/pkix/",
                "list_email": "pkix@ietf.org",
                "list_subscribe": "pkix-request@ietf.org",
                "name": "Public-Key Infrastructure (X.509)",
                "parent_href": "http://localhost:8000/group/sec.json",
                "state": "active",
                "type": "wg"
            },
            "group_acronym": "pkix",
            "group_href": "http://localhost:8000/group/pkix.json",
            "group_id": "1223",
            "href": "http://localhost:8000/meeting/83/session/2157.json",
            "name": "",
            "requested_by": "Stephen Kent",
            "requested_duration": "2.0",
            "requested_time": "2011-12-19",
            "session_id": "2157",
            "short_name": "pkix",
            "special_request": "*",
            "status": "Scheduled",
            "title": "pkix"
        });

    // validate that the session id is there as a basic check.
    ok(group1.event_template().search(/meeting_box_container/) > 0);
    ok(group1.event_template().search(/session_2157/) > 0);
    ok(group1.event_template().search(/wg_style /) > 0);
});

test( "build WG template for BOF group (ticket #1135)", function() {
    reset_globals();

    // this is from http://localhost:8000/meeting/83/session/2157.json
    var group1 = session_obj(
        {
            "agenda_note": "",
            "area": "GEN",
            "attendees": "50",
            "bof": "True",
            "comments": "",
            "description": "RFC Format",
            "group": {
                "acronym": "rfcform",
                "ad_href": "http://localhost:8000/person/5376.json",
                "comments": "",
                "href": "http://localhost:8000/group/rfcform.json",
                "list_archive": "",
                "list_email": "",
                "list_subscribe": "",
                "name": "RFC Format",
                "parent_href": "http://localhost:8000/group/gen.json",
                "state": "bof",
                "type": "wg"
            },
            "group_acronym": "rfcform",
            "group_href": "http://localhost:8000/group/rfcform.json",
            "group_id": "1845",
            "href": "http://localhost:8000/meeting/83/session/22081.json",
            "name": "",
            "requested_by": "Wanda Lo",
            "requested_duration": "1.0",
            "requested_time": "2012-02-27",
            "session_id": "22081",
            "short_name": "rfcform",
            "special_request": "",
            "status": "Scheduled",
            "title": "rfcform"
        }
    );

    // validate that the session id is there as a basic check.
    ok(group1.event_template().search(/meeting_box_container/) > 0);
    ok(group1.event_template().search(/session_22081/) > 0);
    ok(group1.event_template().search(/bof_style /) > 0);
});

test( "compare timeslots sanely (ticket #1135)", function() {
    var timeSlotA = {"timeslot_id":2383,
                 "room":"243",
                 "day":"2012-03-26T00:00:00.000Z",
                 "starttime":1300};

    var timeSlotB = {"timeslot_id":2389,
                 "room":"241",
                 "day":"2012-03-26T00:00:00.000Z",
                 "starttime":900};

    var timeSlotC = {"timeslot_id":2381,
                 "room":"245A",
                 "day":"2012-03-26T00:00:00.000Z",
                 "starttime":1300};

    var timeSlotD = {"timeslot_id":2382,
                 "room":"245A",
                 "day":"2012-03-27T00:00:00.000Z",
                 "starttime":1510};

    // three have the same day
    ok(timeSlotA.day == timeSlotB.day);
    ok(timeSlotA.day == timeSlotC.day);
    ok(timeSlotA.day <  timeSlotD.day);

    // two have the same starttime
    ok(timeSlotA.starttime == timeSlotC.starttime);

    // canonical order is B, A, C, D.
    equal(compare_timeslot(timeSlotB, timeSlotA), -1, "B < A");
    equal(compare_timeslot(timeSlotA, timeSlotC), -1, "A < C");
    equal(compare_timeslot(timeSlotC, timeSlotD), -1, "C < D");
    equal(compare_timeslot(timeSlotB, timeSlotD), -1, "B < D");
    equal(compare_timeslot(timeSlotA, timeSlotD), -1, "A < D");

});

asyncTest( "calculate info_room_select box (ticket 1220/1214)", function() {
    expect(3);

    var ss_promise = full_83_setup();

    ss_promise.done(function() {
        var box = calculate_room_select_box();

        // this is a box which has no session, and therefore no ss.
        // validate that calculate_name_select_box() provides all the timeslots
        ok(box.search(/Mon, 1510, Maillot/) > 0);
        ok(box.search(/undefined/) == -1);

        // this one crept in: it is breakfast!
        ok(box.search(/Mon, 0800, Halle Maillot A/) == -1);
        start();
    });
});

asyncTest( "calculate info_group_select box (ticket 1214)", function() {
    expect(1);

    var ss_promise = full_83_setup();

    ss_promise.done(function() {
        var box = calculate_name_select_box();

        // the list of all of the groups.
        // count the number of occurances of value=
        var count = 0;
        var valueloc = box.search(/value=/);
        while(valueloc != -1) {
            //console.log(count, "valueat",valueloc, "box contains", box);
            count += 1;
            // eat everything upto value=, and then a bit.
            box = box.substring(valueloc+1);
            valueloc = box.search(/value=/);
        }

        // 145 WG and other requests that "can meet"
        equal(count, 145);
        start();
    });
});

asyncTest( "look for an empty slot(ticket 1215)", function() {
    expect(1);

    var ss_promise = full_83_setup();

    ss_promise.done(function() {
        target_session = agenda_globals.sessions_objs["pcp"][0];
        ok(find_empty_slot(target_session) != null);
        start();
    });

});
