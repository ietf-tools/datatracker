jQuery(function($) {
    $(document).ready(
        function() {
	    $("#displayinbrowsertime")
		 .removeAttr("disabled")
		 .val("Display in Browser time");
	 
	 });
    $("#displayinbrowsertime").click(
	function() {
	    var datere = new RegExp("^\\s*(\\w\\w\\w) (\\d\\d)");
	    var timere = new RegExp("(\\d\\d)(\\d\\d)-(\\d\\d)(\\d\\d)");
	    var months = { "Jan": 0, "Feb": 1, "Mar": 2, "Apr": 3, "May": 4, "Jun": 5, "Jul": 6, "Aug": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11 };

	    var twod = function(n) {
		return (n < 10 ? "0" : "") + n;
	    };

	    var timehhmm = function(d) {
		return twod(d.getHours()) + twod(d.getMinutes());
	    };

	    var tzshhmm = function(d) {
		var tzo = -d.getTimezoneOffset();
		var s = "+";
		if (tzo < 0) {
		    s = "\u2013"; // en dash
		    tzo = - tzo;
		}
		return s + twod(~~(tzo / 60)) + twod(tzo % 60);
	    };

	    // to fill in the blank left from the text (will be wrong a year after the event):
	    var thisyear = (new Date).getFullYear();
	    $(".timecolumn").each (
		function() {
		    var deco = $(this).find(".ietf-tiny"); // brittle...
		    if (deco[1].innerHTML == "UTC") {      // i.e., we haven't done this already
			var mdday = datere.exec(deco.html());
			var mdfine = timere.exec($(this).html());
			if (mdday && mdfine) {
			    var month = mdday[1];
			    var daystr = mdday[2]
			    var date1 = new Date(Date.UTC(thisyear, months[month], +daystr,
							  +mdfine[1], +mdfine[2], 0, 0));
			    var time1 = timehhmm(date1);
			    var date2 = new Date(Date.UTC(thisyear, months[month], +daystr,
							  +mdfine[3], +mdfine[4], 0, 0));
			    var time2 = timehhmm(date2);

			    deco[0].innerHTML = date1.toString().slice(4,11) + "&nbsp"; // month, day
			    deco[1].innerHTML = tzshhmm(date1);
			    // outerHTML replacement that is portable back to Firefox < 11
			    var d0 = $(deco[0]).clone().wrap('<div>').parent().html();
			    var d1 = $(deco[1]).clone().wrap('<div>').parent().html();
			    $(this).html(d0 + time1 + "\u2013" + time2 + " " + d1);
			};
		    };

		});
	    $("#displayinbrowsertime")
		.attr("disabled", "disabled") // FIX THIS to true for jQuery 1.6+
		.val("Shown in Browser time");
	}
    );
});
