
/*
*   timeslot_edit.js
*
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013 
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*   This file should contain functions relating to
*   determining what a given timeslot can be used for.
*
*/




//////////////-GLOBALS----////////////////////////////////////////

var meeting_objs = {};    // contains a list of session objects
var slot_status = {};     // the status of the slot, in format { room_year-month-day_hour: { free: t/f, timeslotid: id } }
var slot_objs   = {};
var group_objs = {};      // list of working groups

var days = [];
var legend_status = {};   // agenda area colors.

var duplicate_sessions = {};

/********* colors ************************************/

var highlight = "red"; // when we click something and want to highlight it.
var dragging_color = "blue"; // color when draging events.
var none_color = '';         // unset the color.
var color_droppable_empty_slot = 'rgb(0, 102, 153)';

// these are used for debugging only.
var last_json_txt   = "";   // last txt from a json call.
var last_json_reply = [];   // last parsed content

var hidden_rooms = [];
var total_rooms = 0; // the number of rooms
var hidden_days = [];
var total_days = 0; // the number of days
/****************************************************/

/////////////-END-GLOBALS-///////////////////////////////////////

/* refactor this out into the html */
$(document).ready(function() {
    init_timeslot_edit();

    $("#CLOSE_IETF_MENUBAR").click();
});

/*
   init_timeslot_editf()
   This is ran at page load and sets up the entire page.
*/
function init_timeslot_edit(){
    log("initstuff() ran");
    setup_slots();
    log("setup_slots() ran");
    fill_timeslots();

    resize_listeners();
    static_listeners();

    $(".delete_room").unbind('click');
    $(".delete_room").click(delete_room);

    $("#add_room").unbind('click')
    $("#add_room").click(add_room);

    $(".delete_slot").unbind('click');
    $(".delete_slot").click(delete_slot);

    $("#add_day").unbind('click')
    $("#add_day").click(add_day);
}

function add_room(event) {
    event.preventDefault();
    var rooms_url  = $(event.target).attr('href');

    $("#add_room_dialog").dialog({
        "title" : "Add new room",
      buttons : {
        "Cancel" : function() {
            $(this).dialog("close");
        }
      }
    });

    $("#room_delete_dialog").dialog("open");
}

function delete_room(event) {
    var clickedroom = $(event.target).attr('roomid');
    var room_url    = $(event.target).attr('href');
    event.preventDefault();

    $("#room_delete_dialog").dialog({
      buttons : {
        "Confirm" : function() {
            console.log("deleting room "+clickedroom);
	    $.ajax({
		url: room_url,
	       type: 'DELETE',
	    success: function(result) {
			window.location.reload(true);
                 }
            });
            $(this).dialog("close");
        },
        "Cancel" : function() {
            $(this).dialog("close");
        }
      }
    });

    $("#room_delete_dialog").dialog("open");
}

function add_day(event) {
    event.preventDefault();
    var rooms_url  = $(event.target).attr('href');

    $("#add_day_dialog").dialog({
        "title" : "Add new day/time",
      buttons : {
        "Cancel" : function() {
            $(this).dialog("close");
        }
      }
    });

    $("#room_day_dialog").dialog("open");
}

function delete_slot(event) {
    var clickedday      = $(event.target).attr('timeslot_id');
    var timeslot_url    = $(event.target).attr('href');
    event.preventDefault();

    $("#slot_delete_dialog").dialog({
        title: "Deleting slot "+clickedday,
      buttons : {
        "Confirm" : function() {
            console.log("deleting day "+clickedday);
	    $.ajax({
		url: timeslot_url,
	       type: 'DELETE',
	    success: function(result) {
			window.location.reload(true);
                 }
            });
            $(this).dialog("close");
        },
        "Cancel" : function() {
            $(this).dialog("close");
        }
      }
    });

    $("#slot_delete_dialog").dialog("open");
}

function fill_timeslots() {
    $.each(slot_status, function(key) {
        ssid_arr = slot_status[key];

	for(var q = 0; q<ssid_arr.length; q++){
	    ssid = ssid_arr[q];
            insert_timeslotedit_cell(ssid);
	}
    });
}

function insert_timeslotedit_cell(ssid) {
    var domid  = ssid.domid
    var roomtype=ssid.roomtype
    var slot_id = ("#"+domid)

    roomtypesession="";
    roomtypeother="";
    roomtypeplenary="";
    roomtypereserved="";
    roomtypeclass="";
    roomtypeunavailable="";
    //console.log("domid: "+domid+" has roomtype: "+roomtype)
    $(slot_id).removeClass("agenda_slot_unavailable")
    $(slot_id).removeClass("agenda_slot_other")
    $(slot_id).removeClass("agenda_slot_session")
    $(slot_id).removeClass("agenda_slot_plenary")
    $(slot_id).removeClass("agenda_slot_reserved")

    if(roomtype == "session") {
        roomtypesession="selected";
        roomtypeclass="agenda_slot_session";
    } else if(roomtype == "other") {
        roomtypeother="selected";
        roomtypeclass="agenda_slot_other";
    } else if(roomtype == "plenary") {
        roomtypeplenary="selected";
        roomtypeclass="agenda_slot_plenary";
    } else if(roomtype == "reserved") {
        roomtypereserved="selected";
        roomtypeclass="agenda_slot_reserved";
    } else {
        roomtypeunavailable="selected";
        roomtypeclass="agenda_slot_unavailable";
    }

    var select_id = domid + "_select"
    html = "<form action=\"/some/place\" method=\"post\"><select id='"+select_id+"'>";
    html = html + "<option value='session'     "+roomtypesession+" id='option_"+domid+"_session'>session</option>";
    html = html + "<option value='other'       "+roomtypeother+" id='option_"+domid+"_other'>non-session</option>";
    html = html + "<option value='reserved'    "+roomtypereserved+" id='option_"+domid+"_reserved'>reserved</option>";
    html = html + "<option value='plenary'     "+roomtypeplenary+" id='option_"+domid+"_plenary'>plenary</option>";
    html = html + "<option value='unavail'     "+roomtypeunavailable+" id='option_"+domid+"_unavail'>unavailable</option>";
    html = html + "</select>";


    $(slot_id).html(html)
    $(slot_id).addClass(roomtypeclass)

    $("#"+select_id).change(function(eventObject) {
	start_spin();
        var newpurpose = $("#"+select_id).val()
        console.log("setting id: #"+select_id+" to "+newpurpose+" ("+roomtypeclass+")");

        Dajaxice.ietf.meeting.update_timeslot_purpose(
            function(json) {
                if(json == "") {
                    console.log("No reply from server....");
                } else {
                    stop_spin();
                    for(var key in json) {
	                ssid[key]=json[key];
                    }
                    console.log("server replied, updating cell contents: "+ssid.roomtype);
                    insert_timeslotedit_cell(ssid);
                }
            },
	    {
		'timeslot_id': ssid.timeslot_id,
                'purpose': newpurpose,
	    });
    });

}

/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */

