from django.conf import settings

from Dajaxice import Dajaxice, dajaxice_autodiscover


class DajaxiceConfig(object):
    """ Provide an easy to use way to read the dajaxice configuration and
    return the default values if no configuration is present."""

    default_config = {'DAJAXICE_XMLHTTPREQUEST_JS_IMPORT': True,
                      'DAJAXICE_JSON2_JS_IMPORT': True,
                      'DAJAXICE_EXCEPTION': 'DAJAXICE_EXCEPTION',
                      'DAJAXICE_MEDIA_PREFIX': 'dajaxice'}

    def __getattr__(self, name):
        """ Return the customized value for a setting (if it exists) or the
        default value if not. """

        if name in self.default_config:
            if hasattr(settings, name):
                return getattr(settings, name)
            return self.default_config.get(name)
        return None

    @property
    def dajaxice_url(self):
        return r'^%s/' % self.DAJAXICE_MEDIA_PREFIX

    @property
    def django_settings(self):
        return settings

    @property
    def modules(self):
        return dajaxice_functions.modules

dajaxice_functions = Dajaxice()
dajaxice_config = DajaxiceConfig()
