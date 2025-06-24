from django.forms import PasswordInput
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

# The PasswordStrengthInput and PasswordConfirmationInput widgets come from the
# django-password-strength project, https://pypi.org/project/django-password-strength/
#
# Original license:
#
# Copyright &copy; 2015 A.J. May and individual contributors. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the 
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the 
# following disclaimer in the documentation and/or other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote 
# products derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE 
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

class PasswordStrengthInput(PasswordInput):
    """
    Form widget to show the user how strong his/her password is.
    """

    def render(self, name, value, attrs=None, renderer=None):
        strength_markup = """
        <div style="margin-top: 10px;">
            <div class="progress" style="margin-bottom: 10px;">
                <div class="progress-bar progress-bar-warning password_strength_bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="5" style="width: 0%"></div>
            </div>
            <p class="text-body-secondary password_strength_info hidden">
                <span class="label label-danger">
                    {}
                </span>
                <span style="margin-left:5px;">
                    {}
                </span>
                <span class="password_improvement_hint d-none"></span>
            </p>
        </div>
        """.format(
            _("Warning"),
            _(
                'This password would take <em class="password_strength_time"></em> to crack.'
            ),
        )

        try:
            self.attrs["class"] = "%s password_strength".strip() % self.attrs["class"]
        except KeyError:
            self.attrs["class"] = "password_strength"

        return mark_safe(
            super(PasswordInput, self).render(name, value, attrs, renderer)
            + strength_markup
        )

    class Media:
        js = (
            "ietf/js/zxcvbn.js",
            "ietf/js/password_strength.js",
        )


class PasswordConfirmationInput(PasswordInput):
    """
    Form widget to confirm the users password by letting him/her type it again.
    """

    def __init__(self, confirm_with=None, attrs=None, render_value=False):
        super(PasswordConfirmationInput, self).__init__(attrs, render_value)
        self.confirm_with = confirm_with

    def render(self, name, value, attrs=None, renderer=None):
        if self.confirm_with:
            self.attrs["data-confirm-with"] = "id_%s" % self.confirm_with
            
        confirmation_markup = """
        <div style="margin-top: 10px;" class="hidden password_strength_info">
            <p class="text-body-secondary">
                <span class="label label-danger">
                    %s
                </span>
                <span style="margin-left:5px;">%s</span>
            </p>
        </div>
        """ % (
            _("Warning"),
            _("Your passwords don't match."),
        )

        try:
            self.attrs["class"] = (
                "%s password_confirmation".strip() % self.attrs["class"]
            )
        except KeyError:
            self.attrs["class"] = "password_confirmation"

        return mark_safe(
            super(PasswordInput, self).render(name, value, attrs, renderer)
            + confirmation_markup
        )
