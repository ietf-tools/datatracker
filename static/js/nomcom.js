/*jslint vars: false, browser: true */
/*global jQuery */

(function ($) {
    "use strict";
    $.fn.nominateForm = function () {
        return this.each(function () {
            var $position = $("#id_position"),
                $comments = $("#id_comments"),
                baseurl = "/nomcom/ajax/position-text/";

            $comments.change(function () {
                $.ajax({
                    url: baseurl + $position.val() + '/',
                    type: 'GET',
                    cache: false,
                    async: true,
                    dataType: 'json',
                    success: function (response) {
                        $comments.text(response.text);
                    }
                });
            });

            $position.change(function () {
                $comments.trigger("change");
            });

        });
    };

    $(document).ready(function () {
        $("#nominateform").nominateForm();
    });

}(jQuery));