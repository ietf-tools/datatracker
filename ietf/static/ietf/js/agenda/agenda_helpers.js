/*
*   agenda_helpers.js
*
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*   Should contain miscellaneous commonly used functions.
*
*
*/

/* do_work:
   when we are waiting for something to either resolve to true, or another similar job
   this function should achieve this.

   result will be a function that when returns true will stop the work and then the callback
   will be triggered.

   ex:
      global_x = 0
      do_work(function(){ global_x++; return global_x > 100 }, function(){ console.log("resolved") })
*/
function do_work(result,callback){
    setTimeout(function(){
	if(!result()){
	    setTimeout(arguments.callee,1);
	}
	else{
	    callback();
	}
    });
}


function log(text){
    console.log(text);
}

function print_all(){
    console.log("all");
    console.log(agenda_globals.meeting_objs.length);
    for(var i=0; i<agenda_globals.meeting_objs.length; i++){
		agenda_globals.meeting_objs[i].print_out();
    }
}

function find_title(title){
    $.each(agenda_globals.meeting_objs, function(key){
	if (agenda_globals.meeting_objs[key].title == title) {
	    console.log(agenda_globals.meeting_objs[key]);
	}
    });
}
function find_session_id(session_id){
    $.each(agenda_globals.meeting_objs, function(key){
	if (agenda_globals.meeting_objs[key].session_id == session_id) {
	    console.log(agenda_globals.meeting_objs[key]);
	}
    });
}

function find_same_area(area){
    var areas = []
    area = area.toUpperCase();
    $.each(agenda_globals.meeting_objs, function(index,obj){
	if(obj.area == area){
	    areas.push({id:index,slot_status_key:obj.slot_status_key})
	    }
    });
    return areas
}

function style_empty_slots(){

}

var __debug_load_events = false;
/* this pushes every event into the agendas */
function load_events(){
    var slot_id;

    console.log("load events...");

    /* first delete all html items that might have gotten saved if
     * user save-as and went offline.
     */
    if(__debug_load_events) {
        console.log("processing double slot status relations");
    }

    /* clear out all the timeslots */
    $.each(agenda_globals.timeslot_bydomid, function(key) {
        insert_cell(key, "", true);

        var timeslot = agenda_globals.timeslot_bydomid[key];
        slot_id = ("#"+key);

	$(slot_id).addClass("agenda_slot_" + timeslot.roomtype);

        if(timeslot.roomtype == "unavail") {
            $(slot_id).removeClass("ui-droppable");
            $(slot_id).removeClass("free_slot");
            $(slot_id).addClass("agenda_slot_unavailable");
        } else {
            $(slot_id).removeClass("agenda_slot_unavailable");
            $(slot_id).addClass("ui-droppable");
        }
    });

    $.each(agenda_globals.slot_status, function(key) {
        ssid_arr = agenda_globals.slot_status[key];

	for(var q = 0; q<ssid_arr.length; q++){
	    ssid = ssid_arr[q];

            ssid.connect_to_timeslot_session();

            // also see if the slots have any declared relationship, and take it forward as
            // well as backwards.
            if(ssid.extendedfrom_id != false) {
                other = agenda_globals.slot_objs[ssid.extendedfrom_id];
                if(__debug_load_events) {
                    console.log("slot:",ssid.assignment_id, "extended from: ",key,ssid.extendedfrom_id); // ," is: ", other);
                }
                if(other != undefined) {
                    ssid.extendedfrom = other;
                    other.extendedto  = ssid;
                } else {
                    if(__debug_load_events) {
                        console.log("extended from: ",ssid.extendedfrom_id," not found");
                    }
                }
            }
	}
    });

    // go through the slots again, and if one slot has been extended, then
    // extend any other "sister" slots as well.
    if(__debug_load_events) {
        console.log("marking extended slots for slots with multiple sessions");
    }
    $.each(agenda_globals.slot_status, function(key) {
        ssid_arr = agenda_globals.slot_status[key];

        var extendedto = undefined;
	for(var q = 0; q<ssid_arr.length; q++){
	    ssid = ssid_arr[q];
            if(extendedto == undefined &&
               ssid.extendedto != undefined) {
                if(__debug_load_events) {
                    console.log("ssid",ssid.session_id,"extended 1");
                }
                extendedto = ssid.extendedto;
            }
        }
	for(var q = 0; q<ssid_arr.length; q++){
	    ssid = ssid_arr[q];
            ssid.extendedto = extendedto;
            if(__debug_load_events) {
                console.log("ssid",ssid.session_id,"extended 2");
            }
        }
    });

    if(__debug_load_events) {
        console.log("finding responsible ad");
    }
    $.each(agenda_globals.meeting_objs, function(key) {
        session = agenda_globals.meeting_objs[key];
        session.find_responsible_ad();
    });

    $.each(agenda_globals.slot_status, function(key) {
        ssid_arr = agenda_globals.slot_status[key]
	if(key == "sortable-list"){
	    console.log("sortable list");
	}else {
	    for(var q = 0; q<ssid_arr.length; q++){
	        ssid = ssid_arr[q];
                slot_id = ("#"+ssid.domid());

                if(__debug_load_events) {
                    console.log("populating slot: ",slot_id,key);
                }

                if(ssid.timeslot.roomtype != "unavail") {
                    session = agenda_globals.meeting_objs[ssid.session_id];
                    if (session != null) {
                        if(ssid.extendedto != undefined) {
                            session.double_wide = true;
                            session.slot2 = ssid.extendedto;
                        }
                        if(ssid.extendedfrom == undefined) {
	       	            session.slot_status_key = key;
                        }

	                $(slot_id).removeClass('free_slot');

                        if(ssid.extendedfrom == undefined) {
                            if(__debug_load_events) {
                                console.log("  with session", session.title);
                            }

                            session.populate_event(key);
                        }
                        session.placed(ssid.timeslot, false, ssid);
                    } else {
	                $(slot_id).addClass('free_slot');
                    }
                }
            }
	}
    });

    $.each(agenda_globals.meeting_objs, function(key) {
        session = agenda_globals.meeting_objs[key];

	// note in the group, what the set of column classes is.
	// this is an array, as the group might have multiple
	// sessions!
	group = session.group;
        if(group == undefined) {
            console.log("session: ", session.title, "has no group_href:", session.group_href);
        } else {
            group.add_column_classes(session.column_class_list);
	    group.add_session(session);
        }
    });

}

function check_free(inp){
    var empty = false;
    slot = agenda_globals.timeslot_bydomid[inp.id];
    if(slot == null){
        //console.log("\t from check_free, slot is null?", inp,inp.id, agenda_globals.slot_status[inp.id]);
	return false;
    }
    if (slot.empty == false) {
	return false;
    }
    return true;
}

/* clears any background highlight colors of scheduled sessions */
function clear_highlight(inp_arr){ // @args: array from slot_status{}
    if(inp_arr == null){
	return false;
    }
    for(var i =0; i<inp_arr.length; i++){
	$("#session_"+inp_arr[i].session_id).removeClass('free_slot');
	$("#session_"+inp_arr[i].session_id).css('background-color','');
    }
    return true;

}

/* based on any meeting object, it finds any other objects inside the same timeslot. */
function find_friends(inp){
    var ts = $(inp).parent().attr('id');
    var ss_arr = agenda_globals.slot_status[ts];
    if (ss_arr != null){
	return ss_arr;
    }
    else{
	//console.log("find_friends("+inp+") did not find anything");
	return null;
    }
}


function json_to_id(j){
    return (j.room()+"_"+j.date()+"_"+j.time());
}

function id_to_json(id){
    if(id != null){
	var split = id.split('_');
	return {"room":split[0],"date":split[1],"time":split[2]}
    }
    else{
	return null;
    }
}


/* returns a the html for a row in a table
   as: <tr><td>title</td><td>data</td></tr>
*/
function gen_tr_td(title,data){
    return "<tr><td>"+title+"</td><td>"+data+"</td></tr>";
}

/* Mainly for the case where we didn't get any data back from the server */
function empty_info_table(){
    $("#info_grp").html(name_select_html);
    $("#info_name").html("");
    $("#info_area").html("");
    $("#info_duration").html("");

    $(".agenda_selected_buttons").attr('disabled',true);
    $(".agenda_double_slot").addClass("button_disabled");
    $(".agenda_double_slot").removeClass("button_enabled");

    if(!read_only) {
        $("#info_location").html(generate_select_box()+"<button id='info_location_set'>Set</button>");
        $("#info_location_select").val("");
        $("#info_location_select").val($("#info_location_select_option_"+current_timeslot_id).val());
    }
    $("#info_responsible").html("");
    $("#info_requestedby").html("");
    $("#agenda_requested_features").html("");

    /* need to reset listeners, because we just changed the HTML */
    listeners();
}


var temp_1;
/* creates the 'info' table that is located on the right side.
   takes in a json.
*/

function compare_timeslot(a,b) {
    //console.log("day: a,b", a.day, b.day);

    // sometimes (a.day==b.say)==false and (a.day===b.day)==false,
    // for days that appear identical, but built from different strings,
    // yet (a.day-b.day)==0.
    if((a.day - b.day) == 0) {
        //console.log("time: a,b", a.starttime, b.starttime);
        if(a.starttime == b.starttime) {
            //console.log("room: a,b", a.room, b.room, a.room < b.room);
            if(a.room > b.room) {
                return 1;
            } else {
                return -1;
            }
        };
        if(a.starttime > b.starttime) {
            return 1;
        } else {
            return -1;
        }
    }
    if(a.day > b.day) {
        return 1;
    } else {
        return -1;
    }
}

var room_select_html = "";
function calculate_room_select_box() {
    var html = "<select id='info_location_select'>";
    var mobj_array = [];

    $.each(agenda_globals.timeslot_byid, function(key, value){
        mobj_array.push(value)
    });

    var sorted = mobj_array.sort(compare_timeslot);
    var lastone_id = undefined;

    $.each(sorted, function(index, value) {
        // this check removes duplicates from the list, if there are any.
        if(value.roomtype == "break" || value.roomtype=="reg") {
            return;
        }
        if(value.timeslot_id == lastone_id) {
            return; // from subfunction.
        }
        //console.log("room_select_html", index, value, value.short_string);
        html=html+"<option value='"+value.timeslot_id;
        html=html+"' id='info_location_select_option_";
        html=html+value.timeslot_id+"'>";
        html=html+value.short_string;
        if(value.roomtype != "session") {
            html = html+ "(" + value.roomtype + ")";
        }
        html=html+"</option>";
        lastone_id = value.timeslot_id;
    });
    html = html+"</select>";
    room_select_html = html;
    return room_select_html;
}

var name_select_html = undefined;
var temp_sorted = null;
function calculate_name_select_box(){
    var html = "<select id='info_name_select'>";
    var mobj_array = [];
    var mobj_array2;
    $.each(agenda_globals.meeting_objs, function(key, value){ mobj_array.push(value) });
    mobj_array2 = mobj_array.sort(function(a,b) { return a.title.localeCompare(b.title); });

    var mlen = mobj_array.length;
    console.log("calculate name_select box with",mlen,"objects");
    for(var i = 0; i < mlen; i++){
	//console.log("select box mobj["+i+"]="+mobj_array[i]);
	// html=html+"<option value='"+mobj_array[i].slot_status_key;
	html=html+"<option value='"+mobj_array[i].session_id;
        html=html+"' id='info_name_select_option_";
	ts_id = "err";
	//console.log(mobj_array[i].session_id);
	try{
	    ts_id = mobj_array[i].session_id;
	}catch(err){
	    console.log(err); // bucket list items.

	}
        html=html+ts_id+"'>";


	try{
	    html=html+mobj_array[i].title; // + " (" + mobj_array[i].description + ")";
	} catch(err) {
	    html=html+"ERRROR!!!";
	}
        html=html+"</option>";
    }

    html = html+"</select>";
    name_select_html = html;
    return html;
}



function generate_select_box(){
    if(!room_select_html) {
        calculate_name_select_box();
    }
    return room_select_html;
}




function insert_cell(js_room_id, text, replace){
    slot_id = ("#"+js_room_id);
    try{
	var found;
        if(replace) {
	    found = $(slot_id).html(text);
        } else {
            found = $(slot_id).append($(text));

        }
        $(slot_id).css('background','');
	$(slot_id).removeClass('free_slot');
        if(found.length == 0){
            // do something here, if length was zero... then?
        }

    }
    catch(err){
	log("error");
	log(err);
    }
}


function find_meeting_no_room(){
    $.each(agenda_globals.meeting_objs, function(key){
	if(agenda_globals.meeting_objs[key].slot_status_key == null) {
	    session = agenda_globals.meeting_objs[key]
	    session.slot_status_key = null;
	    session.populate_event(bucketlist_id);
	}
    })
}


/* in some cases we have sessions that span over two timeslots.
   so we end up with two slot_status pointing to the same meeting_obj.
   this this occures when someone requests a session that is extra long
   which will then fill up the next timeslot.

   this functions finds those cases.

   returns a json{ 'ts': arr[time_slot_ids] }

*/
function find_double_timeslots(){
    var duplicate = {};

    $.each(agenda_globals.slot_status, function(key){
	for(var i =0; i<agenda_globals.slot_status[key].length; i++){
	    // goes threw all the slots
	    var ss_id = agenda_globals.slot_status[key][i].session_id;
	    if(duplicate[ss_id]){
		duplicate[ss_id]['count']++;
		duplicate[ss_id]['ts'].push(key);
	    }
	    else{
		duplicate[ss_id] = {'count': 1, 'ts':[key]};

	    }
	}
    });

    var dup = {};
    // console.log(duplicate);
    $.each(duplicate, function(key){
	if(duplicate[key]['count'] > 1){
	    dup[key] = duplicate[key]['ts'];

	}
    });
    return dup;
}


var child = null;
/* removes a duplicate timeslot. completely. it's gone. */
function remove_duplicate(timeslot_id, ss_id){
    children = $("#"+timeslot_id).children();
    child = children;
    for(var i = 0; i< children.length; i++){ // loop to
	if($(children[i]).attr('session_id') == ss_id) { // make sure we only remove duplicate.
	    try{
		$(children[i]).remove();
	    }catch(exception){
		console.log("exception from remove_duplicate",exception);
	    }
	}
    }

}



function auto_remove(){
    dup = find_double_timeslots();
    $.each(dup, function(key){
	remove_duplicate(dup[key][1], key);
    })
}



/* for the spinnner */

/* spinner code from:
       http://fgnass.github.com/spin.js/

       ex: $("#spinner").spin()      < start the spin
           $("#spinner").spin(false) < stop the spin

       http://gist.github.com/itsflorida   < jquery functionality.

       lines: 30,            // The number of lines to draw
       length: 7,            // The length of each line
       width: 1,             // The line thickness
       radius: 20,           // The radius of the inner circle
       corners: 1,           // Corner roundness (0..1)
       rotate: 0,            // The rotation offset
       color: '#000',        // #rgb or #rrggbb
       speed: 1,             // Rounds per second
       trail: 60,            // Afterglow percentage
       shadow: false,        // Whether to render a shadow
       hwaccel: true,        // Whether to use hardware acceleration
       className: 'spinner', // The CSS class to assign to the spinner
       zIndex: 2e9,          // The zindex (defaults to 2000000000)
       top: 'auto',          // Top position relative to parent in px
       left: 'auto'          // Left position relative to parent in px

*/

(function($) {
    $.fn.spin = function(opts, color) {
        if (Spinner) {
           return this.each(function() {
               var $this = $(this),
               data = $this.data();

               if (data.spinner) {
                   data.spinner.stop();
                   delete data.spinner;
               }
               if (opts !== false) {
                   if (typeof opts === "string") {
                       if (opts in presets) {
                           opts = presets[opts];
                       } else {
                           opts = {};
                       }
                       if (color) {
                           opts.color = color;
                       }
                   }
                   data.spinner = new Spinner($.extend({color: $this.css('color')}, opts)).spin(this);
               }
           });
       } else {
           throw "Spinner class not available.";
       }
    };
})(jQuery);


function start_spin(opts){
//spinner
    // $("#schedule_name").hide();
    $("#spinner").show();
    $("#spinner").spin({lines:16, radius:8, length:16, width:4});
    $("#pageloaded").hide();
}
function stop_spin(){
//spinner
    $("#schedule_name").show();
    $("#spinner").hide();
    $("#spinner").spin(false);
    $("#pageloaded").show();
}

/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */
