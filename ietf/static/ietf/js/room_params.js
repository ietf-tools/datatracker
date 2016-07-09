var verbose = 0;

function suffixmap(nm)
// Given a name like "foo-ab" or "foo-X-and-Y", change it to the "list-of-room-names" format, "foo-a/foo-b".
{
    var andsuffix = /^(.*-)([^-]+)-and-(.*)$/;
    var andMatch = andsuffix.exec(nm);
    if (andMatch && andMatch[0] != '') {
	nm = andMatch[1] + andMatch[2] + "-" + andMatch[3];
    }
    // xyz-a/b/c => xyz-a/xyz-b/xyz-c
    var abcsuffix = /^(.*)-([a-h0-9]+)[-\/]([a-h0-9]+)([-\/][a-h0-9]+)?$/;
    var suffixMatch = abcsuffix.exec(nm);
    if (verbose) alert("nm=" + nm);
    if (suffixMatch && suffixMatch[0] != '') {
	if (verbose) alert("matched");
	nm = suffixMatch[1] + "-" + suffixMatch[2] + "/" +
	     suffixMatch[1] + "-" + suffixMatch[3];
	if (verbose) alert("nm=>" + nm);
	if (suffixMatch[4] && suffixMatch[4] != '')
	     nm += "/" + suffixMatch[1] + "-" + suffixMatch[4];
	if (verbose) alert("nm=>" + nm);
    }
    // xyz-abc => xyz-a/xyz-b/xyz-c
    abcsuffix = /^(.*)-([a-h])([a-h]+)([a-h])?$/;
    var suffixMatch = abcsuffix.exec(nm);
    if (suffixMatch && suffixMatch[0] != '') {
	nm = suffixMatch[1] + "-" + suffixMatch[2] + "/" +
	     suffixMatch[1] + "-" + suffixMatch[3];
	if (suffixMatch[4] && suffixMatch[4] != '')
	     nm += "/" + suffixMatch[1] + "-" + suffixMatch[4];
    }
    if (verbose) alert("suffixmap returning: " + nm);
    return nm;
}

function roomcoords(nm)
// Find the coordinates of a room or list of room names separated by "/".
// Calls the function findroom() to get the coordinates for a specific room.
{
    if (!nm) return null;

    if (nm.match("/")) {
        var nms = nm.split("/");
	var nm0 = findroom(nms[0]);
	if (!nm0) return null;
	for (var i = 1; i < nms.length; i++) {
	    var nmi = roomcoords(nms[i]);
	    if (!nmi) return null;
	    if (nmi[0] < nm0[0]) nm0[0] = nmi[0];
	    if (nmi[1] < nm0[1]) nm0[1] = nmi[1];
	    if (nmi[2] > nm0[2]) nm0[2] = nmi[2];
	    if (nmi[3] > nm0[3]) nm0[3] = nmi[3];
	}
	return [nm0[0], nm0[1], nm0[2], nm0[3], nm0[4], nm0[5]];
    } else {
	return findroom(nm);
    }
}

function setarrow(nm)
// Place an arrow at the center of a given room name (or list of room names separated by "/").
{
    for (var i = 0; i < arguments.length; i+=2) {
       nm = roommap(arguments[i]);
       if (verbose) alert("nm=" + nm);
       var rooms = nm.split(/[|]/);
       for (var j = 0; j < rooms.length; j++) {
	  var room = rooms[j];
	  var ret = roomcoords(room);
	  if (verbose) alert("roomcoords returned: " + ret);
	  if (!ret) continue;

	  var left = ret[0], top = ret[1], right = ret[2], bottom = ret[3], floor=ret[4], width=ret[5], offsetleft = -25, offsettop = -25;
	  if (verbose) alert("left=" + left + ", top=" + top + ", right=" + right + ", bottom=" + bottom + ", floor=" + floor + ", width=" + width);
	  //alert("left=" + left + ", top=" + top + ", right=" + right + ", bottom=" + bottom);
	  // calculate arrow position
	  for (var i = 0; i < arrowsuffixlist.length; i++) {
	      removearrow(arrowsuffixlist[i], floor);
	  }
	  arrow_left = (left + (right - left) / 2 );
	  arrow_top  = (top + (bottom - top) / 2 );
	  // scale the coordinates to match image scaling
	  var img = document.getElementById(floor+"-image");
	  scale = img.width / width;
	  arrow_left = arrow_left * scale;
	  arrow_top  = arrow_top  * scale;
	  var arrowdiv = floor+'-arrowdiv'+j;
	  //if (verbose) alert("arrowdiv: " + arrowdiv);
	  var adiv = document.getElementById(arrowdiv);
	  if (adiv) {
	      adiv.style.left = arrow_left + offsetleft + "px";
	      adiv.style.top  = arrow_top + offsettop + "px";
	      adiv.style.visibility = "visible";
	  }
      }
   }
}

function removearrow(which, fl)
{
    for (var i = 0; i < arguments.length; i++) {
       var which = arguments[i];
       var arrowdiv = fl+'-arrowdiv' + (which ? which : "");
       var adiv = document.getElementById(arrowdiv);
       // if (verbose) alert("looking for '" + arrowdiv + "'");
       if (adiv) {
	   // if (verbose) alert("adiv found");
	   adiv.style.left = -500;
	   adiv.style.top = -500;
	   adiv.style.visibility = "hidden";
       }
   }
}

function setarrowlist(which, names)
{
   for (var i = 1; i < arguments.length; i++) {
      setarrow(arguments[i], which);
   }
}

function QueryString()
// Create a QueryString object
{
    // get the query string, ignore the ? at the front.
    var querystring = location.search.substring(1);

    // parse out name/value pairs separated via &
    var args = querystring.split('&');

    // split out each name = value pair
    for (var i = 0; i < args.length; i++) {
        var pair = args[i].split('=');

        // Fix broken unescaping
        var temp = unescape(pair[0]).split('+');
        var name_ = temp.join(' ');

        var value_ = '';
        if (typeof pair[1] == 'string') {
            temp = unescape(pair[1]).split('+');
            value_ = temp.join(' ');
        }

        this[name_] = value_;
    }

    this.get = function(nm, def) {
        var value_ = this[nm];
        if (value_ == null) return def;
        else return value_;
    };
}

function checkParams()
// Check the parameters for one named "room". If found, call setarrow(room).
{
    var querystring = new QueryString();
    var room = querystring.get("room");
    if (room && room != "") setarrow(room);
}

// new functions
function located(loc)
{
   if (loc.civic && loc.civic.ROOM) {
      // map from "TerminalRoom" to "terminal-room" as necessary.
      setarrow(loc.civic.ROOM.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase(), "-green");
   }
}

// this needs to be called onload
function automaticarrow()
{
    //   if (navigator.geolocation) {
    //      navigator.geolocation.getCurrentPosition(located);
    //   }
}
