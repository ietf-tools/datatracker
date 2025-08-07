# The MIT License (MIT)
#
# Copyright (c) 2016 Adam Schubert
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import gettext
import os
import logging


logger = logging.getLogger(__name__)


class FallBackNull(gettext.NullTranslations):
    def gettext(self, message):
        # If we get here, that means that original translator failed, we will return empty string
        return ""


class GetText(object):
    """
    Handles language translations
    """

    def __init__(self, locale_code, locale_location=None):
        """
        Initialize GetText
        :param locale_code selected locale
        """
        try:
            self.trans = self.load_locale(locale_code, locale_location)
        except IOError:
            logger.debug('Failed to find locale {}'.format(locale_code))
            logger.debug('Attempting to load en_US as fallback')
            self.trans = self.load_locale('en_US')

        # Add fallback that does not return original string, this is hack to add
        # support for _("") or _("")
        self.trans.add_fallback(FallBackNull())

    def load_locale(self, locale_code, locale_location=None):
        if locale_location is None:
            filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locale', '{}.mo'.format(locale_code))
        else:
            filename = os.path.join(locale_location, '{}.mo'.format(locale_code))
        with open(filename, "rb") as f:
            trans = gettext.GNUTranslations(f)
        logger.debug('{} Loaded'.format(filename))
        return trans


