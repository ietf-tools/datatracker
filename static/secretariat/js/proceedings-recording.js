/* proceedings-recordings.js - utility functions */


$(document).ready(function() {
  // auto populate Session select list
  $('#id_group').blur(function(){
      var loadUrl = "/secr/proceedings/ajax/get-sessions/";
      var url = window.location.pathname;
      var parts = url.split("/");
      var acronym = $(this).val();
      loadUrl = loadUrl+parts[3]+"/"+acronym+"/";
      $('.errorlist').remove();
      $.getJSON(loadUrl,function(data) {
          $('#id_session').find('option').remove();
          if (data.length == 0) {
              $( '<ul class="errorlist"><li>No sessions found</li></ul>' ).insertBefore( "#id_group" );
          } else {
              $.each(data,function(i,item) {
                  $('#id_session').append('<option value="'+item.id+'">'+item.value+'</option>');
              });
          }
      });
  });
});
