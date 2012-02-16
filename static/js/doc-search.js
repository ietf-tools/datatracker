$(function () {
    var form = jQuery("#search_form");

    form.find(".search_field input[name=by]").parents("label").click(changeBy);

    form.find(".search_field").find("input,select")
        .change(toggleSubmit).click(toggleSubmit).keyup(toggleSubmit);

    form.find(".toggle_advanced").click(function () {
        togglePlusMinus("search_advanced");
        form.find('.search_field input[type="radio"]').attr("checked", false);
        changeBy();
    });

    changeBy();

    // we want to disable our submit button if we have no search text, 
    // and we have no advanced options selected
    function toggleSubmit() {
        var button = document.getElementById("id_search_submit");
        var by = findCheckedSearchBy();
        var value = findSearchByValue(by);
        var text = document.getElementById("id_name");
        if ((value == "") && (text.value == "")) {
            button.disabled = true;
        } else {
            button.disabled = false;
        }
    }

    function togglePlusMinus(id) {
        var el = document.getElementById(id);
        var imgEl = document.getElementById(id+"-img");
        if (el.style.display == 'none') { 
            el.style.display = 'block'; 
            imgEl.src = "/images/minus.png";
        } else { 
            el.style.display = 'none'; 
            imgEl.src = "/images/plus.png";
        }
    }

    function findCheckedSearchBy() {
        var by=''; 
        var f = document.search_form;
        for (var i = 0; i < f.by.length; i++) {
            if (f.by[i].checked) { 
                by = f.by[i].value; 
                break; 
            }
        }
        return by;
    }

    function findSearchByValue(by) {
        if (by == 'author') { return document.getElementById("id_author").value; }
        if (by == 'group') { return document.getElementById("id_group").value; }
        if (by == 'area') { return document.getElementById("id_area").value; }
        if (by == 'ad') { return document.getElementById("id_ad").value; }
        if (by == 'state') { 
            // state might be state...
            state_value = document.getElementById("id_state").value;
            if (state_value) { return state_value; }
            // ...or sub-state
            return document.getElementById("id_subState").value;
        }
        return '';
    }

    function changeBy() {
        var by = findCheckedSearchBy();
        var f = document.search_form;
        f.author.disabled=true;  
        f.group.disabled=true;
        f.area.disabled=true;
        f.ad.disabled=true;
        f.state.disabled=true; f.subState.disabled=true;
        if (by=='author') { f.author.disabled=false;}
        if (by=='group') { f.group.disabled=false;}
        if (by=='area') { f.area.disabled=false;}
        if (by=='ad') { f.ad.disabled=false; }
        if (by=='state') { f.state.disabled=false; f.subState.disabled=false; }

        toggleSubmit();
    }
});
