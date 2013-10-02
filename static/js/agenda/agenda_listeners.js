/*
*   agenda_listeners.js
*
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*   This file should contain functions relating to
*   jquery ui droppable ( http://jqueryui.com/droppable/ )
*   and other interactions.
*
*/

var bucketlist_id = "sortable-list" // for if/when the id for bucket list changes.

function resize_listeners() {
    for(i = 0; i<days.length;i++){
        $("#resize-"+days[i]+"-spacer").resizable({maxHeight:10,
						   handles: "e, s",
						   minWidth:2,

						  });

    }

}



/* this function needs to be renamed...
   it should only deal with listeners who need to be unbound prior to rebinding.
*/
function listeners(){
    //$(".agenda_slot td").not(".meeting_event ui-draggable").unbind('click');
    //$(".agenda_slot td").not(".meeting_event ui-draggable").click(function(event){ console.log("#meetings clicked"); console.log(event); });
    $("#meetings").unbind('click');
    $("#meetings").click(all_click);

    // If we don't unbind it, things end up getting stacked, and tons of ajax things are sent.
    $('.meeting_event').unbind('click');
    $('.meeting_event').click(meeting_event_click);

    $('#info_location_select').unbind('change');
    $('#info_location_select').change(info_location_select_change);

    $('#info_name_select').unbind('change');
    $('#info_name_select').change(info_name_select_change);

    $('.color_checkboxes').unbind('click');
    $('.color_checkboxes').click(color_legend_click);

    resize_listeners()

    $('#find_free').unbind('click');
    $('#find_free').click(function(event){ find_free(); });

    $('#double_slot').unbind('click');

    /* listener for when one clicks the 'show all' checkbox */
    $('.cb_all_conflict').unbind('click');
    $('.cb_all_conflict').click(cb_all_conflict);

    /* hiding rooms */
    $(".close_room").unbind('click');
    $(".close_room").click(close_room)

    /* hiding days */
    $(".close_day").unbind('click');
    $(".close_day").click(close_day);

    // $("#show_hidden_days").unbind('click');
    // $("#show_hidden_days").click(show_hidden_days);
    // $("#show_hidden_rooms").unbind('click');
    // $("#show_hidden_rooms").click(show_hidden_rooms);

    $("#show_all_area").unbind('click');
    $("#show_all_area").click(show_all_area);

    $("#show_all_button").unbind('click');
    $("#show_all_button").click(show_all);

    resize_th();
}

var __debug_movement_warnings = false;
var __debug_toggle_result;
var __debug_toggle_parameters;
function toggle_dialog(parameters) {
    var result = "null";
    var message = "";
    if(parameters.slot_occupied==true && parameters.too_small==false) {
        dialogid = $( "#dialog-confirm-two" );
    }
    else if(parameters.slot_occupied==false && parameters.too_small==true) {
        dialogid = $( "#dialog-confirm-toosmall" );
    }
    else if(parameters.too_small==true && parameters.slot_occupied==true){
        dialogid = $( "#dialog-confirm-twotoosmall" );
    }
    else{
	console.log("error, from toggle_dialog:", parameters);
	return;
    }

    if(__debug_movement_warnings) {
        console.log("toggle_dialog param", parameters, "message", message);
        __debug_toggle_parameters = parameters;
    }

    dialogid.dialog({
	resizable: true,
	modal: true,
	buttons: {
            "Yes": function() {
		$( this ).dialog( "close" );
		__debug_toggle_result = "yes";
                parameters.session.double_wide = false;
		move_slot(parameters);
            },
	    //"Swap Slots": function(){
	    //	$( this ).dialog( "close" );
	    //	result = "swap";
	    //},
            Cancel: function() {
		$( this ).dialog( "close" );
		__debug_toggle_result = "cancel"
            }
	}
    });

    return __debug_toggle_result;
}

function resize_th(){
/* with the hovering rooms the sizes get messed up
   this function looks at the tr's height and resizes the room's height */
    $.each($(".vert_time"), function(k,v){
	$(v).height($("#"+v.parentElement.id).height()-2); /* -2 so the grid remains */
    })
}


function clear_all_selections() {
    $(".same_group").removeClass("same_group");
    $(".selected_group").removeClass("selected_group");
    $(".selected_slot").removeClass("selected_slot");
}

function all_click(event){
    var all_classes = $(event.srcElement).attr('class');
    var classes = [];
    if(all_classes != undefined) {
            classes = all_classes.split(' ');
    }
    // console.log("all_click:", classes, classes.indexOf('meeting_obj'), meeting_clicked);
    if(!meeting_clicked && classes!=undefined && classes.indexOf('meeting_obj') < 0){
        // console.log("32 show_all");
        clear_all_selections();
        clear_conflict_classes();   // remove the display showing the conflict classes.
        last_session = null;
        last_item    = null;
    }
    meeting_clicked = false;
    // console.log(this);
    // console.log($(this));
}

/************ click functions *********************************************************************/
function cb_all_conflict(event){
    var conflict_clicked = $(event.target).attr('id');
    try{
	var conflict_clicked = conflict_clicked.substr(3);
    }catch(err){

    }
    $("."+conflict_clicked+" input").click();


}

function close_room(event){
    var close_room = $(event.target).attr('id');
    close_room =  close_room.substr(6);
    //console.log("close_room",close_room);
    $("#"+close_room).hide("fast");
    hidden_rooms.push("#"+close_room);
    $("#hidden_rooms").html((hidden_rooms.length.toString()+"/"+total_rooms.toString()));
}

function show_hidden_rooms(event){
    $.each(hidden_rooms, function(index,room){
	$(room).show("fast");
    });
    hidden_rooms = [];
    $("#hidden_rooms").html(hidden_rooms.length.toString()+"/"+total_rooms.toString());
}

function close_day(event){
    var close_day = $(event.target).attr('id');
    close_day = close_day.substr(6);
    close_day = ".day_"+close_day;
    $(close_day).hide("slow");
    hidden_days.push(close_day);
    $("#hidden_days").html(hidden_days.length.toString()+"/"+total_days.toString());
}

function show_all(){
    show_hidden_days();
    show_hidden_rooms();
}

function show_hidden_days(event){
    $.each(hidden_days, function(index,room){
	$(room).show("fast");
    });
    hidden_days = [];
    $("#hidden_days").html(hidden_days.length.toString()+"/"+total_days.toString());

}

function show_all_area(event){
    var areas = find_same_area($("#info_area").children().text());
    //console.log("show all area",areas);
    $.each(areas, function(index,obj){

	var selector = $("#"+obj.slot_status_key);
	if(slot_item_hidden(selector) ){
	    $("#"+obj.slot_status_key).effect("highlight", {color:"lightcoral"}, 2000);
	}
    });
}


/************ END click functions *********************************************************************/

function slot_item_hidden(selector){
// checking if the thing we will visually display is hidden. (performing effects will break the previous hide)
    var show = true;

    $.each(hidden_days, function(index,value){
	if(selector.hasClass(value.substr(1))){
	    show=false;
	    return show;
	}
    });
    return show;
}



var free_slots = [];

function find_empty_slot(){

    $.each($(".free_slot"), function(index,item){
	if(!$(item).hasClass("show_conflict_view_highlight")){
	       free_slots.push(item);
	}
    });
    var perfect_slots = []; // array of slots that have a capacity higher than the session.
    if(free_slots.length > 0){
	for(var i = 0; i< free_slots.length; i++){
	    if(parseInt($(free_slots[i]).attr("capacity")) >= parseInt(meeting_objs[current_item.attr('session_id')].attendees) ){
		perfect_slots.push(free_slots[i]);
	    }
	}
	if(perfect_slots.length > 0){
	    return perfect_slots[0];
	}
	else{
	    return free_slots[0]; // just return the first one.
	}

    }
    else{
	return null;
    }

}

function extend_slot(event) {
    // event is just the button push, ignore it.

    session = last_session;
    slot    = session.slot;

    console.log("session", session.title, "slot:", slot.scheduledsession_id);

    // determine if this slot can be extended.
    if(slot.can_extend_right()) {
        $("#can-extend-dialog").html("Extend "+session.title+" to slot "+slot.following_timeslot.domid);
        $("#can-extend-dialog").dialog({
	    resizable: true,
	    modal: true,
	    buttons: {
                "Yes": function() {
	            Dajaxice.ietf.meeting.update_timeslot(dajaxice_callback,
					                  {
                                                              'schedule_id':schedule_id,
						              'session_id': session.session_id,
						              'scheduledsession_id': slot.following_timeslot.scheduledsession_id,
                                                              'extended_from_id': slot.scheduledsession_id
					                  });
                    slot.extendedto = slot.following_timeslot;
                    slot.extendedto.extendedfrom = slot;
                    session.double_wide = true;
                    session.repopulate_event(slot.domid);
                    session.placed(slot.extendedto, false);
                    droppable();
                    listeners();
		    $( this ).dialog( "close" );

                    // may have caused some new conflicts!!!!
                    recalculate_conflicts_for_session(session,
                                                      [slot.column_class],
                                                      [slot.column_class, slot.extendedto.column_class]);
                },
                Cancel: function() {
		    $( this ).dialog( "close" );
		    result = "cancel"
                }
	    }
        });
    } else {
        $( "#can-not-extend-dialog" ).dialog();
    }
}

function find_free(){
    var empty_slot = find_empty_slot();
    if(empty_slot != null){
	$(empty_slot).effect("highlight", {},3000);
	if(current_item != null){
	    $(current_item).addClass('ui-effects-transfer');
	    $(current_item).effect("transfer", {to: $(empty_slot) }, 1000);
	}
	$(current_item).removeClass('ui-effects-transfer');
    }
}


function expand_spacer(target) {
    var current_width = $(target).css('min-width');
    current_width = current_width.substr(0,current_width.search("px"));
    current_width = parseInt(current_width) + 20;
    $(target).css('min-width',current_width);
    $(target).css('width',current_width);

}

function sort_by_alphaname(a,b) {
    am = meeting_objs[$(a).attr('session_id')]
    bm = meeting_objs[$(b).attr('session_id')]
    if(am.title < bm.title) {
        return -1;
    } else {
        return 1;
    }
}
function sort_by_area(a,b) {
    am = meeting_objs[$(a).attr('session_id')]
    bm = meeting_objs[$(b).attr('session_id')]
    if(am.area < bm.area) {
        return -1;
    } else {
        return 1;
    }
}
function sort_by_duration(a,b) {
    am = meeting_objs[$(a).attr('session_id')]
    bm = meeting_objs[$(b).attr('session_id')]
    if(am.duration < bm.duration) {
        // sort duration biggest to smallest.
        return 1;
    } else if(am.duration == bm.duration &&
              am.title    < bm.title) {
        return 1;
    } else {
        return -1;
    }
}
function sort_by_specialrequest(a,b) {
    am = meeting_objs[$(a).attr('session_id')]
    bm = meeting_objs[$(b).attr('session_id')]
    if(am.special_request == '*' && bm.special_request == '') {
        return -1;
    } else if(am.special_request == '' && bm.special_request == '*') {
        return 1;
    } else if(am.title < bm.title) {
        return -1;
    } else {
        return 1;
    }
}

function sort_unassigned() {
    $('#'+bucketlist_id+" div.meeting_box_container").sort(unassigned_sort_function).appendTo('#'+bucketlist_id);
}

var unassigned_sort_function = sort_by_alphaname;
function unassigned_sort_change(){
    var last_sort_method = unassigned_sort_function;
    var sort_method= $("#unassigned_sort_button").attr('value');

    if(sort_method == "alphaname") {
        unassigned_sort_function = sort_by_alphaname;
    } else if(sort_method == "area") {
        unassigned_sort_function = sort_by_area;
    } else if(sort_method == "duration") {
        unassigned_sort_function = sort_by_duration;
    } else if(sort_method == "special") {
        unassigned_sort_function = sort_by_specialrequest;
    } else {
        unassigned_sort_function = sort_by_alphaname;
    }

    if(unassigned_sort_function != last_sort_method) {
        sort_unassigned();
    }
}


/* the functionality of these listeners will never change so they do not need to be run twice  */
function static_listeners(){
    $('#CLOSE_IETF_MENUBAR').click(hide_ietf_menu_bar);

    $('#unassigned_sort_button').unbind('change');
    $('#unassigned_sort_button').change(unassigned_sort_change);
    $('#unassigned_sort_button').css('display','block');
    $("#unassigned_alpha").attr('selected',true);
    sort_unassigned();
}

// recalculate all conflicts from scratch
function recalculate(event) {
    start_spin();
    console.log("loading all conflicts");

    var promise = get_all_conflicts();
    promise.done(function() {
        stop_spin();
        console.log("showing all conflicts");
        show_all_conflicts();
    });
}

function color_legend_click(event){
    var clicked = $(event.target).attr('id');
    if(legend_status[clicked]){
	legend_status[clicked] = false;
    }
    else{
	legend_status[clicked] = true;
    }
    set_transparent();
}

var conflict_status = {};

function conflict_click(event){
    var clicked = $(event.target).attr('id');
    var constraint = find_conflict(clicked);
    //console.log("7 fill", clicked, conflict_status[clicked]);
    if(conflict_status[clicked] == true){
        //console.log("8 fill", constraint.href);
	conflict_status[clicked] = false;
	constraint.checked = "checked";
    }
    else{
        //console.log("9 fill", constraint.href);
	conflict_status[clicked] = true;
	constraint.show_conflict_view();
    }
}

function set_transparent(){
    $.each(legend_status, function(k){
	if(legend_status[k] != true){
	    $("."+k+"-scheme.meeting_obj").parent().parent().parent().draggable("option","disabled",true);
	}else{
	    $("."+k+"-scheme.meeting_obj").parent().parent().parent().draggable("option","disabled",false);
	}

    });
}

var __debug_meeting_click = false;
var clicked_event;
var __DEBUG__SESSION_OBJ;
var __DEBUG__SLOT_OBJ;
var current_item = null;
var current_timeslot = null;
var current_timeslot_id = null;  // global used by empty_info_table to move picker.
var meeting_clicked  = false;
function meeting_event_click(event){
    //hide_all_conflicts();
    try{
	clear_highlight(find_friends(current_item));
    }catch(err){ }

    if(__debug_meeting_click) {
        console.log("1 meeting_click:", event);
    }

    // keep event from going up the chain.
    event.preventDefault();
    meeting_clicked = true;

    if(last_session != null) {
        last_session.unselectit();
    }

    /* clear set ot conflict views */
    clear_conflict_classes();
    conflict_classes = {};

    var slot_id = $(event.target).closest('.agenda_slot').attr('id');
    var container  = $(event.target).closest('.meeting_box_container');

    if(container == undefined) {
        fill_in_session_info(session, true, session.slot);
        // no async necessary, session is completely loaded
	//session.load_session_obj(fill_in_session_info, session.slot);
	return;
    }

    var session_id = container.attr('session_id');
    var session = meeting_objs[session_id];
    last_session = session;

    session.selectit();
    current_item = session.element();

    current_timeslot    = session.slot;
    if(current_timeslot != undefined) {
        current_timeslot_id = current_timeslot.timeslot_id;
    }
    if(__debug_meeting_click) {
        console.log("2 meeting_click:", current_timeslot, session);
    }

    empty_info_table();
    fill_in_session_info(session, true, session.slot);
    __DEBUG__SLOT_OBJ = current_timeslot;
    __DEBUG__SESSION_OBJ = session;
}

var last_item = null; // used during location change we make the background color
// of the timeslot highlight because it is being set into that slot.
function info_location_select_change(){
    if(last_item != null){
	$(last_item).removeClass("selected_slot");
    }

    last_item = '#'+$('#info_location_select').val();
    $(last_item).addClass("selected_slot");
}

var last_session = null;
var last_name_item = null;
function info_name_select_change(){
    if(last_session != null) {
        console.log("unselecting:",last_session.title);
	/* clear set ot conflict views */
	clear_conflict_classes();
	conflict_classes = {};
        last_session.unselectit();
    }
    $(".same_group").removeClass("same_group");
    $(".selected_group").removeClass("selected_group");
    $(".selected_slot").removeClass("selected_slot");

    if(last_item != null) {
        $(last_item).removeClass("selected_slot");
    }
    if(current_item != null){
	$(current_item).addClass("selected_slot");
    }
    var slot_id    = $('#info_name_select').val();
    last_name_item = '#'+slot_id;
    console.log("selecting group", slot_id);

    var ssk = meeting_objs[slot_id].slot_status_key;
    // ssk is null when item is in bucket list.

    current_item = "#session_"+slot_id; //slot_status_obj[0].session_id;

    if(ssk != null){
	var slot_status_obj = slot_status[ssk];
	current_timeslot = slot_status_obj[0].timeslot_id;
	ss = slot_status_obj[0];
	session = ss.session();
        last_session = session;
        last_session.selectit();
	// now set up the call back that might have to retrieve info.
        fill_in_session_info(session, true, ss);
    }
    else {
	ss = meeting_objs[slot_id];
        last_session = ss;
        last_session.selectit();
        fill_in_session_info(ss, true, ss.slot);
    }

    console.log("selecting new item:", last_session.title);
}

function XMLHttpGetRequest(url, sync) {
    var oXMLHttpRequest = new XMLHttpRequest;
    oXMLHttpRequest.open('GET', url, sync);
    oXMLHttpRequest.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    oXMLHttpRequest.setRequestHeader("X-CSRFToken", Dajaxice.get_cookie('csrftoken'));

    return oXMLHttpRequest;
}

function retrieve_session_by_id(session_id) {
    var session_obj = {};
    var oXMLHttpRequest = XMLHttpGetRequest(meeting_base_url+'/session/'+session_id+".json", false);
    oXMLHttpRequest.send();
    if(oXMLHttpRequest.readyState == XMLHttpRequest.DONE) {
        try{
            last_json_txt = oXMLHttpRequest.responseText;
            session_obj   = JSON.parse(oXMLHttpRequest.responseText);
            last_json_reply = session_obj;
        }
        catch(exception){
            console.log("retrieve_session_by_id("+session_id+") exception: "+exception);
        }
    }
    return session_obj;
}

function dajaxice_error(a){
    console.log("dajaxice_error");
}

function set_pin_session_button(scheduledsession) {
    $("#pin_slot").unbind('click');
    if(scheduledsession == undefined) {
        return;
    }
    state = scheduledsession.pinned;
    console.log("button set to: ",state);
    if(state) {
        $("#pin_slot").html("unPin");
        $("#agenda_pin_slot").addClass("button_down");
        $("#agenda_pin_slot").removeClass("button_up");
        $("#pin_slot").click(function(event) {
            update_pin_session(scheduledsession, false);
        });
    } else {
        $("#pin_slot").html(" Pin ");
        $("#agenda_pin_slot").addClass("button_up");
        $("#agenda_pin_slot").removeClass("button_down");
        $("#pin_slot").click(function(event) {
            update_pin_session(scheduledsession, true);
        });
    }
}

function update_pin_session(scheduledsession, state) {
    start_spin();
    console.log("Calling dajaxice", scheduledsession, state);
    Dajaxice.ietf.meeting.update_timeslot_pinned(function(message) {
        console.log("dajaxice callback");
        stop_spin();
        if(message.message != "valid") {
            alert("Update of pinned failed");
            return;
        }
        scheduledsession.pinned = state;
        session = scheduledsession.session()
        session.pinned = state;
        session.repopulate_event(scheduledsession.domid);
        set_pin_session_button(scheduledsession);
    },
						 {
                                                     'schedule_id': schedule_id,
						     'scheduledsession_id':  scheduledsession.scheduledsession_id,
                                                     'pinned': state
						 });
}

function fill_in_session_info(session, success, extra) {
    if(session == null || session == "None" || !success){
	empty_info_table();
    }
    $('#ss_info').html(session.generate_info_table());
    $('#double_slot').click(extend_slot);
    $(".agenda_double_slot").removeClass("button_disabled");
    $(".agenda_double_slot").addClass("button_enabled");
    $(".agenda_selected_buttons").attr('disabled',false);

    if(!read_only) {
        $("#agenda_pin_slot").removeClass("button_disabled");
        $("#agenda_pin_slot").addClass("button_enabled");
        set_pin_session_button(session.slot);
    } else {
        $("#pin_slot").unbind('click');
    }

    // here is where we would set up the session request edit button.
    // $(".agenda_sreq_button").html(session.session_req_link);

    session.retrieve_constraints_by_session().success(function(newobj,status,jq) {
        draw_constraints(session);
    });
}

function group_name_or_empty(constraint) {
    if(constraint == undefined) {
	return "";
    } else {
	return constraint.conflict_view();
    }
}

function draw_constraints(session) {

    if("conflicts" in session) {
        var group_icons = "";

        $.each(session.conflicts, function(index) {
            conflict = session.conflicts[index];
            if(conflict.conflict_groupP()) {
                group_icons += "<li class='conflict'>"+conflict.conflict_view();
                highlight_conflict(conflict);
            }
        });
        if(group_icons == "") {
            $("#conflict_group_list").html("none");
        } else {
            $("#conflict_group_list").html("<ul>"+group_icons+"</ul>");
        }
    } else {
        $("#conflict_group_list").html("none");
    }
    if("bethere" in session.constraints) {
        var people_icons = "";

        $.each(session.constraints.bethere, function(index) {
            conflict = session.constraints.bethere[index];
            if(conflict.conflict_peopleP()) {
                people_icons += "<li class='conflict'>"+conflict.conflict_view();
            }
        });
        if(people_icons == "") {
            $("#conflict_people_list").html("none");
        } else {
            $("#conflict_people_list").html("<ul>"+people_icons+"</ul>");
        }
    } else {
        $("#conflict_people_list").html("none");
    }

}

function highlight_conflict(constraint) {
    if(constraint != undefined) {
        var clicked = constraint.dom_id;
        //console.log("91 fill", constraint.href, constraint.othergroup.href);
	conflict_status[clicked] = true;
	constraint.show_conflict_view();
    }
}

var menu_bar_hidden = false;
function hide_ietf_menu_bar(){
    $('#IETF_MENUBAR').toggle('slide',"",100);
    if(menu_bar_hidden){
	menu_bar_hidden = false;
	$('.wrapper').css('width','auto');
	$('.wrapper').css('margin-left','160px');
	$('#CLOSE_IETF_MENUBAR').html("<");

    }
    else{
	menu_bar_hidden = true;
	$('.wrapper').css('width','auto');
	$('.wrapper').css('margin-left','0px');
	$('#CLOSE_IETF_MENUBAR').html(">");
    }
}



/* create the droppable */
function droppable(){
    if(read_only) {
	return;
    }
    $(function() {
	/* the thing that is draggable */
	$( ".meeting_event").draggable({
	    appendTo: "body",
	    helper: "clone",
	    drag: drag_drag,
	    start: drag_start,
	    stop: drag_stop,
	});

	$( "#sortable-list").droppable({
	    over : drop_over,
	    activate: drop_activate,
	    out : drop_out,
	    drop : drop_drop,
	    start: drop_start,
	})

	$("#meetings td.ui-droppable").droppable({
	    over :drop_over,
	    activate:drop_activate,
	    out :drop_out,
	    drop : drop_drop,
	    create: drop_create,
	    start: drop_start,

	}); // end $(#meetings td).droppable
    }); // end function()
} // end droppable()


var arr_key_index = null;
function update_to_slot(session_id, to_slot_id, force){
    console.log("meeting_id:",session_id);
    var to_slot = slot_status[to_slot_id];

    var found = false;
    for(var i=0; i<to_slot.length; i++){
	if(to_slot[i].empty == "True" || to_slot[i].empty == true){ // we found a empty place to put it.
	    // setup slot_status info.
	    to_slot[i].session_id = session_id;

            if(to_slot_id != bucketlist_id) {
	        to_slot[i].empty = false;
            }

	    // update meeting_obj
	    //meeting_objs[session_id].slot_status_key = to_slot[i].domid
	    arr_key_index = i;
	    meeting_objs[session_id].placed(to_slot, true);
	    found = true;
	    // update from_slot

	    return found;
	}
    }

    if(!found && force){
        var unassigned_slot_obj = new ScheduledSlot();
        unassigned_slot_obj.scheduledsession_id = to_slot[0].scheduledsession_id;
        unassigned_slot_obj.timeslot_id         = to_slot[0].timeslot_id;
        unassigned_slot_obj.session_id          = session_id;
        // unassigned_slot_obj.session_id          = to_slot[0].session_id;

	//console.log("session_id:",session_id);
	//console.log("to_slot (BEFORE):", to_slot, to_slot.length);

	to_slot.push(unassigned_slot_obj);
	//console.log("to_slot (AFTER):", to_slot, to_slot.length);
	arr_key_index = to_slot.length-1;
	found = true;
	return found;
    }
    return found;
}


function update_from_slot(session_id, from_slot_id){

    var from_slot = slot_status[meeting_objs[session_id].slot_status_key]; // remember this is an array...
    var found = false;

    if(from_slot_id != null){ // it will be null if it's coming from a bucketlist
	for(var k = 0; k<from_slot.length; k++){
	    if(from_slot[k].session_id == session_id){
		found = true;
		from_slot[k].empty = true;
		from_slot[k].session_id = null;
		return found;
	    }
	}
    }
    else{
	found = true; // this may be questionable. It deals with the fact that it's coming from a bucketlist.
	return found;
    }
    return found;
}



function drop_drop(event, ui){

    var session_id = ui.draggable.attr('session_id');   // the session was added as an attribute
    // console.log("UI:", ui, session_id);
    var session    = meeting_objs[session_id];

    var to_slot_id = $(this).attr('id'); // where we are dragging it.
    var to_slot = slot_status[to_slot_id]

    var from_slot_id = session.slot_status_key;
    var from_slot = slot_status[session.slot_status_key]; // remember this is an array...

    var room_capacity = parseInt($(this).attr('capacity'));
    var session_attendees = parseInt(session.attendees);

    var too_small = false;
    var occupied = false;


    if(from_slot_id == to_slot_id){ // hasn't moved don't do anything
	return
    }


    if(session_attendees > room_capacity){
	too_small = true;
    }

    // console.log("from -> to", from_slot_id, to_slot_id);


    bucket_list = (to_slot_id == bucketlist_id);
    if(!check_free({id:to_slot_id}) ){
	console.log("not free...");
	if(!bucket_list) {
	    occupied = true
	}
    }

    if(too_small || occupied){
	toggle_dialog({ "session": session,
                        "to_slot_id": to_slot_id,
                        "to_slot":    to_slot,
                        "from_slot_id": from_slot_id,
                        "from_slot":    from_slot,
                        "bucket_list":  bucket_list,
                        "event":        event,
                        "ui":           ui,
                        "dom_obj":      this,
                        "slot_occupied":     occupied,
                        "too_small":    too_small});
	return
    }

    clear_conflict_classes();
    // clear double wide setting for now.
    // (could return if necessary)
    session.double_wide = false;

    move_slot({"session": session,
               "to_slot_id": to_slot_id,
               "to_slot":    to_slot,
               "from_slot_id":from_slot_id,
               "from_slot":   from_slot,
               "bucket_list": bucket_list,
               "event":       event,
               "ui":          ui,
               "dom_obj":     this,
               "force":       false});
}

function recalculate_conflicts_for_session(session, old_column_classes, new_column_classes)
{
    // go recalculate things
    session.clear_all_conflicts();

    find_and_populate_conflicts(session);
    session.examine_people_conflicts(old_column_classes);

    var sk;
    for(sk in meeting_objs) {
        var s = meeting_objs[sk];

        for(ocn in old_column_classes) {
            var old_column_class = old_column_classes[ocn];

            if(old_column_class == undefined) continue;

            for(ncn in new_column_classes) {
                var new_column_class = new_column_classes[ncn];

                if(new_column_class == undefined) continue;

                //console.log("recalc? looking at ",s.title, old_column_class.column_tag, new_column_class.column_tag);
                for(ccn in s.column_class_list) {
                    var column_class = s.column_class_list[ccn];

                    if(s != session && column_class != undefined &&
                       (column_class.column_tag == new_column_class.column_tag||
                        column_class.column_tag == old_column_class.column_tag)) {
                        console.log("recalculating conflicts for:", s.title);
                        s.clear_conflict();
                        find_and_populate_conflicts(s);
                        s.examine_people_conflicts();
                    }
                }
            }
        }
    }
    console.log("new conflict for ",session.title," is ", session.conflicted);
    show_all_conflicts();
}

var _move_debug = false;
var _LAST_MOVED;
function move_slot(parameters) {
    /* dom_obj: is a jquery selector of where the slot will be appeneded to
       Naming is in regards to that most often function is called from
       drop_drop where 'this' is the dom dest.
    */
    var update_to_slot_worked = false;

    if(_move_debug) {
        _LAST_MOVED = parameters.session;
        if(parameters.from_slot != undefined) {
            console.log("from_slot", parameters.from_slot.domid);
        } else {
            console.log("from_slot was unassigned");
        }
    }
    var update_to_slot_worked = false;
    if(parameters.same_timeslot == null){
	parameters.same_timeslot = false;
    }
    if(parameters.bucket_list) {
	update_to_slot_worked = update_to_slot(parameters.session.session_id,
                                               parameters.to_slot_id, true);
    }
    else{
	update_to_slot_worked = update_to_slot(parameters.session.session_id,
                                               parameters.to_slot_id, parameters.same_timeslot);
    }

    if(_move_debug) {
        console.log("update_slot_worked", update_to_slot_worked);
    }
    if(update_to_slot_worked){
	if(update_from_slot(parameters.session.session_id, parameters.from_slot_id)){
	    remove_duplicate(parameters.from_slot_id, parameters.session.session_id);
	    // do something
	}
	else{
            if(_move_debug) {
	        console.log("issue updateing from_slot");
	        console.log("parameters.from_slot_id",parameters.from_slot_id, slot_status[parameters.from_slot_id]);
            }
	    return;
	}
    }
    else{
        if(_move_debug) {
	    console.log("issue updateing to_slot");
	    console.log("to_slot_id",parameters.to_slot_id, slot_status[parameters.to_slot_id]);
        }
	return;
    }
    parameters.session.slot_status_key = parameters.to_slot[arr_key_index].domid;

    var eTemplate = parameters.session.event_template()

    console.log("dom_obj:", parameters.dom_obj);
    $(parameters.dom_obj).append(eTemplate);

    parameters.ui.draggable.remove();



    /* set colours */
    $(parameters.dom_obj).removeClass('highlight_free_slot');
    if(check_free({id:parameters.to_slot_id}) ){
	$(parameters.dom_obj).addClass('free_slot')
    }
    else{
	$(parameters.dom_obj).removeClass('free_slot')
    }

    if(check_free({id:parameters.from_slot_id}) ){
	$("#"+parameters.from_slot_id).addClass('free_slot');
    }
    else{
	$("#"+parameters.from_slot_id).removeClass('free_slot');
    }
    $("#"+bucketlist_id).removeClass('free_slot');
    /******************************************************/

    var scheduledsession = null;
    for(var i =0; i< parameters.to_slot.length; i++){
	if (parameters.to_slot[i].session_id == parameters.session.session_id){
            scheduledsession = parameters.to_slot[i];
	    break;
	}
    }

    if(scheduledsession != null){
        console.log("moved session",parameters.session.title,"to",scheduledsession);
        parameters.session.placed(scheduledsession, true);
        start_spin();
        if(_move_debug) {
	    console.log('schedule_id',schedule_id,
                        'session_id', parameters.session.session_id,
                        'scheduledsession_id', scheduledsession.scheduledsession_id);
        }

        if(parameters.session.slot2) {
            parameters.session.double_wide = false;
	    Dajaxice.ietf.meeting.update_timeslot(dajaxice_callback,
					      {
                                                  'schedule_id':schedule_id,
						  'session_id': parameters.session.session_id,
						  'scheduledsession_id': 0,
					      });
            parameters.session.slot2 = undefined;
        }

	if(parameters.same_timeslot){
	    	Dajaxice.ietf.meeting.update_timeslot(dajaxice_callback,
					      {
                                                  'schedule_id':schedule_id,
						  'session_id': parameters.session.session_id,
						  'scheduledsession_id': scheduledsession.scheduledsession__id,
                                                  'extended_from_id': 0,
						  'duplicate':true
					      });
	}else {
	    Dajaxice.ietf.meeting.update_timeslot(dajaxice_callback,
						  {
                                                      'schedule_id':schedule_id,
						      'session_id': parameters.session.session_id,
						      'scheduledsession_id': scheduledsession.scheduledsession_id,
						  });
	}

        parameters.session.update_column_classes([scheduledsession], parameters.bucket_list);
    }
    else{
        if(_move_debug) {
	    console.log("issue sending ajax call!!!");
        }
    }

    droppable();
    listeners();
    sort_unassigned();
}

/* first thing that happens when we grab a meeting_event */
function drop_activate(event, ui){
    //$(event.draggable).css("background",dragging_color);
    $(event.currentTarget).addClass('highlight_current_moving');
}


/* what happens when moving a meeting event over something that is 'droppable' */
function drop_over(event, ui){
    if(check_free(this)){
	$(this).addClass('highlight_free_slot');
    }
    $(event.draggable).addClass('highlight_current_selected');
    $(ui.draggable).addClass('highlight_current_selected');

//    $(ui.draggable).css("background",dragging_color);
//    $(event.draggable).css("background",dragging_color);
}

/* when we have actually dropped the meeting event */
function drop_out(event, ui){
    if(check_free(this)){
	if($(this).attr('id') != bucketlist_id){
	    $(this).addClass("free_slot");
	}
    }
    $(this).removeClass('highlight_free_slot');
    $(event.draggable).removeClass('highlight_current_selected');
    $(ui.draggable).removeClass('highlight_current_selected');

}

function drag_stop(event,ui){
    $(event.target).removeClass('highlight_current_selected');
    $(event.target).removeClass('highlight_current_moving');
}


/* functions here are not used at the moment */
function drop_create(event,ui){
}

function drop_start(event,ui){
}

function drag_drag(event, ui){
}

function drag_start(event, ui){
    return;
}

/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */
