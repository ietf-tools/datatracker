var lastfrag;

function setGroupState()
{
    var frag = window.location.hash.replace("#",'');
    window.setTimeout("setGroupState()",1000);
    if (frag == lastfrag) { return; }

    var weekview = document.getElementById('weekview');
    var ical_link = document.getElementById('ical-link');
    var ical_href = document.getElementById('ical-href');


    lastfrag = frag;

    var fragment = frag.split(',');

    if (frag.length)
    {
        weekview.setAttribute("src","week-view.html#"+frag);
        weekview.className = '';
        ical_url = ical_href.getAttribute("href").split("?")[0];
        ical_href.setAttribute("href",ical_url+"?"+frag);
        ical_link.className = '';
    }
    else
    {
        weekview.className = 'hidden';
        ical_link.className = 'hidden';
    }

    var selectors = document.getElementsByTagName('div');
    var re = RegExp("^selector-");
    var re2 = RegExp("^selector-(" + fragment.join('|') + ")$");

    for (var i=0 ; i<selectors.length; i++)
    {
        if (re.test(selectors[i].id))
        {
            var wg = selectors[i].textContent?selectors[i].textContent:selectors[i].text;
            var area_groups = document.getElementById(wg + "-groups");
            if (re2.test(selectors[i].id))
            {
                selectors[i].className="selected";
                if (area_groups)
                {
                    area_groups.className = 'inactive';
                }
            }
            else
            {
                selectors[i].className="unselected";
                if (area_groups)
                {
                    area_groups.className = '';
                }
            }
        }
    }
    var rows = document.getElementsByTagName('tr');
    var hidenone = false;
    if (frag.length == 0) { hidenone=true; }

    var re = RegExp("-(" + fragment.join('|') + ")($|-)");

    for (var i = 0; i < rows.length; i++)
    {
        if (rows[i].className == 'groupagenda' || rows[i].className == 'grouprow')
        {
            if (re.test(rows[i].id) || (hidenone && rows[i].className == 'grouprow'))
            {
                rows[i].style.display="table-row";
                if (rows[i].className == 'groupagenda')
                {
                    var iframe = rows[i].firstElementChild.nextElementSibling.firstElementChild;
                    if (iframe.getAttribute("xsrc") != iframe.getAttribute("src"))
                    {
                        iframe.setAttribute("src",iframe.getAttribute("xsrc"));
                    }
                }
            }
            else
            {
                rows[i].style.display="none";
            }
        }
    }

    // Handle special cases (checkboxes)
    var special = ['edu','ietf','tools','iesg','iab'];
    var re3 = RegExp("^(" + fragment.join('|') + ")$");
    for (i in special)
    {
        var include = document.getElementById("include-"+special[i]);
        include.checked = ! re3.test("\-"+special[i]);
    }
}

/* Resizes an IFRAME to fit its contents. */
function r(iframe)
{
    try
    {
        iframe.height = 1;
        iframe.style.border = "solid";
        iframe.style.borderWidth = "1px";
        iframe.style.margin = "0";
        iframe.style.padding = "10px";
        iframe.style.overflow = "auto";
        docHeight = iframe.contentWindow.document.body.scrollHeight;
        iframe.height = docHeight;
    }
    catch (e) { return; }

    /* The following code works really well UNLESS some crazy chair
       decides to submit a text agenda that is, say, 500 columns wide.
       But this tends to happen. So, until I find a way to stop
       that brand of crazy from breaking the world, I'm disabling
       this code. Too bad, really -- it made the page much nicer to
       use. */
    return;

    if (iframe.contentWindow.document.body.innerHTML)
    {
        var div = document.createElement("div");
        div.style.border = "solid";
        div.style.borderWidth = "1px";
        div.style.margin = "0";
        div.style.padding = "10px";
        div.style.overflow = "auto";
        div.innerHTML=iframe.contentWindow.document.body.innerHTML;
        iframe.parentNode.replaceChild(div,iframe);
    }
}

function add_hash_item(item)
{
    if (window.location.hash.replace("#","").length == 0)
    {
        window.location.hash = item;
    }
    else
    {
        window.location.hash += "," + item;
    }
    window.location.hash = window.location.hash.replace(/^#?,/,'');
}

function remove_hash_item(item)
{
    var re = new RegExp('(^|#|,)' + item + "(,|$)");
    window.location.hash = window.location.hash.replace(re,"$2")
    window.location.hash = window.location.hash.replace(/^#?,/,'');
}

function toggle(selection)
{
    var active = selection.className;
    var wg = selection.textContent?selection.textContent:selection.text;

    if (active == "selected")
    {
        remove_hash_item(wg);
    }
    else
    {
        add_hash_item(wg);
    }
    setGroupState();
}

function toggle_special(checkbox)
{
    var special = checkbox.id.replace('include-','');
    if (checkbox.checked)
    {
        remove_hash_item("-"+special);
    }
    else
    {
        add_hash_item("-"+special);
    }
}

function toggle_wg_selector ()
{
    var wg_selector = document.getElementById('wg-selector');
    var triangle_right = document.getElementById('wg-selector-triangle-right');
    var triangle_down = document.getElementById('wg-selector-triangle-down');
    if (wg_selector.className == 'hidden')
    {
        wg_selector.className = '';
        triangle_right.className = 'hidden';
        triangle_down.className = '';
    }
    else
    {
        wg_selector.className = 'hidden';
        triangle_right.className = '';
        triangle_down.className = 'hidden';
    }
    setGroupState();
}
