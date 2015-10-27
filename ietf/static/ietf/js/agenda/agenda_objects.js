/*
*
*  FILE: agenda_objects.js
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*  Description:
*      Contains the objects relating to django's models.
*      As much business logic as possible should be here.
*      This file should be resuable by other than agenda_edit.js
*
*      Display logic should be contained in agenda_listeners.js
*
*   Functions:
*      - check_delimiter(inp)
*      - upperCaseWords(inp)
*
*/

function AgendaGlobals() {
    this.group_objs = {};
    this.slot_status = {};
    this.slot_objs   = {};
    this.meeting_objs = {};
    this.sessions_objs = {};
    this.timeslot_bydomid = {};
    this.timeslot_byid    = {};
    this.assignment_promise = undefined;
    this.timeslot_promise = undefined;
    this.__debug_session_move = false;
}

function createLine(x1,y1, x2,y2){
    var length = Math.sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2));
  var angle  = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
  var transform = 'rotate('+angle+'deg)';

    var line = $('<div>')
        .appendTo('#meetings')
        .addClass('line')
        .css({
          'position': '',
          'transform': transform
        })
        .width(length)
        .offset({left: x1, top: y1});

    return line;
}


function empty_callback(inp){
//    console.log('inp:', inp);
}

function get_all_constraints(){
    for(s in agenda_globals.meeting_objs){
       show_non_conflicting_spots(s)
    }

}

function show_all_conflicts(){
    console.log("showing all conflicts");
    for(sk in agenda_globals.meeting_objs) {
        var s = agenda_globals.meeting_objs[sk];
        s.display_conflict();
        s.display_personconflict();
    }
}

// not really used anymore -- just for debugging
function hide_all_conflicts(){
    for(sk in agenda_globals.meeting_objs) {
        var s = agenda_globals.meeting_objs[sk];
        s.hide_conflict();
    }
}

function get_all_conflicts(){
    var all_constraint_promises = [];
    var one_constraint;
    var sess1;
    //console.log("get_all_conflicts()");
    for(var s in agenda_globals.meeting_objs){
        sess1 = agenda_globals.meeting_objs[s];
        sess1.clear_conflict();
        sess1.display_conflict();

        one_constraint = sess1.retrieve_constraints_by_session();
        all_constraint_promises.push(one_constraint);
    }

    /* now make a promise that ends when all the conflicts are loaded */
    var all_constraints = $.when.apply($,all_constraint_promises);

    all_constraints.done(function() {
        for(var s in agenda_globals.meeting_objs) {
            var sess2 = agenda_globals.meeting_objs[s];
            sess2.examine_people_conflicts();
        }
    });
    return all_constraints;
}

var __debug_conflict_calculate = false;
var __verbose_conflict_calculate = false;

function calculate_real_conflict(conflict, vertical_location, room_tag, session_obj) {
    if(__debug_conflict_calculate) {
        console.log(" conflict check:", conflict.othergroup.acronym, "me:", vertical_location, room_tag);
    }

    if(session_obj.group.href == conflict.othergroup.href) {
        console.log("  session: ",session_obj.session_id, "lists conflict with self");
        return;
    }

    var osessions = conflict.othergroup.all_sessions;
    if(__debug_conflict_calculate) {
        console.log("  ogroup: ", conflict.othergroup.href, "me: ", session_obj.group.href);
    }
    if(conflict.othergroup === session_obj.group) {
        osessions = conflict.thisgroup.all_sessions;
    }
    if(osessions != null) {
        $.each(osessions, function(index) {
            osession = osessions[index];
            for(ccn in osession.column_class_list) {
                var value = osession.column_class_list[ccn];
                if(value != undefined) {
                    if(__debug_conflict_calculate) {
                        console.log("    vs: ",index, "session_id:",osession.session_id," at: ",value.column_tag, value.room_tag);
                    }
                    if(value.column_tag == vertical_location &&
                       value.room_tag   != room_tag) {
                        if(__verbose_conflict_calculate || __debug_conflict_calculate) {
                            console.log("real conflict:",session_obj.title," with: ",conflict.othergroup.acronym, " #session_",session_obj.session_id, value.room_tag, room_tag, value.column_tag, vertical_location);
                        }
                        // there is a conflict!
                        __DEBUG_SHOW_CONSTRAINT = $("#"+value[0]).children()[0];
                        session_obj.add_conflict(conflict);
                    }
                }
            }
        });
    }
}

var __DEBUG_SHOW_CONSTRAINT = null;
// can become a method now.
function find_and_populate_conflicts(session_obj) {
    if(__debug_conflict_calculate) {
        console.log("populating conflict:", session_obj.title, session_obj.column_class_list);
    }

    var room_tag = null;
    session_obj.reset_conflicts();

    for(ccn in session_obj.column_class_list) {
        var vertical_location = session_obj.column_class_list[ccn].column_tag;
        var room_tag          = session_obj.column_class_list[ccn].room_tag;

        if(session_obj.constraints.conflict != null){
            $.each(session_obj.constraints.conflict, function(i){
                var conflict = session_obj.constraints.conflict[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }
        if(session_obj.constraints.conflic2 != null){
            $.each(session_obj.constraints.conflic2, function(i){
                var conflict = session_obj.constraints.conflic2[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }
        if(session_obj.constraints.conflic3 != null){
            $.each(session_obj.constraints.conflic3, function(i){
                var conflict = session_obj.constraints.conflic3[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }

        if(session_obj.theirconstraints.conflict != null){
            $.each(session_obj.theirconstraints.conflict, function(i){
                var conflict = session_obj.theirconstraints.conflict[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }
        if(session_obj.theirconstraints.conflic2 != null){
            $.each(session_obj.theirconstraints.conflic2, function(i){
                var conflict = session_obj.theirconstraints.conflic2[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }
        if(session_obj.theirconstraints.conflic3 != null){
            $.each(session_obj.theirconstraints.conflic3, function(i){
                var conflict = session_obj.theirconstraints.conflic3[i];
                calculate_real_conflict(conflict, vertical_location, room_tag, session_obj);
            });
        }

        /* bethere constraints are processed in another loop */
    }
}


function show_non_conflicting_spots(ss_id){
    var conflict_spots = []
    $.each(conflict_classes, function(key){
       conflict_spots.push(conflict_classes[key].session.slot_status_key);
    });
    var empty_slots = find_empty_slots();
    conflict_spots.forEach(function(val){
       empty_slots.forEach(function(s){
           if(val == s.key){
           }
       });
    });
}

function find_empty_slots(){
    var empty_slots = [];
    $.each(slot_status, function(key){
       for(var i =0; i<slot_status[key].length; i++){
           if(slot_status[key][i].empty == "True" || slot_status[key][i].empty == true){
              var pos = { "index" :i, key:key } ;
              empty_slots.push(pos);
           }
       }
    });
    return empty_slots;
}


// ++++++++++++++++++
// Slot Object
function slot(){
}

/*
   check_delimiter(inp), where inp is a string.
       returns char.

   checks for what we should split a string by.
   mainly we are checking for a '/' or '-' character

   Maybe there is a js function for this. doing 'a' in "abcd" does not work.
 */
function check_delimiter(inp){
    for(var i =0; i<inp.length; i++){
       if(inp[i] == '/'){
           return '/';
       }
       else if(inp[i] == '-'){
           return '-';
       }
    }
    return ' ';

}

/*
   upperCaseWords(inp), where inp is a string.
       returns string

   turns the first letter of each word in a string to uppercase
   a word is something considered be something defined by the function
   check_delimiter(). ( '/' , '-' , ' ' )
*/
function upperCaseWords(inp){
    var newStr = "";
    var split = inp.split(check_delimiter(inp));

       for(i=0; i<split.length; i++){
              newStr = newStr+split[i][0].toUpperCase();
              newStr = newStr+split[i].slice(1,split[i].length);

              if(i+1 < split.length){ // so we don't get a extra space
                     newStr = newStr+" ";
              }
    }

       return newStr;

}

var daysofweek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// ++++++++++++++++++
// ColumnClass is an object that knows about columns, but also about
// columns + room (so it can identify a single slot, or a column of them)
function ColumnClass(room,date,time) {
    this.room = room;
    this.date = date;
    this.time = time;
    this.room_tag   = this.room+"_"+this.date+"_"+this.time;
    this.th_time    = this.date+"-"+this.time;
    this.column_tag = ".agenda-column-"+this.th_time;
    this.th_tag     = ".day_" + this.th_time;
};


// ++++++++++++++++++
// TimeSlot Object
//
//   { "timeslot_id":"{{timeslot.id}}",
//     "room"       :"{{timeslot.location|slugify}}",
//     "time"       :"{{timeslot.time|date:'Hi' }}",
//     "date"       :"{{timeslot.time|date:'Y-m-d'}}",
//     "domid"      :"{{timeslot.js_identifier}}"}
function TimeSlot(){
    this.timeslot_id  = undefined;
    this.room         = undefined;
    this.time         = undefined;
    this.date         = undefined;
    this.domid        = undefined;
    this.empty        = true;
    this.assignments = [];
    this.following_timeslot_id = undefined;
    this.unscheduled_box = false;
}

TimeSlot.prototype.initialize = function(json) {
    for(var key in json) {
       this[key]=json[key];
    }
    //console.log("timeslot processing: ", this.timeslot_id,
    //            this.room, this.date, this.time);

    this.column_class=new ColumnClass(this.room, this.date, this.time);

    this.day   = new Date(this.date);
    this.starttime = parseInt(this.time,10);
    var t = this.day.getUTCDay();
    if(this.room == "Unassigned"){
       this.short_string = "Unassigned";
    }
    else{
       this.short_string = daysofweek[t] + ", "+ this.time + ", " + this.room;
    }

    agenda_globals.timeslot_bydomid[this.domid] = this;
    agenda_globals.timeslot_byid[this.timeslot_id] = this;
};

TimeSlot.prototype.title = function() {
    return this.room + " "+this.date+" "+this.time;
};
TimeSlot.prototype.slot_title = function() {
    return "id#"+this.timeslot_id+" dom:"+this.domid;
};
TimeSlot.prototype.mark_empty = function() {
    if(agenda_globals.__debug_session_move) {
        console.log("marking slot empty", this.domid);
        $("#"+this.domid).html("empty");
    }
    this.empty = true;
};
TimeSlot.prototype.mark_occupied = function() {
    if(agenda_globals.__debug_session_move) {
        console.log("marking slot occupied", this.domid);

        // if it was empty before, then clear it (might have word "empty" in it)
        if(this.empty == true) {
            $("#"+this.domid).html("");
        }
    }
    this.empty = false;
};
TimeSlot.prototype.can_extend_right = function() {
    if(this.following_timeslot == undefined) {
        if(this.following_timeslot_id != undefined) {
            this.following_timeslot = agenda_globals.timeslot_byid[this.following_timeslot_id];
        }
    }
    if(this.following_timeslot == undefined) {
        console.log("can_extend_right:",this.timeslot_id," no slot to check");
        return false;
    } else {
        console.log("can_extend_right:",
                    this.slot_title()," for slot: ",
                    this.following_timeslot.slot_title(),
                    "is ",this.following_timeslot.empty);
        return this.following_timeslot.empty;
    }
};

function make_timeslot(json) {
    var ts = new TimeSlot();
    ts.initialize(json);
    return ts;
}

/* feed this an array of timeslots */
function make_timeslots(json, status, jqXHR) {
    $.each(json, function(index) {
        var thing = json[index];
        make_timeslot(thing);
    });
}

function load_timeslots(href) {
    if(agenda_globals.timeslot_promise == undefined) {
        agenda_globals.timeslot_promise = $.Deferred();
        var ts_promise = agenda_globals.timeslot_promise;

        var ts = $.ajax(href);
        ts.success(function(newobj, status, jqXHR) {
            make_timeslots(newobj);
            ts_promise.resolve(newobj);
            console.log("finished timeslot promise");
        });
    }
    return agenda_globals.timeslot_promise;
}


// ++++++++++++++++++
// ScheduledSlot Object
// SchedTimeSessAssignment is the DJANGO name for this object
// It represents a TimeSlot that can be assigned in this schedule.
//   { "assignment_id": "{{s.id}}",
//     "href:        "{{s.href}}",
//     "timeslot_id":"{{s.timeslot.id}}",
//     "session_id" :"{{s.session.id}}",
//     "extendedfrom_id"    :refers to another schedtimesessassignment by ss.id
function ScheduledSlot(){
    this.extendedfrom = undefined;
    this.extendedto   = undefined;
    this.extendedfrom_id = false;
    this.pinned       = false;
}

ScheduledSlot.prototype.room = function() {
    return this.timeslot.room;
};

ScheduledSlot.prototype.time = function() {
    return this.timeslot.time;
};

ScheduledSlot.prototype.date = function() {
    return this.timeslot.date;
};

ScheduledSlot.prototype.domid = function() {
    return this.timeslot.domid;
};

ScheduledSlot.prototype.column_class = function() {
    return this.timeslot.column_class;
};

ScheduledSlot.prototype.short_string = function() {
    return this.timeslot.short_string;
};

ScheduledSlot.prototype.saveit = function() {
    var myss = this;
    stuffjson = new Object();
    stuffjson.session_id  = this.session_id;
    stuffjson.timeslot_id = this.timeslot_id;
    if(this.extendedfrom_id != undefined && this.extendedfrom_id != false) {
        stuffjson.extendedfrom_id = this.extendedfrom_id;
    }

    var stuff = JSON.stringify(stuffjson, null, '\t');

    var saveit = $.ajax(assignments_post_href,{
        "content-type": "text/json",
        "type": "POST",
        "data": stuff,
    });
    // should do something on success and failure.
    saveit.done(function(result, status, jqXHR) {
        myss.initialize(result, "saveit");
        var session = myss.session;
        if(session != undefined) {
            session.placed(myss.timeslot);
        }
    });

    // return the promise, in case someone (tests!) needs to know when we are done.
    return saveit;
};

ScheduledSlot.prototype.set_pinned = function(state, completefunc) {
    var ss = this;
    var pinned_struct = { "pinned" : state };
    var pinned_update = $.ajax(this.href, {
        "content-type": "text/json",
        "type": "PUT",
        "data": pinned_struct,
    });

    pinned_update.success(function(result, status, jqXHR) {
        if(result.message != "valid") {
            alert("Update of pinned failed");
            return;
        }
        ss.pinned = state;
        completefunc(this);
    });
};



function remove_from_slot_status(domid, ss_id) {
    var found_at;
    if(agenda_globals.__debug_session_move) {
        console.log("remove", domid, agenda_globals.slot_status[domid]);
    }
    if(agenda_globals.slot_status[domid] != undefined) {
        $.each(agenda_globals.slot_status[domid], function(index, value) {
            if(agenda_globals.__debug_session_move) {
                console.log("  checking", index, value, ss_id);
            }
            if(value.assignment_id == ss_id) {
                found_at = index;
                return;
            }
        });
        if(found_at != undefined) {
            agenda_globals.slot_status[domid].splice(found_at, 1);
            console.log("removed", found_at, agenda_globals.slot_status[domid]);
        }
    } else {
        //console.log("  already empty");
    }
};

ScheduledSlot.prototype.deleteit = function() {
    var deleteit = $.ajax(this.href, {
        "content-type": "text/json",
        "type": "DELETE",
    });
    // now nuke self!
    var me = this;
    delete agenda_globals.slot_objs[this.assignment_id];
    remove_from_slot_status(this.domid(), this.assignment_id);
    return deleteit;
};

function update_if_not_undefined(old, newval) {
    if(newval != undefined) {
        return newval;
    } else {
        return old;
    }
}

ScheduledSlot.prototype.make_unassigned = function() {
    this.assignment_id	     = 0;
    this.empty               = true;
    this.session_id          = null;
    this.room                = "unassigned";
    this.time                = null;
    this.date                = null;
    this.timeslot            = new TimeSlot();
    this.timeslot.initialize({"domid":"sortable-list"});
    this.timeslot.unscheduled_box = true;
    this.timeslot.short_string = "Unscheduled";


    agenda_globals.slot_status[this.domid()]=[];
    agenda_globals.slot_status[this.domid()].push(this);
    agenda_globals.slot_objs[this.assignment_id] = this;
};

ScheduledSlot.prototype.real_initialize = function(json, extra) {
    /* do not copy everything over */
    this.pinned              = update_if_not_undefined(this.pinned, json.pinned);
    this.assignment_id	     = update_if_not_undefined(this.assignment_id, json.assignment_id);
    this.session_id          = update_if_not_undefined(this.session_id, json.session_id);
    this.timeslot_id         = update_if_not_undefined(this.timeslot_id, json.timeslot_id);
    this.href                = update_if_not_undefined(this.href, json.href);
    this.extendedfrom_id     = update_if_not_undefined(this.extendedfrom_id, json.extendedfrom_id);

    //console.log("timeslot_id", this.timeslot_id);
    this.timeslot            = agenda_globals.timeslot_byid[this.timeslot_id];
    if(this.timeslot != undefined && this.session_id != undefined) {
        this.timeslot.mark_occupied();
    }
    if(this.session_id != undefined) {
        this.session = agenda_globals.meeting_objs[this.session_id];
    }

    // translate Python booleans to JS.
    if(this.pinned == "True") {
        this.pinned = true;
    } else {
        this.pinned = false;
    }

    // timeslot should never be null, but if there is old/flaky
    // data it could happen, so guard against it.
    if(this.timeslot != undefined) {
        // do not include in data structures if session_id is nil
        // the key so two sessions in the same timeslot
        if(agenda_globals.slot_status[this.domid()] == null) {
            agenda_globals.slot_status[this.domid()]=[];
        }
        if(this.session_id != undefined) {
            // remove any old duplicate that might exist.
            remove_from_slot_status(this.domid(), this.assignment_id);
            if(agenda_globals.__debug_session_move) {
                console.log(extra, "adding to slot_status", this.domid());
            }

            agenda_globals.slot_status[this.domid()].push(this);
            //console.log("filling slot_objs", this.assignment_id);
        }
    }

    agenda_globals.slot_objs[this.assignment_id] = this;
};
ScheduledSlot.prototype.initialize = ScheduledSlot.prototype.real_initialize;

function load_assignments(ts_promise, session_promise, href) {
    if(agenda_globals.assignment_promise == undefined) {
        agenda_globals.assignment_promise = $.Deferred();

        var ss = $.ajax(href);
        var ss_loaded = $.when(ss,ts_promise,session_promise);

        ss_loaded.done(function(result, status, jqXHR) {
            console.log("finished ss promise");

            newobj = result[0]
            $.each(newobj, function(index) {
                one = newobj[index];
                //console.log("ss has:", one);
                make_ss(one);
            });
            agenda_globals.assignment_promise.resolve(newobj);
        });
    }
    return agenda_globals.assignment_promise;
}

ScheduledSlot.prototype.connect_to_timeslot_session = function() {
    if(this.timeslot == undefined) {
        if(this.timeslot_id != undefined) {
            this.timeslot = agenda_globals.timeslot_byid[this.timeslot_id];
        } else {
            /* must be the unassigned one?! */
            this.timeslot = new TimeSlot();
            this.timeslot.domid = "sortable-list";
        }
    }
    /* session could be hooked up, but it is now always session() */
};

ScheduledSlot.prototype.session = function() {
    if(this.session_id != undefined) {
       return agenda_globals.meeting_objs[this.session_id];
    } else {
        console.log("ss id:", this.assignment_id, "timeslot:", this.timeslot_id, this.timeslot.title(), "has null session");
        return undefined;
    }
};
ScheduledSlot.prototype.slot_title = function() {
    return "id#"+this.assignment_id+" dom:"+this.domid();
};

function make_ss(json) {
    var ss = new ScheduledSlot();
    ss.initialize(json, "make_ss");
    return ss;
}


// ++++++++++++++++++
// Session Objects
//
// initialized by loading a json from /meeting/XX/sessions.json, return JSON that looks like:
//
//               {"title" : "{{ s.short_name }}",
//                "description":"{{ s.group.name }}",
//                "special_request": "{{ s.special_request_token }}",
//                "session_id":"{{s.id}}",
//                "owner": "{{s.owner.owner}}",
//                "area":"{{s.group.parent.acronym|upper}}",
//                "duration":"{{s.requested_duration.seconds|durationFormat}}"});
//


function Session() {
    this.constraints = {};
    this.theirconstraints = {};
    this.constraint_load_andthen_list = [];
    this.constraints_loaded = false;
    this.last_timeslot_id = null;
    this.slot_status_key = null;
    this.href       = false;
    this.group      = undefined;
    this.column_class_list = [];
    this.loaded = undefined;
    this.area = "noarea";
    this.special_request = "";
    this.conflicted = false;
    this.conflicted_direction = {};
    this.theirconflicted = false;
    this.double_wide = false;
    this.attendees   = undefined;
}

function session_obj(json) {
    session = new Session();

    for(var key in json) {
        //console.log("copying", key, "value: ", json[key]);
        if(json[key] != undefined && json[key] != "") {
            session[key]=json[key];
        }
    }
    // dict will not pass .length > 0 above.
    session.group = json.group;

    if(session.requested_duration == undefined) {
        session.requested_duration = session.duration;
    }

    // make it a number.
    session.attendees = parseInt(session.attendees);

    session.ogroup = session.group;
    if(session.group != undefined) {
        /* it has an inline group object, intern it, and redirect to interned object */
        //console.log(session.title, "using embedded group: ",
        //            session.group.acronym, session.group.href, session.group);
        session.group = load_group_from_json(session.group);
        session.group_href = session.group.href;
        //console.log(session.title, "2 using embedded group: ",
        //            session.group.acronym, session.group.href, session.group);
    } else if(session.group_href != undefined) {
        console.log("session ",session.session_id,
                    "has no embedded group, load by href", session.group_href);
        session.group = find_group_by_href(session.group_href, "session_load");
    } else {
        // bogus
        session.group_href = site_base_url+'/group/'+session.title+".json";
    }

    // keep a list of sessions by name
    // this is mostly used for debug purposes only.
    if(agenda_globals.sessions_objs[session.title] == undefined) {
        agenda_globals.sessions_objs[session.title] = [];
    }
    agenda_globals.sessions_objs[session.title].push(session);   // an array since there can be more than one session/wg

    agenda_globals.meeting_objs[session.session_id] = session;

    return session;
}

/* feed this an array of sessions */
function make_sessions(json, status, jqXHR) {
    $.each(json, function(index) {
        var thing = json[index];
        session_obj(thing);
    });
}

function load_sessions(href) {
    if(agenda_globals.session_promise == undefined) {
        agenda_globals.session_promise = $.Deferred();

        var ss = $.ajax(href);
        ss.success(function(newobj, status, jqXHR) {
            console.log("finished session promise");
            make_sessions(newobj);
            agenda_globals.session_promise.resolve(newobj);
        });
    }
    return agenda_globals.session_promise;
}

function count_sessions() {
    $.each(agenda_globals.sessions_objs, function(title) {
        //console.log("title", title, this);
        var lastone  = null;
        var sessions = agenda_globals.sessions_objs[title];
        var num_sessions = sessions.length;
        $.each(sessions, function(index) {
            //console.log("session", index, this);
            this.number = index;          // a number
            this.maxNum = num_sessions;

            this.prev_session = lastone;
            this.next_session = null;
            if(index < num_sessions) {
                this.next_session = sessions[index+1];
            }
            lastone = this;
        });
    });
}


// augument to jQuery.getJSON( url, [data], [callback] )
Session.prototype.load_session_obj = function(andthen, arg) {
    session = this;
    if(this.loaded == undefined) {
        start_spin();
        this.loaded = $.ajax(this.href);
    }

    this.loaded.success(function(newobj, status, jqXHR) {
        last_json_reply = newobj;
        $.extend(session, newobj);

        if(andthen != undefined) {
            andthen(session, true, arg);
        }
        stop_spin();
    });
    this.loaded.error(function(jqXHR, textStatus, errorThrown ) {
        console.log("exception: ",textStatus,errorThrown);
        if(andthen != undefined) {
            andthen(session, false, arg);
        }
        stop_spin();
    });
};

Session.prototype.find_responsible_ad = function() {
    var session = this;
    //console.log("session",this.title, this.session_id,"looking for ad",this.group.ad_href);
    if(this.group && this.group.ad_href) {
        find_person_by_href(session.group.ad_href).done(function(ad) {
            //console.log("session",session.session_id,"found ", ad);
            session.responsible_ad = ad;
        });
    }
};

Session.prototype.element = function() {
    return $("#session_"+this.session_id);
};

Session.prototype.personconflict_element = function() {
    return this.element().parent().find(".personconflict");
};

Session.prototype.selectit = function() {
    clear_all_selections();
    // mark self as selected
    if(this.group != undefined) {
        $("." + this.group.acronym).addClass("same_group");
    }
    this.element().removeClass("save_group");
    this.element().addClass("selected_group");
};
Session.prototype.unselectit = function() {
    clear_all_selections();
};

Session.prototype.on_bucket_list = function() {
    this.is_placed = false;
    this.column_class_list = [];
    this.element().parent("div").addClass("meeting_box_bucket_list");
};
Session.prototype.placed = function(where, forceslot, assignment) {
    this.is_placed = true;

    // forceslot is set on a move, but unset on initial placement,
    // as placed might be called more than once for a double slot session.
    if(forceslot || this.slot==undefined) {
        this.slot      = where;
        this.assignment = assignment;

        /* we can not mark old slot as empty, because it
           might have multiple sessions in it.
           we can do the opposite: mark it was not empty when we fill it.
        */

        if(where != undefined) {
            where.empty = false;
        }
    }
    if(where != undefined) {
        this.add_column_class(where.column_class);
    }
    //console.log("session:",session.title, "column_class", ssid.column_class());
    this.element().parent("div").removeClass("meeting_box_bucket_list");
    this.pinned = where.pinned;
};

Session.prototype.populate_event = function(js_room_id) {
    var eTemplate =     this.event_template()
    insert_cell(js_room_id, eTemplate, false);
};
Session.prototype.repopulate_event = function(js_room_id) {
    var eTemplate =     this.event_template()
    insert_cell(js_room_id, eTemplate, true);
    this.display_conflict();
};

Session.prototype.visible_title = function() {
    return this.special_request + this.title;
};

var _conflict_debug = false;
Session.prototype.mark_conflict = function(value) {
    this.conflicted = value;
};
Session.prototype.add_conflict = function(conflict) {
    this.conflicted = true;
    if (this.conflicted_direction==undefined) {
        this.conflicted_direction={};
    }
    this.conflicted_direction[conflict.direction] = true;
    if (this.highest_conflict==undefined) {
        this.highest_conflict={};
    }
    if(this.highest_conflict[conflict.direction]==undefined) {
        this.highest_conflict[conflict.direction] = conflict;
    } else {
        var oldhighest = this.highest_conflict[conflict.direction];
        this.highest_conflict[conflict.direction] = this.highest_conflict[conflict.direction].conflict_compare(conflict);
        if(_conflict_debug) {
            console.log("add conflict for", this.title,
                        oldhighest.conflict_type, ">?", conflict.conflict_type,
                        "=", this.highest_conflict[conflict.direction].conflict_type);
        }
    }
    if (this.conflict_level==undefined){
        this.conflict_level={};
    }
    this.conflict_level[conflict.direction] = this.highest_conflict[conflict.direction].conflict_type;
};

Session.prototype.clear_conflict = function() {
    this.conflicted = false;
};

Session.prototype.clear_all_conflicts = function(old_column_classes) {
    var session_obj = this;
    this.clear_conflict();

    if(old_column_classes != undefined) {
        $.each(session_obj.constraints.bethere, function(i) {
            var conflict = session_obj.constraints.bethere[i];
            var person = conflict.person;

            person.clear_session(session_obj, old_column_classes);
        });
    }
};

Session.prototype.show_conflict = function() {
    if(_conflict_debug) {
        console.log("showing conflict for", this.title, this.conflict_level['ours'],this.conflict_level['theirs']);
    }
    var display = { 'conflict':'1' , 'conflic2':'2' , 'conflic3':'3' };
    if (this.conflicted) {
        if ('ours' in this.conflict_level) {
            this.element().find('.ourconflicts').text('->'+display[this.conflict_level.ours]);
        }
        if ('theirs' in this.conflict_level) {
            this.element().find('.theirconflicts').text(display[this.conflict_level.theirs]+'->');
        }
    }
};

Session.prototype.hide_conflict = function() {
    if(_conflict_debug) {
        console.log("removing conflict for", this.title);
    }
    this.element().find('.ourconflicts').text('');
    this.element().find('.theirconflicts').text('');
};

Session.prototype.display_conflict = function() {
    if(this.conflicted || this.theirconflicted) {
        this.show_conflict();
    } else {
        this.hide_conflict();
    }
};

Session.prototype.reset_conflicts = function() {
    this.conflict_level = undefined;
    this.highest_conflict = undefined;
    this.conflicted = false;
    this.conflicted_direction = undefined;
    this.theirconflict_level = undefined;
    this.highest_theirconflict = undefined;
    this.theirconflicted = false;
};

Session.prototype.show_personconflict = function() {
    if(_conflict_debug) {
        console.log("showing person conflict for", this.title, this.conflict_level.ours);
    }
    this.personconflict_element().removeClass("hidepersonconflict");
    this.personconflict_element().addClass("showpersonconflict");
};
Session.prototype.hide_personconflict = function() {
    if(_conflict_debug) {
        console.log("removing person conflict for", this.title);
    }
    this.personconflict_element().addClass("hidepersonconflict");
    this.personconflict_element().removeClass("showpersonconflict");
};
Session.prototype.display_personconflict = function() {
    if(this.person_conflicted) {
        this.show_personconflict();
    } else {
        this.hide_personconflict();
    }
};
Session.prototype.add_personconflict = function(conflict) {
    this.person_conflicted = true;
};

Session.prototype.examine_people_conflicts = function() {
    /*
     * the scan for people conflicts has to be done after the fill_in_constraints
     * because we don't know which sessions the people will need to attend until
     * all the constraints have been examined.
     */
    var session_obj = this;

    // reset people conflicts.
    session_obj.person_conflicted = false;

    for(ccn in session_obj.column_class_list) {
        var vertical_location = session_obj.column_class_list[ccn].column_tag;
        var room_tag          = session_obj.column_class_list[ccn].room_tag;

        if(session_obj.constraints.bethere != null) {
            if(_person_bethere_debug) {
                console.log("examining bethere constraints for", session_obj.title);
            }
            $.each(session_obj.constraints.bethere, function(i) {
                var conflict = session_obj.constraints.bethere[i];
                find_person_by_href(conflict.person_href).done(function(person) {
                    conflict.person = person;
                    if(_person_bethere_debug) {
                        console.log("examining", person.ascii," bethere constraints for", session_obj.title);
                    }
                    if(person.conflicted_time(vertical_location)) {
                        session_obj.add_personconflict(conflict);
                    }
                });
            });
        }
    }
}


Session.prototype.area_scheme = function() {
    return this.area.toUpperCase() + "-scheme";
};

Session.prototype.is_bof = function() {
    return this.bof == "True";
}
Session.prototype.wg_scheme = function() {
    if(this.is_bof()) {
        return "bof_style";
    } else {
        return "wg_style";
    }
};

Session.prototype.add_column_class = function(column_class) {
    if(__column_class_debug) {
        console.log("adding:",column_class, "to ", this.title);
    }
    this.column_class_list.push(column_class);
};

var _LAST_MOVED_OLD;
var _LAST_MOVED_NEW;
// timeslot_list is a list of slots where the session has been located.
// bucket_list is a boolean.
Session.prototype.update_column_classes = function(timeslot_list, bucket_list) {

    // COLUMN CLASSES MUST BE A LIST because of multiple slot use
    console.log("updating column_classes for ", this.title);

    var old_column_classes = this.column_class_list;
    if(old_column_classes.length == 0) {
        console.log("old column class was undefined for session:", session.title);
        old_column_classes = [new ColumnClass()];
    }

    // zero out list.
    this.column_class_list = [];
    var new_column_tag = "none";
    if(bucket_list) {
        this.on_bucket_list();

    } else {
        for(tsn in timeslot_list) {
            var ts = timeslot_list[tsn];
            console.log("timeslot_list", tsn, ts);
            this.add_column_class(ts.column_class);
        }
        new_column_tag = this.column_class_list[0].column_tag;
    }

    var old_column_class_name = "none";
    if(old_column_classes != undefined &&
       old_column_classes[0] != undefined) {
        old_colum_class_name = old_column_classes[0].column_tag;
    }

    console.log("setting column_class for ",this.title," to ",
                new_column_tag, "was: ", old_column_class_name);

    console.log("unset conflict for ",this.title," is ", this.conflicted);

    _LAST_MOVED_OLD = old_column_classes;
    _LAST_MOVED_NEW = this.column_class_list;

    this.group.del_column_classes(old_column_classes);
    this.group.add_column_classes(this.column_class_list);
    recalculate_conflicts_for_session(this, old_column_classes, this.column_class_list);
};


// utility/debug function, draws all events.
function update_all_templates() {
    for(key in agenda_globals.meeting_objs) {
        session = agenda_globals.meeting_objs[key];
        var slot = session.slot_status_key;
	if(slot != null) {
            session.repopulate_event(slot);
        }
    }
}

Session.prototype.event_template = function() {
    // the extra div is present so that the table can have a border which does not
    // affect the total height of the box.  The border otherwise screws up the height,
    // causing things to the right to avoid this box.
    var area_mark = "";
    if(this.responsible_ad != undefined) {
        area_mark = this.responsible_ad.area_mark;
        if(area_mark == undefined) {
            // This doesn't seem to do the right thing
            // area_mark = "ad:" + this.responsible_ad.href;
            area_mark = "";
        }
    }

    var bucket_list_style = "meeting_box_bucket_list"
    if(this.is_placed) {
        bucket_list_style = "";
        area_mark = "";        /* no mark for unplaced items: it goes to the wrong place */
    }
    if(this.double_wide) {
        bucket_list_style = bucket_list_style + " meeting_box_double";
    }

    var pinned = "";
    if(this.pinned) {
        bucket_list_style = bucket_list_style + " meeting_box_pinned";
        pinned="<td class=\"pinned-tack\">P</td>";
    }

    var groupacronym = "nogroup";
    if(this.group != undefined) {
        groupacronym = this.group.acronym;
    }
    //console.log("acronym", groupacronym, this.group.acronym, this.visible_title());

    var durationstring="";
    if (this.requested_duration!="0.0") {
         durationstring = " ("+this.requested_duration+")"
    }
    // see comment in ietf.ccs, and
    // http://stackoverflow.com/questions/5148041/does-firefox-support-position-relative-on-table-elements
    return "<div class='meeting_box_container' session_id=\""+this.session_id+"\"><div class=\"meeting_box "+bucket_list_style+"\" ><table class='meeting_event "+
        groupacronym +
        "' id='session_"+
        this.session_id+
        "' session_id=\""+this.session_id+"\"" +
        "><tr id='meeting_event_title'><td class=\"theirconflicts\"></td><th class='"+
        this.wg_scheme()+" "+
        this.area_scheme() +" meeting_obj'>"+
        this.visible_title()+
        "<span>" + durationstring + "</span>" +
        "</th><td class=\"ourconflicts\"></td>"+pinned+"</tr></table>"+ area_mark +"</div></div>";
};

function andthen_alert(object, result, arg) {
    alert("result: "+result+" on obj: "+object);
};

Session.prototype.generate_info_table = function() {
    $("#info_grp").html(name_select_html);
    if(this.is_bof()) {
        $("#grp_type").html("BOF");
    } else {
        $("#grp_type").html("WG");
    }

    $("#info_name_select").val($("#info_name_select_option_"+this.session_id).val());
    if(this.description.length > 33) {
        $("#info_name").html("<span title=\""+this.description+"\">"+this.description.substring(0,35)+"...</span>");
    } else {
        $("#info_name").html(this.description);
    }
    $("#info_area").html("<span class='"+this.area.toUpperCase()+"-scheme'>"+this.area+"</span>");
    $("#info_duration").html(this.requested_duration);
    if(this.attendees == "None") {
        $("#info_capacity").text("size unknown");
    } else {
        $("#info_capacity").text(this.attendees + " people");
    }

    if(!read_only) {
        $("#info_location").html(generate_select_box()+"<button id='info_location_set'>set</button>");
    }

    if("comments" in this && this.comments.length > 0 && this.comments != "None") {
        $("#special_requests").text(this.comments);
    } else {
        $("#special_requests").text("Special requests: None");
    }

    this.selectit();

    if(this.slot != undefined) {
        ss = this.slot;
        if(ss.timeslot_id == null){
            $("#info_location_select").val(agenda_globals.meeting_objs[ss.assignment_id]);
        }else{
            $("#info_location_select").val(ss.timeslot_id); // ***
        }
        $("#info_location_select").val($("#info_location_select_option_"+ss.timeslot_id).val());
    }

    //console.log("ad for session",this.session_id,"is",this.responsible_ad);
    if(this.responsible_ad) {
        this.responsible_ad.populate_responsible_ad();
    }
    $("#info_requestedby").html(this.requested_by +" ("+this.requested_time+")");

    listeners();
};

function load_all_groups() {
    for(key in agenda_globals.meeting_objs) {
        session = agenda_globals.meeting_objs[key];
        session.group = find_group_by_href(session.group_href, "load all");
    }
}

var __DEBUG_THIS_SLOT;
Session.prototype.retrieve_constraints_by_session = function() {
    __DEBUG_THIS_SLOT = this;
    //console.log("4 retrieve loaded:", this.title, this.constraints_loaded, "loading:", this.constraints_loading);

    if(this.constraints_promise != undefined) {
        return this.constraints_promise;
    }

    var session_obj = this;
    var href = meeting_base_url+'/session/'+session_obj.session_id+"/constraints.json";

    this.constraints_promise = $.ajax(href);
    this.constraints_loading = true;
    this.constraints_promise.success(function(newobj, status, jq) {
        session_obj.fill_in_constraints(newobj);
        session_obj.constraints_loaded  = true;
        session_obj.constraints_loading = false;
        find_and_populate_conflicts(session_obj);
    });

    return this.constraints_promise;
};

var __verbose_person_conflicts = false;
Session.prototype.calculate_bethere = function() {
    var session_obj = this;

    if("bethere" in this.constraints) {
        $.each(this.constraints["bethere"], function(index) {
            var bethere = session_obj.constraints["bethere"][index];
            find_person_by_href(bethere.person_href).done(function(person) {
                if(__verbose_person_conflicts) {
                    console.log("person",person.ascii,"attends session",session_obj.group.acronym);
                }
                person.attend_session(session_obj);
            });
        });
    }
};

Session.prototype.fill_in_constraints = function(constraint_list) {
    var session_obj = this;
    $.each(constraint_list, function(key){
        thing = constraint_list[key];
        session_obj.add_constraint_obj(thing);
    });

    // here we can sort the constraints by group name.
    // make a single list. this.constraints is not an array, can not use concat.
    this.conflicts = [];
    if("conflict" in this.constraints) {
        $.each(this.constraints["conflict"], function(index) {
            session_obj.conflicts.push(session_obj.constraints["conflict"][index]);
        });
    }
    if("conflic2" in this.constraints) {
        $.each(this.constraints["conflic2"], function(index) {
            session_obj.conflicts.push(session_obj.constraints["conflic2"][index]);
        });
    }
    if("conflic3" in this.constraints) {
        $.each(this.constraints["conflic3"], function(index) {
            session_obj.conflicts.push(session_obj.constraints["conflic3"][index]);
        });
    }
    if("conflict" in this.theirconstraints) {
        $.each(this.theirconstraints["conflict"], function(index) {
            session_obj.conflicts.push(session_obj.theirconstraints["conflict"][index]);
        });
    }
    if("conflic2" in this.theirconstraints) {
        $.each(this.theirconstraints["conflic2"], function(index) {
            session_obj.conflicts.push(session_obj.theirconstraints["conflic2"][index]);
        });
    }
    if("conflic3" in this.theirconstraints) {
        $.each(this.theirconstraints["conflic3"], function(index) {
            session_obj.conflicts.push(session_obj.theirconstraints["conflic3"][index]);
        });
    }
    this.calculate_bethere();
    this.conflicts = sort_conflict_list(this.conflicts)
};

// ++++++++++++++++++
// Group Objects
function Group() {
    this.andthen_list = [];      /* should be removed, or replaced with promise */
    this.all_sessions = [];
}

Group.prototype.loaded_andthen = function() {
    me = this;
    $.each(this.andthen_list, function(index, andthen) {
        andthen(me);
    });
    this.andthen_list = [];
};

Group.prototype.load_group_obj = function(andthen) {
    //console.log("group ",this.href);
    var group_obj = this;

    if(!this.loaded && !this.loading) {
        this.loading = true;
        this.andthen_list.push(andthen);
        $.ajax(this.href,
               {
                   success: function(newobj, status, jqXHR) {
                       if(newobj) {
                           $.extend(group_obj, newobj);
                           group_obj.loaded = true;
                       }
                       group_obj.loading = false;
                       group_obj.loaded_andthen();
                   },
                   error: function(jqXHR, textStatus, errorThrown ) {
                       console.log("error loading ",group_obj.href," textStatus: ", textStatus,errorThrown);
                       group_obj.loading = false;
                       group_obj.loaded  = true;  // white lie
                       group_obj.load_error = true;
                   }
               });
    } else {
        if(!this.loaded) {
            // queue this continuation for later.
            this.andthen_list.push(andthen);
        } else {
            this.loading = false;
            andthen(group_obj);
        }
    }
}

Group.prototype.add_session = function(session) {
    if(this.all_sessions == undefined) {
        this.all_sessions = [];
    }
    this.all_sessions.push(session);
};

var __DEBUG_GROUP_COLUMN_CLASSES = false;
Group.prototype.add_column_class = function(column_class) {
    if(this.column_class_list == undefined) {
       this.column_class_list = [];
    }
    if(__DEBUG_GROUP_COLUMN_CLASSES) {
        console.log("group",this.acronym,"adding column_class",column_class);
    }
    this.column_class_list.push(column_class);
};
Group.prototype.del_column_class = function(column_class) {
    if(__DEBUG_GROUP_COLUMN_CLASSES) {
        console.log("group",this.acronym,"del column_class",column_class);
    }
    for(n in this.column_class_list) {
        if(this.column_class_list[n] == column_class) {
            this.column_class_list.splice(n,1);
        }
    }
};

Group.prototype.add_column_classes = function(column_class_list) {
    for(ccn in column_class_list) {
        cc = column_class_list[ccn];
        this.add_column_class(cc);
    }
};
Group.prototype.del_column_classes = function(column_class_list) {
    for(ccn in column_class_list) {
        cc = column_class_list[ccn];
        this.del_column_class(cc);
    }
};

var __debug_group_load = false;
function create_group_by_href(href) {
    if(agenda_globals.group_objs[href] == undefined) {
       agenda_globals.group_objs[href]=new Group();
        var g = agenda_globals.group_objs[href];
        if(__debug_group_load) {
            console.log("creating new group for", href);
        }
        g.loaded = false;
        g.loading= false;
    }
    return agenda_globals.group_objs[href];
}

function load_group_by_href(href) {
    var g = agenda_globals.group_objs[href];
    if(!g.loaded) {
        g.href = href;
        if(__debug_group_load) {
            console.log("loading group href", href);
        }
        g.load_group_obj(function() {});
    }
    return g;
}

// takes a json that has at least a "href" member,
// and finds or creates the object.  Any additional
// fields are added to the group object, and the group
// is marked loaded.  The resulting group object is returned.
function load_group_from_json(json) {
    var g = create_group_by_href(json.href);
    for(var key in json) {
        if(json[key].length > 0) {
            g[key]=json[key];
        }
    }
    g.loaded = true;
    g.loading= false;
    return g;
}

var group_references   = 0;
var group_demand_loads = 0;
function find_group_by_href(href, msg) {
    group_references++;
    var g=agenda_globals.group_objs[href];
    if(g == undefined) {
        group_demand_loads++;
        if(__debug_group_load) {
            console.log("loading",href,"because of",msg);
        }
        g = create_group_by_href(href);
        load_group_by_href(href);
    }
    //console.log("finding group by ", href, "gives: ", g);
    return g;
}

// ++++++++++++++++++
// Constraint Objects
function Constraint() {
// fields: (see ietf.meeting.models Constraint.json_dict)
//
//  -constraint_id
//  -href
//  -name             -- really the conflict_type, which will get filled in
//  -person/_href
//  -source/_href
//  -target/_href
//  -meeting/_href
//
}

var conflict_classes = {};

function clear_conflict_classes() {
    // remove all conflict boxes from before
    $(".show_conflict_specific_box").removeClass("show_conflict_specific_box");
    $(".show_conflic2_specific_box").removeClass("show_conflic2_specific_box");
    $(".show_conflic3_specific_box").removeClass("show_conflic3_specific_box");

    // reset all column headings
    $(".show_conflict_view_highlight").removeClass("show_conflict_view_highlight");
}
function find_conflict(domid) {
    return conflict_classes[domid];
}

Constraint.prototype.column_class_list = function() {
    return this.othergroup.column_class_list;
};

Constraint.prototype.conflict1P = function() {
    return (this.conflict_type == "conflict")
};

Constraint.prototype.conflict2P = function() {
    return (this.conflict_type == "conflic2")
};

Constraint.prototype.conflict3P = function() {
    return (this.conflict_type == "conflic3")
};

Constraint.prototype.conflict_groupP = function() {
    return (this.conflict_type == "conflict" ||
            this.conflict_type == "conflic2" ||
            this.conflict_type == "conflic3");
};

Constraint.prototype.conflict_peopleP = function() {
    return (this.conflict_type == "bethere")
};

Constraint.prototype.conflict_compare = function(oflict) {
    if(this.conflict_peopleP()) {
        return oflict;
    }
    if(this.conflict1P()) {
        /* "conflict" is highest, return it. */
        return this;
    }
    if(this.conflict2P() && oflict.conflict3P()) {
        /* "conflic2" > "conflic3" */
        return this;
    }
    /* self > 2, so otype would win */
    return oflict;
};

// red is arbitrary here... There should be multiple shades of red for
// multiple types of conflicts.



var __CONSTRAINT_DEBUG = null;
var __column_class_debug = false;

// one used to get here by having the conflict boxes enabled/disabled, but they were
// removed from the UI.
// when a session is selected, the conflict boxes are filled in,
// and then they are all clicked in order to highlight everything.
Constraint.prototype.show_conflict_view = function() {
    classes=this.column_class_list();
    if(classes == undefined) {
        classes = []
    }
    //console.log("show_conflict_view", this);
    __CONSTRAINT_DEBUG = this;
    if(__column_class_debug) {
        console.log("show conflict", this.href, "classes", classes.length, this);
    }

    // this highlights the column headings of the sessions that conflict.
    for(ccn in classes) {
       var cc = classes[ccn];   // cc is a ColumnClass now

        if(cc != undefined) {
            /* this extracts the day from this structure */
            var th_tag = cc.th_tag;
            if(__column_class_debug) {
                console.log("add conflict for column_class", this.session.title, th_tag);
            }
            $(th_tag).addClass("show_conflict_view_highlight");
        } else {
            console.log("cc is undefined for ccn:",ccn);
        }
    }

    // this highlights the conflicts themselves
    //console.log("make box", this.thisgroup.href);
    sessions = this.othergroup.all_sessions
    // set class to like:  .show_conflict_specific_box
    conflict_class = "show_"+this.conflict_type+"_specific_box";
    if(sessions) {
      $.each(sessions, function(key) {
          //console.log("2 make box", key);
          this.element().addClass(conflict_class);
      });
    }
    //console.log("viewed", this.thisgroup.href);
};

Constraint.prototype.populate_conflict_classes = function() {
    // this is used for the red square highlighting.
    var checkbox_id = "conflict_"+this.dom_id;
    conflict_classes[checkbox_id] = this;
};

// Made dead by change to how the group view is built out
//Constraint.prototype.build_group_conflict_view = function() {
//
//    var display = { 'conflict':'1' , 'conflic2':'2' , 'conflic3':'3' };
//
//    // this is used for the red square highlighting.
//    var checkbox_id = "conflict_"+this.dom_id;
//    conflict_classes[checkbox_id] = this;
//
//    build  = "<div id='"+this.dom_id+"'>";
//    if (this.direction=='theirs') {
//        build += display[this.conflict_type]+"->";
//    }
//    build += this.othergroup_name;
//    if (this.direction=='ours') {
//        build += "->"+display[this.conflict_type];
//    }
//    build += "</div>";
//
//    return build
//
//};

Constraint.prototype.build_people_conflict_view = function() {
    var area_mark =  "";
    if(this.person != undefined && this.person.area_mark_basic != undefined) {
        area_mark = this.person.area_mark_basic;
    }
    return "<div class='conflict our-"+this.conflict_type+"' id='"+this.dom_id+
           "'>"+area_mark+"</div>";
};

Constraint.prototype.build_othername = function() {
    if(this.othergroup.load_error) {
        console.log("request for unloaded group: ",this.othergroup.href);
        var patt = /.*\/group\//;  // ugly assumption about href structure.
        var base = this.othergroup.href.replace(patt,"")
        this.othergroup_name = base.replace(".json","")
    } else {
        this.othergroup_name = this.othergroup.acronym;
    }
};

// subclasses would make some sense here.
Constraint.prototype.conflict_view = function() {
    this.dom_id = "constraint_"+this.constraint_id;

    if(this.conflict_peopleP()) {
        return this.build_people_conflict_view();
    }
    else {
        // This function is currently never called for this case
        console.log("!! unexpected conflict_view for", this.href);
        //this.build_othername();
        //return this.build_group_conflict_view();
    }
};

var _constraint_load_debug = false;
// SESSION CONFLICT OBJECTS
// take an object and add attributes so that it becomes a session_conflict_obj.
// note that constraints are duplicated: each session has both incoming and outgoing constraints added.
Session.prototype.add_constraint_obj = function(obj) {
    // turn this into a Constraint object
    // can not print or JSONify these on ff as this has cyclic references. Chrome can.
    //console.log("session: ",       this);
    //console.log("add_constraint: ",obj.constraint_id, obj.name);

    obj2 = new Constraint();
    $.extend(obj2, obj);

    obj = obj2;
    obj.session   = this;

    var listname = obj.name;
    obj.conflict_type = listname;
    if(this.constraints[listname]==undefined) {
       this.constraints[listname]={};
    }
    if(this.theirconstraints[listname]==undefined) {
       this.theirconstraints[listname]={};
    }

    if(listname == "bethere") {
        //console.log("bethere constraint: ", obj);
        var person_href = obj.person_href;
        var session     = this;
        this.constraints[listname][person_href]=obj;
        find_person_by_href(person_href).done(function(person) {
            if(_constraint_load_debug) {
                console.log("recorded bethere constraint: ",person.ascii,"for group",session.group.acronym);
            }
            obj.person = person;
        });
    } else {
        // must be conflic*
        var ogroupname;
        if(obj.source_href == this.group_href) {
            obj.thisgroup  = this.group;
            obj.othergroup = find_group_by_href(obj.target_href, "constraint src"+obj.href);
            obj.direction = 'ours';
            ogroupname = obj.target_href;
            if(this.constraints[listname][ogroupname]) {
                console.log("Found multiple instances of",this.group_href,listname,ogroupname);
            }
            this.constraints[listname][ogroupname] = obj
        } else {
            obj.thisgroup  = this.group;
            obj.othergroup = find_group_by_href(obj.source_href, "constraint dst"+obj.href);
            obj.direction = 'theirs';
            ogroupname = obj.source_href;
            if(this.theirconstraints[listname][ogroupname]) {
                console.log("Found multiple instances of",ogroupname,listname,this.group_href);
            }
            this.theirconstraints[listname][ogroupname] = obj
        }

    }

};

function constraint_compare(a, b)
{
    if(a==undefined || a.othergroup == undefined) {
       return -1;
    }
    if(b==undefined || b.othergroup == undefined) {
       return 1;
    }
    return (a.othergroup.href > b.othergroup.href ? 1 : -1);
}

function sort_conflict_list(things) {
    var keys = Object.keys(things);
    var keys1 = keys.sort(function(a,b) {
                                 return constraint_compare(things[a],things[b]);
                             });
    var newlist = [];
    for(i=0; i<keys1.length; i++) {
       var key  = keys1[i];
       newlist[i] = things[key];
    }
    return newlist;
}

// ++++++++++++++
// Person Objects
function Person() {
// fields: (see ietf.person.models Person.json_dict)
//
//
}

var all_people = {};

// this should be done completely with promises, but
// one can't use the promise returned by $.ajax() directly,
// because the object it returns does not seem to persist.
// So, one has to create a new persistent object.
// This returns a promise that will receive the person object.
function find_person_by_href(href) {

    // first, look and see if the a promise for this href
    // already.

    var deferal;
    if(!(href in all_people)) {
        deferal = $.Deferred();
        all_people[href]= deferal;

        var lookup = $.ajax(href);
        lookup.success(function(newobj, status, jqXHR) {
	    person = new Person();
	    $.extend(person, newobj);
            person.loaded = true;
            deferal.resolve(person);
        });
    } else {
        deferal = all_people[href];
    }

    // or should this be deferal.promise()?
    return deferal.promise();
}

var area_result;
// this function creates a unique per-area director mark
function mark_area_directors(directorpromises) {
    $.each(area_directors, function(areaname) {
        var adnum = 1;
        $.each(area_directors[areaname], function(key) {
            var thisad = adnum;
            directorpromises.push(this);
            this.done(function(person) {
                person.make_area_mark(areaname, thisad);
                person.marked = true;
            });
            adnum++;
        });
    });
    return directorpromises;
}

Person.prototype.make_area_mark = function(areaname, adnum) {
    this.area_mark =  "<span title=\""+areaname+" "+this.name+"\" class=\" director-rightup\">";
    this.area_mark += "<span class=\"personconflict hidepersonconflict\">AD</span>";
    this.area_mark += "<span class=\"director-mark-" + areaname.toUpperCase() + " director-mark\">";
    this.area_mark += adnum;
    this.area_mark += "</span></span>";

    this.area_mark_basic =  "<span title=\""+areaname+" "+this.name+"\" class=\"director-mark-" + areaname.toUpperCase() + " director-mark director-right\">";
    this.area_mark_basic += adnum;
    this.area_mark_basic += "</span>";
};

Person.prototype.populate_responsible_ad = function() {
    var area_mark = "";
    if(this.area_mark != undefined) {
        area_mark = this.area_mark_basic;
    }
    $("#info_responsible").html(this.name + area_mark);
};

var _person_bethere_debug = false;
// this marks a person as needing to attend a session
// in a particular timeslot.
Person.prototype.clear_session = function(session, old_column_classes) {
    for(ccn in old_column_class_list) {
        var vertical_location = session.column_class_list[ccn].column_tag;
        var room_tag          = session.column_class_list[ccn].room_tag;

        if(_person_bethere_debug) {
            console.log("person",this.ascii,"maybe no longer attending session",
                        session.session_id, "in room",room_tag);
        }

        // probably should make it dict, to make removal easier
        if(this.sessions == undefined) {
            continue;
        }

        if(this.sessions[vertical_location] == undefined) {
            continue;
        }

        if(room_tag in this.sessions[vertical_location]) {
            delete this.sessions[vertical_location][room_tag];
            if(_person_bethere_debug) {
                console.log("person: ",this.ascii,"removed from room",
                            room_tag, "at", vertical_location);
            }
        }
    }
};

Person.prototype.attend_session = function(session) {
    for(ccn in session.column_class_list) {
        var vertical_location = session.column_class_list[ccn].column_tag;
        var room_tag          = session.column_class_list[ccn].room_tag;

        if(_person_bethere_debug) {
            console.log("person",this.ascii,"maybe attending session", session.session_id, "in room",room_tag);
        }

        // probably should make it dict, to make removal easier
        if(this.sessions == undefined) {
            this.sessions = [];
        }
        if(this.sessions[vertical_location] == undefined) {
            this.sessions[vertical_location] = [];
        }


        if(!(room_tag in this.sessions[vertical_location])) {
            this.sessions[vertical_location][room_tag]=true;
            if(_person_bethere_debug) {
                console.log("person: ",this.ascii,"needs to be in room",
                            room_tag, "at", vertical_location);
            }
        }
    }
};

Person.prototype.conflicted_time = function(vertical_location) {
    var yesno = this.conflicted_time1(vertical_location);
    //console.log("person: ",this.ascii,"examining for", vertical_location, "gives",yesno);
    return yesno;
}

Person.prototype.conflicted_time1 = function(vertical_location) {
    if(this.sessions == undefined) {
        return false;
    }

    if(this.sessions[vertical_location] == undefined) {
        return false;
    }

    var placestobe = Object.keys(this.sessions[vertical_location]);
    if(placestobe.length > 1) {
        return true;
    } else {
        return false;
    }
};


/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */
