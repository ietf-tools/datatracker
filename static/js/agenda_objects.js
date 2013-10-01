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
    for(s in meeting_objs){
       show_non_conflicting_spots(s)
    }

}

function show_all_conflicts(){
    console.log("all conflicts");
    for(sk in meeting_objs) {
        var s = meeting_objs[sk];
        s.display_conflict();
    }
}

// not really used anymore -- just for debugging
function hide_all_conflicts(){
    for(sk in meeting_objs) {
        var s = meeting_objs[sk];
        s.hide_conflict();
    }
}

function get_all_conflicts(){
    //console.log("get_all_conflicts()");
    for(s in meeting_objs){
        session = meeting_objs[s];
        session.clear_conflict();
        session.display_conflict();
        try {
           session.retrieve_constraints_by_session(find_and_populate_conflicts,
                                                            increment_conflict_load_count);
       }
       catch(err){
          console.log(err);
       }

    }
}

var __debug_conflict_calculate = false;

function calculate_real_conflict(conflict, vertical_location, room_tag, session_obj) {
    if(__debug_conflict_calculate) {
        console.log("  conflict check:", conflict.othergroup.acronym, "me:", vertical_location, room_tag);
    }

    if(session_obj.group.href == conflict.othergroup.href) {
        console.log("session: ",session_obj.session_id, "lists conflict with self");
        return;
    }

    var osessions = conflict.othergroup.all_sessions;
    if(__debug_conflict_calculate) {
        console.log("ogroup: ", conflict.othergroup.href, "me: ", session_obj.group.href);
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
                        console.log("    vs: ",index, "session_id:",osession.session_id," at: ",value.column_tag);
                    }
                    if(value.column_tag == vertical_location &&
                       value.room_tag   != room_tag) {
                        console.log("real conflict:",session_obj.title," with: ",conflict.othergroup.acronym, " #session_",session_obj.session_id, value.room_tag, room_tag, value.column_tag, vertical_location);
                        // there is a conflict!
                        __DEBUG_SHOW_CONSTRAINT = $("#"+value[0]).children()[0];
                        session_obj.add_conflict();
                    }
                }
            }
        });
    }
}

var __DEBUG_SHOW_CONSTRAINT = null;
function find_and_populate_conflicts(session_obj) {
    if(__debug_conflict_calculate) {
        console.log("populating conflict:", session_obj.title);
    }

    var room_tag = null;

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


// ScheduledSession is DJANGO name for this object, but needs to be renamed.
// It represents a TimeSlot that can be assigned in this schedule.
//   { "scheduledsession_id": "{{s.id}}",
//     "empty": "{{s.empty_str}}",
//     "timeslot_id":"{{s.timeslot.id}}",
//     "session_id" :"{{s.session.id}}",
//     "room"       :"{{s.timeslot.location|slugify}}",
//     "extendedfrom_id"    :refers to another scheduledsession by ss.id
//     "time"       :"{{s.timeslot.time|date:'Hi' }}",
//     "date"       :"{{s.timeslot.time|date:'Y-m-d'}}",
//     "domid"      :"{{s.timeslot.js_identifier}}"}

function ScheduledSlot(){
    this.extendedfrom = undefined;
    this.extendedto   = undefined;
    this.extendedfrom_id = false;
}

ScheduledSlot.prototype.initialize = function(json) {
    for(var key in json) {
       this[key]=json[key];
    }

    /* this needs to be an object */
    this.column_class=new ColumnClass(this.room, this.date, this.time);

    var d = new Date(this.date);
    var t = d.getUTCDay();
    if(this.room == "Unassigned"){
       this.short_string = "Unassigned";
    }
    else{
       this.short_string = daysofweek[t] + ", "+ this.time + ", " + upperCaseWords(this.room);
    }
    if(!this.domid) {
           this.domid = json_to_id(this);
        //console.log("gen "+timeslot_id+" is domid: "+this.domid);
    }
    //console.log("extend "+this.domid+" with "+JSON.stringify(this));

    // the key so two sessions in the same timeslot
    if(slot_status[this.domid] == null) {
       slot_status[this.domid]=[];
    }
    slot_status[this.domid].push(this);
    //console.log("filling slot_objs", this.scheduledsession_id);
    slot_objs[this.scheduledsession_id] = this;
};

ScheduledSlot.prototype.session = function() {
    if(this.session_id != undefined) {
       return meeting_objs[this.session_id];
    } else {
       return undefined;
    }
};
ScheduledSlot.prototype.slot_title = function() {
    return "id#"+this.scheduledsession_id+" dom:"+this.domid;
};
ScheduledSlot.prototype.can_extend_right = function() {
    if(this.following_timeslot == undefined) {
        if(this.following_timeslot_id != undefined) {
            this.following_timeslot = slot_objs[this.following_timeslot_id];
        }
    }
    if(this.following_timeslot == undefined) {
        console.log("can_extend_right:",this.scheduledsession_id," no slot to check");
        return false;
    } else {
        console.log("can_extend_right:",
                    this.slot_title()," for slot: ",
                    this.following_timeslot.slot_title(),
                    "is ",this.following_timeslot.empty);
        return this.following_timeslot.empty;
    }
};

function make_ss(json) {
    var ss = new ScheduledSlot();
    ss.initialize(json);
}


// SESSION OBJECTS
//
// initialized from landscape_edit.html template with:
//   session_obj({"title" : "{{ s.short_name }}",
//                "description":"{{ s.group.name }}",
//                "special_request": "{{ s.special_request_token }}",
//                "session_id":"{{s.id}}",
//                "owner": "{{s.owner.owner}}",
//                "group_id":"{{s.group.id}}",
//                "area":"{{s.group.parent.acronym|upper}}",
//                "duration":"{{s.requested_duration.seconds|durationFormat}}"});
//


function Session() {
    this.constraints = {};
    this.constraint_load_andthen_list = [];
    this.constraints_loaded = false;
    this.last_timeslot_id = null;
    this.slot_status_key = null;
    this.href       = false;
    this.group      = undefined;
    this.column_class_list = [];
    this.loaded = false;
    this.area = "noarea";
    this.special_request = "";
    this.conflicted = false;
    this.double_wide = false;
}

function session_obj(json) {
    session = new Session();

    for(var key in json) {
        if(json[key].length > 0) {
            session[key]=json[key];
        }
    }

    if(!session.href) {
        session.href       = meeting_base_url+'/session/'+session.session_id+".json";
    }
    if(!session.group_href) {
        session.group_href = site_base_url+'/group/'+session.title+".json";
    }

    // keep a list of sessions by name
    // this is mostly used for debug purposes only.
    if(session_objs[session.title] == undefined) {
        session_objs[session.title] = [];
    }
    session_objs[session.title].push(session);   // an array since there can be more than one session/wg

    meeting_objs[session.session_id] = session;

    return session;
}

// augument to jQuery.getJSON( url, [data], [callback] )
Session.prototype.load_session_obj = function(andthen, arg) {
    if(!this.loaded) {
       start_spin();
       var oXMLHttpRequest = XMLHttpGetRequest(this.href, true);
       var session = this; // because below, this==XMLHTTPRequest
       oXMLHttpRequest.onreadystatechange = function() {
           if (this.readyState == XMLHttpRequest.DONE) {
              try{
                  last_json_txt = this.responseText;
                  session_obj   = JSON.parse(this.responseText);
                  last_json_reply = session_obj;
                  $.extend(session, session_obj);
                  session.loaded = true;
                  if(andthen != undefined) {
                     andthen(session, true, arg);
                  }
                  stop_spin();
              }
              catch(exception){
                  console.log("exception: "+exception);
                  if(andthen != undefined) {
                     andthen(session, false, arg);
                  }
              }
           }
       };
       oXMLHttpRequest.send();
    } else {
       if(andthen != undefined) {
           andthen(this, true, arg);
       }
    }
};

Session.prototype.element = function() {
    return $("#session_"+this.session_id);
};

Session.prototype.selectit = function() {
    clear_all_selections();
    // mark self as selected
    $("." + this.title).addClass("same_group");
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
Session.prototype.placed = function(where, forceslot) {
    this.is_placed = true;

    // forceslot is set on a move, but unset on initial placement,
    // as placed might be called more than once for a double slot session.
    if(forceslot || this.slot==undefined) {
        this.slot      = where;
    }
    if(where != undefined) {
        this.add_column_class(where.column_class);
    }
    //console.log("session:",session.title, "column_class", ssid.column_class);
    this.element().parent("div").removeClass("meeting_box_bucket_list");
};

Session.prototype.populate_event = function(js_room_id) {
    var eTemplate =     this.event_template()
    insert_cell(js_room_id, eTemplate, false);
};
Session.prototype.repopulate_event = function(js_room_id) {
    var eTemplate =     this.event_template()
    insert_cell(js_room_id, eTemplate, true);
};

Session.prototype.visible_title = function() {
    return this.special_request + this.title;
};

var _conflict_debug = false;
Session.prototype.mark_conflict = function(value) {
    this.conflicted = value;
};
Session.prototype.add_conflict = function() {
    this.conflicted = true;
};
Session.prototype.clear_conflict = function() {
    this.conflicted = false;
};
Session.prototype.show_conflict = function() {
    if(_conflict_debug) {
        console.log("adding conflict for", this.title);
    }
    this.element().addClass("actual_conflict");
};
Session.prototype.hide_conflict = function() {
    if(_conflict_debug) {
        console.log("removing conflict for", this.title);
    }
    this.element().removeClass("actual_conflict");
};
Session.prototype.display_conflict = function() {
    if(this.conflicted) {
        this.show_conflict();
    } else {
        this.hide_conflict();
    }
};

Session.prototype.area_scheme = function() {
    return this.area.toUpperCase() + "-scheme";
};

Session.prototype.add_column_class = function(column_class) {
    if(__column_class_debug) {
        console.log("adding:",column_class, "to ", this.title);
    }
    this.column_class_list.push(column_class);
};

var _LAST_MOVED_OLD;
var _LAST_MOVED_NEW;
Session.prototype.update_column_classes = function(scheduledsession_list, bucket_list) {

    // COLUMN CLASSES MUST BE A LIST because of multiple slot use

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
        for(ssn in scheduledsession_list) {
            ss = scheduledsession_list[ssn];
            this.add_column_class(ss.column_class);
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
    this.group.add_column_classes(this.column_classes);
    recalculate_conflicts_for_session(this, old_column_classes, this.column_class_list);
};


Session.prototype.event_template = function() {
    // the extra div is present so that the table can have a border which does not
    // affect the total height of the box.  The border otherwise screws up the height,
    // causing things to the right to avoid this box.
    var bucket_list_style = "meeting_box_bucket_list"
    if(this.is_placed) {
        bucket_list_style = "";
    }
    if(this.double_wide) {
        bucket_list_style = bucket_list_style + " meeting_box_double";
    }
    // see comment in ietf.ccs, and
    // http://stackoverflow.com/questions/5148041/does-firefox-support-position-relative-on-table-elements
    return "<div class='meeting_box_container' session_id=\""+this.session_id+"\"><div class=\"meeting_box "+bucket_list_style+"\" ><table class='meeting_event "+
        this.title +
        "' id='session_"+
        this.session_id+
        "' session_id=\""+this.session_id+"\"" +
        "><tr id='meeting_event_title'><th class='"+
        this.area_scheme() +" meeting_obj'>"+
        this.visible_title()+
        "<span> ("+this.duration+")</span>"+
        "</th></tr></table></div></div>";
};

function andthen_alert(object, result, arg) {
    alert("result: "+result+" on obj: "+object);
};

Session.prototype.generate_info_table = function() {
    $("#info_grp").html(name_select_html);
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
            $("#info_location_select").val(meeting_objs[ss.scheduledsession_id]);
        }else{
            $("#info_location_select").val(ss.timeslot_id); // ***
        }
        $("#info_location_select").val($("#info_location_select_option_"+ss.timeslot_id).val());
    }

    listeners();

    $("#info_responsible").html(this.responsible_ad);
    $("#info_requestedby").html(this.requested_by +" ("+this.requested_time+")");
};

function load_all_groups() {
    for(key in meeting_objs) {
        session = meeting_objs[key];
        session.group = create_group_by_href(session.group_href);
    }
}

var __DEBUG_THIS_SLOT;
Session.prototype.retrieve_constraints_by_session = function(andthen, success) {
    __DEBUG_THIS_SLOT = this;
    //console.log("4 retrieve loaded:", this.constraints_loaded, "loading:", this.constraints_loading);
    if(this.constraints_loaded) {
       /* everything is good, call continuation function */
       andthen(this);
    } else {
        this.constraint_load_andthen_list.push(andthen);
        if(this.constraints_loading) {
            return;
        }

        this.constraints_loading = true;
        var session_obj = this;
        var href = meeting_base_url+'/session/'+session_obj.session_id+"/constraints.json";
        $.getJSON( href, "", function(constraint_list) {
            session_obj.fill_in_constraints(constraint_list);
            session_obj.constraints_loaded  = true;
            session_obj.constraints_loading = false;
        }).done(success);
    }
};

Session.prototype.fill_in_constraints = function(constraint_list) {
    if(constraint_list['error']) {
        console.log("failed to get constraints for session_id: "+this.session_id, constraint_list['error']);
        return false;
    }

    var session_obj = this;
    $.each(constraint_list, function(key){
       thing = constraint_list[key];
       session_obj.add_constraint_obj(thing);
    });
    this.sort_constraints();

    $.each(this.constraint_load_andthen_list, function(index, andthen) {
        andthen(session_obj);
    });
    this.constraint_load_andthen_list = [];
};

// GROUP OBJECTS
function Group() {
    this.andthen_list = [];
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
        $.getJSON( this.href, "", function(newobj) {
            if(newobj) {
                $.extend(group_obj, newobj);
                group_obj.loaded = true;
            }
            group_obj.loading = false;
            group_obj.loaded_andthen();
        });
    } else {
        if(!this.loaded) {
            // queue this continuation for later.
            this.andthen_list.push(andthen);
        } else {
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
Group.prototype.add_column_class = function(column_class) {
    if(this.column_class_list == undefined) {
       this.column_class_list = [];
    }
    this.column_class_list.push(column_class);
};
Group.prototype.del_column_class = function(column_class) {
    for(n in this.column_class_list) {
        if(this.column_class_list[n] == column_class) {
            delete this.column_class_list[n];
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
    if(group_objs[href] == undefined) {
       group_objs[href]=new Group();
        g = group_objs[href];
        g.loaded = false;
        g.loading= false;
    }
    g = group_objs[href];
    if(!g.loaded) {
        g.href = href;
        if(__debug_group_load) {
            console.log("loading group href", href);
        }
        g.load_group_obj(function() {});
    }
    return g;
}

function find_group_by_href(href) {
    g=group_objs[href];
    if(g == undefined) {
        g = create_group_by_href(href);
    }
    //console.log("finding group by ", href, "gives: ", g);
    return g;
}

// Constraint Objects
function Constraint() {
// fields: (see ietf.meeting.models Constraint.json_dict)
//
//  -constraint_id
//  -href
//  -name
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

    // reset all column headings
    $(".show_conflict_view_highlight").removeClass("show_conflict_view_highlight");
}
function find_conflict(domid) {
    return conflict_classes[domid];
}

Constraint.prototype.column_class_list = function() {
    return this.othergroup.column_class_list;
};

// red is arbitrary here... There should be multiple shades of red for
// multiple types of conflicts.



var __CONSTRAINT_DEBUG = null;
var __column_class_debug = false;

// one can get here by having the conflict boxes enabled/disabled.
// but, when a session is selected, the conflict boxes are filled in,
// and then they are all clicked in order to highlight everything.
Constraint.prototype.show_conflict_view = function() {
    classes=this.column_class_list();
    //console.log("show_conflict_view", this);
    __CONSTRAINT_DEBUG = this;
    if(__column_class_debug) {
        console.log("viewing", this.href, this.thisgroup.href);
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
    if(sessions) {
      $.each(sessions, function(key) {
          //console.log("2 make box", key);
          this.element().addClass("show_conflict_specific_box");
      });
    }
    //console.log("viewed", this.thisgroup.href);
};

Constraint.prototype.build_conflict_view = function() {
    var bothways = "&nbsp;&nbsp;&nbsp;";
    if(this.bothways) {
       bothways=" &lt;-&gt;";
    }
    //this.checked="checked";

    var checkbox_id = "conflict_"+this.dom_id;
    conflict_classes[checkbox_id] = this;
    return "<div class='conflict conflict-"+this.conflict_type+"' id='"+this.dom_id+
           "'><input class='conflict_checkboxes' type='checkbox' id='"+checkbox_id+
           "' value='"+this.checked+"'>"+this.othergroup_name+bothways+"</div>";

};

Constraint.prototype.build_othername = function() {
    this.othergroup_name = this.othergroup.acronym;
};

Constraint.prototype.conflict_view = function() {
    this.dom_id = "constraint_"+this.constraint_id;

    var theconstraint = this;
    // this used to force loading of groups, async, but now all groups are loaded at
    // page load time.
    this.build_othername();

    return this.build_conflict_view();
};


// SESSION CONFLICT OBJECTS
// take an object and add attributes so that it becomes a session_conflict_obj.
// note that constraints are duplicated: each session has both incoming and outgoing constraints added.
Session.prototype.add_constraint_obj = function(obj) {
    // turn this into a Constraint object
    //console.log("session: ",JSON.stringify(this));
    //console.log("add_constraint: ",JSON.stringify(obj));

    obj2 = new Constraint();
    $.extend(obj2, obj);

    obj = obj2;
    obj.session   = this;

    var ogroupname;
    if(obj.source_href == this.group_href) {
        obj.thisgroup  = this.group;
        obj.othergroup = find_group_by_href(obj.target_href);
       ogroupname = obj.target_href;
    } else {
        obj.thisgroup  = this.group;
        obj.othergroup = find_group_by_href(obj.source_href);
       ogroupname = obj.source_href;
    }

    var listname = obj.name;
    obj.conflict_type = listname;
    if(this.constraints[listname]==undefined) {
       this.constraints[listname]={};
    }

    if(this.constraints[listname][ogroupname]) {
       this.constraints[listname][ogroupname].bothways = true;
    } else {
       this.constraints[listname][ogroupname]=obj;
    }
};

function split_list_at(things, keys, place) {
    var half1 = [];
    var half2 = [];
    var len = keys.length;
    var i=0;
    for(i=0; i<place; i++) {
       var key  = keys[i];
       half1[i] = things[key];
    }
    for(;i<len; i++) {
       var key  = keys[i];
       half2[i-place] = things[key];
    }
    return [half1, half2];
}

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

function split_constraint_list_at(things, place) {
    var keys = Object.keys(things);
    var keys1 = keys.sort(function(a,b) {
                                 return constraint_compare(things[a],things[b]);
                             });
    var sorted_conflicts = split_list_at(things, keys1, place);
    return sorted_conflicts;
}

// this sorts the constraints into two columns such that the number of rows
// is half of the longest amount.
Session.prototype.sort_constraints = function() {
    // find longest amount
    var big = 0;
    if("conflict" in this.constraints) {
       big = Object.keys(this.constraints.conflict).length;
    }

    if("conflic2" in this.constraints) {
       var c2 = Object.keys(this.constraints.conflic2).length;
       if(c2 > big) {
           big = c2;
       }
    }

    if("conflic3" in this.constraints) {
       var c3 = Object.keys(this.constraints.conflic3).length;
       if(c3 > big) {
           big = c3;
       }
    }

    this.conflict_half_count = Math.floor((big+1)/2);
    var half = this.conflict_half_count;

    this.conflicts = [];
    this.conflicts[1]=[[],[]]
    this.conflicts[2]=[[],[]]
    this.conflicts[3]=[[],[]]

    if("conflict" in this.constraints) {
       var list1 = this.constraints.conflict;
       this.conflicts[1] = split_constraint_list_at(list1, half);
    }

    if("conflic2" in this.constraints) {
       var sort2 = this.constraints.conflic2;
       this.conflicts[2] = split_constraint_list_at(sort2, half);
    }

    if("conflic3" in this.constraints) {
       var sort3 = this.constraints.conflic3;
       this.conflicts[3] = split_constraint_list_at(sort3, half);
    }

};


/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */

