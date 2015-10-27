/*
*
*  FILE: agenda_edit.js
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*  Description:
*      This is the main file for the agenda editing page.
*      It contains the document read function that starts everything
*      off, and uses functions and objects from agenda_*.js
*
*/




//////////////-GLOBALS----////////////////////////////////////////

// these need to be setup in landscape_edit's setup_slots() inline function:
//var meeting_number = 0;   // is the meeting name.
//var schedule_id    = 0;   // what is the schedule we are editing.
//var schedule_name;        // what is the schedule we are editing.
//var schedule_owner_href = '';  // who owns this schedule
//var assignments_post_href;
//var meeting_base_url;
//var site_base_url;
//var total_rooms = 0; // the number of rooms
//var total_days = 0; // the number of days

var is_secretariat = false;

var agenda_globals;

var area_directors = {};  // list of promises of area directors, index by href.

var read_only = true;     // it is true until we learn otherwise.
var days = [];
var legend_status = {};   // agenda area colors.
var load_conflicts = true;
var duplicate_sessions = {};
/********* colors ************************************/

var dragging_color = "blue"; // color when draging events.
var none_color = '';  // when we reset the color. I believe doing '' will force it back to the stylesheet value.
var color_droppable_empty_slot = 'rgb(0, 102, 153)';

// these are used for debugging only.
var last_json_txt   = "";   // last txt from a json call.
var last_json_reply = [];   // last parsed content

var hidden_rooms = [];
var hidden_days = [];

/****************************************************/

/////////////-END-GLOBALS-///////////////////////////////////////

/* refactor this out into the html */
$(document).ready(function() {
    initStuff();

   $("#close_ietf_menubar").click();

});

/* initStuff()
   This is ran at page load and sets up the entire page.
*/
function initStuff(){
    agenda_globals = new AgendaGlobals();
    //agenda_globals.__debug_session_move = true;

    log("initstuff() running...");
    var directorpromises = [];

    /* define a slot for unscheduled items */
    var unassigned = new ScheduledSlot();
    unassigned.make_unassigned();

    setup_slots(directorpromises);
    mark_area_directors(directorpromises);
    log("setup_slots() ran");
    droppable();
    log("droppable() ran");

    $.when.apply($,directorpromises).done(function() {
        /* can not load events until area director info,
           timeslots, sessions, and assignments
           have been loaded
        */
        log("loading/linking objects");
        load_events();
        log("load_events() ran");
        find_meeting_no_room();
        calculate_name_select_box();
        calculate_room_select_box();
        listeners();
        droppable();
        duplicate_sessions = find_double_timeslots();
        empty_info_table();
        count_sessions();

        if(load_conflicts) {
            recalculate(null);
        }
    });

    static_listeners();
    log("listeners() ran");

    start_spin();

    read_only = true;
    log("do read only check");
    read_only_check();
    stop_spin();

    meeting_objs_length = Object.keys(agenda_globals.meeting_objs).length;

    /* Comment this out for fast loading */
    //load_conflicts = false;
}

var __READ_ONLY;
function read_only_result(msg) {
    __READ_ONLY = msg;
    is_secretariat = msg.secretariat;

    read_only = msg.read_only;
    console.log("read only", read_only);

    if(!read_only) {
	$("#read_only").css("display", "none");
    }

    if(msg.save_perm) {
        $(".agenda_save_box").css("display", "block");
        if(read_only) {
            $(".agenda_save_box").css("position", "fixed");
            $(".agenda_save_box").css("top", "20px");
            $(".agenda_save_box").css("right", "10px");
            $(".agenda_save_box").css("bottom", "auto");
            $(".agenda_save_box").css("border", "3px solid blue");
            $(".agenda_save_box").css("z-index", "2000");
        }
    } else {
        $(".agenda_save_box").html("please login to save");
    }

    schedule_owner_href = msg.owner_href;
    // XX go fetch the owner and display it.
    console.log("owner href:", schedule_owner_href);

    $("#pageloaded").show();

    listeners();
    droppable();
}

function read_only_check() {
    var read_only_url  = meeting_base_url + "/agenda/" + schedule_owner_email + "/" + schedule_name + "/permissions";
    console.log("Loading readonly status from: ", read_only_url);
    var read_only_load = $.ajax(read_only_url);

    read_only_load.success(function(newobj, status, jqXHR) {
        last_json_reply = newobj;
        read_only_result(newobj);
    });
}

function print_all_ss(objs){
    console.log(objs)
}


/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */

