
function toggle_visibility() {
   var h = window.location.hash;
   h = h.replace(/^#?,?/, '');

   // reset UI elements to default state
   $(".pickview").removeClass("active disabled");
   $(".pickviewneg").addClass("active");

   if (h) {
       // if there are items in the hash, hide all rows
       $('[id^="row-"]').hide();

       // show the customizer
       $("#customize").collapse("show");

       // loop through the has items and change the UI element and row visibilities accordingly
       var query_array = [];
       $.each(h.split(","), function (i, v) {
           if (v.indexOf("-") == 0) {
               // this is a "negative" item: when present, hide these rows
               v = v.replace(/^-/, '');
               $('[id^="row-"]').filter('[id*="-' + v + '"]').hide();
               $(".view." + v).find("button").removeClass("active disabled");
               $("button.pickviewneg." + v).removeClass("active");
           } else {
               // this is a regular item: when present, show these rows
               $('[id^="row-"]').filter('[id*="-' + v + '"]').show();
               $(".view." + v).find("button").addClass("active disabled");
               $("button.pickview." + v).addClass("active");
               query_array.push("filters=" + v)
           }
       });

       // adjust the custom .ics link
       var link = $('a[href*="upcoming.ics"]');
       var new_href = link.attr("href").split("?")[0]+"?"+query_array.join("&");
       link.attr("href",new_href);
       
   } else {
       // if the hash is empty, show all
       $('[id^="row-"]').show();
       // adjust the custom .ics link
       var link = $('a[href*="upcoming.ics"]');
       link.attr("href",link.attr("href").split("?")[0]);
   }
}

$(".pickview, .pickviewneg").click(function () {
   var h = window.location.hash;
   var item = $(this).text().trim().toLowerCase();
   if ($(this).hasClass("pickviewneg")) {
       item = "-" + item;
   }

   re = new RegExp('(^|#|,)' + item + "(,|$)");
   if (h.match(re) == null) {
       if (h.replace("#", "").length == 0) {
           h = item;
       } else {
           h += "," + item;
       }
       h = h.replace(/^#?,/, '');
   } else {
       h = h.replace(re, "$2").replace(/^#?,/, '');
   }
   window.location.hash = h.replace(/^#$/, '');
   toggle_visibility();
});

$(document).ready(function () {
   toggle_visibility();
});

