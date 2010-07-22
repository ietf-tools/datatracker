(function ($) {
    $.fn.AttachmentWidget = function() {
        return this.each(function () {
            var button = $(this);
            var fieldset = $(this).parents('.fieldset');
            var config = {};
            var count = 0;

            var readConfig = function() {
                var disabledLabel = fieldset.find('.attachDisabledLabel');

                if (disabledLabel.length) {
                    config.disabledLabel = disabledLabel.html();
                    var required = ''
                    fieldset.find('.attachRequiredField').each(function(index, field) {
                        required += '#' + $(field).html() + ',';
                    });
                    var fields = fieldset.find(required);
                    config.fields = fields;
                }

                config.showOn = $('#' + fieldset.find('.showAttachsOn').html());
                config.showOnDisplay = config.showOn.find('.attachedFiles');
                config.showOnEmpty = config.showOn.find('.showAttachmentsEmpty').html();
                config.enabledLabel = fieldset.find('.attachEnabledLabel').html();
            };

            var setState = function() {
                var enabled = true;
                config.fields.each(function() {
                    if (!$(this).val()) {
                        enabled = false;
                        return;
                    }
                });
                if (enabled) {
                    button.removeAttr('disabled');
                    button.val(config.enabledLabel);
                } else {
                    button.attr('disabled', 'disabled');
                    button.val(config.disabledLabel);
                }
            };

            var cloneFields = function() {
                var html = '<div class="attachedFileInfo">';
                if (count) {
	            html = config.showOnDisplay.html() + html;
                }
                config.fields.each(function() {
                    var field = $(this);
                    var newcontainer= $(this).parents('.field').clone();
                    var newfield = newcontainer.find('#' + field.attr('id'));
                    newcontainer.hide();
                    newfield.attr('name', newfield.attr('name') + '_' + count);
                    newcontainer.attr('id', 'container_id_' + newfield.attr('name'));
                    newcontainer.insertBefore(button.parents('.field'));
                    if (newcontainer.find(':file').length) {
                        html += ' (' + newfield.val() + ')';
                    } else {
                        html += ' ' + newfield.val();
                    }
                    html += '<span style="display: none;" class="removeField">';
                    html += newcontainer.attr('id');
                    html += '</span>';
                });
                html += ' <a href="#" class="removeAttach">Remove</a>';
                html += '</div>';
                config.showOnDisplay.html(html);
                config.fields.val('');
                count += 1;
            };

            var doAttach = function() {
                cloneFields();    
                setState();
            };

            var removeAttachment = function() {
                var link = $(this);
                var attach = $(this).parent('.attachedFileInfo');
                var fields = attach.find('.removeField');
                fields.each(function() {
                    $('#' + $(this).html()).remove();
                });
                attach.remove();
                if (!config.showOnDisplay.html()) {
                    config.showOnDisplay.html(config.showOnEmpty);
                    count = 0;
                }
                return false;
            };

            var initTriggers = function() {
                config.fields.change(setState);
                config.fields.keyup(setState);
                config.showOnDisplay.find('a.removeAttach').live('click', removeAttachment);
                button.click(doAttach);
            };

            var initWidget = function() {
                readConfig();
                initTriggers();
                setState();
            };

            initWidget();
        });
    };

    $.fn.LiaisonForm = function() {
        return this.each(function () {
            var form = $(this);
            var organization = form.find('#id_organization');
            var from = form.find('#id_from_field');
            var poc = form.find('#id_to_poc');
            var cc = form.find('#id_cc1');
            var reply = form.find('#id_replyto');
            var purpose = form.find('#id_purpose');
            var other_purpose = form.find('#id_purpose_text');
            var deadline = form.find('#id_deadline_date');
            var config = {};

            var readConfig = function() {
                var confcontainer = form.find('.formconfig');
                config.poc_update_url = confcontainer.find('.poc_update_url').text();
                config.cc_update_url = confcontainer.find('.cc_update_url').text();
            };

            var render_mails_into = function(container, person_list) {
                var html='';

                $.each(person_list, function(index, person) {
                    html += person[0] + ' &lt;<a href="mailto:'+person[1]+'">'+person[1]+'</a>&gt;<br />';
                });
                container.html(html);
            };

            var updatePOC = function() {
                var entity = organization.find('option:selected');
                var url = config.poc_update_url;
                $.ajax({
                    url: url,
                    type: 'GET',
                    cache: false,
                    async: true,
                    dataType: 'json',
                    data: {entity_id: entity.val()},
                    success: function(response){
                        if (!response.error) {
                            render_mails_into(poc, response.poc);
                        }
                    }
                });
                return false;
            };

            var updateCC = function() {
                var entity = organization.find('option:selected');
                var sdo = from.find('option:selected');
                var url = config.cc_update_url;
                $.ajax({
                    url: url,
                    type: 'GET',
                    cache: false,
                    async: true,
                    dataType: 'json',
                    data: {to_entity_id: organization.val(),
                           sdo_id: sdo.val()},
                    success: function(response){
                        if (!response.error) {
                            render_mails_into(cc, response.cc);
                        }
                    }
                });
                return false;
            };

            var updateFrom = function() {
                var reply_to = reply.val();
                form.find('a.from_mailto').attr('href', 'mailto:' + reply_to);
            };

            var updatePurpose = function() {
                var datecontainer = deadline.parents('.field');
                var othercontainer = other_purpose.parents('.field');
                var selected_id = purpose.find('option:selected').val();
                var deadline_required = datecontainer.find('.fieldRequired');
             
                if (selected_id == '1' || selected_id == '2' || selected_id == '5') {
                    datecontainer.show();
                } else {
                    datecontainer.hide();
                    deadline.val('');
                }

                if (selected_id == '5') {
                    othercontainer.show();
                    deadline_required.hide();
                } else {
                    othercontainer.hide();
                    other_purpose.val('');
                    deadline_required.show();
                }
            };

            var initTriggers = function() {
                organization.change(updatePOC);
                organization.change(updateCC);
                from.change(updateCC);
                reply.keyup(updateFrom);
                purpose.change(updatePurpose);
            };

            var updateOnInit = function() {
                updateFrom();
                updateCC();
                updatePOC();
                updatePurpose();
            };

            var initDatePicker = function() {
                deadline.datepicker({
                    dateFormat: $.datepicker.ATOM,
                    changeYear: true
                });
            };

            var initAttachments = function() {
                form.find('.addAttachmentWidget').AttachmentWidget();
            };

            var initForm = function() {
                readConfig();
                initTriggers();
                updateOnInit();
                initDatePicker();
                initAttachments();
            };

            initForm();
        });

    };

    $(document).ready(function () {
        $('form.liaisonform').LiaisonForm();
    });

})(jQuery);
