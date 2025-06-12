// Taken from django-password-strength, with changes to use the bower-managed zxcvbn.js The
// bower-managed zxcvbn.js is kept up-to-date to a larger extent than the copy packaged with
// the django-password-strength component.
(function ($, window, document, undefined) {
    window.djangoPasswordStrength = {
        config: {
            passwordClass: 'password_strength',
            confirmationClass: 'password_confirmation'
        },

        init: function (config) {
            var self = this;
            // Setup configuration
            if ($.isPlainObject(config)) {
                $.extend(self.config, config);
            }

            // Fix the initial widget for bootstrap 5
            var widget = $("." + self.config.passwordClass)
                .closest("form");
            widget
                .find(".hidden")
                .addClass("d-none")
                .removeClass("hidden");

            widget
                .find(".label")
                .addClass("badge rounded-pill")
                .removeClass("label");

            widget
                .find(".label-danger")
                .addClass("text-bg-danger")
                .removeClass("label-danger");

            widget
                .find(".text-body-secondary")
                .addClass("form-text")
                .removeClass("text-body-secondary");

            self.initListeners();
        },

        initListeners: function () {
            var self = this;

            $('.' + self.config.passwordClass)
                .on('keyup', function () {
                    var password_strength_bar = $(this)
                        .parent()
                        .find('.password_strength_bar');
                    var password_strength_info = $(this)
                        .parent()
                        .find('.password_strength_info');
                    var password_strength_offline_info = $(this)
                        .parent()
                        .parent()
                        .parent()
                        .find('.password_strength_offline_info');
                    let password_improvement_hint = $(password_strength_info)
                        .find('.password_improvement_hint');

                    if ($(this)
                        .val()) {
                        var result = zxcvbn($(this)
                            .val());
                        const enforceStrength = !('disableStrengthEnforcement' in this.dataset);
                        const strongEnough = !enforceStrength || (result.score >= 3);
                        if (strongEnough) {
                            // Mark input as valid
                            this.setCustomValidity('');
                        } else {
                            // Mark input as invalid
                            this.setCustomValidity('This password does not meet complexity requirements');
                        }
                        
                        if (this.checkValidity()) {
                            password_strength_bar.removeClass('text-bg-warning')
                                .addClass('text-bg-success');
                            password_strength_info.find('.badge')
                                .addClass('d-none');
                            this.classList.remove('is-invalid')
                            password_improvement_hint.addClass('d-none');
                            password_improvement_hint.text('')
                        } else {
                            this.classList.add('is-invalid')
                            password_improvement_hint.text(this.validationMessage)
                            password_improvement_hint.removeClass('d-none');

                            password_strength_bar.removeClass('text-bg-success')
                                .addClass('text-bg-warning');
                            password_strength_info.find('.badge')
                                .removeClass('d-none');
                        }

                        password_strength_bar.width(((result.score + 1) / 5) * 100 + '%')
                            .attr('aria-valuenow', result.score + 1);
                        // henrik@levkowetz.com -- this is the only changed line:
                        password_strength_info.find('.password_strength_time')
                            .html(result.crack_times_display.online_no_throttling_10_per_second);
                        password_strength_info.removeClass('d-none');

                        password_strength_offline_info.find('.password_strength_time')
                            .html(result.crack_times_display.offline_slow_hashing_1e4_per_second);
                        password_strength_offline_info.removeClass('d-none');
                    } else {
                        password_strength_bar.removeClass('text-bg-success')
                            .addClass('text-bg-warning');
                        password_strength_bar.width('0%')
                            .attr('aria-valuenow', 0);
                        password_strength_info.addClass('d-none');
                    }
                    self.match_passwords($(this));
                });

            var timer = null;
            $('.' + self.config.confirmationClass)
                .on('keyup', function () {
                    var password_field;
                    var confirm_with = $(this)
                        .data('confirm-with');

                    if (confirm_with) {
                        password_field = $('#' + confirm_with);
                    } else {
                        password_field = $('.' + self.config.passwordClass);
                    }

                    if (timer !== null) clearTimeout(timer);

                    timer = setTimeout(function () {
                        self.match_passwords(password_field);
                    }, 400);
                });
        },

        display_time: function (seconds) {
            var minute = 60;
            var hour = minute * 60;
            var day = hour * 24;
            var month = day * 31;
            var year = month * 12;
            var century = year * 100;

            // Provide fake gettext for when it is not available
            if (typeof gettext !== 'function') { gettext = function (text) { return text; }; }

            if (seconds < minute) return gettext('only an instant');
            if (seconds < hour) return (1 + Math.ceil(seconds / minute)) + ' ' + gettext('minutes');
            if (seconds < day) return (1 + Math.ceil(seconds / hour)) + ' ' + gettext('hours');
            if (seconds < month) return (1 + Math.ceil(seconds / day)) + ' ' + gettext('days');
            if (seconds < year) return (1 + Math.ceil(seconds / month)) + ' ' + gettext('months');
            if (seconds < century) return (1 + Math.ceil(seconds / year)) + ' ' + gettext('years');

            return gettext('centuries');
        },

        match_passwords: function (password_field, confirmation_fields) {
            var self = this;
            // Optional parameter: if no specific confirmation field is given, check all
            if (confirmation_fields === undefined) { confirmation_fields = $('.' + self.config.confirmationClass); }
            if (confirmation_fields === undefined) { return; }

            var password = password_field.val();

            confirmation_fields.each(function (index, confirm_field) {
                var confirm_value = $(confirm_field)
                    .val();
                var confirm_with = $(confirm_field)
                    .data('confirm-with');

                if (confirm_with && confirm_with == password_field.attr('id')) {
                    if (password) {
                        if (confirm_value === password) {
                            $(confirm_field)
                                .parent()
                                .find('.password_strength_info')
                                .addClass('d-none');
                            confirm_field.setCustomValidity('')
                            confirm_field.classList.remove('is-invalid')
                        } else {
                            if (confirm_value !== '') {
                                $(confirm_field)
                                    .parent()
                                    .find('.password_strength_info')
                                    .removeClass('d-none');
                            }
                            confirm_field.setCustomValidity('Does not match new password')
                            confirm_field.classList.add('is-invalid')
                        }
                    } else {
                        $(confirm_field)
                            .parent()
                            .find('.password_strength_info')
                            .addClass('d-none');
                        confirm_field.setCustomValidity('')
                        confirm_field.classList.remove('is-invalid')
                    }
                }
            });

            // If a password field other than our own has been used, add the listener here
            if (!password_field.hasClass(self.config.passwordClass) && !password_field.data('password-listener')) {
                password_field.on('keyup', function () {
                    self.match_passwords($(this));
                });
                password_field.data('password-listener', true);
            }
        }
    };

    // Call the init for backwards compatibility
    djangoPasswordStrength.init();

})(jQuery, window, document);
