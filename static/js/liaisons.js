(function ($) {
    $.fn.LiaisonForm = function() {
        return this.each(function () {
            var form = $(this);
            var organization = form.find('#id_organization');
            var from = form.find('#id_from_field');
            var poc = form.find('#id_to_poc');
            var cc = form.find('#id_cc1');
            var reply = form.find('#id_replyto');
            var purpose = form.find('#id_purpose');
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

            var initTriggers = function() {
                organization.change(updatePOC);
                organization.change(updateCC);
                from.change(updateCC);
                reply.keyup(updateFrom);
            };

            var updateOnInit = function() {
                updateFrom();
                updateCC();
                updatePOC();
            };

            var initForm = function() {
                readConfig();
                initTriggers();
                updateOnInit();
            };

            initForm();
        });

    };

    $(document).ready(function () {
        $('form.liaisonform').LiaisonForm();
    });

})(jQuery);
