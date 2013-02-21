/* utils.js - utility functions */


//returns the requested GET parameter from the URL
function get_param(param) {
    var regex = '[?&]' + param + '=([^&#]*)';
    var results = (new RegExp(regex)).exec(window.location.href);
    if(results) return results[1];
    return '';
}

function restripe(id) {
      $(id + ' tbody tr:visible:even').removeClass('row1 row2').addClass('row1');
      $(id + ' tbody tr:visible:odd').removeClass('row1 row2').addClass('row2');
}

function init_area_table() {
  // add "Show All" button
  $("#areas-button-list").append('<li><button type="button" id="areas-list-toggle" value="Show All">Show All</button></li>');
  // register button
  $("#areas-list-toggle").click(function() {
      if (this.value == "Show All") {
          $('#areas-list-table tbody tr:not(.active)').show();
          $(this).val("Show Active");
          $(this).text("Show Active");
      } else if (this.value == "Show Active") {
          $('#areas-list-table tbody tr:not(.active)').hide();
          $(this).val("Show All");
          $(this).text("Show All");
      }
      // restripe the table
      restripe('#areas-list-table');
  });
  // hide non-active areas
  $('#areas-list-table tbody tr:not(.active)').hide();
  restripe('#areas-list-table');
}

function style_current_tab() {
    path_array = window.location.pathname.split('/');
    page = path_array[path_array.length-2];
    id = "#nav-" + page;
    $(id + ' a').addClass('current');
}


/*********************************
/*Functions : For Proceedings    */
/*********************************/
function change_material_type(obj) {
    if (obj.value == "Agenda") {
        alert('agenda');
    }
}

function init_proceedings_upload() {
  // dynamic help message
  $('#id_material_type').change(function() {
    if(this.value == "slides") {
      //alert('Presentation handler called');
      $('div#id_file_help').html("Note 1: You can only upload a presentation file in txt, pdf, doc, or ppt/pptx. System will not accept presentation files in any other format.<br><br>Note 2: All uploaded files will be available to the public immediately on the Preliminary Page. However, for the Proceedings, ppt/pptx files will be converted to html format and doc files will be converted to pdf format manually by the Secretariat staff.");
      $('#id_slide_name').attr('disabled', false);
    }
    if(this.value == "minutes") {
      //alert('Minutes handler called');
      $('div#id_file_help').html("Note: You can only upload minutes in txt/html/ppt/pdf formats. System will not accept minutes in any other format.");
      $('#id_slide_name').attr('disabled', true);
      $('#id_slide_name').val('');
    }
    if(this.value == "agenda") {
      //alert('Agenda handler called');
      $('div#id_file_help').html("Note: You can only upload agendas in txt/html/ppt/pdf formats. System will not accept agendas in any other format.");
      $('#id_slide_name').attr('disabled', true);
      $('#id_slide_name').val('');
    }
  });

  // handle slide sorting
  $('#slides.sortable tbody').sortable({
     axis:'y',
     containment:'parent',
     update: function(event, ui){  
         var data = $(this).sortable("toArray");
         var element_id = ui.item.attr("id");
         var slide_name = $("tr#"+element_id+" td.hidden").text();
         var order = $.inArray(element_id,data);
         $.post('/secr/proceedings/ajax/order-slide/',{'slide_name':slide_name,'order':order});
         // restripe the table
        restripe('#slides.sortable');
     }
  }).disableSelection();
}

function init_proceedings_table() {
  // do only if table with secretariat class exists
  if ($('table.secretariat').length) {
    // add "Show All" button
    $("#proceedings-meeting-buttons").append('<li><button type="button" id="proceedings-list-toggle" value="Show All">Show All</button></li>');
    // register button
    $("#proceedings-list-toggle").click(function() {
	if (this.value == "Show All") {
	    $('#proceedings-list-table tbody tr:not(.open)').show();
	    $(this).val("Show Active");
	    $(this).text("Show Active");
	} else if (this.value == "Show Active") {
	    $('#proceedings-list-table tbody tr:not(.open)').hide();
	    $(this).val("Show All");
	    $(this).text("Show All");
	}
	// restripe the table
	restripe('#proceedings-list-table');
    });
    // hide non-active areas
    $('#proceedings-list-table tbody tr:not(.open)').hide();
    restripe('#proceedings-list-table');
  }
}

$(document).ready(function() {
  // in general set focus on first input field
  $("input:text:visible:enabled:first").focus();

  // custom focus settings --------------------------------
  if ( $("form[id^=group-role-assignment-form]").length > 0){
      $("#id_role_type").focus();
  }
  if ( $("form[id=draft-search-form]").length > 0){
      $("#id_filename").focus();
  }
  if ( $("form[id=drafts-add-form]").length > 0){
      $("#id_title").focus();
  }
  if ( $("form[id=proceedings-add-form]").length > 0){
      $("#id_start_date").focus();
  }
  if ( $("form[id=proceedings-upload-form]").length > 0){
      $("#id_group_name").focus();
  }
  if ( $("form[id=session-request-form]").length > 0){
      $("#id_num_session").focus();
  }
  if ( $("form[id^=meetings-meta]").length > 0){
      $("button[type=submit]:first").focus();
  }
  if ( $("form[id=meetings-schedule-form]").length > 0){
      $("#id_form-0-time").focus();
  }


  // unset Primary Area selection unless it appears as URL parameter 
  //if (($('#id_primary_area').length) && (get_param('primary_area') == '')) {
  //    $('#id_primary_area')[0].selectedIndex = -1;

  // special features for area list page
  if ($('#areas-button-list').length) {
      init_area_table();
  }
  // Setup autocomplete for adding names 
  if ($('input.name-autocomplete').length) {
      $('input.name-autocomplete').autocomplete({
          source: "/secr/areas/getpeople/",
          minLength: 3,
          select: function(event, ui) {
              //match number inside paren and then strip paren
              id = ui.item.label.match(/\(\d+\)/);
              val = id[0].replace(/[\(\)]/g, "");
              //alert(id,val);
              //alert(id.match(/\d+/));
              $.getJSON('/secr/areas/getemails/',{"id":val},function(data) {
                  $('#id_email option').remove();
                  $.each(data,function(i,item) {
                      $('#id_email').append('<option value="'+item.id+'">'+item.value+'</option>');
                  });
              });
          }
      });
  }

  // nav bar setup
  if ($('ul#list-nav').length) {
      style_current_tab();
  }

  // auto populate Area Director List when primary area selected (add form)
  $('#id_primary_area').change(function(){
      $.getJSON('/secr/groups/get_ads/',{"area":$(this).val()},function(data) {
          $('#id_primary_area_director option').remove();
          $.each(data,function(i,item) {
              $('#id_primary_area_director').append('<option value="'+item.id+'">'+item.value+'</option>');
          });
      });
  });

  // auto populate Area Director List when area selected (edit form)
  $('#id_ietfwg-0-primary_area').change(function(){
      $.getJSON('/secr/groups/get_ads/',{"area":$(this).val()},function(data) {
          $('#id_ietfwg-0-area_director option').remove();
          $.each(data,function(i,item) {
              $('#id_ietfwg-0-area_director').append('<option value="'+item.id+'">'+item.value+'</option>');
          });
      });
  });

  // special features for Proceedings list page
  if ($('#proceedings-button-list').length) {
      init_proceedings_table();
  }

  // special features for Proceedings Upload Material Page 
  if ($('#proceedings-upload-table').length) {
      init_proceedings_upload();
  }

});
