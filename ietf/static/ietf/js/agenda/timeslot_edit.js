
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




/* ////////////-GLOBALS----/////////////////////////////////////// */

var agenda_globals;

var days = [];
var legend_status = {};   /* agenda area colors. */

var duplicate_sessions = {};

/* the following are initialized in the timeslot_edit.html template */
/* var meeting_slots_href = URL to get/post new timeslots.          */

/********* colors ************************************/

var highlight = "red";       /* when we click something and want to highlight it. */
var dragging_color = "blue"; /* color when draging events. */
var none_color = '';         /* unset the color. */
var color_droppable_empty_slot = 'rgb(0, 102, 153)';

// these are used for debugging only.
var last_json_txt   = "";    /* last txt from a json call. */
var last_json_reply = [];    /* last parsed content */

var hidden_rooms = [];
var total_rooms = 0;         /* the number of rooms */
var hidden_days = [];
var total_days = 0;          /* the number of days  */
/****************************************************/

/* ///////////-END-GLOBALS-///////////////////////////////////// */

/* refactor this out into the html */
$(document).ready(function() {
    init_timeslot_edit();

    $("#close_ietf_menubar").click();
});

/*
   init_timeslot_editf()
   This is ran at page load and sets up the entire page.
*/
function init_timeslot_edit(){
    agenda_globals = new AgendaGlobals();
    log("initstuff() ran");
    var directorpromises = [];
    setup_slots(directorpromises);

    log("setup_slots() ran");

    $.when.apply($,directorpromises).done(function() {
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
        console.log("timeslot editor ready");
    });

    /* datepicker stuff */
    create_datetimepicker();

    /* hide the django form stuff we don't need */
    $("#id_duration").hide();
    $("label[for*='id_duration']").hide();
    $("#duration_time").val("01:00");
    format_datetime();

    $("#pageloaded").show();
}

function create_datetimepicker(){
    $("#start_date").datepicker({
	dateFormat: "yy-mm-dd",
    });
    $("#duration_time").timepicker({
	timeFormat: 'HH:mm',
	hourMin: 0,
    	hourMax: 8,
    	stepMinute:5,
	defaultValue: "01:00",
	onSelect: function(selected){
	    $("input[name*='duration_hours']").val($(this).val().split(':')[0]);
	    $("input[name*='duration_minutes']").val($(this).val().split(':')[1]);
	    format_datetime();
    	}
    })

    $("#id_time").datetimepicker({
    	timeFormat: 'HH:mm',
    	dateFormat: "yy-mm-dd",
    	defaultValue: first_day,
    	hourMin: 9,
    	hourMax: 22,
    	stepMinute:5,
    	onSelect: function(selected){
    	    duration_set($(this).datetimepicker('getDate'));
	    format_datetime()
    	}
    });
    $("#id_time").datepicker('setDate', first_day);
}

function format_datetime(){
    var startDate = $("#id_time").datetimepicker('getDate');
    var endTime = $("#id_time").datetimepicker('getDate');
    endTime.setHours(endTime.getHours()+parseInt($("#duration_time").val().split(':')[0]))
    endTime.setMinutes(endTime.getMinutes()+parseInt($("#duration_time").val().split(':')[1]))
    $("#timespan").html(moment($("#id_time").datetimepicker('getDate')).format('HH:mm') + " <-> " + moment(endTime).format('HH:mm'));
}

function duration_set(d){
    $("input[name*='duration_hours']").val(d.getHours());
    $("input[name*='duration_minutes']").val(d.getMinutes());
}

function add_room(event) {
    event.preventDefault();

    $("#add_room_dialog").dialog({
        "title" : "Add new room",
        buttons : {
            "Cancel" : function() {
                $(this).dialog("close");
            }
        }
    });
    $("#add_room_dialog").dialog("open");
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
    /* add no_timeslot class to all timeslots, it will be removed */
    /* when an item is placed into the slot. */
    $(".agenda_slot").addClass("no_timeslot");
    $.each(agenda_globals.timeslot_bydomid, function(key) {
        ts = agenda_globals.timeslot_bydomid[key];
        insert_timeslotedit_cell(ts);
    });

    /* now add a create option for every slot which hasn't got a timeslot */
    $.each($(".no_timeslot"),function(slot) {
        create_timeslotedit_cell(this);
    });
}

function build_select_box(roomtype, domid, slot_id, select_id) {
    /* console.log("updating for", ts); */
    roomtypesession="";
    roomtypeother="";
    roomtypeplenary="";
    roomtypereserved="";
    roomtypeclass="";
    roomtypeunavailable="";

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

    html = "<form action=\"/some/place\" method=\"post\"><select id='"+select_id+"'>";
    html = html + "<option value='session'     "+roomtypesession+" id='option_"+domid+"_session'>session</option>";
    html = html + "<option value='other'       "+roomtypeother+" id='option_"+domid+"_other'>non-session</option>";
    html = html + "<option value='reserved'    "+roomtypereserved+" id='option_"+domid+"_reserved'>reserved</option>";
    html = html + "<option value='plenary'     "+roomtypeplenary+" id='option_"+domid+"_plenary'>plenary</option>";
    html = html + "<option value='unavail'     "+roomtypeunavailable+" id='option_"+domid+"_unavail'>unavailable</option>";
    html = html + "</select>";

    $(slot_id).html(html)
    $(slot_id).addClass(roomtypeclass);
    return roomtypeclass;
}


function insert_timeslotedit_cell(ts) {
    var roomtype=ts.roomtype;
    var domid   =ts.domid;
    var slot_id =("#" + domid);

    $(slot_id).removeClass("agenda_slot_unavailable")
    $(slot_id).removeClass("agenda_slot_other")
    $(slot_id).removeClass("agenda_slot_session")
    $(slot_id).removeClass("agenda_slot_plenary")
    $(slot_id).removeClass("agenda_slot_reserved")
    $(slot_id).removeClass("no_timeslot");

    var select_id = domid + "_select";
    var roomtypeclass = build_select_box(roomtype, domid, slot_id, select_id);
    /* console.log("Creating box for old ", select_id); */

    $("#"+select_id).off();  /* removes all old events */
    $("#"+select_id).change(function(eventObject) {
	start_spin();
        var newpurpose = $("#"+select_id).val()
        console.log("setting id: #"+select_id+" to "+newpurpose+" ("+roomtypeclass+")");

        var purpose_struct = { "purpose" : newpurpose };
        var purpose_update = $.ajax(ts.href, {
            "content-type": "text/json",
            "type": "PUT",
            "data": purpose_struct,
        });

        purpose_update.success(function(result, status, jqXHR) {
            if(result.message != "valid") {
                alert("Update of pinned failed");
                return;
            }
            stop_spin();
            for(var key in result) {
	        ts[key]=result[key];
            }
            console.log("server replied, updating cell contents: "+ts.roomtype);
            insert_timeslotedit_cell(ts);
        });
    });
}

var __debug_object;
function create_timeslotedit_cell(slot_id) {
    var roomtype = "unavailable";

    __debug_object = object;

    var object = $(slot_id);
    var room = object.attr('slot_room');
    var time = object.attr('slot_time');
    var duration=object.attr('slot_duration');
    var domid= object.attr('id');

    /* $(slot_id).removeClass("agenda_slot_unavailable") */
    $(slot_id).removeClass("agenda_slot_other")
    $(slot_id).removeClass("agenda_slot_session")
    $(slot_id).removeClass("agenda_slot_plenary")
    $(slot_id).removeClass("agenda_slot_reserved")

    var select_id = domid + "_select";
    var roomtypeclass = build_select_box(roomtype, "default", slot_id, select_id);
    /* console.log("Creating box for new ", $("#"+select_id)); */

    $("#"+select_id).off();  /* removes all old events */
    $("#"+select_id).change(function(eventObject) {
	start_spin();
        var newpurpose = $("#"+select_id).val()
        /* console.log("creating new slot id: #"+select_id+" to "+newpurpose+" (was "+roomtypeclass+")"); */
        var ts = {
            'room_id': room,
            'time'   : time,
            'duration':duration,
            /* 'purpose': newpurpose, */
            'type': newpurpose,
	};


        var new_timeslot_promise = $.ajax(meeting_slots_href, {
            "content-type": "text/json",
            "type": "POST",
            "data": ts,
        });

        new_timeslot_promise.success(function(result, status, jqXHR) {
            stop_spin();
            if(jqXHR.status != 201) {
                __debug_object = jqXHR;
                alert("creation of new timeslot failed");
                return;
            }

            ts_obj = make_timeslot(result);
            /* change the domid of the unavailable slot to that which we just created */
            $(slot_id).attr('id', ts_obj.domid);
            insert_timeslotedit_cell(ts_obj);
        });
    });
}

/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */

