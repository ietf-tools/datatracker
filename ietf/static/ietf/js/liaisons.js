
var attachmentWidget = {
    button : null,
    config : {},
    count : 0,

    readConfig : function() {
        var buttonFormGroup = attachmentWidget.button.parents('.form-group');
        var disabledLabel = buttonFormGroup.find('.attachDisabledLabel');

        if (disabledLabel.length) {
            attachmentWidget.config.disabledLabel = disabledLabel.html();
            var required = [];
            buttonFormGroup.find('.attachRequiredField').each(function(index, field) {
                required.push('#' + $(field).text());
            });
            attachmentWidget.config.basefields = $(required.join(","));
        }

        attachmentWidget.config.showOn = $('#' + buttonFormGroup.find('.showAttachsOn').html());
        attachmentWidget.config.showOnDisplay = attachmentWidget.config.showOn.find('.attachedFiles');
        attachmentWidget.count = attachmentWidget.config.showOnDisplay.find('.initialAttach').length;
        attachmentWidget.config.showOnEmpty = attachmentWidget.config.showOn.find('.showAttachmentsEmpty').html();
        attachmentWidget.config.enabledLabel = buttonFormGroup.find('.attachEnabledLabel').html();
    },

    setState : function() {
        var enabled = true;
        attachmentWidget.config.fields.each(function() {
            if (!$(this).val()) {
                enabled = false;
                return;
            }
        });
        if (enabled) {
            attachmentWidget.button.removeAttr('disabled').removeClass('disabledAddAttachment');
            attachmentWidget.button.val(attachmentWidget.config.enabledLabel);
        } else {
            attachmentWidget.button.attr('disabled', 'disabled').addClass('disabledAddAttachment');
            attachmentWidget.button.val(attachmentWidget.config.disabledLabel);
        }
    },

    cloneFields : function() {
        var html = '<div class="attachedFileInfo">';
        if (attachmentWidget.count) {
            html = attachmentWidget.config.showOnDisplay.html() + html;
        }
        attachmentWidget.config.fields.each(function() {
            var field = $(this);
            var container= $(this).parents('.form-group');
            if (container.find(':file').length) {
                html += ' (' + field.val() + ')';
            } else {
                html += ' ' + field.val();
            }
            html += '<span style="display: none;" class="removeField">';
            html += container.attr('id');
            html += '</span>';
            container.hide();
        });
        //html += ' <a href="" class="removeAttach glyphicon glyphicon-remove text-danger"></a>';
        html += ' <a href="" class="removeAttach btn btn-default btn-xs">Delete</a>';
        html += '</div>';
        attachmentWidget.config.showOnDisplay.html(html);
        attachmentWidget.count += 1;
        attachmentWidget.initFileInput();
    },

    doAttach : function() {
        attachmentWidget.cloneFields();
        attachmentWidget.setState();
    },

    removeAttachment : function() {
        var link = $(this);
        var attach = $(this).parent('.attachedFileInfo');
        var fields = attach.find('.removeField');
        fields.each(function() {
            $('#' + $(this).html()).remove();
        });
        attach.remove();
        if (!attachmentWidget.config.showOnDisplay.html()) {
            attachmentWidget.config.showOnDisplay.html(attachmentWidget.config.showOnEmpty);
            attachmentWidget.count = 0;
        }
        return false;
    },

    initTriggers : function() {
        attachmentWidget.config.showOnDisplay.on('click', 'a.removeAttach', attachmentWidget.removeAttachment);
        attachmentWidget.button.click(attachmentWidget.doAttach);
    },

    initFileInput : function() {
        var fieldids = [];
        attachmentWidget.config.basefields.each(function(i) {
            var field = $(this);
            var oldcontainer= $(this).parents('.form-group');
            var newcontainer= oldcontainer.clone();
            var newfield = newcontainer.find('#' + field.attr('id'));
            newfield.attr('name', newfield.attr('name') + '_' + attachmentWidget.count);
            newfield.attr('id', newfield.attr('id') + '_' + attachmentWidget.count);
            newcontainer.attr('id', 'container_id_' + newfield.attr('name'));
            oldcontainer.after(newcontainer);
            oldcontainer.hide();
            newcontainer.show();
            fieldids.push('#' + newfield.attr('id'));
        });
        attachmentWidget.config.fields = $(fieldids.join(","));
        attachmentWidget.config.fields.change(attachmentWidget.setState);
        attachmentWidget.config.fields.keyup(attachmentWidget.setState);
    },

    initWidget : function() {
        attachmentWidget.button = $(this);
        attachmentWidget.readConfig();
        attachmentWidget.initFileInput();
        attachmentWidget.initTriggers();
        attachmentWidget.setState();
    },
}


var liaisonForm = {
    initVariables : function() {
        liaisonForm.is_edit_form = liaisonForm.form.attr("data-edit-form") == "True"
        liaisonForm.from_groups = liaisonForm.form.find('#id_from_groups');
        liaisonForm.from_contact = liaisonForm.form.find('#id_from_contact');
        liaisonForm.response_contacts = liaisonForm.form.find('#id_response_contacts');
        liaisonForm.to_groups = liaisonForm.form.find('#id_to_groups');
        liaisonForm.to_contacts = liaisonForm.form.find('#id_to_contacts');
        liaisonForm.cc = liaisonForm.form.find('#id_cc_contacts');
        liaisonForm.purpose = liaisonForm.form.find('#id_purpose');
        liaisonForm.deadline = liaisonForm.form.find('#id_deadline');
        liaisonForm.submission_date = liaisonForm.form.find('#id_submitted_date');
        liaisonForm.approval = liaisonForm.form.find('#id_approved');
        liaisonForm.initial_approval_label = liaisonForm.form.find("label[for='id_approved']").text();
        liaisonForm.cancel = liaisonForm.form.find('#id_cancel');
        liaisonForm.cancel_dialog = liaisonForm.form.find('#cancel-dialog');
        liaisonForm.config = {};
        liaisonForm.related_trigger = liaisonForm.form.find('.id_related_to');
        liaisonForm.related_url = liaisonForm.form.find('#id_related_to').parent().find('.listURL').text();
        liaisonForm.related_dialog = liaisonForm.form.find('#related-dialog');
        liaisonForm.unrelate_trigger = liaisonForm.form.find('.id_no_related_to');
    },
    
    render_mails_into : function(container, person_list, as_html) {
        var html='';

        $.each(person_list, function(index, person) {
            if (as_html) {
                html += person[0] + ' &lt;<a href="mailto:'+person[1]+'">'+person[1]+'</a>&gt;<br />';
            } else {
                //html += person[0] + ' &lt;'+person[1]+'&gt;\n';
                html += person + '\n';
            }
        });
        container.html(html);
    },

    toggleApproval : function(needed) {
        if (!liaisonForm.approval.length) {
            return;
        }
        if (!needed) {
            liaisonForm.approval.prop('checked',true);
            liaisonForm.approval.hide();
            //$("label[for='id_approved']").text("Approval not required");
            var nodes = $("label[for='id_approved']:not(.control-label)")[0].childNodes;
            nodes[nodes.length-1].nodeValue= 'Approval not required';
            return;
        }
        if ( needed && !$('#id_approved').is(':visible') ) {
            liaisonForm.approval.prop('checked',false);
            liaisonForm.approval.show();
            //$("label[for='id_approved']").text(initial_approval_label);
            var nodes = $("label[for='id_approved']:not(.control-label)")[0].childNodes;
            nodes[nodes.length-1].nodeValue=initial_approval_label;
            return;
        }
    },

    checkPostOnly : function(post_only) {
        if (post_only) {
            $("button[name=send]").hide();
        } else {
            $("button[name=send]").show();
        }
    },

    updateInfo : function(first_time, sender) {
        // don't overwrite fields when editing existing liaison
        if(liaisonForm.is_edit_form){
            return false;
        }
        
        var from_ids = liaisonForm.from_groups.val();
        var to_ids = liaisonForm.to_groups.val();
        var url = liaisonForm.form.data("ajaxInfoUrl");
        $.ajax({
            url: url,
            type: 'GET',
            cache: false,
            async: true,
            dataType: 'json',
            data: {from_groups: from_ids,
                   to_groups: to_ids},
            success: function(response){
                if (!response.error) {
                    if (!first_time || !liaisonForm.cc.text()) {
                        liaisonForm.render_mails_into(liaisonForm.cc, response.cc, false);
                    }
                    //render_mails_into(poc, response.poc, false);
                    if ( sender.attr('id') == 'id_to_groups' ) {
                        liaisonForm.to_contacts.val(response.to_contacts);
                    }
                    if ( sender.attr('id') == 'id_from_groups' ) {
                        liaisonForm.toggleApproval(response.needs_approval);
                        liaisonForm.response_contacts.val(response.response_contacts);
                    }
                    liaisonForm.checkPostOnly(response.post_only);
                }
            }
        });
        return false;
    },

    updatePurpose : function() {
        var deadlinecontainer = liaisonForm.deadline.closest('.form-group');
        var value = liaisonForm.purpose.val();
        
        if (value == 'action' || value == 'comment') {
            liaisonForm.deadline.prop('required',true);
            deadlinecontainer.show();
        } else {
            liaisonForm.deadline.prop('required',false);
            deadlinecontainer.hide();
            liaisonForm.deadline.val('');
        }
    },

    cancelForm : function() {
        liaisonForm.cancel_dialog.dialog("open");
    },

    checkSubmissionDate : function() {
        var date_str = liaisonForm.submission_date.val();
        if (date_str) {
            var sdate = new Date(date_str);
            var today = new Date();
            if (Math.abs(today-sdate) > 2592000000) {  // 2592000000 = 30 days in milliseconds
                return confirm('Submission date ' + date_str + ' differ more than 30 days.\n\nDo you want to continue and post this liaison using that submission date?\n');
            }
            return true;
        }
        else
            return false;
    },

    init : function() {
        liaisonForm.form = $(this);
        liaisonForm.initVariables();
        $('#id_from_groups').select2();
        $('#id_to_groups').select2();
        liaisonForm.to_groups.change(function() { liaisonForm.updateInfo(false,$(this)); });
        liaisonForm.from_groups.change(function() { liaisonForm.updateInfo(false,$(this)); });
        liaisonForm.purpose.change(liaisonForm.updatePurpose);
        liaisonForm.form.submit(liaisonForm.checkSubmissionDate);
        $('.addAttachmentWidget').each(attachmentWidget.initWidget);
        
        liaisonForm.updatePurpose();
        if($('#id_to_groups').val()) {
            $('#id_to_groups').trigger('change');
        }
        if($('#id_from_groups').val()) {
            $('#id_from_groups').trigger('change');
        }
    },
}


var searchForm = {
    // search form, based on doc search feature
    init : function() {
        searchForm.form = $(this);
        $("#search-clear-btn").bind("click", searchForm.clearForm);
    },
    
    clearForm : function() {
        var form = $(this).parents("form");
        form.find("input").val("");
    }
}


$(document).ready(function () {
    // use traditional style URL parameters
    $.ajaxSetup({ traditional: true });
    
    $('form.liaisons-form').each(liaisonForm.init);
    $('#liaison_search_form').each(searchForm.init);
});
