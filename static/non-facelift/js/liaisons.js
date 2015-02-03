jQuery(function () {
    function setupAttachmentWidget() {
        var button = jQuery(this);
        var fieldset = jQuery(this).parents('.fieldset');
        var config = {};
        var count = 0;

        var readConfig = function() {
            var disabledLabel = fieldset.find('.attachDisabledLabel');

            if (disabledLabel.length) {
                config.disabledLabel = disabledLabel.html();
                var required = '';
                fieldset.find('.attachRequiredField').each(function(index, field) {
                    required += '#' + jQuery(field).html() + ',';
                });
                var fields = fieldset.find(required);
                config.basefields = fields;
            }

            config.showOn = jQuery('#' + fieldset.find('.showAttachsOn').html());
            config.showOnDisplay = config.showOn.find('.attachedFiles');
            count = config.showOnDisplay.find('.initialAttach').length;
            config.showOnEmpty = config.showOn.find('.showAttachmentsEmpty').html();
            config.enabledLabel = fieldset.find('.attachEnabledLabel').html();
        };

        var setState = function() {
            var enabled = true;
            config.fields.each(function() {
                if (!jQuery(this).val()) {
                    enabled = false;
                    return;
                }
            });
            if (enabled) {
                button.removeAttr('disabled').removeClass('disabledAddAttachment');
                button.val(config.enabledLabel);
            } else {
                button.attr('disabled', 'disabled').addClass('disabledAddAttachment');
                button.val(config.disabledLabel);
            }
        };

        var cloneFields = function() {
            var html = '<div class="attachedFileInfo">';
            if (count) {
                html = config.showOnDisplay.html() + html;
            }
            config.fields.each(function() {
                var field = jQuery(this);
                var container= jQuery(this).parents('.field');
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
            html += ' <a href="#" class="removeAttach">Remove</a>';
            html += '</div>';
            config.showOnDisplay.html(html);
            count += 1;
            initFileInput();
        };

        var doAttach = function() {
            cloneFields();    
            setState();
        };

        var removeAttachment = function() {
            var link = jQuery(this);
            var attach = jQuery(this).parent('.attachedFileInfo');
            var fields = attach.find('.removeField');
            fields.each(function() {
                jQuery('#' + jQuery(this).html()).remove();
            });
            attach.remove();
            if (!config.showOnDisplay.html()) {
                config.showOnDisplay.html(config.showOnEmpty);
                count = 0;
            }
            return false;
        };

        var initTriggers = function() {
            config.showOnDisplay.find('a.removeAttach').live('click', removeAttachment);
            button.click(doAttach);
        };

        var initFileInput = function() {
            var fieldids = [];
            config.basefields.each(function(i) {
                var field = jQuery(this);
                var oldcontainer= jQuery(this).parents('.field');
                var newcontainer= oldcontainer.clone();
                var newfield = newcontainer.find('#' + field.attr('id'));
                newfield.attr('name', newfield.attr('name') + '_' + count);
                newfield.attr('id', newfield.attr('id') + '_' + count);
                newcontainer.attr('id', 'container_id_' + newfield.attr('name'));
                oldcontainer.after(newcontainer);
                oldcontainer.hide();
                newcontainer.show();
                fieldids.push('#' + newfield.attr('id'));
            });
            config.fields = jQuery(fieldids.join(","));
            config.fields.change(setState);
            config.fields.keyup(setState);
        };

        var initWidget = function() {
            readConfig();
            initFileInput();
            initTriggers();
            setState();
        };

        initWidget();
    }

    jQuery('form.liaisonform').each(function() {
        var form = jQuery(this);
        var organization = form.find('#id_organization');
        var from = form.find('#id_from_field');
        var poc = form.find('#id_to_poc');
        var cc = form.find('#id_cc1');
        var reply = form.find('#id_replyto');
        var purpose = form.find('#id_purpose');
        var other_purpose = form.find('#id_purpose_text');
        var deadline = form.find('#id_deadline_date');
        var submission_date = form.find('#id_submitted_date');
        var other_organization = form.find('#id_other_organization');
        var approval = form.find('#id_approved');
        var cancel = form.find('#id_cancel');
        var cancel_dialog = form.find('#cancel-dialog');
        var config = {};
        var related_trigger = form.find('#id_related_to');
        var related_url = form.find('#id_related_to').parent().find('.listURL').text();
        var related_dialog = form.find('#related-dialog');
        var unrelate_trigger = form.find('#id_no_related_to');

        var readConfig = function() {
            var confcontainer = form.find('.formconfig');
            config.info_update_url = confcontainer.find('.info_update_url').text();
        };

        var render_mails_into = function(container, person_list, as_html) {
            var html='';

            jQuery.each(person_list, function(index, person) {
                if (as_html) {
                    html += person[0] + ' &lt;<a href="mailto:'+person[1]+'">'+person[1]+'</a>&gt;<br />';
                } else {
                    html += person[0] + ' &lt;'+person[1]+'&gt;\n';
                }
            });
            container.html(html);
        };

        var toggleApproval = function(needed) {
            if (!approval.length) {
                return;
            }
            if (needed) {
                approval.removeAttr('disabled');
                approval.removeAttr('checked');
            } else {
                approval.attr('checked','checked');
                approval.attr('disabled','disabled');
            }
        };

        var checkPostOnly = function(post_only) {
            if (post_only) {
                jQuery("input[name=send]").hide();
            } else {
                jQuery("input[name=send]").show();
            }
        };

        var updateReplyTo = function() {
            var select = form.find('select[name=from_fake_user]');
            var option = select.find('option:selected');
            reply.val(option.attr('title'));
            updateFrom();
        };

        var userSelect = function(user_list) {
            if (!user_list || !user_list.length) {
                return;
            }
            var link = form.find('a.from_mailto');
            var select = form.find('select[name=from_fake_user]');
            var options = '';
            link.hide();
            jQuery.each(user_list, function(index, person) {
                options += '<option value="' + person[0] + '" title="' + person[1][1] + '">'+ person[1][0] + ' &lt;' + person[1][1] + '&gt;</option>';
            });
            select.remove();
            link.after('<select name="from_fake_user">' + options +'</select>');
            form.find('select[name=from_fake_user]').change(updateReplyTo);
            updateReplyTo();
        };

        var updateInfo = function(first_time, sender) {
            var entity = organization;
            var to_entity = from;
            if (!entity.is('select') || !to_entity.is('select')) {
                return false;
            }
            var url = config.info_update_url;
            jQuery.ajax({
                url: url,
                type: 'GET',
                cache: false,
                async: true,
                dataType: 'json',
                data: {to_entity_id: organization.val(),
                       from_entity_id: to_entity.val()},
                success: function(response){
                    if (!response.error) {
                        if (!first_time || !cc.text()) {
                            render_mails_into(cc, response.cc, false);
                        }
                        render_mails_into(poc, response.poc, true);
                        toggleApproval(response.needs_approval);
                        checkPostOnly(response.post_only);
                        if (sender == 'from') {
                            userSelect(response.full_list);
                        }
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
            var selected_id = purpose.val();
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

        var checkOtherSDO = function() {
            var entity = organization.val();
            if (entity=='othersdo') {
                other_organization.parents('.field').show();
            } else {
                other_organization.parents('.field').hide();
            }
        };

        var cancelForm = function() {
            cancel_dialog.dialog("open");
        };

        var getRelatedLink = function() {
            var link = jQuery(this).text();;
            var pk = jQuery(this).nextAll('.liaisonPK').text();
            var widget = related_trigger.parent();
            widget.find('.relatedLiaisonWidgetTitle').text(link);
            widget.find('.relatedLiaisonWidgetValue').val(pk);
            widget.find('.noRelated').hide();
            unrelate_trigger.show();
            related_dialog.dialog('close');
            return false;
        };

        var selectNoRelated = function() {
            var widget = jQuery(this).parent();
            widget.find('.relatedLiaisonWidgetTitle').text('');
            widget.find('.noRelated').show();
            widget.find('.relatedLiaisonWidgetValue').val('');
            jQuery(this).hide();
            return false;
        };

        var selectRelated = function() {
            var trigger = jQuery(this);
            var widget = jQuery(this).parent();
            var url = widget.find('.listURL').text();
            var title = widget.find('.relatedLiaisonWidgetTitle');
            related_dialog.html('<img src="/images/ajax-loader.gif" />');
            related_dialog.dialog('open');
            jQuery.ajax({
                url: url,
                type: 'GET',
                cache: false,
                async: true,
                dataType: 'html',
                success: function(response){
                    related_dialog.html(response);
                    related_dialog.find('th a').click(function() {
                        widget.find('.listURL').text(related_url + jQuery(this).attr('href'));
                        trigger.click();
                        return false;
                    });
                    related_dialog.find('td a').click(getRelatedLink);
                }
            });
            return false;
        };

        var checkFrom = function(first_time) {
            var reduce_options = form.find('.reducedToOptions');
            if (!reduce_options.length) {
                updateInfo(first_time, 'from');
                return;
            }
            var to_select = organization;
            var from_entity = from.val();
            if (!reduce_options.find('.full_power_on_' + from_entity).length) {
                to_select.find('optgroup').eq(1).hide();
                to_select.find('option').each(function() {
                    if (!reduce_options.find('.reduced_to_set_' + jQuery(this).val()).length) {
                        jQuery(this).hide();
                    } else {
                        jQuery(this).show();
                    }
                });
                if (!to_select.find('option:selected').is(':visible')) {
                    to_select.find('option:selected').removeAttr('selected');
                }
            } else {
                to_select.find('optgroup').show();
                to_select.find('option').show();
            }
            updateInfo(first_time, 'from');
        };

        var checkSubmissionDate = function() {
            var date_str = submission_date.val();
            if (date_str) {
                var sdate = new Date(date_str);
                var today = new Date();
                if (Math.abs(today-sdate) > 2592000000) {  // 2592000000 = 30 days in milliseconds
                    return confirm('Submission date ' + date_str + ' differ more than 30 days.\n\nDo you want to continue and post this liaison using that submission date?\n');
                }
            }
        };

        var initTriggers = function() {
            organization.change(function() {updateInfo(false, 'to');});
            organization.change(checkOtherSDO);
            from.change(function() {checkFrom(false);});
            reply.keyup(updateFrom);
            purpose.change(updatePurpose);
            cancel.click(cancelForm);
            related_trigger.click(selectRelated);
            unrelate_trigger.click(selectNoRelated);
            form.submit(checkSubmissionDate);
        };

        var updateOnInit = function() {
            updateFrom();
            checkFrom(true);
            updatePurpose();
            checkOtherSDO();
        };

        var initDatePicker = function() {
            deadline.datepicker({
                dateFormat: jQuery.datepicker.ATOM,
                changeYear: true
            });
            submission_date.datepicker({
                dateFormat: jQuery.datepicker.ATOM,
                changeYear: true
            });
        };

        var initAttachments = function() {
            form.find('.addAttachmentWidget').each(setupAttachmentWidget);
        };

        var initDialogs = function() {
            cancel_dialog.dialog({
                resizable: false,
                height:200,
                modal: true,
                autoOpen: false,
                buttons: {
                   "Ok": function() {
                       window.location='..';
                       jQuery( this ).dialog( "close" );
                   },
                   "Cancel": function() {
                       jQuery( this ).dialog( "close" );
                   }
                }
            });

            related_dialog.dialog({
                height: 400,
                width: 800,
                draggable: true,
                modal: true,
                autoOpen: false
            });
        };

        var initForm = function() {
            readConfig();
            initTriggers();
            updateOnInit();
            initDatePicker();
            initAttachments();
            initDialogs();
        };

        initForm();
    });
});
