$(document).ready(function() {
    var form = $(".ipr-form");

    var template = form.find('.draft-row.template');

    var templateData = template.clone();

    $('.draft-add-row').click(function() {
        var el = template.clone(true);
        var totalField = $('#id_iprdocrel_set-TOTAL_FORMS');
        var total = +totalField.val();

        el.find(':input').each(function() {
            var name = $(this).attr('name').replace('-' + (total-1) + '-','-' + total + '-');
            var id = 'id_' + name;
            $(this).attr({'name': name, 'id': id}).val('');
        });

        el.find('label').each(function() {
            var newFor = $(this).attr('for').replace('-' + (total-1) + '-','-' + total + '-');
            $(this).attr('for', newFor);
        });

        ++total;

        totalField.val(total);

        template.before(el);
        el.removeClass("template");
    
        el.find(".select2-field").each(function () {
            setupSelect2Field($(this));
        });
    });

    function updateRevisions() {
        var selectbox = $(this).find('[name$="document"]');
        if (selectbox.val()) {
            var name = selectbox.select2("data").text;
            if (name.toLowerCase().substring(0, 3) == "rfc")
                $(this).find('[name$=revisions]').val("").hide();
            else
                $(this).find('[name$=revisions]').show();
        }
    }

    form.on("change", ".select2-field", function () {
        $(this).closest(".draft-row").each(updateRevisions);
    });

    // add a little bit of delay to let the select2 box have time to do its magic
    setTimeout(function () {
        form.find(".draft-row").each(updateRevisions);
    }, 10);
});
