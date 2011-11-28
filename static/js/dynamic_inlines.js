/* Following functions based off code written by Arne Brodowski
http://www.arnebrodowski.de/blog/507-Add-and-remove-Django-Admin-Inlines-with-JavaScript.html
*/
function increment_form_ids(el, to, name) {
    var from = to-1
    $(':input', $(el)).each(function(i,e){
        var old_name = $(e).attr('name')
        var old_id = $(e).attr('id')
        $(e).attr('name', old_name.replace(from, to))
        $(e).attr('id', old_id.replace(from, to))
        $(e).val('')
    })
}

function add_inline_form(name) {
    var first = $('#id_'+name+'-0-id').parents('.inline-related')
    // check to see if this is a stacked or tabular inline
    if (first.hasClass("tabular")) {
        var field_table = first.parent().find('table > tbody')
        var count = field_table.children().length
        var copy = $('tr:last', field_table).clone(true)
        copy.removeClass("row1 row2")
        copy.addClass("row"+((count % 2) == 0 ? 1 : 2))
        field_table.append(copy)
        increment_form_ids($('tr:last', field_table), count, name)
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
            '<a class="addlink" href="#" onclick="return add_inline_form(\'{{prefix}}\')">'+
            'Add another</a>'+
        '</li>'+
    '</ul>'
    $('.inline-group').each(function(i) {
        //prefix is in the name of the input fields before the "-"
        var prefix = $("input[type='hidden']", this).attr("name").split("-")[0]
        $(this).append(html_template.replace("{{prefix}}", prefix))
    })
})
