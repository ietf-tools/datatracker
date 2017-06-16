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
						   handles: "e",
						   minWidth:2,

						  });

    }

    $("#session-info").resizable({handles: "s",
				  minWidth:"100%",
				  containment: "parent"
				 });

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

    $('#info_location_set').unbind('click');
    $('#info_location_set').click(info_location_select_set);

    $('#info_name_select').unbind('change');
    $('#info_name_select').change(info_name_select_change);

    $('.color_checkboxes').unbind('click');
    $('.color_checkboxes').click(color_legend_click);

    resize_listeners()

    $('#find_free').unbind('click');
    $('#find_free').click(function(event){ find_free(); });

    $('#double_slot').unbind('click');

    /* hiding rooms */
    $(".close_room").unbind('click');
    $(".close_room").click(close_room)

    /* hiding days */
    $(".close_day").unbind('click');
    $(".close_day").click(close_day);

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
                parameters.same_timeslot = true;
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
        $(v).offset({ left: 2});
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
function update_room_count() {
   $("#hidden_rooms").html((hidden_rooms.length.toString()+"/"+total_rooms.toString()));
}

function close_room(event){
    var close_room = $(event.target).attr('id');
    close_room =  close_room.substr(6);
    //console.log("close_room",close_room);
    $("#"+close_room).hide("fast");
    hidden_rooms.push("#"+close_room);
    update_room_count();
}

function show_hidden_rooms(event){
    $.each(hidden_rooms, function(index,room){
	$(room).show("fast");
    });
    hidden_rooms = [];
    update_room_count();
}

function update_day_count() {
    $("#hidden_days").html(hidden_days.length.toString()+"/"+total_days.toString());
}

function close_day(event){
    var close_day = $(event.target).attr('id');
    close_day = close_day.substr(6);
    close_day = ".day_"+close_day;
    $(close_day).hide("slow");
    hidden_days.push(close_day);
    update_day_count();
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
    update_day_count();
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

function show_all_session(event){
    var session_class = "." + last_session.short_name;

    $(session_class).parent().parent().parent().effect("highlight", {color:"lightcoral"}, 5000);
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




function find_empty_slot(session) {
    var free_slots = [];

    $.each(agenda_globals.timeslot_byid, function(id, slot) {
        if(slot.empty && !slot.unscheduled_box) {
	    free_slots.push(slot);
	}
    });

    //console.log("free_slot list", free_slots);
    var target_capacity = session.attendees;

    // array of slots that have a capacity higher than the session.
    var perfect_slots = [];

    if(free_slots.length > 0){
	for(var i = 0; i< free_slots.length; i++){
	    if(free_slots[i].capacity  >= target_capacity) {
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

    session  = last_session;

    console.log("session", session.title, "sslot:", current_scheduledslot.assignment_id);

    /* bind current_timeslot into this function and continuations */
    var slot = current_timeslot;

    // determine if this slot can be extended.
    if(current_timeslot.can_extend_right()) {
        $("#can-extend-dialog").html("Extend "+session.title+" to slot "+slot.following_timeslot.domid);
        $("#can-extend-dialog").dialog({
	    resizable: true,
	    modal: true,
            dialogClass: "extend-dialog",
	    buttons: {
                "Yes": {
                    click: function() {
                        // need to create new assignment
                        var new_ss = make_ss({ "session_id" : session.session_id,
                                               "timeslot_id": slot.following_timeslot.timeslot_id,
                                               "extendedfrom_id" : current_scheduledslot.assignment_id});
                        // make_ss also adds to slot_status.
                        new_ss.saveit();

                        slot.extendedto = slot.following_timeslot;
                        slot.extendedto.extendedfrom = slot;
                        session.double_wide = true;
                        session.repopulate_event(slot.domid);

                        droppable();
                        listeners();
		        $( this ).dialog( "close" );

                        // may have caused some new conflicts!!!!
                        recalculate_conflicts_for_session(session,
                                                          [slot.column_class],
                                                          [slot.column_class, slot.extendedto.column_class]);
                    },
                    text: "Yes",
                    id: "extend-yes"},
                "Cancel": {
                    click: function() {
		        $( this ).dialog( "close" );
		        result = "cancel"
                    },
                    text: "Cancel",
                    id: "extend-cancel"},
	    }
        });
    } else {
        $( "#can-not-extend-dialog" ).dialog();
    }
}

function find_free(){
    if(last_session) {
        var empty_slot = find_empty_slot(last_session);
        if(empty_slot != null){
            var domthing = $("#"+empty_slot.domid);
	    domthing.effect("highlight", {},3000);
	    if(current_item != null){
	        $(current_item).addClass('ui-effects-transfer');
	        $(current_item).effect("transfer", {to: domthing }, 1000);
	    }
	    $(current_item).removeClass('ui-effects-transfer');
        }
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
    am = agenda_globals.meeting_objs[$(a).attr('session_id')]
    bm = agenda_globals.meeting_objs[$(b).attr('session_id')]
    if(am.title < bm.title) {
        return -1;
    } else {
        return 1;
    }
}
function sort_by_area(a,b) {
    am = agenda_globals.meeting_objs[$(a).attr('session_id')]
    bm = agenda_globals.meeting_objs[$(b).attr('session_id')]
    if(am.area < bm.area) {
        return -1;
    } else {
        return 1;
    }
}
function sort_by_duration(a,b) {
    am = agenda_globals.meeting_objs[$(a).attr('session_id')]
    bm = agenda_globals.meeting_objs[$(b).attr('session_id')]
    if(am.requested_duration < bm.requested_duration) {
        // sort duration biggest to smallest.
        return 1;
    } else if(am.requested_duration == bm.requested_duration &&
              am.title    < bm.title) {
        return 1;
    } else {
        return -1;
    }
}
function sort_by_specialrequest(a,b) {
    am = agenda_globals.meeting_objs[$(a).attr('session_id')]
    bm = agenda_globals.meeting_objs[$(b).attr('session_id')]
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
    $('#close_ietf_menubar').click(hide_ietf_menu_bar);

    $("#show_hidden_days").unbind('click');
    $("#show_hidden_days").click(show_hidden_days);
    $("#show_hidden_rooms").unbind('click');
    $("#show_hidden_rooms").click(show_hidden_rooms);

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
var __debug_click_slot_id;
var __debug_click_container;

// current_item is the domid that was clicked
// last_session is the session active.
var current_item = null;
var current_timeslot = null;
var current_scheduledslot = null;
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

    var slot_id = $(event.target).closest('.agenda_slot').attr('id');
    var container  = $(event.target).closest('.meeting_box_container');
    __debug_click_slot_id   = slot_id;
    __debug_click_container = container;

    if(container == undefined) {
	return;
    }

    var session_id = container.attr('session_id');
    var session = agenda_globals.meeting_objs[session_id];

    select_session(session);
    __DEBUG__SS_OBJ   = current_scheduledslot;
    __DEBUG__SLOT_OBJ = current_timeslot;
    __DEBUG__SESSION_OBJ = session;
}

function select_session(session) {
    if(last_session != null) {
        last_session.unselectit();
    }
    last_session = session;

    empty_info_table();
    current_item = session.element();

    /* clear set ot conflict views */
    clear_conflict_classes();
    conflict_classes = {};

    current_timeslot      = session.slot;
    if(current_timeslot) {
        current_timeslot_id   = current_timeslot.timeslot_id;
    }
    current_scheduledslot = session.assignment;
    if(__debug_meeting_click) {
        console.log("2 meeting_click:", current_timeslot, session);
    }

    fill_in_session_info(session, true, session.slot);
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

// called when the "Set" button is called, needs to perform a move, as if
// it was dragged and dropped.
function info_location_select_set() {
    // figure out where the item was, and where it is going to.
    var session = last_session;
    var from_slot = session.slot;

    var id = $('#info_location_select').val();
    var to_slot = agenda_globals.timeslot_byid[id];

    console.log("moved by select box from", from_slot, "to", to_slot);

    move_thing({ "session": session,
                 "to_slot_id": to_slot.domid,
                 "to_slot":    to_slot,
                 "dom_obj":      "#" + to_slot.domid,
                 "from_slot_id": from_slot.domid,
                 "from_slot":    from_slot});
}

function move_thing(parameters) {
    // hasn't moved don't do anything
    if(parameters.from_slot_id == parameters.to_slot_id){
        $(parameters.dom_obj).removeClass('highlight_free_slot');
	return;
    }

    parameters.too_small = false;
    parameters.slot_occupied = false;

    var room_capacity = parameters.to_slot.capacity;

    if(parameters.session.session_attendees > room_capacity){
	parameters.too_small = true;
    }

    parameters.bucket_list = (parameters.to_slot_id == bucketlist_id);
    if(!parameters.bucket_list && !parameters.to_slot.empty){
	parameters.slot_occupied = true
    }

    if(parameters.too_small || parameters.slot_occupied){
	toggle_dialog(parameters);
	return
    }

    clear_conflict_classes();
    // clear double wide setting for now.
    // (could return if necessary)
    parameters.session.double_wide = false;

    move_slot(parameters);
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

    var slot_id    = $('#info_name_select').val();
    last_name_item = '#'+slot_id;
    console.log("selecting group", slot_id);

    var ssk = agenda_globals.meeting_objs[slot_id].slot_status_key;
    // ssk is null when item is in bucket list.

    current_item = "#session_"+slot_id; //slot_status_obj[0].session_id;
    if(current_item != null){
	$(current_item).addClass("selected_slot");
        $(current_item).get(0).scrollIntoView(true);
    }

    if(ssk != null){
	var slot_status_obj = agenda_globals.slot_status[ssk];
	current_timeslot    = slot_status_obj[0].timeslot;
	current_timeslot_id = slot_status_obj[0].timeslot_id;
	ss = slot_status_obj[0];
	session = ss.session;
        last_session = session;
        last_session.selectit();
	// now set up the call back that might have to retrieve info.
        fill_in_session_info(session, true, ss);
    }
    else {
	ss = agenda_globals.meeting_objs[slot_id];
        last_session = ss;
        last_session.selectit();
        fill_in_session_info(ss, true, ss.slot);
    }

    console.log("selecting new item:", last_session.title);
}

function set_pin_session_button(assignment) {
    $("#pin_slot").unbind('click');
    if(assignment == undefined) {
        console.log("pin not set, assignment undefined");
        return;
    }
    state = assignment.pinned;
    //console.log("button set to: ",state);
    $("#pin_slot").attr('disabled',false);
    if(state) {
        $("#pin_slot").html("unPin");
        $("#agenda_pin_slot").addClass("button_down");
        $("#agenda_pin_slot").removeClass("button_up");
        $("#pin_slot").click(function(event) {
            update_pin_session(assignment, false);
        });
    } else {
        $("#pin_slot").html(" Pin ");
        $("#agenda_pin_slot").addClass("button_up");
        $("#agenda_pin_slot").removeClass("button_down");
        $("#pin_slot").click(function(event) {
            update_pin_session(assignment, true);
        });
    }
}

function update_pin_session(assignment, state) {
    start_spin();
    assignment.set_pinned(state, function(assignment) {
        stop_spin();
        session.repopulate_event(assignment.domid());
        set_pin_session_button(assignment);
    });
}

function enable_button(divid, buttonid, func) {
    $(buttonid).unbind('click');
    $(buttonid).click(func);
    $(buttonid).attr('disabled',false);

    $(divid).removeClass("button_disabled");
    $(divid).addClass("button_enabled");
}

function disable_button(divid, buttonid) {
    $(buttonid).unbind('click');
    $(buttonid).attr('disabled',true);

    $(divid).addClass("button_disabled");
    $(divid).removeClass("button_enabled");
}

function highlight_session(session) {
    var element = session.element()[0];
    element.scrollIntoView(true);
    session.element().parent().parent().parent().effect("pulsate", {color:"lightcoral"}, 10000);
}

function fill_in_session_info(session, success, extra) {
    var prev_session = null;
    var next_session = null;

    if(session == null || session == "None" || !success){
	empty_info_table();
        return;
    }
    session.generate_info_table();

    prev_session = session.prev_session;
    next_session = session.next_session;

    if(!read_only) {
        enable_button("#agenda_double_slot", "#double_slot", extend_slot);

        $("#agenda_pin_slot").removeClass("button_disabled");
        $("#agenda_pin_slot").addClass("button_enabled");
        set_pin_session_button(session.assignment);
    } else {
        $("#pin_slot").unbind('click');
    }

    enable_button("#agenda_show", "#show_session", show_all_session);

    if(prev_session) {
        enable_button("#agenda_prev_session", "#prev_session", function(event) {
            select_session(prev_session);
            highlight_session(prev_session);
        });
    } else {
        disable_button("#agenda_prev_session", "#prev_session");
    }
    if(next_session) {
        enable_button("#agenda_next_session", "#next_session", function(event) {
            select_session(next_session);
            highlight_session(next_session);
        });
    } else {
        disable_button("#agenda_next_session", "#next_session");
    }

    $("#agenda_requested_features").html("");
    // fill in list of resources into #agenda_requested_features
    if(session.resources != undefined) {
        $.each(session.resources, function(index) {
            resource = this;

            $("#agenda_requested_features").html(function(inbox, oldhtml) {
                return "<div id=\"resource_"+resource.resource_id+"\"class=\"agenda_requested_feature\">"+
                    "<img height=30 src=\""+
                    resource.icon+"\" title=\""+
                    resource.desc+"\" alt=\""+
                    resource.name+
                    "\" />"+
                    "</div>"+
                    oldhtml
            });

            console.log(session.title, "asks for resource", resource.desc);
        });
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
        var display = { 'conflict':'1' , 'conflic2':'2' , 'conflic3':'3' };
        var group_icons = "";
        var group_set = {};
        $.each(session.conflicts, function(index) {
            conflict = session.conflicts[index];
            conflict.build_othername();
            if(conflict.conflict_groupP()) {
                if ( ! (conflict.othergroup_name in group_set) ) {
                    group_set[conflict.othergroup_name] = {};
                }
                group_set[conflict.othergroup_name][conflict.direction]=display[conflict.conflict_type];
                // This had been in build_group_conflict_view
                conflict.populate_conflict_classes();
                highlight_conflict(conflict);
            }
        });


        $.each(group_set, function(index) {
            group = group_set[index];
            group_view = "<li class='conflict'>";
            group_view += "<div class='conflictlevel'>"
            if ('ours' in group_set[index]) {
                group_view += group_set[index].ours+"->"
            }
            group_view += "</div>"
            group_view += index;
            group_view += "<div class='conflictlevel'>"
            if ('theirs' in group_set[index]) {
                group_view += "->"+group_set[index].theirs
            }
            group_view += "</div>"
            group_view += "</li>";
            group_icons += group_view;
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
    $('#ietf_menubar').toggle('slide',"",100);
    if(menu_bar_hidden){
	menu_bar_hidden = false;
	$('.wrapper').css('width','auto');
	$('.wrapper').css('margin-left','160px');
	$('#close_ietf_menubar').html("<");

    }
    else{
	menu_bar_hidden = true;
	$('.wrapper').css('width','auto');
	$('.wrapper').css('margin-left','0px');
	$('#close_ietf_menubar').html(">");
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


function update_to_slot(session_id, to_slot_id, force){
    //console.log("update_to_slot meeting_id:",session_id, to_slot_id);
    if(to_slot_id == "sortable-list") {
        /* must be bucket list */
        return true;
    }

    var to_timeslot = agenda_globals.timeslot_bydomid[to_slot_id];
    if(to_timeslot != undefined && (to_timeslot.empty == true || force)) {
	// add a new assignment for this, save it.
        var new_ss = make_ss({ "session_id" : session_id,
                               "timeslot_id": to_timeslot.timeslot_id});
        // make_ss also adds to slot_status.
        var save_promise = new_ss.saveit();

        if(to_slot_id != bucketlist_id) {
	    to_timeslot.mark_occupied();
        }

	// update meeting_obj
	agenda_globals.meeting_objs[session_id].placed(to_timeslot, true, new_ss);

	return save_promise;
    } else {
        console.log("update_to_slot failed", to_timeslot, force, "empty", to_timeslot.empty);
        return false;
    }
}

function update_from_slot(session_id, from_slot_id)
{
    var from_timeslot      = agenda_globals.timeslot_bydomid[from_slot_id];

    /* this is a list of schedule-timeslot-session-assignments */
    var from_scheduledslots = agenda_globals.slot_status[from_slot_id];
    var delete_promises = [];

    // it will be null if it's coming from a bucketlist
    if(from_slot_id != null && from_scheduledslots != undefined){
        //console.log("1 from_slot_id", from_slot_id, from_scheduledslots);
        var count = from_scheduledslots.length;
        var found = [];
	for(var k = 0; k<from_scheduledslots.length; k++) {
            var from_ss = from_scheduledslots[k];
	    if(from_ss.session_id == session_id){
                found.push(from_ss)
	    }
	}
        for (var k = 0; k<found.length; k++) {
           // This will affect agenda_globals.slot_status[from_slot_id], hence from_scheduledslots
           delete_promises.push(found[k].deleteit()); 
        }
        if (from_scheduledslots.length==0){
            from_timeslot.mark_empty();
        } 

        /* remove undefined entries */
        new_fromslots = [];
        for(var k =0; k<from_scheduledslots.length; k++) {
            if(from_scheduledslots[k] != undefined && from_scheduledslots[k].session_id != undefined) {
                new_fromslots.push(from_scheduledslots[k]);
            }
        }

        /* any removed sessions will have been done */
        agenda_globals.slot_status[from_slot_id] = new_fromslots;
        //console.log("2 from_slot_id", from_slot_id, new_fromslots);
    }
    else{
        // this may be questionable.
        // It deals with the fact that it's coming from the bucketlist.
        delete_promises = [undefined];
    }
    return delete_promises;
}



function drop_drop(event, ui){

    var session_id = ui.draggable.attr('session_id');   // the session was added as an attribute
    // console.log("UI:", ui, session_id);
    var session    = agenda_globals.meeting_objs[session_id];

    var to_slot_id = $(this).attr('id'); // where we are dragging it.
    var to_slot = agenda_globals.timeslot_bydomid[to_slot_id]

    var from_slot_id = session.slot_status_key;
    var from_slot = agenda_globals.slot_status[session.slot_status_key]; // remember this is an array...

    move_thing({ "session": session,
                 "to_slot_id": to_slot_id,
                 "to_slot":    to_slot,
                 "from_slot_id": from_slot_id,
                 "from_slot":    from_slot,
                 "event":        event,
                 "ui":           ui,
                 "dom_obj":      this});
}

function recalculate_conflicts_for_session(session, old_column_classes, new_column_classes)
{
    // go recalculate things
    session.clear_all_conflicts();

    find_and_populate_conflicts(session);
    session.examine_people_conflicts(old_column_classes);

    var sk;
    for(sk in agenda_globals.meeting_objs) {
        var s = agenda_globals.meeting_objs[sk];

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

var __debug_parameters;
var _LAST_MOVED;
function move_slot(parameters) {
    /* dom_obj: is a jquery selector of where the slot will be appeneded to
       Naming is in regards to that most often function is called from
       drop_drop where 'this' is the dom dest.
    */
    var update_to_slot_worked = false;
    __debug_parameters = parameters;

    if(agenda_globals.__debug_session_move) {
        _LAST_MOVED = parameters.session;
        if(parameters.from_slot != undefined) {
            console.log("from_slot", parameters.from_slot.domid);
        } else {
            console.log("from_slot was unassigned");
        }
    }

    /* if to slot was marked empty, then remove anything in it (like word "empty") */
    if(parameters.to_slot.empty && !parameters.to_slot.unscheduled_box) {
        $(parameters.dom_obj).html("");
    }

    var update_to_slot_worked = false;
    if(parameters.same_timeslot == null){
	parameters.same_timeslot = false;
    }
    var save_promise = undefined;
    if(parameters.bucket_list) {
	save_promise = update_to_slot(parameters.session.session_id,
                                      parameters.to_slot_id, true);
    }
    else{
	save_promise = update_to_slot(parameters.session.session_id,
                                      parameters.to_slot_id, parameters.same_timeslot);
    }

    if(agenda_globals.__debug_session_move) {
        console.log("update_to_slot returned promise", save_promise);
    }

    if(save_promise == false){
	console.log("ERROR updating to_slot", save_promise,
                    parameters.to_slot_id,
                    agenda_globals.slot_status[parameters.to_slot_id]);
	return undefined;
    }

    var delete_promises = update_from_slot(parameters.session.session_id, parameters.from_slot_id);
    if(delete_promises.length > 0) {
	remove_duplicate(parameters.from_slot_id, parameters.session.session_id);
	// do something else?
    }
    else {
	console.log("WARNING -- nothing to delete when updating from_slot", parameters.from_slot_id, agenda_globals.slot_status[parameters.from_slot_id]);
	//return;
    }
    parameters.session.slot_status_key = parameters.to_slot_id;

    var eTemplate = parameters.session.event_template()
    $(parameters.dom_obj).append(eTemplate);

    if(parameters.ui) {
        parameters.ui.draggable.remove();
    }

    /* recalculate all the conflict classes given new slot */
    parameters.session.update_column_classes([parameters.to_slot],
                                             parameters.bucket_list);

    /* set colours */
    $(parameters.dom_obj).removeClass('highlight_free_slot');
    if(parameters.to_slot.empty) {
	$(parameters.dom_obj).removeClass('free_slot')
    }
    else{
	$(parameters.dom_obj).addClass('free_slot')
    }

    if(parameters.from_slot != undefined && parameters.from_slot.empty){
	$("#"+parameters.from_slot_id).removeClass('free_slot');
    }
    else{
	$("#"+parameters.from_slot_id).addClass('free_slot');
    }
    $("#"+bucketlist_id).removeClass('free_slot');
    /******************************************************/

    droppable();
    listeners();
    sort_unassigned();

    delete_promises.push(save_promise);
    return $.when.apply($,delete_promises);
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
