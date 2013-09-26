
// cookie functions used with permission from http://www.elated.com/articles/javascript-and-cookies/
function set_cookie ( name, value, exp_y, exp_m, exp_d, path, domain, secure )
{
    var cookie_string = name + "=" + escape ( value );

    if ( exp_y ) {
	var expires = new Date ( exp_y, exp_m, exp_d );
	cookie_string += "; expires=" + expires.toGMTString();
    }

    if ( path )
        cookie_string += "; path=" + escape ( path );

    if ( domain )
        cookie_string += "; domain=" + escape ( domain );
  
    if ( secure )
        cookie_string += "; secure";
  
    document.cookie = cookie_string;
}
function delete_cookie ( cookie_name )
{
    var cookie_date = new Date ( );  // current date & time
    cookie_date.setTime ( cookie_date.getTime() - 1 );
    document.cookie = cookie_name += "=; expires=" + cookie_date.toGMTString();
}
function get_cookie ( cookie_name )
{
    var results = document.cookie.match ( '(^|;) ?' + cookie_name + '=([^;]*)(;|$)' );

    if ( results )
	return ( unescape ( results[2] ) );
    else
	return null;
}

// set the color of a row to the proper class. optionally set the corresponding cookie.
function setcolor(id, color, skip_cookie)
{
    oneSecond = 1000;
    oneMinute = 60*oneSecond;
    oneHour   = 60*oneMinute;
    oneDay    = 24*oneHour;
    oneWeek   = 7*oneDay;
    oneMonth  = 31*oneDay;
		
    var now = new Date();
    var exp = new Date(now.getTime() + 3*oneMonth);

    var e = $(id);
    if (e) e.className = "bg" + color;
    //if (!skip_cookie) set_cookie(id, color, 2009, 8, 1);
    if (!skip_cookie) set_cookie(id, color, exp.getFullYear(), exp.getMonth(), exp.getDate(),"", ".ietf.org");
}

// return a list of all cookie name/value pairs
function get_cookie_list()
{
    var cookie = document.cookie;
    var cookies = cookie.split(';');
    var cookie_list = [];
    for (var i = 0; i < cookies.length; i++) {
	var cookie_match = cookies[i].match('(^|;) *([^=]*)=([^;]*)(;|$)');
	if (cookie_match) {
	    cookie_list.push(cookie_match[2]);
	    cookie_list.push(cookie_match[3]);
	    // alert("cookie: '" + cookie_match[2] + "'='" + cookie_match[3] + "'");
	}
    }
    return cookie_list;
}

// run through all cookies and set the colors of each row
function set_cookie_colors()
{
    var cl = get_cookie_list();
    for (var i = 0; i < cl.length; i += 2) {
        setcolor(cl[i], cl[i+1], true);
    }
    Element.hide('colorpallet');
}

// the current color being picked by the popup
var curid;

// pop up the pallet to let a color be picked
function pickcolor(id)
{
    curid = id;
    var colorpallet = $('colorpallet');
    if (colorpallet) {
        Element.show(colorpallet);
	Element.absolutize(colorpallet);
	Element.clonePosition(colorpallet, "p-" + id);
    }
}

// called by the pallet popup to set the current color
function setcurcolor(color)
{
    setcolor(curid, color);
    var colorpallet = $('colorpallet');
    if (colorpallet) {
	Element.hide(colorpallet);
    }
}

// open up a new window showing the given room
function venue(room)
{
    window.open('venue/?room=' + room, 'IETF meeting rooms',
	'scrollbars=no,toolbar=no,width=621,height=560');
    return false;
}

