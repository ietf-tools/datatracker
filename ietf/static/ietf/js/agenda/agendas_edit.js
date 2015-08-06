/*
*   agendas_edit.js
*
* Copyright (c) 2013, The IETF Trust. See ../../../LICENSE.
*
*   www.credil.org: Project Orlando 2013 
*   Author: Justin Hornosty ( justin@credil.org )
*           Michael Richardson <mcr@sandelman.ca>
*
*   This file should contain functions relating to
*   editing a list of agendas
*
*/




//////////////-GLOBALS----////////////////////////////////////////


/////////////-END-GLOBALS-///////////////////////////////////////

$(document).ready(function() {
    init_agendas_edit();

    /* hide the side bar by default. */
    $("#close_ietf_menubar").click();
});

/*
   init_timeslot_editf()
   This is ran at page load and sets up appropriate listeners
*/
function init_agendas_edit(){
    log("initstuff() ran");
    static_listeners();

    $(".agenda_delete").unbind('click');
    $(".agenda_delete").click(delete_agenda);

    $(".agenda_official_mark").unbind('click');
    $(".agenda_official_mark").click(toggle_official);
}

function toggle_official(event) {
    var agenda_line   = $(event.target).closest('tr');
    var agenda_url    = agenda_line.attr('href');
    var agenda_name   = agenda_line.attr('agenda_name');
    var agenda_id     = agenda_line.attr('id');
    var meeting_url   = $(".agenda_list_title").attr('href');
    event.preventDefault();

    /*
     * if any of them are clicked, then go through all of them
     * and set them to "unofficial", then based upon the return
     * we might this one to official.
     */

    /* if agenda_official is > 1, then it is enabled */
    var value = 0;
    if($(event.target).html() == "official") {
        value = 1;
    }
    var new_value = agenda_name;
    var new_official = 1;
    if(value > 0) {
        new_value    = "None";
        new_official = 0;
    }


    if(new_official == 1) {
        // see if this item is public, fail otherwise.
        var agenda_public_span = agenda_line.find('.agenda_public').html();
        // console.log("public_span", agenda_public_span);
        if (agenda_public_span == "private") {
            $("#agenda_notpublic_dialog").dialog();
            return;
        }
    }


    var rows = $(".agenda_list tr:gt(0)");
    rows.each(function(index) {
                  log("row: "+this);
		  /* this is now the tr */
		  $(this).removeClass("agenda_official_row");
		  $(this).addClass("agenda_unofficial_row");

		  /* not DRY, this occurs deep in the model too */
		  $(this).find(".agenda_official_mark").html("unofficial");
	      });

    log("clicked on "+agenda_url+" sending to "+meeting_url);

    $.ajax({ "url": meeting_url,
             "type": "POST",
             "data": { "agenda" : new_value },
             "dataType": "json",
             "success": function(result) {
                 /* result is a json object, which has the agenda_href to mark official */
                 var agenda_href = result.agenda_href;

                 var rows = $(".agenda_list tr:gt(0)");
                 rows.each(function(index) {
                     var my_href = $(this).attr('href')
		     /* this is now the tr */

                     if(agenda_href == my_href) {
                         $(this).find(".agenda_official_mark").html("official");
                         $(this).addClass("agenda_official_row");
                     }
                 });
             }});
}


/*
 * Local Variables:
 * c-basic-offset:4
 * End:
 */

