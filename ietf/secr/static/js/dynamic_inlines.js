/* Following functions based off code written by Arne Brodowski
http://www.arnebrodowski.de/blog/507-Add-and-remove-Django-Admin-Inlines-with-JavaScript.html

2012-02-01 customized for new Rolodex.  Email formset doesn't have an id field, rather a "address"
field as primary key.  Also for some reason the "active" boolean field doesn't get saved properly
if the checkbox input has an empty "value" argument.
*/
import $ from 'jquery';

function increment_form_ids(el, to, name) {
    var from = to-1
    $(':input', $(el)).each(function(i,e){
        var old_name = $(e).attr('name')
        var old_id = $(e).attr('id')
        $(e).attr('name', old_name.replace(from, to))
        $(e).attr('id', old_id.replace(from, to))
        if ($(e).attr('type') != 'checkbox') {
           $(e).val('')
        }
    })
}

function add_inline_form(name) {
    if (name=="email") {
        var first = $('#id_'+name+'-0-address').parents('.inline-related')
    }
    else {
        var first = $('#id_'+name+'-0-id').parents('.inline-related')
    }
    // check to see if this is a stacked or tabular inline
    if (first.hasClass("tabular")) {
        var field_table = first.parent().find('table > tbody')
        const children = field_table.children('tr.dynamic-inline')
        var count = children.length
        const last = $(children[count-1])
        var copy = last.clone(true)
        copy.removeClass("row1 row2")
        copy.find("input[name$='address']").attr("readonly", false)
        copy.addClass("row"+((count % 2) ? 2 : 1))
        copy.insertAfter(last)
        increment_form_ids($(copy), count, name)
    }
    else {
        var last = $(first).parent().children('.last-related')
        var copy = $(last).clone(true)
        var count = $(first).parent().children('.inline-related').length
        $(last).removeClass('last-related')
        var header = $('h3', copy)
        header.html(header.html().replace("#"+count, "#"+(count+1)))
        $(last).after(copy)
        increment_form_ids($(first).parents('.inline-group').children('.last-related'), count, name)
    }
    $('input#id_'+name+'-TOTAL_FORMS').val(count+1)
    return false;
}

// Add all the "Add Another" links to the bottom of each inline group
$(function() {
    var html_template = '<ul class="tools">'+
        '<li>'+
            '<a id="addlink-{{prefix}}" class="addlink" href="#">'+
            'Add another</a>'+
        '</li>'+
    '</ul>'
    $('.inline-group').each(function(i) {
        //prefix is in the name of the input fields before the "-"
        var prefix = $("input[type='hidden'][name!='csrfmiddlewaretoken']", this).attr("name").split("-")[0];
        $(this).append(html_template.replace("{{prefix}}", prefix));
        $('#addlink-' + prefix).on('click', () => add_inline_form(prefix));
    })
})
